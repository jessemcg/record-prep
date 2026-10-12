"""Exercise the real main window with only isolated synthetic profile/case state."""
from __future__ import annotations
import importlib
import os
from pathlib import Path
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
PACKAGE = "recordprep" if (HERE / "recordprep").exists() else "focus"
TEMP = tempfile.TemporaryDirectory(prefix=f"{PACKAGE}-main-profile-")
ROOT = Path(TEMP.name)
for key, directory in (("HOME", "home"), ("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"), ("XDG_CACHE_HOME", "cache")):
    path = ROOT / directory
    path.mkdir()
    os.environ[key] = str(path)
os.environ["FOCUS_CONFIG_DIR"] = str(ROOT / "focus-config")
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, GLib
api = importlib.import_module(PACKAGE + ".practice_profiles")
adapter = importlib.import_module(PACKAGE + ".profile_integration")
from importlib import import_module
ProfileEditor = import_module(PACKAGE + ".profile_workflows").ProfileEditor
bundle = ROOT / "bundle"
bundle.mkdir()
(bundle / "text_pages").mkdir()
(bundle / "text_pages/0001.txt").write_text("Synthetic main-window record page.")
if PACKAGE == "recordprep":
    module = import_module("recordprep.ui.main_window")
    module.CONFIG_FILE = ROOT / "recordprep-config.json"
    app = module.RecordPrepApp()
else:
    module = import_module("focus.app")
    app = module.Focus(input_override=bundle)
app.set_application_id("org.synthetic.MainProfiles." + PACKAGE)
errors = []

def drain():
    until = time.monotonic() + .35
    while time.monotonic() < until:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.01)

def run():
    try:
        window = app.get_active_window()
        owner = window if PACKAGE == "recordprep" else app
        window.set_title("Synthetic main-window profile acceptance — " + PACKAGE)
        baseline = api.default_profile_candidate()
        draft = ProfileEditor.create(baseline, "Synthetic long specialty for multi-party proceedings with complete source-record preparation and research").snapshot()
        store = api.profile_store()
        ref = store.accept_profile(draft, expected_previous_digest=None)
        if PACKAGE == "recordprep":
            owner._resolve_case_root = lambda: bundle
            import_module("recordprep.case_profiles").apply_case_profile(bundle, ref, expected_previous=None)
        else:
            import_module("focus.research_selection").apply_selection(bundle, ref, expected_previous=None)
        adapter.update_indicator(owner)
        label = owner._practice_profile_label
        assert label.get_wrap() and label.get_ellipsize() == 0
        assert draft.manifest["display_name"] in label.get_text()
        for width in (480, 640, 820):
            window.unmaximize()
            window.set_default_size(width, 760)
            drain()
            control = owner._practice_profile_button
            assert control.measure(Gtk.Orientation.HORIZONTAL, -1)[0] <= width
            assert label.get_width() <= window.get_width()
            assert label.get_height() >= label.get_layout().get_pixel_size()[1]
        # A malformed private store fails visibly, without a hidden partial chooser or repair.
        registry_before = store.registry_path.read_bytes()
        store.registry_path.write_bytes(b"{}")
        try:
            assert (adapter.open_manager(owner, HERE) if PACKAGE == "recordprep"
                    else adapter.open_manager(owner)) is None
            drain()
            dialogs = [item for item in Gtk.Window.list_toplevels()
                       if hasattr(item, "get_heading") and item.get_heading() == "Profile settings unavailable"]
            assert len(dialogs) == 1
            assert not any(item.get_visible() and item.get_title() == "Choose profile"
                           for item in Gtk.Window.list_toplevels())
            assert store.registry_path.read_bytes() == b"{}"
            dialogs[0].response("close")
            drain()
        finally:
            store.registry_path.write_bytes(registry_before)
        print("REAL MAIN-WINDOW PROFILE ACCEPTANCE PASSED", PACKAGE, flush=True)
        if not os.environ.get("PROFILE_ACCEPT_HOLD"):
            app.quit()
    except Exception as exc:
        import traceback
        traceback.print_exc()
        errors.append(exc)
        app.quit()
    return False
GLib.timeout_add(350, run)
app.run([])
TEMP.cleanup()
if errors:
    raise SystemExit(1)
