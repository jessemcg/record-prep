"""Actual GTK window: no-op layout and blocked Resume preserve a synthetic bundle."""
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory(prefix='recordprep-resume-ui-') as temporary:
    base = Path(temporary)
    for key in ('HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_STATE_HOME'):
        path = base / key.lower()
        path.mkdir()
        os.environ[key] = str(path)
    from recordprep.ui import main_window as ui
    from recordprep.transcript_layout import apply_manual_override
    from gi.repository import GLib
    ui.CONFIG_FILE = base / 'application.json'
    root = base / 'case_bundle'
    for directory in ('text_pages', 'image_pages', 'classification'):
        (root / directory).mkdir(parents=True)
    for number in (1, 2):
        (root / f'text_pages/{number:04d}.txt').write_text('Synthetic court record page')
        (root / f'image_pages/{number:04d}.png').write_bytes(b'synthetic image')
    apply_manual_override(root, mode='split', rt_end_file_page=1)
    (root / 'classification/CT_basic.jsonl').write_text('{"file_name":"0002.txt","page_type":"CT_other"}\n')
    ui.CONFIG_FILE.write_text(json.dumps({'case_root_dir':str(base), 'selected_pdfs':[]}))
    def snapshot():
        return {str(p.relative_to(root)):(p.read_bytes(),p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
    before = snapshot()
    app = ui.RecordPrepApp()
    app.set_application_id('org.synthetic.RecordPrepResumeSafety')
    errors = []
    def run():
        try:
            owner = app.get_active_window()
            owner.set_title('Synthetic RecordPrep — Resume safety')
            assert owner._resolve_case_root() == root
            owner._rt_ct_split_mode_pending = 'split'
            owner._rt_ct_split_pending = 1
            assert owner._try_apply_manual_layout()
            assert snapshot() == before
            owner._rt_ct_split_mode_pending = 'ct_only'
            assert not owner._try_apply_manual_layout()
            assert snapshot() == before
            owner._bundle_reset_required = True
            with patch.object(ui.threading, 'Thread', side_effect=AssertionError('Blocked Resume must not launch work')):
                owner.on_resume_clicked(owner.resume_button)
            assert not owner._pipeline_running
            assert snapshot() == before
            for row in (owner.step_correct_toc_row, owner.step_correct_boundaries_row):
                owner._finish_step(row, 'Already complete')
                label = owner._step_status_labels[row]
                assert label.get_text() == 'Already complete'
                assert label.get_tooltip_text() == 'Already complete'
                assert owner._step_status_values[owner._step_ids_by_row[row]] == 'Already complete'
                owner._finish_step(row, 'Skipped')
                assert label.get_text() == 'Skipped'
            assert snapshot() == before
            print('Actual GTK Resume/layout safety and completion labels passed; synthetic bundle unchanged.')
        except BaseException as exc:
            errors.append(exc)
        finally:
            app.quit()
        return False
    GLib.timeout_add(600, run)
    app.run([])
    if errors:
        raise errors[0]
