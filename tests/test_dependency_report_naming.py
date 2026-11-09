"""Evidence-informed naming contracts; offline checks are not model-quality results."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from recordprep import practice_profiles as api
from recordprep.classification_profiles import classifier_prompt, component
from recordprep.document_naming import compile_naming_profile, NAMING_CONTRACT_VERSION, naming_document
from recordprep.profile_contract import validate_contents
from recordprep.profile_workflows import ProfileEditor
from recordprep.prompt_inspection import inspect_prompt
from test_document_naming import BUNDLED_REPORT_TITLES

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = 'f67e0a93bb226ea682988f54b9555c5705f3d42a952631a3327091aa5561a620'
PRIOR_AGENCY_BASELINE = '26f5ff0c018868b85966f4a54190ac4f6e6c8abc5f8351acfc348d9b5bbd79a4'
DATE_RULE = ('Use the date tied to the report itself or to its hearing, such as a field labeled Hearing Date near the report title. '
             'Ignore file stamps, clerk stamps, page numbers, footer dates, and service/printing dates unless no other report date is visible.\n')


def bundle():
    return api.bundled_profile_for_identity(api.APPLICATION, api.DEFAULT_PROFILE_ID)


def previous_bundle():
    """Reconstruct exact 1.9.0 from unchanged archived naming and manifest bytes.

    No historical fixture, adapter or private snapshot is upgraded to current cards.
    The digest assertion below guards this reconstruction against later drift.
    """
    files = {p.name:p.read_bytes() for p in (ROOT/'tests/fixtures/minute_profile_1_10').iterdir()}
    files['naming.json'] = (ROOT/'recordprep/resources/profile_baselines/dependency-1.6.0/naming-v4.json').read_bytes()
    files['profile.json'] = files['profile.json'].replace(b'"1.10.0"', b'"1.9.0"')
    return validate_contents(tuple(files.items()), api.APPLICATION)


def title_catalog_bundle():
    """Exact former 1.11.0 bundle, reconstructed from immutable 1.10.0 resources."""
    files = {p.name: p.read_bytes() for p in (ROOT/'tests/fixtures/minute_profile_1_10').iterdir()}
    del files['minutes.md']
    manifest = json.loads(files['profile.json'])
    manifest['schema_version'] = 10
    manifest['version'] = '1.11.0'
    del manifest['resources']['minutes']
    files['profile.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode()
    return validate_contents(tuple(files.items()), api.APPLICATION)


class DependencyReportNamingTests(unittest.TestCase):
    def test_release_catalog_ids_forms_and_unrelated_bytes(self):
        b = bundle(); old = previous_bundle()
        self.assertEqual(old.ref.content_sha256, PREVIOUS)
        self.assertIn(PREVIOUS, api.KNOWN_BASELINES)
        self.assertEqual((b.manifest['version'], b.manifest['schema_version'], b.manifest['profile_api']), ('1.17.0',14,1))
        n = b.resource('naming'); historical = old.resource('naming')
        self.assertEqual(n['schema_version'],5)
        self.assertEqual(n['reports'][0]['naming_mode'], 'source_title')
        self.assertEqual(tuple(c['name'] for c in n['reports']),BUNDLED_REPORT_TITLES)
        self.assertEqual(len(n['reports']), 1)
        self.assertEqual(n['reports'][0]['id'], 'report-agency')
        prior = title_catalog_bundle()
        self.assertEqual(prior.ref.content_sha256, PRIOR_AGENCY_BASELINE)
        self.assertIn(PRIOR_AGENCY_BASELINE, api.KNOWN_BASELINES)
        self.assertEqual(len(prior.resource('naming')['reports']), 17)
        for filename, content in prior.files:
            if filename not in ('profile.json', 'naming.json', 'hearings.json'):
                self.assertEqual(dict(b.files)[filename], content, filename)
        self.assertEqual(n['forms'],historical['forms']); self.assertEqual(len(n['forms']),6)
        for name,digest in {
            'case-name.md':'ac60cda00e130e635e15cb7be406317b18a24c0416b7abf2a904b8792dfa016a',
            'reports.json':'f0ee91c592bcd555ba3b8e3f36f9835a9664b194a46195bdb8a02615c2d81c37',
            'policies.json':'ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356',
        }.items():
            self.assertEqual(hashlib.sha256(dict(b.files)[name]).hexdigest(),digest,name)
        self.assertEqual(hashlib.sha256((ROOT/'recordprep/resources/classification/recognition-v1.json').read_bytes()).hexdigest(),
                         '4c564fc3a40fc01fecadce36cc01f91ea8b8732d6d0d07a214a033d73543fb8e')

    def test_category_guidance_selects_authorship_and_purpose_not_literal_title(self):
        prompt = compile_naming_profile(bundle(), 'report').prompt
        for text in (
            'only the fallback when the document clearly qualifies',
            'Memoranda, letters, addenda, supplemental information',
            'including short memoranda explaining or supplying omitted material',
            'substantial narrative or a recommendation is not required',
            'visible evidence on the supplied first page',
            'agency letterhead or department identification',
            'social worker, supervisor, or authorized agency representative',
            'supporting clues, not mandatory fields or an exhaustive checklist',
            'Agency names and report titles vary by jurisdiction',
            'transmitted or filed by the agency',
            'independently authored CASA, medical, psychological, school, service-provider, or law-enforcement records',
            'petitions, motions, notices, proofs of service, and court orders',
            'do not merge separate reports because their names or dates match',
            'leave the name empty rather than guessing',
        ):
            self.assertIn(text, prompt)
        self.assertNotIn('Identify a separately titled', prompt)

    def test_footer_evidence_rule_date_bytes_and_form_prompt_preserved(self):
        b = bundle(); prompt = compile_naming_profile(title_catalog_bundle(),'report').prompt
        for text in ('own visible title or identifying wording', 'interpreted with the catalog descriptions',
                     'strong evidence, not a requirement', 'opening structure and court/report identification',
                     'same supplied image', 'running title, code, or page number alone is insufficient',
                     'conflicting heading and footer evidence', 'explicitly described variants',
                     'conflict remains unresolved, return an empty name', 'attachment list',
                     'hearing-type field', 'request to prepare another report'):
            self.assertIn(text,prompt)
        mechanics = naming_document(b.resource('naming'),'report').sections[1].text
        self.assertIn(DATE_RULE,mechanics)
        self.assertEqual(mechanics.count(DATE_RULE),1)
        self.assertNotIn('must appear as a prominent heading',prompt)
        self.assertEqual(NAMING_CONTRACT_VERSION,2)
        self.assertEqual(hashlib.sha256(compile_naming_profile(b,'form').prompt.encode()).hexdigest(),
                         '1d9d3511f75c78b80c87ee53b40a83b8a2901b73063511a76f84c28a514b24fb')

    def test_descriptions_only_in_report_naming_and_stage_identities(self):
        b = bundle()
        # Motion recognition deliberately advances the application contract.
        # Report catalog changes must still leave all non-Names stages alone.
        old_catalog = title_catalog_bundle()
        for stage in ('basic', 'advanced', 'dates'):
            self.assertEqual(component(b, stage), component(old_catalog, stage), stage)
        self.assertNotEqual(component(b,'names'),'eb02838cd1a6e8994f4d2709747d8f490878f49796f79e75701d905f5c743369')
        resources = {k:b.resource(k) for k in b.manifest['resources']}
        for task in ('rt','ct','first_hearing','first_minute','first_form','first_report','date_hearing','date_minute','form','report'):
            view = inspect_prompt(resources,task,ROOT/'.pi',template=False,snapshot=b)
            self.assertFalse(view.issues)
            prompt = view.components[0][1]
            self.assertEqual(view.components[1][0],'Page image — attached separately')
            for card in b.resource('naming')['reports']:
                self.assertEqual(card['guidance'] in prompt,task=='report')
            if task not in ('report','form'):
                self.assertEqual(prompt,classifier_prompt(b,task)[0])

    def test_source_titles_require_rule_match_and_preserve_unresolved_dates(self):
        contract = compile_naming_profile(bundle(),'report')
        self.assertEqual(contract.response_keys,('name','date','rule_id'))
        for title in ('Memorandum', 'Detention Report', 'Status Review Report', 'Progress Report'):
            result = contract.normalize({'name':title, 'date':'January 02, 2026', 'rule_id':'report-agency'})
            self.assertEqual((result.name,result.date,result.rule_id),(title,'January 2, 2026','report-agency'))
        for rule_id in ('', 'unknown', None):
            result = contract.normalize({'name':'Independent report','date':'January 02, 2026','rule_id':rule_id})
            self.assertEqual((result.name,result.date),('','January 2, 2026'))
            self.assertIn('name_unresolved',result.quality_flags)
        fallback = contract.normalize({'name':'','date':'','rule_id':'report-agency'})
        self.assertEqual(fallback.name, 'Child Welfare Agency Report')
        self.assertIn('source_title_missing', fallback.quality_flags)

    def test_old_acceptance_is_not_personal_and_personal_profiles_are_not_replaced(self):
        old = title_catalog_bundle(); before = old.files
        for personal in (False,True):
            with self.subTest(personal=personal), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                store = api.ProfileStore(api.APPLICATION,config_root=root/'config',data_root=root/'data')
                if personal:
                    editor = ProfileEditor(old)
                    editor.resources['naming']['reports'][0]['guidance'] = 'Literal personal α {x}; preserve me.'
                    saved = editor.snapshot()
                    store.managed_save(saved,expected_head=None,expected_default=None)
                else:
                    saved = old
                    store.accept_profile(saved,expected_previous_digest=None)
                def inventory():
                    return {p:(p.read_bytes(),p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
                stored = inventory()
                candidate = api.profile_catalog(store=store,customization=lambda _:None)[0]
                self.assertEqual(candidate.personal,personal)
                self.assertEqual(candidate.snapshot.files,saved.files if personal else bundle().files)
                self.assertEqual(store.load_profile_snapshot(saved.ref).files,saved.files)
                self.assertEqual(inventory(),stored)
        self.assertEqual(old.files,before)
        self.assertEqual(len(old.resource('naming')['reports']),17)
        self.assertEqual(old.resource('naming')['reports'][0]['name'], 'Detention Report')
