"""Produce a wholly synthetic bundle for Focus/tests/acceptance_motions.py.

Run in RecordPrep's disposable environment. Prints the temporary bundle path.
No provider, private configuration, profile store or maintained app is used.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

root = Path(tempfile.mkdtemp(prefix='recordprep-motions-acceptance-'))
for name in ('HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME'):
    path = root / name.lower(); path.mkdir(mode=0o700); os.environ[name] = str(path)
os.environ['PI_RUN_METRICS_ENABLED'] = '0'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recordprep.motion_pages import build_motion_boundaries
from recordprep import summary_agents as sa
from recordprep.summary_editions import build_summary_edition, publish_summary_edition, summary_edition_output_paths
from recordprep.transcript_layout import apply_manual_override

bundle = root / 'synthetic'; text = bundle / 'text_pages'; text.mkdir(parents=True)
artifacts = bundle / 'artifacts'; artifacts.mkdir()
summaries = bundle / 'summaries'; summaries.mkdir()
(bundle / '.motion-acceptance-fixture').write_text('synthetic-disposable-motion-fixture-v1\n')
(bundle / 'case_name.txt').write_text('Fictional Motion Acceptance')
rows = []
grouped = '--grouped' in sys.argv
if grouped:
    titles = {1: 'Supporting Declaration', 3: 'Opposition to Inspection', 5: 'Motion to Compel Inspection',
              7: 'Supporting Memorandum', 9: 'Reply on Inspection'}
else:
    titles = {1: 'Motion for Protective Order', 3: 'Opposition to Motion for Protective Order', 5: 'Reply in Support of Motion'}
bodies = {1: "This declaration expressly supports Owner's motion to compel inspection of the leased premises.",
          3: 'Respondent opposes inspection, asserting that the request exceeds the agreement.',
          5: 'Owner moves to compel inspection because access is needed to document the condition of the leased premises.',
          7: "This memorandum expressly supports Owner's motion to compel inspection to document the disputed condition.",
          9: 'Owner replies in support of inspection and disputes Respondent\'s interpretation of the agreement.'}
for page in range(1, 11 if grouped else 7):
    body = bodies[max(n for n in bodies if n <= page)] if grouped else 'The author seeks a protective order.'
    (text / f'{page:04d}.txt').write_text(f'Fictional source page {page}. {body}\n' +
        ('The supporting memorandum uses a distinct inspection phrase.\n' if grouped and page == 8 else ''))
    rows.append({'file_name': f'{page:04d}.txt', 'page_type': 'CT_motion_first_page' if page in titles else 'CT_motion',
                 'motion_first_page': 'yes' if page in titles else 'no',
                 **({'name': titles[page], 'date': 'November 1, 2026', 'date_basis': 'filed'} if page in titles else {})})
if grouped:
    classification = bundle / 'classification'; classification.mkdir()
    (classification / 'CT_basic_advanced_corrected_dates_names.jsonl').write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
bounds = build_motion_boundaries(rows, 0)
(artifacts / 'motion_boundaries.json').write_text(json.dumps(bounds))
if grouped:
    from recordprep import motion_groups as mg
    inventory = mg.inventory_from_boundaries(bounds)
    value = mg.normalize_candidate({'groups': [
        {'lead_paper_id': 'motion:0005', 'member_paper_ids': ['motion:0001', 'motion:0005', 'motion:0007'],
         'filing_role': 'motion/application', 'display_title': 'Motion to compel inspection', 'filing_party': 'Owner',
         'purpose': 'Compel inspection', 'evidence': 'Fictional express relationship.'},
        {'lead_paper_id': 'motion:0003', 'member_paper_ids': ['motion:0003'], 'filing_role': 'opposition',
         'display_title': 'Opposition to inspection', 'filing_party': 'Respondent', 'relationship_to': 'motion:0005', 'evidence': 'Express response.'},
        {'lead_paper_id': 'motion:0009', 'member_paper_ids': ['motion:0009'], 'filing_role': 'reply',
         'display_title': 'Reply on inspection', 'filing_party': 'Owner', 'relationship_to': 'motion:0005', 'evidence': 'Express reply.'}],
         'coverage_status': 'complete'}, inventory, mg.source_fingerprint(bundle, inventory)[0])
    (bundle / mg.PATH).write_text(json.dumps(value))
for kind in ('hearing', 'report', 'minutes'):
    (artifacts / f'{kind}_boundaries.json').write_text('[]')
apply_manual_override(bundle, mode='ct_only')
toc_rows = [f"\t{g['display_title']} {g['anchor_page']}" for g in value['groups']] if grouped else [f"\t{r['motion_name']} {r['start_page']}" for r in bounds]
(artifacts / 'toc.txt').write_text('FORMS\nHEARINGS\nREPORTS\nMOTIONS\n' + '\n'.join(toc_rows) + '\nMINUTE ORDERS\nEMPTY CUSTOM\n')
config = sa.ExtractionConfig('motions', sa.default_guidance('motions', 'extract'))
items = sa.build_work_items(bundle, config)
requests = {'motion:0003': 'Respondent opposes inspection.', 'motion:0005': 'Owner requests inspection of the leased premises.',
            'motion:0009': 'Owner maintains the inspection request in reply.'}
digests = [sa.canonicalize_extraction_candidate({'categories': [
    {'id': config.definitions[0].identifier, 'digest': {'text': requests[item.item_id] if grouped else 'The author requests a protective order.'}},
    *([{'id': 'reasons', 'digest': {'text': 'The supporting memorandum supplies the reason.',
        'evidence': [{'text': 'distinct inspection phrase', 'file_page': 8}]}}] if grouped and item.item_id == 'motion:0005' else [])]},
    item, text) for item in items]
sections, flags = sa.normalize_synthesis_sections(digests, [
    {'item_id': item.item_id, 'paragraphs': ['The owner seeks inspection based on {{quote:motion:0005/reasons/1}}; no ruling is established.'
        if grouped and item.item_id == 'motion:0005' else requests[item.item_id] if grouped else 'The author requests a protective order; no ruling is established by this paper.']}
    for item in items])
heading_pages = {item.item_id: (item.anchor_page or item.start_page, None) for item in items}
final_text = sa.render_final_summary('motions', 'Fictional Motion Acceptance', digests, sections, heading_pages)
final = sa.summary_final_path(bundle, 'motions'); final.write_text(final_text)
metadata = sa.build_final_meta(bundle, 'motions', digests, final_text, {}, heading_pages)
sa.summary_final_meta_path(bundle, 'motions').write_text(json.dumps(metadata))
publish_summary_edition(build_summary_edition('motions', final, bundle), final)
for kind in ('hearings', 'reports', 'minutes'):
    path = sa.summary_final_path(bundle, kind)
    if kind == 'minutes':
        from recordprep.minute_summaries import render_final
        path.write_text(render_final(bundle, [], []))
    else:
        path.write_text(sa.render_final_summary(kind, 'Fictional Motion Acceptance', [], [], {}))
    path.with_suffix('.meta.json').write_text(json.dumps({
        'artifact': 'recordprep-summary-final-meta', 'schema_version': 3, 'kind': kind,
        'item_ids': [], 'final_text_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}))
transcript = {'schema_version': 2, 'entries': [dict(row, file_page=i, record_type='CT', citation_label=f'CT {i}')
                                            for i, row in enumerate(rows, 1)], 'citation_series': []}
(artifacts / 'transcript_page_numbers.json').write_text(json.dumps(transcript))
(artifacts / 'case_overview.md').write_text('---\nartifact: recordprep-case-overview\nschema_version: 1\n'
    'status: nonauthoritative-orientation\n---\n# Case Overview\n> Orientation aid only. Verify source pages.\n')
pdf_path, pages_path = summary_edition_output_paths(final)
(bundle / 'manifest.json').write_text(json.dumps({'schema_version': 2, 'files': {
    **{f'summarized_{kind}': str(sa.summary_final_path(bundle, kind).relative_to(bundle))
       for kind in ('hearings', 'reports', 'motions', 'minutes')},
    'summarized_motions_pdf': str(pdf_path.relative_to(bundle)),
    'summarized_motions_pages': str(pages_path.relative_to(bundle))}}))
script = Path(__file__).resolve().parents[1] / '.pi/skills/recordprep-build-source-map/scripts/build_source_map.py'
spec = importlib.util.spec_from_file_location('acceptance_motion_map', script)
builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
source_map, manifest = builder.build_source_map(bundle)
assert source_map['counts']['motions'] == (5 if grouped else 3)
assert [d['id'] for d in source_map['documents']] == [f'motion:{n:04d}' for n in sorted(titles)]
if grouped:
    assert source_map['counts']['motion_entries'] == 3
    support = next(d for d in source_map['documents'] if d['id'] == 'motion:0007')
    assert support['motion_group_id'] == 'motion:0005' and 'Motion to compel inspection' in support['aliases']
    assert len(source_map['documents']) == 5
    from recordprep.profile_artifacts import source_map_profile_metadata
    source_map_profile_metadata(source_map)
    assert manifest['files']['motion_groups'] == 'artifacts/motion_groups.json'
assert all(d['motion_date_basis'] == 'filed' for d in source_map['documents'])
(artifacts / 'source_map.json').write_text(json.dumps(source_map))
(bundle / 'manifest.json').write_text(json.dumps(manifest))
print(bundle, flush=True)
