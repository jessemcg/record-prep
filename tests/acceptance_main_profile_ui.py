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
        title = owner._title_widget
        assert not hasattr(owner, "_practice_profile_button")
        assert title.get_subtitle() == draft.manifest["display_name"]
        for width in (480, 640, 820):
            window.unmaximize()
            window.set_default_size(width, 760)
            drain()
            assert title.get_width() <= window.get_width()
        menu = owner.menu_button if PACKAGE == "recordprep" else owner._profile_menu_button
        menu.popup()
        drain()
        controls = owner._practice_profiles_window
        assert not isinstance(controls, Gtk.Window)
        assert controls.get_ancestor(Gtk.Popover) is menu.get_popover()
        assert controls._selected().snapshot.ref.specialty_id == ref.specialty_id
        def descendants(widget):
            yield widget
            child = widget.get_first_child()
            while child is not None:
                yield from descendants(child)
                child = child.get_next_sibling()
        settings_label = next(item for item in descendants(menu.get_popover())
                              if isinstance(item, Gtk.Label) and item.get_text() == "Model settings")
        def left(widget):
            valid, bounds = widget.compute_bounds(menu.get_popover())
            assert valid
            return bounds.get_x()
        assert abs(left(controls.settings_button.get_child()) - left(settings_label)) <= 1
        assert abs(left(controls.selector.label) - left(settings_label)) <= 1
        controls.selector.popup()
        drain()
        assert controls.selector.popover.get_visible()
        assert menu.get_popover().get_visible()
        controls.selector._choose(next(i for i, item in enumerate(controls.options)
                                      if item and item.snapshot.ref.specialty_id == "general-court-record"))
        drain()
        assert menu.get_popover().get_visible()
        assert not hasattr(controls, "select_button")
        assert controls.settings_button.get_child().get_xalign() == 0
        assert controls.selector.label.get_xalign() == 0
        assert "weight normal" in controls.settings_button.get_child().get_attributes().to_string()
        assert "weight normal" in controls.selector.label.get_attributes().to_string()
        assert title.get_subtitle() == "General Court Record"
        assert controls.selector.names[controls.selector.get_selected()].endswith("✓")
        # A failed immediate choice keeps the real current selection/checkmark.
        from unittest.mock import patch
        current_index = controls.selector.get_selected()
        other_index = next(i for i, item in enumerate(controls.options)
                           if item and item.snapshot.ref.specialty_id == "california-juvenile-dependency")
        with patch.object(controls, "on_select", side_effect=ValueError("synthetic case change")):
            controls.selector._choose(other_index)
        assert controls.selector.get_selected() == current_index
        assert title.get_subtitle() == "General Court Record"
        assert "could not be selected" in controls.message.get_text()
        editor = controls._edit()
        drain()
        assert editor.get_visible() and not editor.get_modal()
        assert editor.get_transient_for() is None
        editor.maximize()
        drain()
        assert editor.is_maximized()
        editor.unmaximize()
        drain()
        editor.close()
        menu.popdown()
        # Reopening binds fresh controls to the current case selection.
        menu.popup()
        drain()
        assert owner._practice_profiles_window is not controls
        assert owner._practice_profiles_window._selected().snapshot.ref.specialty_id == "general-court-record"
        menu.popdown()
        # Model settings retains its existing action contract; no discovery/save.
        settings_module = module if PACKAGE == "recordprep" else import_module("focus.ui.settings")
        settings_class = settings_module.SettingsWindow if PACKAGE == "recordprep" else settings_module.AiSettingsWindow
        with patch.object(settings_class, "_load_pi_models"), \
             patch.object(settings_module, "current_project_pi_model", return_value=None), \
             patch.object(settings_module, "current_project_pi_thinking_level", return_value=None):
            if PACKAGE == "recordprep":
                owner.on_settings(None, None)
                model_window = owner._settings_window
            else:
                owner._on_open_ai_settings(None, None)
                model_window = owner._ai_settings_window
            drain()
            assert model_window.get_title() == "Model settings"
            assert any(isinstance(w, Gtk.Label) and w.get_text() == "Model settings" for w in descendants(model_window))
            model_window.close()
            drain()
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
        else:
            menu.popup()
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
