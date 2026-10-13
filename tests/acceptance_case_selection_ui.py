"""Real GTK header/profile selection acceptance; synthetic settings and cases only."""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
TEMP = tempfile.TemporaryDirectory(prefix="recordprep-selection-ui-")
ROOT = Path(TEMP.name)
for key, name in (("HOME", "home"), ("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"), ("XDG_CACHE_HOME", "cache")):
    directory = ROOT / name
    directory.mkdir()
    os.environ[key] = str(directory)

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib, Gtk
from recordprep import case_profiles, practice_profiles as api, profile_integration
from recordprep.ui import main_window as ui

ui.CONFIG_FILE = ROOT / "application.json"
base = ROOT / "synthetic-case"
bundle = base / "case_bundle"
metadata = bundle / ".recordprep"
metadata.mkdir(parents=True, mode=0o755)
(bundle / "text_pages").mkdir()
(bundle / "text_pages/0001.txt").write_text("Synthetic court record for local UI acceptance only.\n")
(bundle / "case_name.txt").write_text("Synthetic_case\n")
sentinels = {path: path.read_bytes() for path in (bundle / "text_pages/0001.txt", bundle / "case_name.txt")}
dependency = api.validate_profile_directory(api.bundled_profile_directory("california_dependency")).draft
(metadata / "practice-profile.json").write_text(json.dumps({"schema_version": 1, "profile_ref": asdict(dependency.ref)}))
(metadata / "practice-profile.json").chmod(0o644)
(metadata / ".practice-profile.lock").touch(mode=0o644)
ui.CONFIG_FILE.write_text(json.dumps({"case_root_dir": str(base), "case_name": "Synthetic_case", "selected_pdfs": [],
                                    "case_name_prompt": "Preserve synthetic retired guidance", "rt_ct_split_page": 777}))
app = ui.RecordPrepApp()
app.set_application_id("org.synthetic.RecordPrepSelection")
errors = []


def drain():
    until = time.monotonic() + 0.25
    while time.monotonic() < until:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(0.01)


def descendants(widget):
    yield widget
    child = widget.get_first_child()
    while child is not None:
        yield from descendants(child)
        child = child.get_next_sibling()


def run():
    try:
        owner = app.get_active_window()
        owner.set_title("Synthetic RecordPrep — case selection acceptance")
        owner.set_default_size(820, 760)
        drain()
        assert owner._resolve_case_root() == bundle
        assert owner._title_widget.get_subtitle() == "Unavailable profile"
        buttons = (owner.case_bundle_button, owner.file_button, owner.clear_case_button)
        positions = []
        for button in buttons:
            assert button.has_css_class("flat")
            assert isinstance(button.get_child(), Gtk.Image)
            assert button.get_child().has_css_class("dim-label")
            valid, bounds = button.compute_bounds(owner)
            assert valid
            positions.append(bounds.get_x())
        assert positions == sorted(set(positions))
        assert owner.file_button.get_next_sibling() is owner.clear_case_button
        owner._pipeline_running = True
        owner._sync_pipeline_controls()
        assert not any(button.get_sensitive() for button in buttons)
        owner._pipeline_running = False
        owner._sync_pipeline_controls()
        owner.menu_button.popup()
        drain()
        manager = owner._practice_profiles_window
        index = next(i for i, option in enumerate(manager.options)
                     if option and option.snapshot.ref.specialty_id == "general-court-record")
        manager.selector._choose(index)
        drain()
        assert not manager.message.get_text(), manager.message.get_text()
        assert case_profiles.read_case_profile_ref(bundle).specialty_id == "general-court-record"
        assert owner._title_widget.get_subtitle() == "General Court Record"
        assert metadata.stat().st_mode & 0o777 == 0o755
        assert (metadata / ".practice-profile.lock").stat().st_mode & 0o777 == 0o644
        owner.menu_button.popdown()
        # Keep the clear action's config-preservation assertion independent of
        # existing startup controls that save their selected defaults.
        before_clear = json.loads(ui.CONFIG_FILE.read_text())
        before_clear["rt_ct_split_page"] = 777
        ui.CONFIG_FILE.write_text(json.dumps(before_clear))
        owner.clear_case_button.emit("clicked")
        drain()
        assert owner._resolve_case_root() is None and not owner.selected_pdfs
        assert not manager.can_modify()
        assert not owner.clear_case_button.get_sensitive()
        assert owner.case_bundle_button.get_sensitive() and owner.file_button.get_sensitive()
        assert owner.selected_label.get_text() == "Selected: None"
        assert all(label.get_text() == "Pending" for label in owner._step_status_labels.values())
        assert {path: path.read_bytes() for path in sentinels} == sentinels
        config = json.loads(ui.CONFIG_FILE.read_text())
        assert config["rt_ct_split_page"] == 777
        assert config["case_name_prompt"] == "Preserve synthetic retired guidance"
        pin_after = (metadata / "practice-profile.json").read_bytes()
        owner.menu_button.popup()
        drain()
        manager = owner._practice_profiles_window
        assert manager.can_modify() and not manager.has_case
        index = next(i for i, option in enumerate(manager.options)
                     if option and option.snapshot.ref.specialty_id == "general-court-record")
        manager.selector._choose(index)
        editor = manager._edit()
        drain()
        assert editor.get_visible()
        assert "General" not in editor.pages
        editor.editor.resources["classification"] += "\nSynthetic no-case customization.\n"
        save = next(widget for widget in descendants(editor) if isinstance(widget, Gtk.Button) and widget.get_label() == "Save")
        save.emit("clicked")
        drain()
        assert not hasattr(manager, "apply_dialog")
        assert profile_integration.pending_profile(owner, None) == editor.editor.base.ref
        assert "Synthetic no-case customization" in api.profile_store().load_profile_snapshot(editor.editor.base.ref).resource("classification")
        assert (metadata / "practice-profile.json").read_bytes() == pin_after
        assert owner._resolve_case_root() is None
        editor.close()
        drain()
        owner.menu_button.popdown()
        print("CASE SELECTION GTK ACCEPTANCE PASSED", flush=True)
        if not os.environ.get("CASE_SELECTION_HOLD"):
            app.quit()
    except Exception as exc:
        import traceback
        traceback.print_exc()
        errors.append(exc)
        app.quit()
    return False


GLib.timeout_add(500, run)
app.run([])
TEMP.cleanup()
if errors:
    raise SystemExit(1)
