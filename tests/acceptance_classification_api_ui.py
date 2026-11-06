"""Offline API-only Model settings acceptance, always synthetic storage.

Run in a disposable source/environment. API_SETTINGS_HOLD=1 keeps the uniquely
identified window open for Computer Use; closing it finishes acceptance.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory(prefix="recordprep-api-ui-") as temporary:
    root = Path(temporary)
    for key in ("HOME", "RECORDPREP_CONFIG_DIR", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
                "XDG_CACHE_HOME", "XDG_STATE_HOME", "PI_CODING_AGENT_DIR"):
        path = root / key.lower()
        path.mkdir()
        os.environ[key] = str(path)
    os.environ["PI_RUN_METRICS_ENABLED"] = "0"
    from recordprep.ui import main_window as ui
    from gi.repository import Adw, GLib

    Adw.init()
    app = Adw.Application(application_id="org.synthetic.RecordPrep.ApiOnly")
    app.register(None)
    config = Path(os.environ["RECORDPREP_CONFIG_DIR"]) / "config.json"
    legacy = dict(classifier_local_vision_enabled=True,
                  classifier_local_vision_start_command="NEVER EXECUTE legacy",
                  synthetic_unknown=[1])
    config.write_text(json.dumps(legacy))
    prefs = config.parent / "pi/settings.json"
    prefs.parent.mkdir()
    prefs.write_text(json.dumps(dict(defaultProvider="synthetic", defaultModel="offline", defaultThinkingLevel="low")))

    def drain():
        until = time.monotonic() + .3
        while time.monotonic() < until:
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
            time.sleep(.01)

    def create():
        w = ui.SettingsWindow(app)
        w.set_title("Synthetic RecordPrep — API-only settings")
        w.present()
        drain()
        return w

    with patch.object(ui, "available_pi_models", return_value=[ui.PiModel("synthetic", "offline", "Offline fixture")]), \
         patch.object(ui, "resolve_pi_agent_argv", return_value=["synthetic-pi"]), \
         patch.object(ui, "_start_server", side_effect=AssertionError("unexpected server launch")) as start, \
         patch.object(ui, "_endpoint_responding", side_effect=AssertionError("unexpected server probe")) as probe, \
         patch.object(ui, "_stop_server", side_effect=AssertionError("unexpected server stop")) as stop:
        w = create()
        assert set(w._navigation.pages) == {"home", "ocr-command"}
        fields = w._prompt_editors["classify-basic"]
        fields.api_url_row.set_text("https://synthetic.invalid/v1/chat/completions")
        fields.model_row.set_text("synthetic-vision")
        fields.api_key_row.set_text("synthetic-key")
        fields.workers_row.set_text("3")
        fields.disable_reasoning_switch.set_active(True)
        w._local_ocr_widgets.start_command_buffer.set_text("synthetic OCR --slots {slots}")
        w.trigger_save()
        assert w.get_visible()
        assert w._session.baseline == w._draft_snapshot()
        saved = json.loads(config.read_text())
        for key, value in legacy.items():
            assert saved[key] == value
        w.close()
        drain()
        w = create()
        fields = w._prompt_editors["classify-basic"]
        assert fields.model_row.get_text() == "synthetic-vision"
        assert fields.api_key_row.get_text() == "synthetic-key"
        assert fields.workers_row.get_text() == "3"
        assert fields.disable_reasoning_switch.get_active()
        assert w._prompt_text(w._local_ocr_widgets.start_command_buffer) == "synthetic OCR --slots {slots}"
        print("API fields and OCR command saved/reopened; legacy data unchanged; no server calls", flush=True)
        if os.environ.get("API_SETTINGS_HOLD") == "1":
            while w.get_visible():
                GLib.MainContext.default().iteration(True)
        w.destroy()
        drain()
        start.assert_not_called()
        probe.assert_not_called()
        stop.assert_not_called()
        print("PASS: synthetic API-only settings acceptance", flush=True)
