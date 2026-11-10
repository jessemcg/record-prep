"""Grouped motion contracts and real offline pipeline; wholly fictional sources."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from recordprep import motion_groups as mg, motion_organization as org, summary_agents as sa
from recordprep.motion_pages import build_motion_boundaries
from recordprep.motion_guidance import application_metadata, application_guidance
from recordprep.profile_artifacts import validate_motion_groups
from recordprep.profile_contract import json_bytes, validate_contents, ProfileError
from test_structured_classification import bundle
import test_summary_agent_pipeline as pipeline

ROOT = Path(__file__).resolve().parents[1]


class GroupedMotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'case'
        for name in ('text_pages', 'artifacts', 'classification'):
            (self.root / name).mkdir(parents=True)
        self.env = patch.dict(os.environ, {k: str(self.base / k.lower()) for k in
            ('HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_STATE_HOME',
             'PI_CODING_AGENT_DIR', 'RECORDPREP_CONFIG_DIR')} | {'PI_RUN_METRICS_ENABLED': '0'})
        self.env.start(); self.addCleanup(self.env.stop)
        self.project = ROOT / '.pi'
        self.final = self.root / 'classification/CT_basic_advanced_corrected_dates_names.jsonl'

    def papers(self, spans=((98, 99), (100, 101), (102, 103), (104, 106)), *,
               date='November 1, 2026', basis='filed'):
        titles = ['Notice and Motion to Compel Inspection', 'Declaration Supporting Motion to Compel Inspection',
                  'Separate Statement Supporting Inspection', 'Memorandum Supporting Inspection']
        rows = []
        for index, (start, end) in enumerate(spans):
            for n in range(start, end + 1):
                (self.root / f'text_pages/{n:04d}.txt').write_text(
                    f'Fictional source page {n}. QUOTEME:aa bb unique phrase here. This paper expressly supports the inspection request.\n')
                rows.append({'file_name': f'{n:04d}.txt', 'page_type': 'CT_motion_first_page' if n == start else 'CT_motion',
                             'motion_first_page': 'yes' if n == start else 'no',
                             **({'name': titles[index % 4], 'date': date, 'date_basis': basis} if n == start else {})})
        self.final.write_text('\n'.join(json.dumps(r) for r in rows) + '\n')
        bounds = build_motion_boundaries(rows, -1)
        (self.root / 'artifacts/motion_boundaries.json').write_text(json.dumps(bounds))
        return mg.inventory_from_boundaries(bounds)

    def proposal(self, inventory, lead=None, members=None, role='motion/application', title='Motion to compel inspection'):
        return {'lead_paper_id': lead or inventory[0]['paper_id'],
                'member_paper_ids': members or [p['paper_id'] for p in inventory],
                'filing_role': role, 'display_title': title, 'filing_party': 'Owner',
                'purpose': 'Compel inspection', 'evidence': 'The papers expressly identify the same inspection request.'}

    def save(self, proposals, *, coverage='complete'):
        inventory, guard, ref = org.capture(self.root, self.project)
        candidate = self.base / 'candidate.json'
        candidate.write_text(json.dumps({'groups': proposals, 'coverage_status': coverage}))
        return org.publish(self.root, self.project, guard, ref, candidate)

    def test_continuity_policy_is_delivered_without_changing_physical_inventory(self):
        inventory = self.papers()
        workspace = self.base / 'policy-work'; workspace.mkdir()
        _guard, _ref, _candidate, _spec, prompt = org.stage_inputs(self.root, self.project, workspace)
        for phrase in ('continuous supporting paperwork', 'another independent',
                       'without requiring an express', 'back-to-back',
                       'requires express source linkage', "lead paper's inventory source_title",
                       'Never replace a known lead date'):
            self.assertIn(phrase, prompt)
        self.assertEqual(org.selected_inventory(self.root)[0], inventory)
        skill = (self.project / 'skills' / org.SKILL / 'SKILL.md').read_text()
        self.assertIn('continuous declarations', skill)
        self.assertIn('oppositions or replies', skill)
        self.assertNotIn('Short names describe', skill)

    def test_four_physical_papers_nine_pages_one_entry_and_v3_roundtrip(self):
        inventory = self.papers()
        saved = self.save([self.proposal(inventory)])
        self.assertEqual(len(saved['inventory']), 4)
        self.assertEqual(len(saved['groups']), 1)
        self.assertEqual(saved['coverage_status'], 'complete')
        item, = sa.build_work_items(self.root, sa.ExtractionConfig('motions', 'CANARY', additional_guidance='CANARY'))
        self.assertEqual(sa.item_source_pages(item), tuple(range(98, 107)))
        self.assertEqual(item.item_id, 'motion:0098')
        self.assertIn(inventory[0]['source_title'], item.label)
        row = sa.canonicalize_extraction_candidate({'categories': [{'id': 'reasons', 'digest': {
            'text': 'The inspection is needed to resolve a material dispute.',
            'evidence': [{'text': 'unique phrase here', 'file_page': 106}]}}]}, item, self.root / 'text_pages')
        self.assertEqual(row['schema_version'], 4)
        evidence = row['categories'][1]['digest']['evidence'][0]
        self.assertTrue(evidence['verified'])
        self.assertEqual(evidence['quote_id'], 'motion:0098/reasons/1')
        self.assertEqual((self.root / 'text_pages/0106.txt').read_text()[evidence['source_start']:evidence['source_end']], evidence['text'])
        markdown = sa.serialize_digest_markdown('motions', 'case', [row])
        self.assertIn('"format_version": 3', markdown)
        self.assertEqual(sa.parse_digest_markdown(markdown, 'motions', 'case'), [row])
        sa.publish_digests(self.root, 'motions', [item], sa.ExtractionConfig('motions', ''), [row])
        self.assertEqual(sa.load_digest_meta(self.root, 'motions')['schema_version'], 6)
        self.assertEqual(sa.reload_published_digest_rows(self.root, 'motions', [item]), [row])
        self.assertNotIn('CANARY', sa.ExtractionConfig('motions', 'CANARY').guidance)

    def test_nonadjacent_support_before_lead_exact_pages_hashes_and_quotes(self):
        inventory = self.papers(((10, 11), (20, 21), (30, 31), (40, 41)))
        (self.root / 'text_pages/0015.txt').write_text('UNRELATED GAP CANARY')
        self.save([self.proposal(inventory, lead='motion:0030', members=['motion:0010', 'motion:0030'])])
        items = sa.build_work_items(self.root, sa.ExtractionConfig('motions', ''))
        item = next(i for i in items if i.item_id == 'motion:0030')
        self.assertEqual(item.anchor_page, 30)
        self.assertEqual(sa.item_source_pages(item), (10, 11, 30, 31))
        payload = sa.item_source_payload(item, self.root / 'text_pages', {})
        self.assertNotIn('UNRELATED', payload)
        row = sa.canonicalize_extraction_candidate({'categories': [{'id': 'request', 'digest': {'text': 'Inspection requested.',
            'evidence': [{'text': 'UNRELATED GAP CANARY', 'file_page': 15}, {'text': 'unique phrase here', 'file_page': 31}]}}]}, item, self.root / 'text_pages')
        self.assertEqual([q['file_page'] for q in row['categories'][0]['digest']['evidence']], [31])
        md = sa.serialize_digest_markdown('motions', 'case', [row])
        self.assertIn('Source pages: 10-11, 30-31', md)
        self.assertEqual(sa.parse_digest_markdown(md, 'motions', 'case'), [row])
        from recordprep.summary_editions import build_summary_edition, publish_summary_edition, validate_summary_edition_files
        final = sa.render_final_summary('motions', 'case', [row], [sa.SynthesisSectionCandidate(item.item_id, ['The owner requests inspection.'])], {item.item_id: (item.anchor_page, None)})
        metadata = sa.build_final_meta(self.root, 'motions', [row], final, {}, {item.item_id: (item.anchor_page, None)})
        final_path = self.root / 'artifacts/motions_sum_case.txt'
        meta_path = final_path.with_suffix('.meta.json')
        final_path.write_text(final); meta_path.write_text(json.dumps(metadata))
        edition = build_summary_edition('motions', final_path, self.root)
        self.assertIn(30, [link['target_page'] for page in edition.page_map['pages'] for link in page['links']])
        self.assertNotIn(10, [link['target_page'] for page in edition.page_map['pages'] for link in page['links']])
        publish_summary_edition(edition, final_path)
        self.assertEqual(validate_summary_edition_files('motions', final_path, self.root), [])
        before = item.generation_sha256
        (self.root / 'text_pages/0015.txt').write_text('CHANGED UNRELATED')
        after = next(i for i in sa.build_work_items(self.root, sa.ExtractionConfig('motions', '')) if i.item_id == item.item_id)
        self.assertEqual(before, after.generation_sha256)
        row['categories'][0]['digest']['evidence'][0]['file_page'] = 15
        self.assertTrue(sa.validate_digest_row(row, 'motions'))

    def test_motion_opposition_reply_each_owns_its_support(self):
        inventory = self.papers(tuple((n, n + 1) for n in (1, 3, 5, 7, 9, 11)))
        proposals = [self.proposal(inventory, lead=f'motion:{n:04d}', members=[f'motion:{n:04d}', f'motion:{n+2:04d}'],
                                  role=role, title=title) for n, role, title in
                     ((1, 'motion/application', 'Motion to compel inspection'),
                      (5, 'opposition', 'Opposition to inspection'), (9, 'reply', 'Reply on inspection'))]
        saved = self.save(proposals)
        self.assertEqual([g['filing_role'] for g in saved['groups']], ['motion/application', 'opposition', 'reply'])
        self.assertEqual(len(saved['groups']), 3)
        self.assertEqual(len({m for g in saved['groups'] for m in g['member_paper_ids']}), 6)

    def test_bad_groups_do_not_erase_other_useful_groups(self):
        inventory = self.papers()
        useful = self.proposal(inventory, members=['motion:0098', 'motion:0100'])
        for malformed in ({}, [], {'lead_paper_id': 'motion:0999', 'member_paper_ids': ['motion:0999']},
                          self.proposal(inventory, members=['motion:0102'], lead='motion:0102', role=[])):
            with self.subTest(candidate=type(malformed).__name__):
                result = mg.normalize_candidate({'groups': [useful, malformed]}, inventory, 'a' * 64)
                self.assertEqual(result['groups'][0]['member_paper_ids'], ['motion:0098', 'motion:0100'])
                self.assertEqual(len(result['groups']), 3)
                self.assertEqual(result['coverage_status'], 'incomplete')
        duplicate = self.proposal(inventory, lead='motion:0102', members=['motion:0100', 'motion:0102'])
        result = mg.normalize_candidate({'groups': [useful, duplicate]}, inventory, 'a' * 64)
        self.assertEqual(len(result['groups']), 4)
        self.assertTrue(all(len(g['member_paper_ids']) == 1 for g in result['groups']))

    def test_optional_date_recovery_types_and_calendar_through_publication(self):
        missing = object()
        invalid = (missing, None, 20261102, True, False, [], {},
                   'RAW_MODEL_OUTPUT_NOT_A_DATE', 'February 30, 2026', 'February 29, 2025')
        cases = [(value, None) for value in invalid] + [
            ('November 2, 2026', 'November 2, 2026'),
            ('February 29, 2024', 'February 29, 2024')]
        for original_date, original_basis in (('', 'unknown'), ('November 1, 2026', 'document'),
                                               ('November 1, 2026', 'filed')):
            for basis in ('filed', 'document'):
                for value, recovered in cases:
                    with self.subTest(original=(original_date, original_basis), basis=basis, value=value):
                        inventory = self.papers(((98, 99),), date=original_date, basis=original_basis)
                        sources = {p: p.read_bytes() for p in (self.root / 'text_pages').glob('*.txt')}
                        proposal = self.proposal(inventory) | {'date_basis': basis}
                        if value is not missing:
                            proposal['date'] = value
                        attempted = not original_date
                        result = mg.normalize_candidate({'groups': [proposal], 'coverage_status': 'complete'},
                                                        inventory, 'a' * 64)
                        saved = self.save([proposal])
                        self.assertEqual(saved['groups'], result['groups'])
                        self.assertEqual(saved['findings'], result['findings'])
                        self.assertEqual(saved['inventory'], inventory)
                        self.assertEqual(saved['coverage_status'], 'complete')
                        group, = saved['groups']
                        self.assertEqual((group['date'], group['date_basis']),
                                         (recovered, basis) if attempted and recovered else
                                         (original_date, original_basis))
                        self.assertEqual(group['member_paper_ids'], ['motion:0098'])
                        self.assertEqual((group['lead_paper_id'], group['anchor_page']), ('motion:0098', 98))
                        self.assertEqual(group['components'], [{'paper_id': 'motion:0098', 'role': 'lead',
                                                               'start_page': 98, 'end_page': 99}])
                        self.assertEqual(saved['findings'], [
                            'Optional date recovery unavailable; original lead date and basis retained.'
                        ] if attempted and not recovered else [])
                        self.assertEqual({p: p.read_bytes() for p in sources}, sources)
                        self.assertEqual(mg.load(self.root), saved)

    def test_malformed_optional_date_keeps_other_group_and_honest_coverage(self):
        inventory = self.papers(((10, 11), (20, 21), (30, 31)), date='', basis='unknown')
        before = copy.deepcopy(inventory)
        proposals = [self.proposal(inventory, lead='motion:0020', members=['motion:0010', 'motion:0020']) |
                     {'date_basis': 'filed', 'date': {'private': 'RAW_MODEL_OUTPUT'}},
                     self.proposal(inventory, lead='motion:0030', members=['motion:0030']) |
                     {'date_basis': 'filed', 'date': 'November 2, 2026'}]
        saved = self.save(proposals)
        self.assertEqual(saved['inventory'], before)
        self.assertEqual(saved['coverage_status'], 'complete')
        self.assertEqual([g['anchor_page'] for g in saved['groups']], [20, 30])
        self.assertEqual([g['member_paper_ids'] for g in saved['groups']],
                         [['motion:0010', 'motion:0020'], ['motion:0030']])
        self.assertEqual([(g['date'], g['date_basis']) for g in saved['groups']],
                         [('', 'unknown'), ('November 2, 2026', 'filed')])
        self.assertNotIn('RAW_MODEL_OUTPUT', json.dumps(saved))
        incomplete = self.save(proposals, coverage='incomplete')
        self.assertEqual(incomplete['coverage_status'], 'incomplete')
        self.assertEqual(incomplete['groups'], saved['groups'])

    def test_missing_successful_candidate_is_incomplete_singletons_and_reusable(self):
        self.papers()
        inventory, guard, ref = org.capture(self.root, self.project)
        result = org.publish(self.root, self.project, guard, ref, self.base / 'missing.json')
        self.assertEqual(result['coverage_status'], 'incomplete')
        self.assertEqual(len(result['groups']), 4)
        self.assertEqual(org.run_stage(self.root, self.project, lambda: self.fail('Unexpected model call')), 0)

    def test_changed_sources_stop_model_and_publication_failure_preserve_old(self):
        inventory = self.papers()
        self.save([self.proposal(inventory)])
        path = self.root / mg.PATH
        before = path.read_bytes(), path.stat().st_mtime_ns
        _, guard, ref = org.capture(self.root, self.project)
        source = self.root / 'text_pages/0106.txt'
        source.write_text(source.read_text() + ' changed')
        with self.assertRaisesRegex(ValueError, 'changed'):
            org.publish(self.root, self.project, guard, ref)
        _, guard, ref = org.capture(self.root, self.project)
        with self.assertRaises(InterruptedError):
            org.publish(self.root, self.project, guard, ref, check_stop=lambda: (_ for _ in ()).throw(InterruptedError()))
        with patch.object(org, '_atomic_write', side_effect=OSError('scripted publication failure')):
            with self.assertRaises(OSError): org.publish(self.root, self.project, guard, ref)
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def test_corrupt_store_and_unsafe_candidate_never_mean_legacy(self):
        self.papers()
        path = self.root / mg.PATH
        path.write_text('{broken')
        with self.assertRaises(ValueError): org.capture(self.root, self.project)
        path.unlink()
        _, guard, ref = org.capture(self.root, self.project)
        candidate = self.base / 'unsafe.json'
        candidate.symlink_to(self.final)
        with self.assertRaises((OSError, ValueError)): org.publish(self.root, self.project, guard, ref, candidate)
        self.assertFalse(path.exists())

    def test_explicit_organization_reuse_hashes_guidance_and_normalization(self):
        inventory = self.papers()
        self.save([self.proposal(inventory)])
        path = self.root / mg.PATH
        before = path.read_bytes(), path.stat().st_mtime_ns
        self.assertTrue(org.is_current(self.root, self.project))
        with patch.object(org, 'ORGANIZATION_GUIDANCE', org.ORGANIZATION_GUIDANCE + '\nFictional refinement.'):
            self.assertFalse(org.is_current(self.root, self.project))
        original_read = org._read
        def changed_normalizer(path, *args, **kwargs):
            value = original_read(path, *args, **kwargs)
            return value + b'\n# fictional normalization change' if path == Path(mg.__file__) else value
        with patch.object(org, '_read', side_effect=changed_normalizer):
            self.assertFalse(org.is_current(self.root, self.project))
        self.assertTrue(org.is_current(self.root, self.project))
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def test_concurrent_organization_refused(self):
        with org.lock(self.root):
            with self.assertRaisesRegex(ValueError, 'already running'):
                with org.lock(self.root): pass

    def test_stale_metadata_uses_singletons_without_writing(self):
        inventory = self.papers()
        self.save([self.proposal(inventory)])
        before = (self.root / mg.PATH).read_bytes()
        source = self.root / 'text_pages/0106.txt'; source.write_text('changed source')
        groups, warning = mg.current_groups(self.root, json.loads((self.root / 'artifacts/motion_boundaries.json').read_text()))
        self.assertEqual(len(groups), 4)
        self.assertIn('stale', warning)
        self.assertEqual((self.root / mg.PATH).read_bytes(), before)

    def test_fixed_topics_and_fingerprints_ignore_all_profile_and_config_prose(self):
        from test_practice_profiles import historical_snapshot
        profile = historical_snapshot(bundle(), version=13)
        files, manifest = dict(profile.files), profile.manifest
        manifest['schema_version'] = 11
        manifest['resources']['motion_naming'] = 'historical-motion-naming.json'
        files['historical-motion-naming.json'] = json_bytes({'schema_version': 1, 'motions': []})
        manifest['resources']['motions'] = 'historical-motions.json'
        files['historical-motions.json'] = json_bytes([{'id': 'canary', 'title': 'CANARY', 'guidance': 'CANARY CUSTOM MOTION METHOD'}])
        files['profile.json'] = json_bytes(manifest)
        historical = validate_contents(tuple(files.items()), 'recordprep')
        configs = [sa.ExtractionConfig('motions', 'CANARY CONFIG', additional_guidance='CANARY EXTRA', profile=p) for p in (None, profile, historical)]
        self.assertEqual(len({c.fingerprint for c in configs}), 1)
        for c in configs:
            self.assertEqual([d.identifier for d in c.definitions], ['request', 'reasons'])
            self.assertNotIn('CANARY', c.guidance)
        from recordprep.summary_profiles import compile_summary
        self.assertNotIn('CANARY', compile_summary(historical, 'motions', 'synthesize').prompt)
        from recordprep.prompt_inspection import inspect_prompt, DraftInspectionState
        draft = DraftInspectionState({'motions': [{'guidance': 'CANARY'}]}, (), ('INVALID CANARY DRAFT',), None)
        for task in ('motion-organization', 'motions-extract', 'motions-synthesize'):
            inspected = inspect_prompt({}, task, self.project, template=False, draft=draft)
            self.assertNotIn('CANARY', inspected.display_text())
            self.assertFalse(any('DRAFT' in issue for issue in inspected.issues))

    def test_current_schema_rejects_motion_topics_old_snapshots_literal(self):
        current = bundle()
        self.assertEqual(current.manifest['schema_version'], 14)
        self.assertNotIn('motions', current.manifest['resources'])
        files, manifest = dict(current.files), current.manifest
        manifest['resources']['motions'] = 'motions.json'
        files['motions.json'] = json_bytes([])
        files['profile.json'] = json_bytes(manifest)
        with self.assertRaises(ProfileError): validate_contents(tuple(files.items()), 'recordprep')

    def test_native_staging_exact_reads_and_long_page_ids(self):
        self.papers(((9998, 9999), (10000, 10001)))
        work = self.base / 'workspace'; work.mkdir(mode=0o700)
        guard, ref, candidate, spec, prompt = org.stage_inputs(self.root, self.project, work)
        access = json.loads(spec.read_text())
        self.assertTrue(all(Path(p).is_relative_to(work) for p in access['reads']))
        self.assertIn(str(work / 'source-10001.txt'), access['reads'])
        self.assertTrue(prompt.startswith('/skill:recordprep-organize-motion-papers '))
        self.assertIn("lead paper's inventory source_title", prompt)
        self.assertNotIn('Mother to compel police records', prompt)

    def test_zero_selection_has_no_model_call(self):
        self.final.write_text(json.dumps({'file_name': '0001.txt', 'page_type': 'CT_other'}) + '\n')
        marker = {'motion_checks_version': 1, 'outputs': {self.final.name: hashlib.sha256(self.final.read_bytes()).hexdigest()}}
        (self.root / 'classification/profile-advanced.json').write_text(json.dumps(marker))
        self.assertEqual(org.run_stage(self.root, self.project, lambda: self.fail('Unexpected organization call')), 0)
        result = mg.load(self.root)
        self.assertEqual(result['groups'], [])
        self.assertEqual(result['coverage_status'], 'complete')

    def test_real_summary_runner_grouped_calls_and_unchanged_zero_calls(self):
        inventory = self.papers()
        self.save([self.proposal(inventory)])
        acceptance = pipeline.FakePiEndToEndTests()
        project = acceptance._staged_project(self.base)
        fake = self.base / 'fake-pi'; fake.write_text(acceptance.FAKE_PI); fake.chmod(0o755)
        log = self.base / 'calls.log'
        result = acceptance._run_stage('create_motion_summaries', self.root, project, fake, log)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = [json.loads(line) for line in log.read_text().splitlines() if '--version' not in line and 'rpc' not in line]
        self.assertEqual(len(calls), 2)  # One grouped extraction + synthesis, no repair.
        rows = sa.load_digest_markdown(self.root, 'motions')
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['members']), 4)
        self.assertEqual(sa.load_final_meta(self.root, 'motions')['schema_version'], 6)
        self.assertEqual(sa.validate_summary_agent_outputs(self.root, 'motions'), [])
        before = log.read_bytes()
        again = acceptance._run_stage('create_motion_summaries', self.root, project, fake, log)
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(log.read_bytes(), before)

    def test_real_native_runner_one_organization_child_then_reuse(self):
        import sys
        from test_pi_resources import _load_runner_module
        self.papers()
        runner = _load_runner_module()
        fake = self.base / 'native.py'
        fake.write_text('''import json, os, sys
from pathlib import Path
if '--version' in sys.argv:
    print('0.85.0'); raise SystemExit(0)
spec=json.loads(Path(os.environ['RECORDPREP_MOTION_ORGANIZATION_ACCESS_SPEC']).read_text())
inventory=json.loads(Path(spec['reads'][0]).read_text())
Path(spec['candidate']).write_text(json.dumps({'groups':[{'lead_paper_id':inventory[0]['paper_id'],
 'member_paper_ids':[p['paper_id'] for p in inventory], 'filing_role':'motion/application',
 'display_title':'Motion to compel inspection', 'filing_party':'Owner',
 'evidence':'Express relationship in the fictional papers.'}], 'coverage_status':'complete'}))
''')
        with patch.object(runner, '_resolve_pi_command', return_value=[sys.executable, str(fake)]):
            self.assertEqual(runner._run_stage(runner.STAGES['organize_motion_papers'], self.root, self.project), 0)
        self.assertEqual(len(mg.load(self.root)['groups']), 1)
        with patch.object(runner, '_resolve_pi_command', side_effect=AssertionError('No repeated model call')):
            self.assertEqual(runner._run_stage(runner.STAGES['organize_motion_papers'], self.root, self.project), 0)

    def test_digest_pair_failure_and_unsafe_final_preserve_prior_bytes_and_mtime(self):
        inventory = self.papers()
        self.save([self.proposal(inventory)])
        config = sa.ExtractionConfig('motions', '')
        item, = sa.build_work_items(self.root, config)
        row = sa.canonicalize_extraction_candidate({}, item, self.root / 'text_pages')
        sa.publish_digests(self.root, 'motions', [item], config, [row])
        digest = sa.summary_digest_path(self.root, 'motions'); metadata = sa.summary_digest_meta_path(self.root, 'motions')
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (digest, metadata)}
        replace = os.replace
        def fail_meta(source, destination):
            if Path(destination) == metadata: raise OSError('scripted sidecar publication failure')
            return replace(source, destination)
        row['categories'][0]['digest'] = {'text': 'New useful request.', 'evidence': []}
        with patch.object(sa.os, 'replace', side_effect=fail_meta):
            with self.assertRaises(OSError): sa.publish_digests(self.root, 'motions', [item], config, [row])
        self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}, before)
        final = self.root / 'artifacts/unsafe-final.txt'; final.symlink_to(digest)
        with self.assertRaises(ValueError): sa.publish_motion_final(final, self.root / 'artifacts/unsafe-meta.json', 'new', {})
        self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}, before)

    def test_impossible_ranges_and_unsafe_boundaries_fail_without_expanding_pages(self):
        inventory = self.papers()
        self.save([self.proposal(inventory)])
        saved = self.root / mg.PATH
        before = saved.read_bytes(), saved.stat().st_mtime_ns
        boundaries = self.root / 'artifacts/motion_boundaries.json'
        original = boundaries.read_bytes()
        rows = json.loads(original); rows[-1]['end_page'] = 10 ** 12
        boundaries.write_text(json.dumps(rows))
        with self.assertRaisesRegex(ValueError, 'source pages are missing'):
            sa.build_work_items(self.root, sa.ExtractionConfig('motions', ''))
        alternate = self.base / 'boundary-copy.json'; alternate.write_bytes(original)
        boundaries.unlink(); boundaries.symlink_to(alternate)
        with self.assertRaises(ValueError): sa.build_work_items(self.root, sa.ExtractionConfig('motions', ''))
        boundaries.unlink(); boundaries.write_bytes(original)
        self.final.write_text('{corrupt canonical classification')
        with self.assertRaises(ValueError): sa.build_work_items(self.root, sa.ExtractionConfig('motions', ''))
        self.assertEqual((saved.read_bytes(), saved.stat().st_mtime_ns), before)

    def test_lead_title_is_authoritative_even_with_missing_or_rewritten_proposal_title(self):
        inventory = self.papers()
        before = copy.deepcopy(inventory)
        for title in (None, [], {}, '', 'A newly composed short name', 'qualification ' * 200):
            with self.subTest(title=type(title).__name__):
                proposal = self.proposal(inventory, title=title)
                result = mg.normalize_candidate({'groups': [proposal], 'coverage_status': 'complete'}, inventory, 'a' * 64)
                self.assertEqual(len(result['groups']), 1)
                self.assertEqual(result['groups'][0]['display_title'], inventory[0]['source_title'])
                self.assertEqual(result['coverage_status'], 'complete')
                self.assertEqual(result['findings'], [])
        self.assertEqual(inventory, before)

    def test_invalid_optional_role_retains_complete_packet_through_publication(self):
        inventory = self.papers()
        for role in (None, [], {}, '', 'moving papers', 'MOTION', 42):
            with self.subTest(role=role):
                saved = self.save([self.proposal(inventory, role=role)])
                self.assertEqual(saved['coverage_status'], 'complete')
                group, = saved['groups']
                self.assertEqual(group['member_paper_ids'], [p['paper_id'] for p in inventory])
                self.assertEqual(group['filing_role'], 'unresolved supporting paper')
                self.assertIn('invalid filing_role', ' '.join(saved['findings']))
                item, = sa.build_work_items(self.root, sa.ExtractionConfig('motions', ''))
                self.assertEqual(sa.item_source_pages(item), tuple(range(98, 107)))
                self.assertIn(inventory[0]['source_title'], item.label)

    def test_specific_membership_diagnostics_do_not_echo_raw_model_values(self):
        inventory = self.papers()
        base = self.proposal(inventory)
        cases = [
            ([], 'group must be an object'),
            (base | {'member_paper_ids': []}, 'nonempty list'),
            (base | {'member_paper_ids': [{}]}, 'non-string ID'),
            (base | {'member_paper_ids': ['motion:0098'] * 2}, 'duplicate IDs'),
            (base | {'member_paper_ids': ['RAW_PRIVATE_VALUE']}, 'unknown inventory IDs'),
            (base | {'lead_paper_id': {}}, 'identify an inventory paper'),
            (base | {'member_paper_ids': ['motion:0100']}, 'is not a member'),
        ]
        for proposal, reason in cases:
            with self.subTest(reason=reason):
                result = mg.normalize_candidate({'groups': [proposal], 'coverage_status': 'complete'}, inventory, 'a' * 64)
                self.assertEqual(result['coverage_status'], 'incomplete')
                self.assertEqual(len(result['groups']), 4)
                diagnostic = ' '.join(result['findings'])
                self.assertIn('Group proposal 1 rejected:', diagnostic)
                self.assertIn(reason, diagnostic)
                self.assertNotIn('RAW_PRIVATE_VALUE', diagnostic)

    def test_continuous_independent_motions_are_not_mechanically_merged(self):
        inventory = self.papers()
        proposals = [self.proposal(inventory, lead=inventory[n]['paper_id'],
                                  members=[p['paper_id'] for p in inventory[n:n+2]])
                     for n in (0, 2)]
        saved = self.save(proposals)
        self.assertEqual(len(saved['groups']), 2)
        self.assertEqual([g['display_title'] for g in saved['groups']],
                         [inventory[n]['source_title'] for n in (0, 2)])
        self.assertEqual(saved['coverage_status'], 'complete')

    def test_review_coverage_is_independent_of_advisory_notes(self):
        inventory = self.papers()
        proposal = self.proposal(inventory)
        proposal['relationship_to'] = 'motion:9999'  # Optional bad link, not bad membership.
        candidate = {'groups': [proposal], 'coverage_status': 'complete',
                     'findings': ['Fictional advisory: relationship evidence has a qualification.']}
        result = mg.normalize_candidate(candidate, inventory, 'a' * 64)
        self.assertEqual(result['coverage_status'], 'complete')
        self.assertEqual(result['groups'][0]['relationship_to'], '')
        self.assertIn(candidate['findings'][0], result['findings'])
        self.assertIn('relationship reference omitted', ' '.join(result['findings']))
        for status in ('incomplete', None, '', 'COMPLETE'):
            with self.subTest(status=status):
                candidate['coverage_status'] = status
                self.assertEqual(mg.normalize_candidate(candidate, inventory, 'a' * 64)['coverage_status'], 'incomplete')
        candidate['coverage_status'] = 'complete'
        for malformed in ({}, [], self.proposal(inventory, members=['motion:9999'])):
            candidate['groups'] = [proposal, malformed]
            self.assertEqual(mg.normalize_candidate(candidate, inventory, 'a' * 64)['coverage_status'], 'incomplete')

    def test_explicit_ambiguous_singletons_are_reviewed_not_automatic_fallback(self):
        inventory = self.papers()
        proposals = [self.proposal(inventory, lead=p['paper_id'], members=[p['paper_id']],
                                  role='unresolved supporting paper') for p in inventory]
        for proposal in proposals:
            proposal['relationship_notes'] = 'Reviewed; relationship remains ambiguous.'
        candidate = {'groups': proposals, 'coverage_status': 'complete', 'findings': ['Ambiguous support retained.']}
        self.assertEqual(mg.normalize_candidate(candidate, inventory, 'a' * 64)['coverage_status'], 'complete')
        candidate['groups'] = proposals[:-1]
        self.assertEqual(mg.normalize_candidate(candidate, inventory, 'a' * 64)['coverage_status'], 'incomplete')
        duplicate = {'groups': [*proposals, proposals[0]], 'coverage_status': 'complete'}
        self.assertEqual(mg.normalize_candidate(duplicate, inventory, 'a' * 64)['coverage_status'], 'incomplete')
        for missing in (None, {}, {'groups': None}, {'groups': []}):
            self.assertEqual(mg.normalize_candidate(missing, inventory, 'a' * 64)['coverage_status'], 'incomplete')

    def test_review_plain_text_counts_components_notes_and_saved_status(self):
        inventory = self.papers()
        for papers, proposals, expected in (
            ([], [], '0 entries / 0 physical papers'),
            (inventory[:1], [self.proposal(inventory[:1])], '1 entry / 1 physical paper'),
            (inventory, [self.proposal(inventory)], '1 entry / 4 physical papers'),
            (inventory, [], '4 entries / 4 physical papers'),
        ):
            with self.subTest(expected=expected):
                result = mg.normalize_candidate({'groups': proposals, 'coverage_status': 'complete'}, papers, 'a' * 64)
                result['coverage_status'] = 'incomplete'  # Historical status stays as saved.
                result['findings'] = ['<b>Advisory text, not markup</b>']
                original = copy.deepcopy(result)
                rendered = mg.review_text(result)
                self.assertIn('Review coverage: incomplete', rendered)
                self.assertIn(expected, rendered)
                self.assertIn('Notes:\n<b>Advisory text, not markup</b>', rendered)
                for paper in papers:
                    self.assertIn(paper['source_title'], rendered)
                    self.assertIn(f"source pages {paper['start_page']}–{paper['end_page']}", rendered)
                if papers:
                    self.assertIn('  Components:\n', rendered)
                    self.assertIn('Filing party:', rendered)
                    self.assertIn('(filed)', rendered)
                    self.assertIn('lead source page', rendered)
                self.assertEqual(result, original)

    def test_actual_native_guard_exact_reads_and_private_writes(self):
        import shutil
        import subprocess
        node = shutil.which('node')
        if not node:
            self.skipTest('Node is unavailable')
        result = subprocess.run([node, str(Path(__file__).with_name('motion_organization_tools_contract.mjs'))],
            cwd=Path(__file__).resolve().parents[1], env=dict(os.environ, RECORDPREP_GUARD_TEST_ROOT=str(self.base / 'guard')),
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Motion organization boundary contract passed', result.stdout)

    def test_actual_sdk_organization_skill_staged_reads_and_write_boundary(self):
        import shutil
        import subprocess
        node = shutil.which('node')
        if not node: self.skipTest('Node unavailable')
        self.papers()
        workspace = self.base / 'sdk-work'; workspace.mkdir(mode=0o700)
        skill = workspace / '.pi/skills' / org.SKILL / 'SKILL.md'
        skill.parent.mkdir(parents=True)
        shutil.copy2(self.project / 'skills' / org.SKILL / 'SKILL.md', skill)
        guard, ref, candidate, spec, launch = org.stage_inputs(self.root, self.project, workspace)
        reads = json.loads(spec.read_text())['reads']
        data = {'groups': [], 'coverage_status': 'incomplete'}
        frames = [{'content': [{'type': 'toolCall', 'id': f't{i}', 'name': name, 'arguments': arguments}], 'stopReason': 'toolUse'}
                  for i, (name, arguments) in enumerate([
                      ('read', {'path': reads[1]}),
                      ('read', {'path': str(self.root / mg.PATH)}),
                      ('write', {'path': str(candidate), 'content': json.dumps(data)}),
                      ('write', {'path': str(self.root / mg.PATH), 'content': '{}'}),
                  ])]
        plan = {'system': (self.project / 'SYSTEM.md').read_text(), 'skill': str(skill),
                'extension': str(self.project / 'extensions' / org.EXTENSION), 'launch': launch,
                'tools': ['read', 'write', 'edit'], 'frames': frames, 'bindExtensions': True}
        plan_path = workspace / 'plan.json'; result_path = workspace / 'capture.json'
        plan_path.write_text(json.dumps(plan))
        completed = subprocess.run([node, str(ROOT / 'tests/offline_prompt_sdk.mjs'), str(plan_path), str(result_path)],
            cwd=workspace, env=dict(os.environ, RECORDPREP_MOTION_ORGANIZATION_ACCESS_SPEC=str(spec)),
            capture_output=True, text=True, timeout=40)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        result = json.loads(result_path.read_text())
        self.assertEqual([bool(r.get('isError')) for r in result['tool_results']], [False, True, False, True])
        self.assertEqual(json.loads(candidate.read_text()), data)
        self.assertFalse((self.root / mg.PATH).exists())
        self.assertIn('Fictional source page', json.dumps(result['tool_results'][0]))

    def test_final_publication_rolls_back_after_second_replace_failure(self):
        final = self.root / 'artifacts/final.txt'; metadata = final.with_suffix('.meta.json')
        final.write_text('old final'); metadata.write_text('old metadata')
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (final, metadata)}
        replace = os.replace
        def fail_meta(source, destination):
            if Path(destination) == metadata:
                raise OSError('scripted final-metadata replacement failure')
            return replace(source, destination)
        with patch.object(sa.os, 'replace', side_effect=fail_meta):
            with self.assertRaises(OSError): sa.publish_motion_final(final, metadata, 'new final', {'schema_version': 6})
        self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}, before)

    def test_resume_legacy_absence_does_not_write(self):
        from recordprep.output_presence import legacy_organization_skip, step_outputs_present
        self.assertFalse(legacy_organization_skip(self.root))
        path = self.root / 'artifacts/toc.txt'; path.write_text('MOTIONS\n')
        before = path.read_bytes(), path.stat().st_mtime_ns
        self.assertTrue(legacy_organization_skip(self.root))
        self.assertFalse(step_outputs_present('organize_motion_papers', self.root))
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
