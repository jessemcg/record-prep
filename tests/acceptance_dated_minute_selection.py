"""Production GTK activity and new review notes; synthetic/offline only.

Run in the documented disposable checkout/environment. Optional
DATED_MINUTE_ACCEPT_HOLD=1 keeps windows available for local Computer Use.
"""
import base64
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from unittest.mock import patch

TEMP = tempfile.TemporaryDirectory(prefix='recordprep-dated-minute-ui-')
BASE = Path(TEMP.name)
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
for key in ('HOME','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_STATE_HOME','XDG_CACHE_HOME',
            'RECORDPREP_CONFIG_DIR','PI_CODING_AGENT_DIR'):
    directory = BASE/key.lower()
    directory.mkdir()
    os.environ[key] = str(directory)
os.environ['PI_RUN_METRICS_ENABLED'] = '0'
os.environ.pop('RECORDPREP_PROFILE_DIR',None)

import gi
gi.require_version('Gtk','4.0')
from gi.repository import GLib
from recordprep.ui import main_window as ui
from recordprep import classification_review as review
from recordprep.transcript_layout import apply_manual_override

bundle = BASE/'Synthetic_bundle'
for folder in ('classification','text_pages','image_pages','artifacts'):
    (bundle/folder).mkdir(parents=True)
rows = [dict(file_name=f'{i:04d}.txt',page_type=kind,**({'date':value} if value is not None else {}))
        for i,(kind,value) in enumerate([
            ('CT_minute_order_first_page','March 5, 2026'),('CT_minute_order',None),
            ('CT_minute_order_first_page',''),('CT_minute_order',None),
            ('CT_minute_order_first_page','March 5, 2026'),('CT_minute_order_first_page','Date unresolved')],1)]
name_input = bundle/'classification/CT_basic_advanced_dates_names.jsonl'
name_input.write_text(''.join(json.dumps(row)+'\n' for row in rows))
image = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aY4sAAAAASUVORK5CYII=')
for row in rows:
    (bundle/'text_pages'/row['file_name']).write_text('Fictional minute-selection acceptance source')
    (bundle/'image_pages'/(row['file_name'][:-4]+'.png')).write_bytes(image)
apply_manual_override(bundle,mode='ct_only')
watched = [name_input,*list((bundle/'text_pages').iterdir()),*list((bundle/'image_pages').iterdir())]
before = {p:(p.read_bytes(),p.stat().st_mtime_ns) for p in watched}
workspace = BASE/'workspace'
(workspace/'.pi/skills'/review.SKILL).mkdir(parents=True,mode=0o700)
shutil.copyfile(PROJECT/'.pi/skills'/review.SKILL/'SKILL.md',workspace/'.pi/skills'/review.SKILL/'SKILL.md')
guard,ref,candidate,spec,_ = review.stage_inputs(bundle,PROJECT/'.pi',workspace)
access = json.loads(spec.read_text())
Path(access['journal']).write_text(''.join(json.dumps(p)+'\n' for p in access['reads']))
candidate.write_text(json.dumps(dict(schema_version=1,reviewed_blocks=['block-0001'],changes=[],unresolved=[])))
assert review.publish(bundle,PROJECT/'.pi',guard,ref,candidate) == (0,0)
receipt = bundle/review.RECEIPT
receipt_before = receipt.read_bytes(),receipt.stat().st_mtime_ns
app = ui.RecordPrepApp()
app.set_application_id('org.synthetic.RecordPrepDatedMinutes')
errors = []


def drain():
    end = time.monotonic()+.3
    while time.monotonic()<end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.005)


def check():
    try:
        owner = app.get_active_window()
        owner.set_title('Synthetic RecordPrep — dated minute selection')
        owner._resolve_case_root = lambda:bundle
        owner.selected_pdfs = []
        owner._open_phase_for_step('build_toc')
        for method in ('_run_step_six','_run_step_seven'):
            assert getattr(owner,method)(),method
        boundaries = json.loads((bundle/'artifacts/minutes_boundaries.json').read_text())
        assert len(boundaries)==2
        # Explicit filtering, not opening/loading, removes old undated entries.
        (bundle/'artifacts/minutes_boundaries.json').write_text(json.dumps(boundaries+[
            dict(start_page='0003',end_page='0004',date=''),dict(start_page='0006',end_page='0006',date='TBD')]))
        assert owner._run_step_correct_boundaries()
        assert json.loads((bundle/'artifacts/minutes_boundaries.json').read_text())==boundaries
        drain()
        if owner._activity_terminal is not None:
            activity = owner._activity_terminal.get_text_format(ui.Vte.Format.TEXT)
        else:
            activity = owner._log_buffer.get_text(*owner._log_buffer.get_bounds(),True)
        for expected in ('2 minute candidates omitted','0003–0004','0006–0006',
                         'missing dates do not prove misclassification','2 minute entries without recognized dates'):
            assert expected in activity,expected
        owner._refresh_classification_review_result()
        assert '2 review notes' in owner.step_classification_agent_row.get_subtitle()
        dialogs = []
        constructor = ui.ClassificationReviewWindow
        def open_review(*args):
            dialog = constructor(*args)
            dialogs.append(dialog)
            return dialog
        with patch.object(ui,'ClassificationReviewWindow',side_effect=open_review):
            owner._classification_review_button.emit('clicked')
        drain()
        dialog = dialogs[0]
        dialog.set_title('Synthetic dated-minute classification review')
        assert not dialog.text_view.get_editable()
        buffer = dialog.text_view.get_buffer()
        text = buffer.get_text(*buffer.get_bounds(),True)
        assert [note['code'] for note in review.saved_review(bundle)['review']['warnings']] == ['minute_date_unresolved']*2
        for expected in ('0003–0004','0006–0006',
                         'will be omitted when downstream selections are rebuilt'):
            assert expected in text,expected
        assert before=={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in watched}
        assert (receipt.read_bytes(),receipt.stat().st_mtime_ns)==receipt_before
        print('DATED MINUTE SELECTION GTK ACCEPTANCE PASSED',flush=True)
        if os.environ.get('DATED_MINUTE_ACCEPT_HOLD'):
            GLib.timeout_add_seconds(180,lambda:(dialog.close(),app.quit(),False)[2])
        else:
            dialog.close()
            app.quit()
    except Exception as exc:
        import traceback
        traceback.print_exc()
        errors.append(exc)
        app.quit()
    return False


app.connect('activate',lambda *_:GLib.idle_add(check))
app.run([])
TEMP.cleanup()
if errors:
    raise SystemExit(1)
