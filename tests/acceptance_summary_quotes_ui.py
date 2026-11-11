"""Synthetic production prompt inspector and editions; no providers or real settings.

Run in a disposable checkout/environment. QUOTE_UI_ROOT selects a new scratch folder;
QUOTE_UI_HOLD=1 holds the inspector until its window is closed. The generated bundle
can then be opened by a separately isolated, unchanged Focus for click acceptance.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
root = Path(os.environ.get('QUOTE_UI_ROOT') or tempfile.mkdtemp(prefix='recordprep-quotes-ui-'))
root.mkdir(parents=True, exist_ok=True)
for key in ('HOME', 'RECORDPREP_CONFIG_DIR', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME',
            'XDG_CACHE_HOME', 'XDG_STATE_HOME', 'PI_CODING_AGENT_DIR'):
    path = root / key.lower()
    path.mkdir(mode=0o700)
    os.environ[key] = str(path)
os.environ['PI_RUN_METRICS_ENABLED'] = '0'
os.environ['GSETTINGS_BACKEND'] = 'memory'
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, GLib
from recordprep import practice_profiles as api, summary_agents as sa
from recordprep.profile_editor_ui import ProfileEditorWindow, editable_profile
from recordprep.settings_navigation import descendants
from recordprep.paths import resource_root
from recordprep.summary_editions import build_summary_edition, publish_summary_edition
from recordprep.summary_quote_policy import EXTRACTION_QUOTE_GUIDANCE
from recordprep.quote_display import QUOTE_CASE_GUIDANCE
from recordprep.synthesis_fidelity import QUOTATION_INTEGRATION_GUIDANCE

display_repeated = 'the court finds that notice has been given as required by law'

fixture = json.loads((Path(__file__).parent / 'fixtures/summary_quote_navigation.json').read_bytes())
case = root / 'bundle'
(case / 'text_pages').mkdir(parents=True)
(case / 'case_name.txt').write_text('SyntheticQuoteCase')
for i, text in enumerate(fixture['pages'], 1):
    (case / f'text_pages/{i:04d}.txt').write_text(text)
(case / 'artifacts').mkdir()
(case / 'artifacts/hearing_boundaries.json').write_text(json.dumps([
    {'start_page': '0001', 'end_page': '0003', 'date': 'March 1, 2030'}]))
(case / 'artifacts/report_boundaries.json').write_text(json.dumps([
    {'start_page': '0001', 'end_page': '0003', 'report_name': 'Synthetic report', 'report_date': 'March 1, 2030'}]))
(case / 'artifacts/motion_boundaries.json').write_text(json.dumps([
    {'start_page': '0001', 'end_page': '0003', 'motion_name': 'Motion for supervised visits',
     'motion_date': '', 'motion_date_basis': 'unknown'}]))

# Scripted candidates go through production normalization, digest serialization,
# synthesis expansion and deterministic edition building. They are not model work.
for kind in sa.SUMMARY_KINDS:
    topic = 'request' if kind == 'motions' else sa.SUMMARY_CATEGORY_IDS[kind][0]
    item = sa.SummaryWorkItem(kind=kind, item_id=sa.SUMMARY_ITEM_PREFIXES[kind] + ':0001', ordinal=1,
                           label='March 1, 2030', start_page=1, end_page=3,
                           input_sha256='a' * 64, generation_sha256='b' * 64)
    row = sa.canonicalize_extraction_candidate({'categories': [
        {'id': topic, 'digest': {'text': 'The supervision condition remained disputed.', 'evidence': [
            {'text': fixture['distinctive'], 'file_page': 2},
            {'text': fixture['repeated_boilerplate'], 'file_page': 1}]}}]}, item, case / 'text_pages')
    bank = row['categories'][0]['digest']['evidence']
    assert all(q['verified'] for q in bank)
    markdown = sa.serialize_digest_markdown(kind, 'SyntheticQuoteCase', [row])
    sa.summary_digest_path(case, kind).parent.mkdir(exist_ok=True)
    sa.summary_digest_path(case, kind).write_text(markdown)
    restored = sa.parse_digest_markdown(markdown, kind, 'SyntheticQuoteCase')
    path = sa.summary_final_path(case, kind)
    # Find an actual paper split using normal 12-word source language, not an
    # artificially enormous anchor. No renderer/layout changes are involved.
    for padding in range(15, 40):
        paragraphs = (['The order provides for {{quote:' + bank[0]['quote_id'] + '}}.'] +
                      ['Orientation.'] * padding +
                      ['The court reviewed the disputed conditions and explained that {{quote:' + bank[1]['quote_id'] + '}}.'])
        sections, flags = sa.normalize_synthesis_sections(restored, [{'item_id': item.item_id, 'paragraphs': paragraphs,
            'quote_capitalizations': {bank[1]['quote_id']: display_repeated}}])
        assert not any(f.startswith('quote_capitalization_rejected:') for f in flags)
        text = sa.render_final_summary(kind, 'SyntheticQuoteCase', restored, sections, {item.item_id: (1, None)})
        path.write_text(text)
        edition = build_summary_edition(kind, path, case)
        fragments = [p.page for p in edition.pages if any(q.phrase == display_repeated for q in p.quotes)]
        if len(fragments) > 1:
            break
    assert len(fragments) > 1, 'Synthetic fixture must exercise an actual paper split'
    publish_summary_edition(edition, path)
    assert {q.phrase for p in edition.pages for q in p.quotes} == {fixture['distinctive'], display_repeated}
    assert bank[1]['text'] == fixture['repeated_boilerplate']

Adw.init()
app = Adw.Application(application_id='org.synthetic.RecordPrep.QuotePolicy')
app.register(None)
parent = Adw.ApplicationWindow(application=app)
snapshot = api.bundled_profile_for_identity('recordprep', api.DEFAULT_PROFILE_ID)
editor = editable_profile(snapshot)
store = api.ProfileStore('recordprep', config_root=root / 'profiles', data_root=root / 'snapshots')
w = ProfileEditorWindow(parent, editor, store, expected_head=None,
                        can_modify=lambda: True, preview=lambda _: None, on_saved=Mock())
w.set_title('Synthetic RecordPrep — quotation policy acceptance')
w.present()

def drain():
    until = time.monotonic() + .2
    while time.monotonic() < until:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.01)

def inventory():
    return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
            for directory in ('recordprep_config_dir', 'xdg_config_home', 'xdg_data_home',
                              'pi_coding_agent_dir', 'profiles', 'snapshots', 'bundle')
            for p in (root / directory).rglob('*') if p.is_file()}

drain()
before = inventory()
w._select_page('reports-topics')
explanation = next(x for x in descendants(w.pages['reports-topics'])
                   if isinstance(x, Gtk.Expander) and x.get_label() == 'About summaries')
explanation.set_expanded(True)
button = next(x for x in descendants(explanation)
              if isinstance(x, Gtk.Button) and x.get_label() == 'View full prompts…')
button.emit('clicked')
view = w.prompt_inspector
for task in ('hearings-extract', 'reports-extract', 'motions-extract',
             'hearings-synthesize', 'reports-synthesize', 'motions-synthesize'):
    view.selector.set_selected(next(i for i, (k, _) in enumerate(view.tasks) if k == task))
    view._refresh()
    drain()
    text = view.text.get_buffer().get_text(*view.text.get_buffer().get_bounds(), True)
    if task.endswith('extract'):
        assert EXTRACTION_QUOTE_GUIDANCE.strip() in text
        assert '6–12' in text and 'usually 8–10' in text
        assert 'another-model-pass trigger' in text
        assert QUOTE_CASE_GUIDANCE.strip() not in text
        assert QUOTATION_INTEGRATION_GUIDANCE.strip() not in text
    else:
        assert QUOTE_CASE_GUIDANCE.strip() in text
        assert QUOTATION_INTEGRATION_GUIDANCE.strip() in text
        assert 'sentence-case, mixed-case or lowercase quotes' in text
        assert 'For all-caps quotes, optionally' not in text
        if not task.startswith('hearings'):
            assert 'Let the quotation carry the proposition' in ' '.join(text.split())
    assert not view.status.get_text(), view.status.get_text()
    assert not view.text.get_editable()
assert inventory() == before
assert not store.registry_path.exists()
view.selector.set_selected(next(i for i, (k, _) in enumerate(view.tasks) if k == 'reports-synthesize'))
view._refresh()
print(f'PASS: production View full prompts handler, 3 extraction + 3 synthesis views, clean audit, no persistence; PID {os.getpid()}; bundle {case}', flush=True)
if os.environ.get('QUOTE_UI_HOLD') == '1':
    while view.get_visible():
        GLib.MainContext.default().iteration(True)
view.destroy()
drain()
assert inventory() == before
w.set_focus(None)
w.destroy()
parent.destroy()
drain()
print('PASS: inspector closed without Save; synthetic bytes/mtime unchanged', flush=True)
