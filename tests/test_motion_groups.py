"""Deterministic continuity, historical readers and offline motion pipeline."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from recordprep import motion_groups as mg, motion_organization as org, summary_agents as sa
from recordprep.motion_pages import build_motion_boundaries, continuous_selection
from recordprep.profile_artifacts import validate_motion_groups, source_map_profile_metadata
from motion_fixtures import historical_artifact
import test_summary_agent_pipeline as pipeline

ROOT = Path(__file__).resolve().parents[1]


def page(number, title=None, kind=None, date='', basis='unknown'):
    kind = kind or ('CT_motion_first_page' if title is not None else 'CT_motion')
    return {'file_name': f'{number:04d}.txt', 'page_type': kind,
            **({'motion_first_page': 'yes' if kind == 'CT_motion_first_page' else 'no'}
               if kind.startswith('CT_motion') else {}),
            **({'name': title, 'date': date, 'date_basis': basis} if title is not None else {})}


class ContinuousSelectionTests(unittest.TestCase):
    def test_independent_opposing_unnamed_components_and_lead_ownership(self):
        rows = [page(1, 'Request', date='', basis='unknown'), page(2), page(3, ''), page(4),
                page(5, 'Opposition', date='November 2, 2026', basis='filed'), page(6, 'Reply'),
                page(7, 'Different request'), page(8, kind='CT_report'), page(9), page(10, ''),
                page(11, 'New lead'), page(13, 'Gap lead')]
        bounds, packets, findings = continuous_selection(reversed(rows))
        self.assertEqual(packets, [['motion:0001', 'motion:0003', 'motion:0005', 'motion:0006', 'motion:0007'],
                                   ['motion:0011'], ['motion:0013']])
        self.assertEqual([(b['motion_id'], b['end_page']) for b in bounds],
                         [('motion:0001', '0002'), ('motion:0003', '0004'), ('motion:0005', '0005'),
                          ('motion:0006', '0006'), ('motion:0007', '0007'), ('motion:0011', '0011'), ('motion:0013', '0013')])
        self.assertEqual(bounds[1]['motion_name'], '')
        self.assertIn('9–10 (2 pages)', findings[0])
        inventory = mg.inventory_from_boundaries(bounds, allow_unnamed=True)
        value = mg.canonical_packets(inventory, packets, findings, 'a' * 64)
        self.assertEqual(value['groups'][0]['display_title'], 'Request')
        self.assertEqual((value['groups'][0]['date'], value['groups'][0]['date_basis']), ('', 'unknown'))
        self.assertEqual([b['motion_id'] for b in build_motion_boundaries(rows, -1)],
                         ['motion:0001', 'motion:0005', 'motion:0006', 'motion:0007', 'motion:0011', 'motion:0013'])

    def test_leading_fragments_unnamed_start_and_every_interruption(self):
        for kind in ('CT_report', 'CT_form', 'CT_other', 'CT_blank', 'CT_minute_order', 'CT_proof_of_service', 'CT_exhibit'):
            with self.subTest(kind=kind):
                bounds, packets, findings = continuous_selection([page(1), page(2, ''), page(3), page(4, 'Lead'),
                    page(5), page(6, kind=kind), page(7), page(8, ''), page(9, 'Second')])
                self.assertEqual(packets, [['motion:0004'], ['motion:0009']])
                self.assertEqual([(b['start_page'], b['end_page']) for b in bounds], [('0004', '0005'), ('0009', '0009')])
                self.assertEqual(len(findings), 2)
                self.assertIn('(3 pages)', findings[0]); self.assertIn('(2 pages)', findings[1])

    def test_malformed_duplicate_and_incomplete_checks_rejected(self):
        cases = [[page(1, 'Lead'), page(1, 'Lead')], [page(1, 'Lead'), page(1, kind='CT_other')],
                 [dict(page(1, 'Lead'), file_name='../0001.txt')], [dict(page(1), file_name='00001.txt')],
                 [dict(page(1), motion_first_page='yes')], [dict(page(1, 'Lead'), motion_first_page='no')],
                 [dict(page(1), motion_first_page=None)], [dict(page(1), page_type='')]]
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(ValueError): continuous_selection(rows)
        self.assertEqual(continuous_selection([]), ([], [], []))
        self.assertEqual(continuous_selection([page(1, kind='CT_other')]), ([], [], []))
        self.assertEqual(len(continuous_selection([page(9999, 'Lead'), page(10000, '')])[0]), 2)


class GroupedMotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.root = self.base / 'case'
        for name in ('text_pages', 'artifacts', 'classification'): (self.root / name).mkdir(parents=True)
        env = patch.dict(os.environ, {k: str(self.base / k.lower()) for k in ('HOME', 'XDG_CONFIG_HOME',
            'XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_STATE_HOME', 'PI_CODING_AGENT_DIR', 'RECORDPREP_CONFIG_DIR')}
            | {'PI_RUN_METRICS_ENABLED': '0'})
        env.start(); self.addCleanup(env.stop)
        self.project = ROOT / '.pi'
        self.final = self.root / 'classification/CT_basic_advanced_corrected_dates_names.jsonl'

    def papers(self, *, unnamed=False):
        rows = [page(11, 'Request to Change Fictional Order', date='November 1, 2026', basis='filed'),
                page(12), page(13), page(14, '' if unnamed else 'Declaration'), page(15),
                page(16, kind='CT_report'), page(17), page(18, ''), page(21, 'Independent motion')]
        self.final.write_text('\n'.join(json.dumps(r) for r in rows) + '\n')
        for r in rows:
            (self.root / 'text_pages' / r['file_name']).write_text(
                f"Fictional page {r['file_name']}. QUOTEME:aa bb unique phrase here. A distinct inspection phrase supports this attributed position.\n")
        bounds = build_motion_boundaries(rows, -1)
        self.boundaries = self.root / 'artifacts/motion_boundaries.json'
        self.boundaries.write_text(json.dumps(bounds))
        return rows

    def organize(self, *, rebuild=True):
        org.run_stage(self.root)
        value = mg.load(self.root)
        if rebuild:
            inventory, _, _, _ = mg.resolve_context(self.root)
            self.boundaries.write_text(json.dumps(mg.boundaries_from_inventory(inventory)))
        return value

    def test_schema2_roundtrip_no_pi_no_workspace_no_source_changes_and_mtime_reuse(self):
        self.papers(unnamed=True)
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob('*') if p.is_file()}
        with patch('recordprep.case_name_stage._model_settings', side_effect=AssertionError('model consulted')):
            value = self.organize(rebuild=False)
            self.assertTrue(org.is_current(self.root))
            path = self.root / mg.PATH; saved = path.read_bytes(), path.stat().st_mtime_ns
            org.run_stage(self.root)
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), saved)
        self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}, before)
        self.assertEqual(json.loads(json.dumps(value)), validate_motion_groups(value))
        self.assertEqual([g['anchor_page'] for g in value['groups']], [11, 21])
        self.assertEqual(value['inventory'][1]['source_title'], '')
        self.assertEqual(value['groups'][0]['member_paper_ids'], ['motion:0011', 'motion:0014'])
        self.assertIn('17–18 (2 pages)', value['findings'][0])
        self.assertFalse(any('candidate' in p.name or 'workspace' in p.name for p in self.base.rglob('*')))
        rendered = mg.review_text(value)
        self.assertIn('Selected-inventory accounting: complete', rendered)
        self.assertNotIn('Review coverage:', rendered)
        self.assertIn('Unnamed motion paper', rendered)
        self.assertIn('not legal relationship review', rendered)

    def test_contract_rejects_invalid_packets(self):
        self.papers(unnamed=True); value = self.organize()
        def bad(change):
            v = copy.deepcopy(value); change(v)
            with self.assertRaises(ValueError): validate_motion_groups(v)
        bad(lambda v: v.update(schema_version=3))
        bad(lambda v: v.update(organization_contract='recordprep-motion-organization-1'))
        bad(lambda v: v['groups'][0].update(lead_paper_id='motion:0014'))
        bad(lambda v: v['groups'][0].update(display_title='Other'))
        bad(lambda v: v['groups'][0].update(date='November 3, 2026'))
        bad(lambda v: v['groups'][0].update(date_basis='unknown'))
        bad(lambda v: v['groups'][0].update(filing_role='motion/application'))
        bad(lambda v: v['groups'][0].update(filing_party='Claimant'))
        bad(lambda v: v['inventory'][0].update(source_title=''))
        bad(lambda v: v['groups'][0]['components'][1].update(start_page=15))
        bad(lambda v: v['groups'][0]['components'][1].update(role='support'))
        bad(lambda v: v['groups'][0]['member_paper_ids'].append('motion:0014'))
        bad(lambda v: v['groups'][0]['member_paper_ids'].pop())
        def gap(v):
            v['inventory'][1]['end_page'] = 14; v['groups'][0]['components'][1]['end_page'] = 14
            v['inventory'][0]['end_page'] = 12; v['groups'][0]['components'][0]['end_page'] = 12
        bad(gap)
        named = copy.deepcopy(value)
        named['inventory'][1]['source_title'] = 'Opposition'
        first = named['groups'][0]
        first['member_paper_ids'] = first['member_paper_ids'][:1]; first['components'] = first['components'][:1]
        extra = mg.canonical_packets(named['inventory'][1:2], [['motion:0014']], [], 'a'*64)['groups'][0]
        named['groups'].insert(1, extra)
        with self.assertRaisesRegex(ValueError, 'split_continuity'): validate_motion_groups(named)

    def test_current_v2_boundaries_must_be_rebuilt_before_summaries_maps(self):
        self.papers(unnamed=True); value = self.organize(rebuild=False)
        self.assertEqual(len(mg.resolve_context(self.root)[1]), 2)  # TOC/rebuild path does not need old boundaries.
        with self.assertRaisesRegex(ValueError, 'Find boundaries'):
            sa.build_work_items(self.root, sa.ExtractionConfig('motions', ''))
        script = self.project / 'skills/recordprep-build-source-map/scripts/build_source_map.py'
        spec = importlib.util.spec_from_file_location('continuity_source_map', script)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with self.assertRaisesRegex(ValueError, 'Find boundaries'): module.boundary_documents(self.root, {})
        self.boundaries.write_text(json.dumps(mg.boundaries_from_inventory(value['inventory'])))
        self.assertEqual(len(sa.build_work_items(self.root, sa.ExtractionConfig('motions', ''))), 2)

    def test_summary_exact_members_unnamed_digest_reload_quotes_edition_and_map(self):
        self.papers(unnamed=True); value = self.organize()
        config = sa.ExtractionConfig('motions', '')
        items = sa.build_work_items(self.root, config)
        self.assertEqual(len(items), 2)
        item = items[0]
        self.assertEqual(sa.item_source_pages(item), (11, 12, 13, 14, 15))
        self.assertEqual(item.members[1]['source_title'], '')
        payload = sa.item_source_payload(item, self.root / 'text_pages', {})
        for n in range(11, 16): self.assertEqual(payload.count(f'Fictional page {n:04d}.txt'), 1)
        self.assertNotIn('0016.txt', payload)
        rows = [sa.canonicalize_extraction_candidate({'categories': [{'id': 'reasons', 'digest': {
            'text': 'The party seeks inspection to resolve a dispute.', 'evidence': [{'text': 'distinct inspection phrase',
            'file_page': 15 if i == 0 else 21}]}}]}, it, self.root / 'text_pages') for i, it in enumerate(items)]
        self.assertTrue(rows[0]['categories'][1]['digest']['evidence'][0]['verified'])
        md = sa.serialize_digest_markdown('motions', 'case', rows)
        self.assertEqual(sa.parse_digest_markdown(md, 'motions', 'case'), rows)
        sa.publish_digests(self.root, 'motions', items, config, rows)
        self.assertEqual(sa.reload_published_digest_rows(self.root, 'motions', items), rows)
        self.assertEqual(sa.load_digest_meta(self.root, 'motions')['schema_version'], 6)
        for change in (lambda r: r['members'][1].update(role='support'), lambda r: r['members'][0].update(source_title=''),
                       lambda r: r['group_metadata'].update(date='different'), lambda r: r.update(label='Borrowed title')):
            invalid = copy.deepcopy(rows[0]); change(invalid)
            self.assertTrue(sa.validate_digest_row(invalid, 'motions'))
        from recordprep.summary_editions import build_summary_edition
        headings = {it.item_id: (it.anchor_page, None) for it in items}
        sections = [sa.SynthesisSectionCandidate(it.item_id, ['The party requests inspection.']) for it in items]
        final = sa.render_final_summary('motions', 'case', rows, sections, headings)
        self.assertNotIn('Declaration', final)
        path = sa.summary_final_path(self.root, 'motions'); path.parent.mkdir(exist_ok=True); path.write_text(final)
        sa.summary_final_meta_path(self.root, 'motions').write_text(json.dumps(sa.build_final_meta(self.root, 'motions', rows, final, {}, headings)))
        edition = build_summary_edition('motions', path, self.root)
        links = [link['target_page'] for p in edition.page_map['pages'] for link in p['links']]
        self.assertIn(11, links); self.assertIn(21, links); self.assertNotIn(14, links)
        documents, pages = [], []
        for p in value['inventory']:
            group = next(g for g in value['groups'] if p['paper_id'] in g['member_paper_ids'])
            documents.append(dict(id=p['paper_id'], type='motion', start_page=p['start_page'], end_page=p['end_page'],
                motion_name=p['source_title'], motion_date=p['date'], motion_date_basis=p['date_basis'],
                motion_group_id=group['group_id'], motion_entry_title=group['display_title'],
                aliases=[p['paper_id'], group['group_id'], group['display_title']]))
            pages.extend(dict(file_page=n, document_ids=[p['paper_id']], motion_entries=[{k: group[k] for k in
                ('group_id', 'display_title', 'anchor_page', 'member_paper_ids')}]) for n in range(p['start_page'], p['end_page'] + 1))
        context = dict(value, inputs={})
        payload = dict(schema_version=2, documents=documents, pages=pages, motion_groups=context,
                       counts={'motions': 3, 'motion_entries': 2})
        self.assertIsNone(source_map_profile_metadata(payload))
        payload['counts']['motions'] = 2
        with self.assertRaises(ValueError): source_map_profile_metadata(payload)

    def test_source_stop_prior_races_failure_and_corruption_preserve_output(self):
        self.papers(); self.organize()
        path = self.root / mg.PATH; before = path.read_bytes(), path.stat().st_mtime_ns
        result, guard = org.capture(self.root)
        source = self.root / 'text_pages/0015.txt'; source.write_text(source.read_text() + 'Changed')
        with self.assertRaisesRegex(ValueError, 'changed'): org.publish(self.root, None, guard, result)
        result, guard = org.capture(self.root)
        with self.assertRaises(InterruptedError):
            org.publish(self.root, None, guard, result, check_stop=lambda: (_ for _ in ()).throw(InterruptedError()))
        with patch.object(org, '_atomic_write', side_effect=OSError('synthetic failed publication')):
            with self.assertRaises(OSError): org.publish(self.root, None, guard, result)
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
        result, guard = org.capture(self.root)
        path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'changed'): org.publish(self.root, None, guard, result)
        path.write_text('{broken')
        with self.assertRaises(ValueError): org.run_stage(self.root)
        self.assertEqual(path.read_text(), '{broken')

    def test_missing_unreadable_unsafe_selected_source_and_classification(self):
        self.papers(); self.organize()
        path = self.root / mg.PATH; before = path.read_bytes(), path.stat().st_mtime_ns
        source = self.root / 'text_pages/0015.txt'; content = source.read_bytes(); source.unlink()
        with self.assertRaises(ValueError): org.run_stage(self.root)
        source.symlink_to(self.final)
        with self.assertRaises(ValueError): org.run_stage(self.root)
        source.unlink(); source.write_bytes(content)
        original = self.final.read_bytes(); self.final.write_bytes(original + original)
        with self.assertRaisesRegex(ValueError, 'Duplicate'): org.run_stage(self.root)
        self.final.write_bytes(original)
        (self.root / 'classification/review-required').write_text('required')
        with self.assertRaisesRegex(ValueError, 'Correct classification'): org.run_stage(self.root)
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def test_concurrency_and_selection_resource_changes(self):
        self.papers(); self.organize()
        with org.lock(self.root):
            with self.assertRaisesRegex(ValueError, 'already running'): org.run_stage(self.root)
        result, guard = org.capture(self.root)
        self.final.write_text(self.final.read_text().replace('Declaration', 'Changed title'))
        with self.assertRaisesRegex(ValueError, 'changed'): org.publish(self.root, None, guard, result)
        self.organize()
        original_read = org._read
        def changed(path, *args):
            data = original_read(path, *args)
            return data + b'\n# policy change' if path.name == 'motion_pages.py' else data
        with patch.object(org, '_read', side_effect=changed): self.assertFalse(org.is_current(self.root))
        self.assertTrue(org.is_current(self.root))

    def test_checked_zero_and_unnamed_only_are_distinct_zero_call(self):
        for rows in ([page(1, kind='CT_other')], [page(1), page(2, ''), page(3)]):
            self.final.write_text('\n'.join(json.dumps(r) for r in rows) + '\n')
            marker = {'motion_checks_version': 1, 'outputs': {self.final.name: hashlib.sha256(self.final.read_bytes()).hexdigest()}}
            (self.root / 'classification/profile-advanced.json').write_text(json.dumps(marker))
            logs = []; org.run_stage(self.root, log=logs.append)
            value = mg.load(self.root)
            self.assertEqual(value['groups'], [])
            self.assertEqual(bool(value['findings']), len(rows) == 3)
            self.assertIn('fragments omitted' if len(rows) == 3 else 'Checked-zero', logs[-1])

    def test_runner_compatibility_dispatch_precedes_all_pi_resource_preflight(self):
        from test_pi_resources import _load_runner_module
        self.papers(); runner = _load_runner_module()
        with patch.object(runner, '_case_bundle', return_value=self.root), \
             patch.object(runner, '_resolve_pi_command', side_effect=AssertionError('Pi invoked')), \
             patch.object(runner, '_resource_issues', side_effect=AssertionError('resources consulted')):
            self.assertEqual(runner.main(['organize_motion_papers']), 0)
        self.assertNotIn('organize_motion_papers', runner.STAGES)
        from recordprep.pi_bundle import PI_STEP_IDS
        self.assertNotIn('organize_motion_papers', PI_STEP_IDS)

    def test_stale_missing_grouping_never_fabricates_unnamed_singleton(self):
        self.papers(unnamed=True); self.organize()
        path = self.root / mg.PATH; before = path.read_bytes(), path.stat().st_mtime_ns
        (self.root / 'text_pages/0015.txt').write_text('changed')
        inventory, groups, warning, current = mg.resolve_context(self.root, json.loads(self.boundaries.read_text()))
        self.assertIn('stale', warning); self.assertIsNone(current)
        self.assertEqual(len(groups), 2); self.assertTrue(all(p['source_title'] for p in inventory))
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
        path.unlink()
        self.assertEqual(len(sa.build_work_items(self.root, sa.ExtractionConfig('motions', ''))), 2)

    def test_historical_nonadjacent_preceding_support_names_dates_status_stay_literal(self):
        self.papers()
        bounds = json.loads(self.boundaries.read_text()); inventory = mg.inventory_from_boundaries(bounds)
        fingerprint, _ = mg.source_fingerprint(self.root, inventory)
        value = historical_artifact({'groups': [{'lead_paper_id': 'motion:0021',
            'member_paper_ids': ['motion:0011', 'motion:0021'], 'filing_role': 'motion/application',
            'date': 'Historical date', 'date_basis': 'document'}], 'coverage_status': 'incomplete'}, inventory, fingerprint)
        value['groups'][-1]['display_title'] = 'Historical saved headline'
        path = self.root / mg.PATH; path.write_text(json.dumps(value)); before = path.read_bytes(), path.stat().st_mtime_ns
        items = sa.build_work_items(self.root, sa.ExtractionConfig('motions', ''))
        item = next(i for i in items if i.item_id == 'motion:0021')
        self.assertEqual(sa.item_source_pages(item), (11, 12, 13, 21)); self.assertEqual(item.anchor_page, 21)
        self.assertIn('Historical saved headline', item.label)
        row = sa.canonicalize_extraction_candidate({}, item, self.root / 'text_pages')
        self.assertEqual(sa.parse_digest_markdown(sa.serialize_digest_markdown('motions', 'case', [row]), 'motions', 'case'), [row])
        self.assertIn('Review coverage: incomplete', mg.review_text(value))
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
        # Explicit execution alone adopts v2, after a successful guarded publication.
        org.run_stage(self.root); self.assertEqual(mg.load(self.root)['schema_version'], 2)

    def test_real_summary_runner_two_extractions_and_synthesis_then_zero_calls(self):
        self.papers(unnamed=True); self.organize()
        acceptance = pipeline.FakePiEndToEndTests(); project = acceptance._staged_project(self.base)
        fake = self.base / 'fake-pi'; fake.write_text(acceptance.FAKE_PI); fake.chmod(0o755)
        log = self.base / 'calls.log'
        result = acceptance._run_stage('create_motion_summaries', self.root, project, fake, log)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows = sa.load_digest_markdown(self.root, 'motions')
        self.assertEqual(len(rows), 2); self.assertEqual(rows[0]['members'][1]['source_title'], '')
        self.assertEqual(sa.validate_summary_agent_outputs(self.root, 'motions'), [])
        before = log.read_bytes()
        again = acceptance._run_stage('create_motion_summaries', self.root, project, fake, log)
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr); self.assertEqual(log.read_bytes(), before)

    def test_late_publication_input_prior_and_stop_races_are_guarded(self):
        self.papers(); self.organize()
        path = self.root / mg.PATH
        before = path.read_bytes(), path.stat().st_mtime_ns
        for target in ('source', 'classification', 'prior', 'stop'):
            with self.subTest(target=target):
                result, guard = org.capture(self.root)
                calls = 0
                def check():
                    nonlocal calls
                    calls += 1
                    # Fourth check is after the unique temporary output is written.
                    if calls == 4:
                        if target == 'stop': raise InterruptedError('Stopped')
                        changed = {'source': self.root / 'text_pages/0015.txt', 'classification': self.final, 'prior': path}[target]
                        changed.write_bytes(changed.read_bytes() + b'\n')
                with self.assertRaises((ValueError, InterruptedError)):
                    org.publish(self.root, None, guard, result, check_stop=check)
                if target != 'prior': self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
                else:
                    self.assertEqual(path.read_bytes(), before[0] + b'\n')
                    path.write_bytes(before[0]); os.utime(path, ns=(path.stat().st_atime_ns, before[1]))
                self.assertFalse(list((self.root / 'artifacts').glob('.motion-groups-*')))

    def test_root_replacement_and_unsafe_output_preserve_prior(self):
        import shutil
        self.papers(); self.organize()
        result, guard = org.capture(self.root)
        old = self.base / 'old-root'; self.root.rename(old); shutil.copytree(old, self.root)
        with self.assertRaisesRegex(ValueError, 'changed'): org.publish(self.root, None, guard, result)
        saved = self.root / mg.PATH; content = saved.read_bytes()
        saved.unlink(); saved.symlink_to(old / mg.PATH)
        with self.assertRaises(ValueError): org.run_stage(self.root)
        self.assertEqual((old / mg.PATH).read_bytes(), content)

    def test_model_skills_and_editorial_resources_do_not_affect_organization_identity(self):
        self.papers(); self.organize()
        original_read = org._read
        reads = []
        def tracked(path, *args):
            reads.append(str(path)); return original_read(path, *args)
        with patch.object(org, '_read', side_effect=tracked), \
             patch('recordprep.case_name_stage._model_settings', side_effect=AssertionError('model settings read')):
            self.assertTrue(org.is_current(self.root, self.base / 'nonexistent-pi-resources'))
        self.assertFalse(any('/skills/' in p or '/.pi/' in p or p.endswith('motion_guidance.py') for p in reads))

    def test_actual_atomic_replace_failure_keeps_prior_and_removes_temporary(self):
        self.papers(); self.organize()
        path = self.root / mg.PATH; before = path.read_bytes(), path.stat().st_mtime_ns
        result, guard = org.capture(self.root)
        with patch.object(org.os, 'replace', side_effect=OSError('synthetic replace failure')):
            with self.assertRaises(OSError): org.publish(self.root, None, guard, result)
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
        self.assertFalse(list((self.root / 'artifacts').glob('.motion-groups-*')))

    def test_digest_and_final_pair_rollback_remains_intact(self):
        self.papers(unnamed=True); self.organize()
        config = sa.ExtractionConfig('motions', ''); items = sa.build_work_items(self.root, config)
        rows = [sa.canonicalize_extraction_candidate({}, it, self.root / 'text_pages') for it in items]
        sa.publish_digests(self.root, 'motions', items, config, rows)
        digest, metadata = sa.summary_digest_path(self.root, 'motions'), sa.summary_digest_meta_path(self.root, 'motions')
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (digest, metadata)}
        replace = os.replace
        def fail_meta(source, destination):
            if Path(destination) == metadata: raise OSError('synthetic sidecar failure')
            return replace(source, destination)
        with patch.object(sa.os, 'replace', side_effect=fail_meta):
            with self.assertRaises(OSError): sa.publish_digests(self.root, 'motions', items, config, rows)
        self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}, before)
        final = self.root / 'artifacts/final.txt'; final_meta = final.with_suffix('.meta.json')
        final.write_text('old final'); final_meta.write_text('old metadata')
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (final, final_meta)}
        metadata = final_meta
        with patch.object(sa.os, 'replace', side_effect=fail_meta):
            with self.assertRaises(OSError): sa.publish_motion_final(final, final_meta, 'new', {})
        self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}, before)

    def test_resume_presence_and_prompt_picker_unchanged_history(self):
        from recordprep.output_presence import legacy_organization_skip, step_outputs_present
        self.assertFalse(legacy_organization_skip(self.root))
        (self.root / 'artifacts/toc.txt').write_text('MOTIONS\n')
        self.assertTrue(legacy_organization_skip(self.root)); self.assertFalse(step_outputs_present('organize_motion_papers', self.root))
        from recordprep.prompt_inspection import SUMMARY_TASKS, inspect_prompt
        self.assertNotIn('motion-organization', dict(SUMMARY_TASKS))
        for task in ('motions-extract', 'motions-synthesize'):
            text = inspect_prompt({}, task, self.project).display_text()
            self.assertIn('do not re-segment', text)
            self.assertIn('opposing positions', text)
            self.assertNotIn('remain separate entries', text)
