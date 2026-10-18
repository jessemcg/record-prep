"""Real GTK model-menu sizing, synthetic data only; no settings or PI calls.

Run with the maintained project environment. Set MODEL_DROPDOWN_HOLD=1 for
interactive inspection of the same production summary-row builder.
"""
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
TEMP = tempfile.TemporaryDirectory(prefix="recordprep-model-menu-")
for key in ("RECORDPREP_CONFIG_DIR", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
    directory = Path(TEMP.name) / key.lower()
    directory.mkdir()
    os.environ[key] = str(directory)

from recordprep.ui import main_window as ui
from gi.repository import Adw, GLib, Gtk, Pango

Adw.init()
app = Adw.Application(application_id="org.synthetic.RecordPrepModelMenu")
app.register(None)
window = Adw.ApplicationWindow(application=app, title="RecordPrep model menu test")
window.set_default_size(850, 400)
group = Adw.PreferencesGroup(title="Model settings — synthetic choices")
for edge in ("top", "bottom", "start", "end"):
    getattr(group, f"set_margin_{edge}")(24)
window.set_content(group)
owner = SimpleNamespace(
    _summary_model_rows=[],
    _pi_model_options=[None] + [
        SimpleNamespace(provider="example-provider", model_id=f"variant-{variant}")
        for variant in ("alpha", "beta", "long")
    ],
)
owner._update_summary_model_subtitle = (
    ui.SettingsWindow._update_summary_model_subtitle.__get__(owner)
)
labels = [
    "Use project PI model",
    "Example Model with a shared long beginning — provider/variant-alpha-20261018",
    "Example Model with a shared long beginning — provider/variant-beta-20261018",
    "Very long model " + "provider/model-family-" * 8 + "distinctive-ending",
]
for title in ("Extraction model", "Synthesis model"):
    row = ui.SettingsWindow._build_summary_model_row(owner, title, "")
    row.set_model(Gtk.StringList.new(labels))
    group.add(row)
    factory = row.get_list_factory()
    assert isinstance(factory, Gtk.SignalListItemFactory)
    item = Gtk.ListItem()
    factory.emit("setup", item)
    label = item.get_child()
    assert label.get_width_chars() == 64
    assert label.get_max_width_chars() == 80
    assert label.get_wrap() and label.get_wrap_mode() == Pango.WrapMode.WORD_CHAR
    assert label.get_ellipsize() == Pango.EllipsizeMode.NONE
    for text in labels:
        ui._bind_pi_model_list_item(factory, SimpleNamespace(
            get_item=lambda: Gtk.StringObject.new(text), get_child=lambda: label))
        assert label.get_label() == text
    assert row.get_selected() == 0
    assert row.get_subtitle() == "Use project PI model"
    row.set_selected(2)
    assert row.get_selected_item().get_string() == labels[2]
    assert row.get_subtitle() == "example-provider / variant-beta"
    row.set_selected(1)
    assert row.get_subtitle() == "example-provider / variant-alpha"
    row.set_selected(0)
    assert row.get_subtitle() == "Use project PI model"
window.present()
end = time.monotonic() + 0.5
while time.monotonic() < end:
    while GLib.MainContext.default().pending():
        GLib.MainContext.default().iteration(False)
    time.sleep(0.01)
print("MODEL DROPDOWN GTK ACCEPTANCE PASSED", flush=True)
if os.environ.get("MODEL_DROPDOWN_HOLD"):
    loop = GLib.MainLoop()
    window.connect("close-request", lambda *_: loop.quit())
    loop.run()
window.destroy()
TEMP.cleanup()
