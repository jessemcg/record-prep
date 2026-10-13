"""Real GTK case-notice regression; disposable profiles, no case/model access."""
import importlib
from dataclasses import asdict
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
package = "focus" if (HERE / "focus").is_dir() else "recordprep"
TEMP = tempfile.TemporaryDirectory(prefix="profile-case-notice-")
ROOT = Path(TEMP.name)
for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
    directory = ROOT / key.lower()
    directory.mkdir()
    os.environ[key] = str(directory)

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib

api = importlib.import_module(package + ".practice_profiles")
manager_ui = importlib.import_module(package + ".profile_manager_ui")
Adw.init()
app = Adw.Application(application_id="org.synthetic.ProfileCaseNotice")
app.register(None)
parent = Adw.ApplicationWindow(application=app, title="Synthetic profile case notice")
store = api.ProfileStore(package, config_root=ROOT / "config", data_root=ROOT / "data")


def drain():
    until = time.monotonic() + .2
    while time.monotonic() < until:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.01)


with patch.object(api, "profile_store", return_value=store):
    manager = manager_ui.ProfileManagerWindow(parent, can_modify=lambda: True,
        preview=lambda snapshot: None, on_select=lambda ref: None,
        allow_legacy=False, has_case=False)
    assert manager._select()
    pending = manager.selected_ref
    assert store.read_registry()["default"] == (asdict(pending) if package == "recordprep" else None)
    editor = manager._edit()
    drain()
    assert not editor.case_notice.get_visible()
    resource = "research" if package == "focus" else "classification"
    editor.editor.resources[resource] += "\nSynthetic new-case settings.\n"
    editor._save()
    drain()
    assert editor.editor.base.ref != pending
    assert manager.selected_ref == editor.editor.base.ref
    # Focus retains its existing General/default switch semantics on Save;
    # RecordPrep advances the default remembered by its explicit selection.
    assert store.read_registry()["default"] == asdict(editor.editor.base.ref)
    assert not hasattr(manager, "apply_dialog")
    assert not editor.case_notice.get_visible() and not editor.case_notice.get_text()
    editor.close()
    editor = manager._edit()
    drain()
    assert not editor.case_notice.get_visible() and not editor.case_notice.get_text()
    # Only a real case retaining an earlier revision should get the warning.
    manager.selected_ref = pending
    manager.has_case = True
    editor.refresh_case_notice()
    assert editor.case_notice.get_visible()
    assert "This case uses earlier settings" in editor.case_notice.get_text()
    manager.has_case = False
    editor.refresh_case_notice()
    assert not editor.case_notice.get_visible() and not editor.case_notice.get_text()
    # Selecting another specialty for an existing case leaves the default alone.
    remembered_default = store.read_registry()["default"]
    case_choices = []
    bound = manager_ui.ProfileManagerWindow(parent, can_modify=lambda: True,
        preview=lambda snapshot: None, on_select=case_choices.append, allow_legacy=False, has_case=True)
    bound.selector.set_selected(1, notify=False)
    assert bound._select() and case_choices[-1] == bound.selected_ref
    assert bound.selected_ref.specialty_id != remembered_default["specialty_id"]
    assert store.read_registry()["default"] == remembered_default
    # Failed or work-blocked choices cannot replace the remembered default.
    before_failure = store.registry_path.read_bytes()
    allowed = [True]
    def fail_preview(_snapshot):
        raise ValueError("Synthetic preview rejection")
    failed = manager_ui.ProfileManagerWindow(parent, can_modify=lambda: allowed[0],
        preview=fail_preview, on_select=lambda ref: None, allow_legacy=False, has_case=False)
    failed.selector.set_selected(1, notify=False)
    assert not failed._select()
    assert store.registry_path.read_bytes() == before_failure
    allowed[0] = False
    assert not failed._select()
    assert store.registry_path.read_bytes() == before_failure
    print(f"{package}: PROFILE CASE NOTICE GTK ACCEPTANCE PASSED", flush=True)
    if os.environ.get("PROFILE_CASE_NOTICE_HOLD"):
        loop = GLib.MainLoop()
        editor.connect("close-request", lambda *_args: (loop.quit(), False)[1])
        loop.run()
    editor.close()
parent.close()
TEMP.cleanup()
