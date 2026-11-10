"""Build a fictional schema-2 bundle; only temporary sources and scripted summaries."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recordprep import motion_groups as mg, motion_organization as org, summary_agents as sa
from recordprep.motion_pages import build_motion_boundaries
from recordprep.summary_editions import build_summary_edition, publish_summary_edition, summary_edition_output_paths
from recordprep.transcript_layout import apply_manual_override
from recordprep.profile_artifacts import source_map_profile_metadata


def build():
    base = Path(tempfile.mkdtemp(prefix='recordprep-continuity-'))
    for key in ('HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'PI_CODING_AGENT_DIR'):
        directory = base / key.lower(); directory.mkdir(mode=0o700); os.environ[key] = str(directory)
    os.environ['PI_RUN_METRICS_ENABLED'] = '0'
    bundle = base / 'synthetic'; bundle.mkdir()
    for name in ('text_pages', 'artifacts', 'classification', 'summaries'): (bundle / name).mkdir()
    (bundle / '.continuous-motion-fixture').write_text('fictional-only\n')
    (bundle / 'case_name.txt').write_text('Fictional Continuity Acceptance')
    rows = []
    for n in range(1, 23):
        title = {11: 'Request to Change Fictional Order', 14: '', 21: 'Separate Named Motion'}.get(n)
        kind = ('CT_motion_first_page' if n in (11, 14, 21) else 'CT_motion' if n in (12, 13, 15, 17, 18) else 'CT_other')
        if n == 16: kind = 'CT_report'
        row = dict(file_name=f'{n:04d}.txt', page_type=kind)
        if kind.startswith('CT_motion'): row['motion_first_page'] = 'yes' if title is not None else 'no'
        if title is not None: row.update(name=title, date='', date_basis='unknown')
        rows.append(row)
        (bundle / 'text_pages' / row['file_name']).write_text(
            f'Fictional source page {n}. The claimant seeks inspection. The owner opposes disclosure of private details. '
            + ('A distinct inspection phrase anchors the stated reasons.\n' if n in (15, 21) else '\n'))
    (bundle / 'classification/CT_basic_advanced_corrected_dates_names.jsonl').write_text('\n'.join(json.dumps(r) for r in rows) + '\n')
    (bundle / 'artifacts/motion_boundaries.json').write_text(json.dumps(build_motion_boundaries(rows, -1)))
    for kind in ('hearing', 'report', 'minutes'): (bundle / f'artifacts/{kind}_boundaries.json').write_text('[]')
    (bundle / 'manifest.json').write_text('{"schema_version":2,"files":{}}')
    apply_manual_override(bundle, mode='ct_only')
    org.run_stage(bundle)
    inventory, groups, _, _ = mg.resolve_context(bundle)
    (bundle / 'artifacts/motion_boundaries.json').write_text(json.dumps(mg.boundaries_from_inventory(inventory)))
    (bundle / 'artifacts/toc.txt').write_text('FORMS\nHEARINGS\nREPORTS\nMOTIONS\n' + '\n'.join(
        f"\t{g['display_title']} {g['anchor_page']}" for g in groups) + '\nMINUTE ORDERS\n')
    publish_summaries_and_map(bundle, rows)
    return bundle


def publish_summaries_and_map(bundle, rows=None):
    if rows is None:
        rows = [json.loads(line) for line in (bundle / 'classification/CT_basic_advanced_corrected_dates_names.jsonl').read_text().splitlines()]
    config = sa.ExtractionConfig('motions', '')
    items = sa.build_work_items(bundle, config)
    assert [sa.item_source_pages(it) for it in items] == [(11, 12, 13, 14, 15), (21,)]
    digests = [sa.canonicalize_extraction_candidate({'categories': [
        {'id': 'request', 'digest': {'text': 'The claimant requests inspection; the owner opposes disclosure of private details.'}},
        {'id': 'reasons', 'digest': {'text': 'The papers state differing grounds.', 'evidence': [
            {'text': 'distinct inspection phrase', 'file_page': 15 if i == 0 else 21}]}}]}, it, bundle / 'text_pages') for i, it in enumerate(items)]
    sa.publish_digests(bundle, 'motions', items, config, digests)
    digests = sa.reload_published_digest_rows(bundle, 'motions', items)
    sections = [sa.SynthesisSectionCandidate(it.item_id, [
        'The claimant requests inspection; the owner opposes disclosure of private details, citing {{quote:' + it.item_id + '/reasons/1}}.']) for it in items]
    targets = {it.item_id: (it.anchor_page, None) for it in items}
    final = sa.summary_final_path(bundle, 'motions')
    final.write_text(sa.render_final_summary('motions', 'Fictional Continuity Acceptance', digests, sections, targets))
    sa.summary_final_meta_path(bundle, 'motions').write_text(json.dumps(sa.build_final_meta(bundle, 'motions', digests, final.read_text(), {}, targets)))
    publish_summary_edition(build_summary_edition('motions', final, bundle), final)
    for kind in ('hearings', 'reports', 'minutes'):
        path = sa.summary_final_path(bundle, kind)
        path.write_text('Minute Orders Summary\n' if kind == 'minutes' else sa.render_final_summary(kind, 'Fictional Continuity Acceptance', [], [], {}))
        path.with_suffix('.meta.json').write_text(json.dumps(dict(artifact='recordprep-summary-final-meta', schema_version=3,
            kind=kind, item_ids=[], final_text_sha256=hashlib.sha256(path.read_bytes()).hexdigest())))
    (bundle / 'artifacts/transcript_page_numbers.json').write_text(json.dumps(dict(schema_version=2, citation_series=[], entries=[
        dict(r, file_page=int(Path(r['file_name']).stem), record_type='CT', citation_label=f"CT {int(Path(r['file_name']).stem)}") for r in rows])))
    (bundle / 'artifacts/case_overview.md').write_text('---\nartifact: recordprep-case-overview\nschema_version: 1\nstatus: nonauthoritative-orientation\n---\n# Case Overview\n> Orientation aid only. Verify source pages.\n')
    pdf, pages = summary_edition_output_paths(final)
    manifest = json.loads((bundle / 'manifest.json').read_text())
    manifest['files'] = {**manifest.get('files', {}), **{f'summarized_{k}': str(sa.summary_final_path(bundle, k).relative_to(bundle)) for k in ('hearings', 'reports', 'motions', 'minutes')},
                         'summarized_motions_pdf': str(pdf.relative_to(bundle)), 'summarized_motions_pages': str(pages.relative_to(bundle))}
    (bundle / 'manifest.json').write_text(json.dumps(manifest))
    script = Path(__file__).resolve().parents[1] / '.pi/skills/recordprep-build-source-map/scripts/build_source_map.py'
    spec = importlib.util.spec_from_file_location('continuous_acceptance_map', script)
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    source_map, manifest = builder.build_source_map(bundle)
    source_map_profile_metadata(source_map)
    assert source_map['counts']['motions'] == 3 and source_map['counts']['motion_entries'] == 2
    assert source_map['documents'][1]['motion_name'] == ''
    (bundle / 'artifacts/source_map.json').write_text(json.dumps(source_map))
    (bundle / 'manifest.json').write_text(json.dumps(manifest))


if __name__ == '__main__': print(build(), flush=True)
