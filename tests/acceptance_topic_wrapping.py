"""Topic prose uses available editor width without mutating stored guidance."""
import importlib
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
package = "focus" if (HERE / "focus").is_dir() else "recordprep"
with tempfile.TemporaryDirectory(prefix="topic-wrapping-") as temp:
    root = Path(temp)
    for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        directory = root / key.lower()
        directory.mkdir()
        os.environ[key] = str(directory)
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, GLib, Gtk
    api = importlib.import_module(package + ".practice_profiles")
    ui = importlib.import_module(package + ".profile_editor_ui")
    manager_ui = importlib.import_module(package + ".profile_manager_ui")
    unwrap = ui.topic_editor_text
    assert unwrap("A wrapped\nparagraph.\n\nAnother\nparagraph.") == "A wrapped paragraph.\n\nAnother paragraph."
    for text in ("- First\n- Second", "1. First\n2. Second", "# Heading\nText",
                 "```\ncode\n```", "> Quote\n> More", "    code\n    more",
                 "Line  \nBreak", "Line\\\nBreak", "| A | B |\n| C | D |"):
        assert unwrap(text) == text
    Adw.init()
    app = Adw.Application(application_id="org.synthetic.TopicWrapping")
    app.register(None)
    parent = Adw.ApplicationWindow(application=app)
    # Both vendored modules can render a RecordPrep store without importing the sibling app.
    store = api.ProfileStore("recordprep", config_root=root / "config", data_root=root / "data")
    source = "Capture the material evidence across all pages of the complete hearing.\nPreserve attribution and uncertainty rather than guessing.\n\nKeep this second paragraph separate."
    owner = {"guidance": source}
    scroll = ui.text_editor(unwrap(source), lambda text: owner.__setitem__("guidance", text))
    buffer = scroll.get_child().get_buffer()
    assert owner["guidance"] == source
    assert scroll.get_child().get_wrap_mode() == Gtk.WrapMode.WORD_CHAR
    buffer.set_text(unwrap(source) + " Edited.")
    assert owner["guidance"].endswith(" Edited.")
    if package == "recordprep":
        with patch.object(api, "profile_store", return_value=store):
            manager = manager_ui.ProfileManagerWindow(parent, can_modify=lambda: True,
                preview=lambda snapshot: None, on_select=lambda ref: None, allow_legacy=False, has_case=False)
            editor = manager._edit()
            editor.editor.resources["hearings"][0]["guidance"] = source
            editor._render()
            editor._select_page("hearings-topics")
            def descendants(widget):
                yield widget
                child = widget.get_first_child()
                while child is not None:
                    yield from descendants(child)
                    child = child.get_next_sibling()
            expander = next(w for w in descendants(editor.pages["hearings-topics"]) if isinstance(w, Gtk.Expander))
            expander.set_expanded(True)
            actions = [w for w in descendants(expander) if isinstance(w, Gtk.Button)
                       and w.get_label() in ("Move up", "Move down", "Remove")]
            assert [w.get_label() for w in actions] == ["Move up", "Move down", "Remove"]
            assert all(w.has_css_class("flat") and isinstance(w.get_parent(), Gtk.Box)
                       and w.get_ancestor(Gtk.FlowBoxChild) is None for w in actions)
            assert not actions[0].get_sensitive() and actions[1].get_sensitive()
            view = next(w for w in descendants(expander) if isinstance(w, Gtk.TextView))
            buffer = view.get_buffer()
            assert buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True) == unwrap(source)
            assert editor.editor.resources["hearings"][0]["guidance"] == source
            assert not editor._dirty()
            editor._select_page("reports-topics")
            editor._select_page("hearings-topics")
            assert not editor._dirty() and not store.registry_path.exists()
            if os.environ.get("TOPIC_WRAPPING_HOLD"):
                loop = GLib.MainLoop()
                editor.connect("close-request", lambda *_: (loop.quit(), False)[1])
                loop.run()
            editor.close()
    parent.close()
    print(f"{package}: TOPIC WRAPPING GTK ACCEPTANCE PASSED", flush=True)
