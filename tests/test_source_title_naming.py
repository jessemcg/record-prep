"""Practice-neutral naming rules: offline contracts, not model accuracy tests."""
import json
import unittest

from recordprep.classification_profiles import component
from recordprep.classification_review import _proposal_row
from recordprep.document_naming import compile_naming_profile
from recordprep.profile_contract import ProfileError
from recordprep.profile_workflows import ProfileEditor
from recordprep.prompt_inspection import inspect_prompt
from test_dependency_report_naming import bundle, title_catalog_bundle, ROOT
from test_document_naming import with_naming


def custom(kind='report'):
    editor = ProfileEditor.create(bundle(), 'Synthetic Civil Practice')
    editor.resources['naming'] = {'schema_version': 5, 'reports': [], 'forms': []}
    editor.resources['naming'][kind+'s'] = [
        {'id':'expert', 'name':'Expert Report', 'naming_mode':'source_title',
         'guidance':'A retained expert evaluation prepared for the court. Exclude routine laboratory records.'},
        {'id':'fixed', 'name':'Standard Evaluation', 'guidance':'Required heading: Standard Evaluation.'},
    ]
    return editor.snapshot()


class SourceTitleTests(unittest.TestCase):
    def test_generic_mixed_rules_reports_and_forms(self):
        for kind in ('report', 'form'):
            c = compile_naming_profile(custom(kind), kind)
            self.assertEqual(c.mode, 'matched_rules')
            self.assertNotIn('child welfare', c.prompt.lower())
            self.assertIn('best-supported match, not list order', c.prompt)
            self.assertIn("document's own title on its cover/first page", c.prompt)
            extra = {'date':'January 02, 2026'} if kind == 'report' else {}
            for title in ('Engineering Evaluation — Supplemental Opinion', 'MEMORANDUM'):
                result = c.normalize({'name':title, 'rule_id':'expert', **extra})
                self.assertEqual((result.name,result.rule_id), (title,'expert'))
            self.assertEqual(c.normalize({'name':'','rule_id':'expert', **extra}).name, 'Expert Report')
            self.assertEqual(c.normalize({'name':'Standard Evaluation','rule_id':'fixed', **extra}).name,
                             'Standard Evaluation')
            self.assertEqual(c.normalize({'name':'Invented alias','rule_id':'fixed', **extra}).name, '')
            self.assertEqual(c.normalize({'name':'','rule_id':'fixed', **extra}).name, '')
            for missing in (None, '', 'unknown', [], 1):
                self.assertEqual(c.normalize({'name':'Any title','rule_id':missing, **extra}).name, '')
            for malformed in ([], None, 'line\nbreak', 'x'*161):
                result = c.normalize({'name':malformed, 'rule_id':'expert', **extra})
                self.assertEqual(result.name, '')  # malformed is not an absent source title
            if kind == 'form':
                self.assertIn('source-title mode does not waive those requirements', c.prompt)
                self.assertNotIn('Hearing Date near the report title', c.prompt)

    def test_fixed_default_and_explicit_fixed_preserve_old_prompt_and_results(self):
        old = title_catalog_bundle()
        before = old.files
        for explicit in (False, True):
            n = old.resource('naming'); n['schema_version'] = 5
            if explicit:
                for card in n['reports'] + n['forms']:
                    card['naming_mode'] = 'fixed'
            newer = with_naming(old, n)
            for kind in ('report','form'):
                a,b = (compile_naming_profile(p,kind) for p in (old,newer))
                self.assertEqual(a.prompt, b.prompt)
                self.assertEqual(a.component_sha256, b.component_sha256)
                self.assertEqual(a.response_keys, b.response_keys)
                self.assertEqual(a.allowed_names, b.allowed_names)
                self.assertEqual(b.mode, 'approved_titles')
        self.assertEqual(old.files, before)

    def test_schema_rejects_unknown_fields_modes_and_v4_opt_in(self):
        source = custom()
        for mode in ('free_text', '', None, 1, []):
            n = source.resource('naming'); n['reports'][0]['naming_mode'] = mode
            with self.assertRaises(ProfileError): with_naming(source, n)
        n = source.resource('naming'); n['schema_version'] = 4
        with self.assertRaises(ProfileError): with_naming(source, n)
        n = source.resource('naming'); n['reports'][0]['extra'] = 'not supported'
        with self.assertRaises(ProfileError): with_naming(source, n)
        n = source.resource('naming'); n['schema_version'] = 6
        with self.assertRaises(ProfileError): with_naming(source, n)

    def test_inspector_matches_runtime_and_mode_changes_names_only(self):
        source = custom(); before = source.files
        resources = {k:source.resource(k) for k in source.manifest['resources']}
        for template in (False,True):
            view = inspect_prompt(resources,'report',ROOT/'.pi',template=template,snapshot=source)
            self.assertFalse(view.issues)
            self.assertIn('source_title',view.components[0][1])
            self.assertIn('rule_id',view.components[0][1])
            if not template:
                self.assertEqual(view.components[0][1],compile_naming_profile(source,'report').prompt)
        n = source.resource('naming'); n['reports'][0].pop('naming_mode')
        fixed = with_naming(source,n)
        for stage in ('basic','advanced','dates','names'):
            self.assertEqual(component(source,stage)!=component(fixed,stage), stage=='names')
        self.assertEqual(source.files,before)

    def test_correction_accepts_matched_source_titles_without_fixed_allowlist(self):
        contract = compile_naming_profile(custom(),'report')
        row = {'file_name':'0001.txt','page_type':'CT_report_first_page','report_first_page':'yes','name':''}
        rows = {'0001.txt':row}
        def proposal(title, rule_id):
            return {'file_name':'0001.txt', 'before':{'name':'','naming_rule_id':None},
                    'after':{'name':title,'naming_rule_id':rule_id}}
        result = _proposal_row(proposal('Engineering Evaluation','expert'),rows,{'report':contract})
        self.assertEqual((result['name'],result['naming_rule_id']),('Engineering Evaluation','expert'))
        fallback = _proposal_row(proposal('Expert Report','expert'),rows,{'report':contract})
        self.assertEqual(fallback['name'],'Expert Report')
        for identity in (None,'unknown','fixed'):
            with self.assertRaises(ValueError):
                _proposal_row(proposal('Engineering Evaluation',identity),rows,{'report':contract})
        self.assertEqual(rows['0001.txt'],row)
        # Changing/removing a name must not accidentally retain old eligibility metadata.
        changed = {'file_name':'0001.txt','before':{'name':'Engineering Evaluation'},'after':{'name':''}}
        cleared = _proposal_row(changed,{'0001.txt':result},{'report':contract})
        self.assertNotIn('naming_rule_id',cleared)

    def test_source_title_guard_does_not_turn_semantic_uncertainty_into_global_failure(self):
        from recordprep.classification_review import validate_candidate
        from tempfile import TemporaryDirectory
        from pathlib import Path
        contract = compile_naming_profile(custom(),'report')
        rows = {f'{i:04d}.txt':{'file_name':f'{i:04d}.txt','page_type':'CT_report_first_page',
                               'report_first_page':'yes','name':''} for i in (1,2)}
        changes = [{'file_name':filename,'before':{'name':'','naming_rule_id':None},
                    'after':{'name':'Engineering Evaluation','naming_rule_id':identity},
                    'impact':'missed_document','reason':'A fictional expert report was omitted from selection.',
                    'evidence':[]} for filename,identity in [('0001.txt','expert'),('0002.txt','unknown')]]
        with TemporaryDirectory() as td:
            root=Path(td); workspace=root/'workspace'; workspace.mkdir()
            (workspace/'block-0001.jsonl').write_text('')
            candidate=json.dumps({'schema_version':1,'reviewed_blocks':[],'changes':changes,'unresolved':[]})
            corrected,audit=validate_candidate(candidate,rows,{'report':contract},set(),workspace,root)
            removal = {'file_name':'0001.txt','before':{'name':'Engineering Evaluation'},'after':{'name':''},
                       'impact':'document_identity','reason':'Fictional independent exhibit, not an eligible report.', 'evidence':[]}
            cleared, removal_audit = validate_candidate(json.dumps({'schema_version':1, 'reviewed_blocks':[],
                'changes':[removal], 'unresolved':[]}),corrected,{'report':contract},set(),workspace,root)
            self.assertNotIn('naming_rule_id',cleared['0001.txt'])
            self.assertEqual(removal_audit['changes'][0]['before']['naming_rule_id'],'expert')
            self.assertIsNone(removal_audit['changes'][0]['after']['naming_rule_id'])
        self.assertEqual(corrected['0001.txt']['name'],'Engineering Evaluation')
        self.assertEqual(corrected['0002.txt']['name'],'')
        self.assertEqual(len(audit['changes']),1)
        self.assertEqual(len(audit['not_applied']),1)
