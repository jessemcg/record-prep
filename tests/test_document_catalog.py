"""Naming catalogs stay independent of page-type and document-start checks."""
import copy
import json
from pathlib import Path
import unittest

from recordprep.classifier_prompts import classifier_document
from recordprep.classification_profiles import classifier_prompt, component
from recordprep.document_catalog import catalog_entries, catalog_text
from recordprep.document_naming import naming_document, compile_naming_profile
from recordprep.profile_editor_ui import editable_profile
from recordprep.profile_workflows import ProfileEditor
from recordprep.structured_guidance import effective_resource
from test_structured_classification import bundle

ROOT=Path(__file__).resolve().parents[1]


class DocumentCatalogTests(unittest.TestCase):
    def test_catalogs_are_naming_only_and_report_recognition_is_structural(self):
        b=bundle();n=b.resource('naming');t=b.resource('classification_tasks')
        document=classifier_document(t,'ct')
        sections={s.identity:s.text for s in document.sections}
        for kind,title in (('report','Report Names'),('form','Form Names')):
            self.assertIn(catalog_text(n,kind),naming_document(n,kind).render())
            self.assertNotIn(title,document.render())
        self.assertNotIn('ICWA-020',document.render())
        self.assertNotIn('Detention Report',document.render())
        self.assertIn('including continuation pages',sections['CT_report'])
        self.assertIn('need not have an approved output name',sections['CT_report'])
        self.assertIn('CFS 6.7',sections['CT_report']);self.assertIn('DCFS 4216',sections['CT_report'])
        self.assertIn('Page X of XX numbering alone',sections['CT_report'])
        self.assertNotIn('CFS 6.7',catalog_text(n,'report'))
        self.assertNotIn('Return an empty name',document.render())
        self.assertNotIn('both that code and the matching heading must',document.render())
        self.assertIn('both that code and the matching heading must',naming_document(n,'form').render())
        self.assertIn('same first page',naming_document(n,'form').render())

    def test_add_rename_describe_and_remove_change_naming_not_classification(self):
        b=bundle();e=ProfileEditor(b);ct=classifier_prompt(b,'ct')
        for kind in ('report','form'):
            values=e.resources['naming'][kind+'s'];old=values[0]['name']
            values[0]['name']='Renamed '+kind
            values[0]['guidance']='Literal α {"x":1} {{quote:source}}'
            values.append({'id':'synthetic-'+kind,'name':'Added '+kind,'guidance':'Naming recognition clue.'})
            for name in ('Renamed '+kind,'Added '+kind):
                self.assertNotIn(name,classifier_prompt(e.snapshot(),'ct')[0])
                self.assertIn(name,compile_naming_profile(e.snapshot(),kind).allowed_names)
            self.assertNotIn(old,[entry['name'] for entry in catalog_entries(e.resources['naming'],kind)])
            self.assertIn(json.dumps(values[0]['guidance'],ensure_ascii=False),compile_naming_profile(e.snapshot(),kind).prompt)
            values.pop()
            self.assertNotIn('Added '+kind,compile_naming_profile(e.snapshot(),kind).allowed_names)
            self.assertEqual(classifier_prompt(e.snapshot(),'ct'),ct)

    def test_catalog_edits_invalidate_names_only(self):
        b=bundle();stages=('basic','advanced','corrected','dates','names')
        before={stage:component(b,stage) for stage in stages}
        for kind in ('reports','forms'):
            for field in ('name','guidance'):
                e=ProfileEditor(b);e.resources['naming'][kind][0][field]+=' Synthetic change'
                s=e.snapshot()
                with self.subTest(kind=kind,field=field):
                    for stage in stages:self.assertEqual(component(s,stage)!=before[stage],stage=='names')
                    for task in ('rt','ct','first_hearing','first_minute','first_form','first_report','date_hearing','date_minute'):
                        self.assertEqual(classifier_prompt(s,task),classifier_prompt(b,task))

    def test_naming_instruction_wording_changes_names_not_ct_recognition(self):
        from unittest.mock import patch
        from recordprep import document_naming
        b=bundle();stages=('basic','advanced','corrected','dates','names')
        before={stage:component(b,stage) for stage in stages}
        with patch.object(document_naming,'_CORE',document_naming._CORE+'\nSynthetic naming wording change.\n'):
            for stage in stages:
                self.assertEqual(component(b,stage)!=before[stage],stage=='names')

    def test_empty_catalogs_do_not_change_page_recognition(self):
        e=ProfileEditor(bundle());e.resources['naming'].update(reports=[],forms=[]);s=e.snapshot()
        self.assertEqual(classifier_prompt(s,'ct'),classifier_prompt(bundle(),'ct'))
        for kind in ('report','form'):
            c=compile_naming_profile(s,kind)
            self.assertEqual(c.allowed_names,())
            self.assertEqual(c.normalize({'name':'Unapproved','date':''}).name,'')
        self.assertEqual(classifier_document(s.resource('classification_tasks'),'ct').render(),classifier_prompt(s,'ct')[0])

    def test_historical_catalog_projection_does_not_split_first_page_prose(self):
        old={'schema_version':3,'report_guidance':'- **Legacy Report**\nFIRST_PAGE_REPORT_CANARY',
             'form_guidance':'- **Legacy Form**\nFIRST_PAGE_FORM_CANARY'}
        before=copy.deepcopy(old)
        self.assertEqual(catalog_entries(old,'report'),[{'name':'Legacy Report','description':''}])
        self.assertEqual(catalog_entries(old,'form'),[{'name':'Legacy Form','description':''}])
        self.assertEqual(old,before)
        v2={'schema_version':2,'form_rules':[{'name':'Canonical','title':'Short heading','code':'XY-10'}]}
        self.assertEqual(catalog_entries(v2,'form'),[{'name':'Canonical','description':'Heading: Short heading. Form code: XY-10.'}])
        v1={'mode':'source_title','report_titles':[],'form_titles':['Old Form'],'guidance':'Do not split.'}
        self.assertEqual(catalog_entries(v1,'report'),[])
        self.assertEqual(catalog_entries(v1,'form'),[{'name':'Old Form','description':''}])

    def test_exact_initial_structured_profiles_adapt_without_writes(self):
        e=ProfileEditor(bundle());e.manifest['schema_version']=7
        base=ROOT/'recordprep/resources/profile_baselines/dependency-1.7.0-initial'
        for resource,file in (('classification_tasks','classification-v2.json'),('naming','naming-v4.json')):
            e.resources[resource]=json.loads((base/file).read_bytes())
        old=e.snapshot();before=old.files
        self.assertIn('DETENTION REPORT heading',old.resource('naming')['reports'][0]['guidance'])
        self.assertEqual(classifier_prompt(old,'ct'),classifier_prompt(bundle(),'ct'))
        self.assertEqual(compile_naming_profile(old,'report').prompt,compile_naming_profile(bundle(),'report').prompt)
        draft=editable_profile(old)
        self.assertEqual(draft.resources['naming']['reports'][0]['guidance'],'')
        self.assertEqual(draft.manifest['schema_version'],8)
        self.assertNotIn('Detention Report',draft.resources['classification_tasks']['page_types']['ct']['CT_report'])
        self.assertEqual(old.files,before)
        custom=old.resource('naming');custom['reports'][0]['guidance']+=' Custom literal prose.'
        self.assertEqual(effective_resource(custom,'naming'),custom)
