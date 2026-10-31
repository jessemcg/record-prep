"""Real GTK settings with synthetic config/catalog/profile stores only."""
import copy
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from gi.repository import GLib
from recordprep.ui import main_window as ui
from recordprep import practice_profiles as api
from recordprep.profile_editor_ui import ProfileEditorWindow, editable_profile, CLASSIFICATION_EXPLANATION, CLASSIFICATION_PROGRESSION, SUMMARY_EXPLANATION, topic_editor_text
from recordprep.settings_navigation import descendants

Adw, Gtk = ui.Adw, ui.Gtk


def drain():
    end = time.monotonic() + .2
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.005)


def dispose(window):
    # Let native dialog/clipboard responses drain before destroying the owned
    # synthetic surface; never overlap a destroyed Wayland seat target.
    window.set_focus(None)
    drain()
    window.destroy()
    drain()


class UnifiedSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Gtk.init_check():
            raise unittest.SkipTest("GTK display unavailable")
        Adw.init()
        cls.app = Adw.Application(application_id="org.synthetic.RecordPrep.UnifiedSettings")
        cls.app.register(None)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.parent = Adw.ApplicationWindow(application=self.app)
        self.addCleanup(dispose, self.parent)

    def model_window(self):
        self.config = {"synthetic_unknown": [1], "case_name_prompt": "Retired literal"}
        def write(value):
            self.config.clear()
            self.config.update(copy.deepcopy(value))
        for name, value in (("_read_config", lambda: copy.deepcopy(self.config)), ("_write_config", write),
                            ("current_project_pi_model", lambda: ("synthetic", "saved")),
                            ("current_project_pi_thinking_level", lambda: None),
                            ("save_project_pi_model", Mock()), ("save_project_pi_thinking_level", Mock())):
            p = patch.object(ui, name, value)
            p.start()
            self.addCleanup(p.stop)
        with patch.object(ui.SettingsWindow, "_load_pi_models"):
            window = ui.SettingsWindow(self.app)
        window.present()
        self.addCleanup(dispose, window)
        drain()
        return window

    def test_model_inline_categories_commands_save_failure_and_hidden_validation(self):
        w = self.model_window()
        self.assertEqual([w._navigation.home_list.get_row_at_index(i).get_title() for i in range(3)], ["OCR", "Classify", "Agent"])
        self.assertEqual(set(w._navigation.pages), {"home", "ocr-command", "vision-command"})
        self.assertTrue(all(row.get_margin_start() == 0 and row.get_margin_end() == 0
                            for row in descendants(w._navigation.home_list)
                            if isinstance(row, Adw.ActionRow)))
        w._navigation.open("ocr-command")
        buffer = w._local_ocr_widgets.start_command_buffer
        buffer.set_text("literal {slots} α\n  synthetic command")
        w._prompt_editors["classify-basic"].workers_row.set_text("invalid")
        before = copy.deepcopy(self.config)
        w._navigation.save_buttons["ocr-command"].emit("clicked")
        self.assertEqual(self.config, before)
        self.assertTrue(w.get_visible())
        w._prompt_editors["classify-basic"].workers_row.set_text("3")
        with patch.object(ui, "resolve_pi_agent_argv", return_value=["synthetic-pi"]):
            w.trigger_save()
            self.assertEqual(w._session.baseline, w._draft_snapshot())
            self.assertEqual(self.config["synthetic_unknown"], [1])
            self.assertEqual(self.config["case_name_prompt"], "Retired literal")
            self.assertEqual(w._navigation.view.get_visible_page().get_tag(), "ocr-command")
            baseline = w._session.baseline
            buffer.insert_at_cursor(" unsaved")
            with patch.object(ui, "_write_config", side_effect=OSError("synthetic failure")):
                w.trigger_save()
            self.assertEqual(w._session.baseline, baseline)
            w.trigger_save()
            self.assertEqual(w._session.baseline, w._draft_snapshot())
        buffer.insert_at_cursor(" dirty")
        self.assertTrue(w._on_pi_settings_close_request())
        self.assertFalse(w._pi_model_closed)
        w._session.dialog.response("keep")

    def test_model_refresh_retains_unsaved_unavailable_identity_and_ignores_late_results(self):
        w = self.model_window()
        models = [ui.PiModel("synthetic", "saved", "Saved"), ui.PiModel("synthetic", "other", "Other")]
        w._finish_pi_model_load(0, models, "", ("synthetic", "saved"))
        w._pi_model_row.set_selected(1)
        desired = w._selected_pi_model().settings_key
        w._finish_pi_model_load(0, [], "synthetic offline", desired)
        self.assertEqual(w._selected_pi_model().settings_key, desired)
        self.assertTrue(w._pi_model_selection_changed)
        w._finish_pi_model_load(0, [models[0]], "", desired)
        self.assertEqual(w._selected_pi_model().settings_key, desired)
        options = w._pi_model_options
        w._finish_pi_model_load(-1, [], "stale", None)
        self.assertIs(w._pi_model_options, options)
        w._pi_model_closed = True
        w._finish_pi_model_load(0, [], "late", None)
        self.assertIs(w._pi_model_options, options)

    def profile_window(self):
        store = api.ProfileStore("recordprep", config_root=self.root / "config", data_root=self.root / "data")
        no_legacy = patch("recordprep.profile_customization.initial_candidate", return_value=None)
        no_legacy.start()
        self.addCleanup(no_legacy.stop)
        candidates = list(api.profile_catalog(store=store))
        candidate = next(c for c in candidates if c.snapshot.ref.specialty_id == api.DEFAULT_PROFILE_ID)
        window = ProfileEditorWindow(self.parent, editable_profile(candidate.snapshot), store,
            expected_head=None, can_modify=lambda: True, preview=lambda _: None, on_saved=Mock(), candidates=candidates)
        self.addCleanup(dispose, window)
        window.present()
        for card, _ in window._recognition_cards.values():
            card.set_expanded(True)
        drain()
        return window, store

    def test_classification_outline_structure_navigation_and_bindings(self):
        from recordprep.profile_editor_ui import CLASSIFICATION_PAGES
        w, store = self.profile_window()
        keys = [key for key, _, _ in CLASSIFICATION_PAGES]
        self.assertEqual(list(w.nav_rows)[:5], keys)
        self.assertEqual(keys, ['rt', 'ct', 'first-pages', 'report-naming', 'form-naming'])
        self.assertNotIn("classification", w.pages)
        self.assertNotIn("Common guidance", [row.get_title() for row in w.nav_rows.values()])
        chooser_before = list(w._navigation._prompt_keys)
        for key, row in w.nav_rows.items():
            self.assertEqual(row.get_margin_start(), 0, key)
            self.assertEqual(row.get_margin_end(), 0, key)
        w.nav_groups["Classification"].set_expanded(True)
        drain()
        for key in keys:
            with self.subTest(key=key):
                row = w.nav_rows[key]
                self.assertTrue(row.get_activatable())
                row.emit("activated")  # Callback contract, not native-input proof.
                drain()
                self.assertEqual(w._navigation.view.get_visible_page().get_tag(), key)
                if key.endswith('-naming'):
                    plural = key.removesuffix('-naming') + 's'
                    detail = 'topic:naming-' + plural + ':' + w.editor.resources['naming'][plural][0]['id']
                    w._topic_expanders[detail].set_expanded(True)
                view = next(x for x in descendants(w.pages[key]) if isinstance(x, Gtk.TextView))
                buffer = view.get_buffer()
                literal = "Synthetic outline guidance: " + key
                buffer.set_text(literal)
                if key.endswith("-naming"):
                    self.assertEqual(w.editor.resources['naming'][plural][0]['guidance'], literal)
                elif key == 'first-pages':
                    self.assertEqual(w.editor.resources['classification_tasks']['first_pages']['first_hearing'], literal)
                else:
                    field = 'RT_cover' if key == 'rt' else 'CT_cover'
                    self.assertEqual(w.editor.resources['classification_tasks']['page_types'][key][field], literal)
                self.assertTrue(w._navigation.view.pop())
                drain()
                self.assertEqual(w._navigation.view.get_visible_page().get_tag(), "home")
                self.assertTrue(w.nav_groups["Classification"].get_expanded())
        self.assertEqual(w._navigation._prompt_keys, chooser_before)
        self.assertFalse(store.registry_path.exists())

    def test_outline_rt_ct_buffers_and_undo_survive_navigation_and_save(self):
        w, _ = self.profile_window()
        buffers = {}
        for key in ("rt", "ct"):
            w.nav_rows[key].emit("activated")
            drain()
            buffer = next(x for x in descendants(w.pages[key]) if isinstance(x, Gtk.TextView)).get_buffer()
            buffer.set_text("Synthetic " + key)
            buffer.insert_at_cursor(" edited")
            self.assertTrue(buffer.get_can_undo())
            buffers[key] = buffer
        for key, buffer in buffers.items():
            w.nav_rows[key].emit("activated")
            drain()
            self.assertIs(next(x for x in descendants(w.pages[key]) if isinstance(x, Gtk.TextView)).get_buffer(), buffer)
            self.assertEqual(buffer.get_text(*buffer.get_bounds(), True), "Synthetic " + key + " edited")
            self.assertTrue(buffer.get_can_undo())
        w._navigation.save_buttons["ct"].emit("clicked")
        self.assertFalse(w._dirty())
        for buffer in buffers.values():
            self.assertTrue(buffer.get_can_undo())
            buffer.undo()
        self.assertTrue(w._dirty())
        self.assertTrue(w._close_request())
        w.unsaved_dialog.response("keep")
        drain()
        self.assertTrue(w.get_visible())

    def test_profile_explanations_literal_state_topics_and_revision_rebinding(self):
        w, store = self.profile_window()
        self.assertEqual(list(w.nav_groups), ["Classification", "Summaries"])
        self.assertFalse(any(row.get_expanded() for row in w.nav_groups.values()))
        self.assertEqual(w._navigation.view.get_visible_page().get_tag(), "home")
        self.assertFalse(store.registry_path.exists())
        w._select_page("rt")
        drain()
        widgets = list(descendants(w.pages["rt"]))
        explanation = next(x for x in widgets if isinstance(x, Gtk.Expander))
        self.assertFalse(explanation.get_expanded())
        self.assertIsInstance(explanation.get_child(), Gtk.Box)
        self.assertFalse(any(isinstance(x, Gtk.ScrolledWindow) for x in descendants(explanation.get_child())))
        text = "\n".join(x.get_text() for x in descendants(explanation.get_child()) if isinstance(x, Gtk.Label))
        self.assertIn(CLASSIFICATION_EXPLANATION, text)
        self.assertTrue(text.endswith(CLASSIFICATION_PROGRESSION))
        self.assertFalse(any(isinstance(x, Gtk.Label) and x.get_text().startswith(
            ("Classification ·", "Compare all descriptions")) for x in widgets))
        self.assertEqual(explanation.get_label(), "About classification")
        for detail in (
            "Detect transcript layout",
            "only RT or only CT pages",
            "This allows the app to know the boundary of each hearing, minute order, report, and form.",
            "for each form, only the name is extracted",
            "This ensures that only relevant reports and forms are identified.",
        ):
            self.assertIn(detail, text)
        explanation.set_expanded(True)
        drain()
        self.assertTrue(explanation.get_expanded())
        explanation.set_expanded(False)
        view = next(x for x in widgets if isinstance(x, Gtk.TextView))
        buffer = view.get_buffer()
        literal = "Literal α {{placeholder}}\n  retained\ttext.\n" * 100
        buffer.set_text(literal)
        view.grab_focus()
        drain()
        scroll = view.get_ancestor(Gtk.ScrolledWindow)
        drain()
        scroll.get_vadjustment().set_value(400)
        buffer.select_range(buffer.get_iter_at_offset(50), buffer.get_iter_at_offset(10))
        w._select_page("ct")
        self.assertEqual(w._navigation._selections["rt"][0][1:], (50, 10))
        drain()
        w._select_page("rt")
        drain()
        self.assertEqual(buffer.get_text(*buffer.get_bounds(), True), literal)
        if w.is_active():
            self.assertEqual(tuple(i.get_offset() for i in buffer.get_selection_bounds()), (10, 50))
        else:
            # Wayland rejects primary-selection ownership for inactive synthetic
            # windows (also reproduced with a lone ordinary Gtk.TextView).
            self.assertEqual(w._navigation._selections["rt"][0][1:], (50, 10))
        self.assertAlmostEqual(scroll.get_vadjustment().get_value(), 400, delta=2)
        self.assertTrue(buffer.get_enable_undo())
        before_buffer = buffer
        w._navigation.save_buttons["rt"].emit("clicked")
        self.assertEqual(w.message.get_text(), "Profile saved.")
        self.assertTrue(w.get_visible())
        self.assertIs(buffer, before_buffer)
        self.assertFalse(w._dirty())
        base = w.editor.base.ref
        buffer.insert_at_cursor(" second revision ")
        w._navigation.save_buttons["rt"].emit("clicked")
        self.assertEqual(w.message.get_text(), "Profile saved.")
        self.assertNotEqual(w.editor.base.ref, base)
        self.assertIn("second revision", store.load_profile_snapshot(w.editor.base.ref).resource("classification_tasks")["page_types"]["rt"]["RT_cover"])
        self.assertEqual(w._navigation.view.get_visible_page().get_tag(), "rt")
        topic = w.editor.resources["hearings"][0]
        key = "topic:hearings:" + topic["id"]
        original = topic["guidance"]
        w._select_page("hearings-topics")
        drain()
        topic_buffer = w._topic_editors[key].get_child().get_buffer()
        self.assertEqual(topic_buffer.get_text(*topic_buffer.get_bounds(), True), topic_editor_text(original))
        self.assertEqual(topic["guidance"], original)
        topic_buffer.insert_at_cursor(" topic revision ")
        values = w.editor.resources["hearings"]
        values[0], values[1] = values[1], values[0]
        self.assertTrue(w._save())
        topic_buffer.insert_at_cursor(" after save ")
        self.assertIn("after save", next(v for v in w.editor.resources["hearings"] if v["id"] == topic["id"])["guidance"])
        self.assertTrue(w._save())
        self.assertFalse(w._dirty())
        self.assertIn("after save", next(v for v in store.load_profile_snapshot(w.editor.base.ref).resource("hearings") if v["id"] == topic["id"])["guidance"])
        self.assertEqual(w._navigation.view.get_navigation_stack().get_n_items(), 2)
        self.assertFalse(any(key.startswith("topic:") for key in w._navigation.pages))
        summary = next(x for x in descendants(w.pages["hearings-topics"])
                       if isinstance(x, Gtk.Expander) and x.get_label() == "About summaries")
        content = summary.get_child()
        self.assertIsInstance(content.get_first_child(), Gtk.Button)
        self.assertEqual(content.get_first_child().get_label(), "View full prompts…")
        self.assertIn(SUMMARY_EXPLANATION, content.get_last_child().get_text())
        self.assertFalse(any(isinstance(x, Gtk.ScrolledWindow) for x in descendants(content)))

    def test_topic_catalog_native_rename_reorder_remove_and_add(self):
        w, store = self.profile_window()
        w._select_page("hearings-topics")
        drain()
        values = w.editor.resources["hearings"]
        original = values[0]
        key = "topic:hearings:" + original["id"]
        w._topic_expanders[key].set_expanded(True)
        entry = next(x for x in descendants(w.pages["hearings-topics"])
                     if isinstance(x, Gtk.Entry) and x.get_text() == original["title"])
        card = entry.get_ancestor(Gtk.Expander)
        card.set_expanded(True)
        topic_editor = w._topic_editors[key]
        buffer = topic_editor.get_child().get_buffer()
        buffer.insert_at_cursor(" retained edit ")
        entry.set_text("Renamed topic α")
        self.assertEqual(card.get_label_widget().get_text(), "Renamed topic α")
        next(x for x in descendants(card) if isinstance(x, Gtk.Button) and x.get_label() == "Move down").emit("clicked")
        self.assertIs(values[1], original)
        self.assertIs(w._topic_editors[key], topic_editor)
        self.assertTrue(card.get_expanded())
        self.assertTrue(buffer.get_can_undo())
        self.assertIn("retained edit", buffer.get_text(*buffer.get_bounds(), True))
        entry = next(x for x in descendants(w.pages["hearings-topics"])
                     if isinstance(x, Gtk.Entry) and x.get_text() == "Renamed topic α")
        next(x for x in descendants(entry.get_parent()) if isinstance(x, Gtk.Button) and x.get_label() == "Remove").emit("clicked")
        self.assertNotIn(key, w._navigation.pages)
        self.assertNotIn(key, w._topic_editors)
        count = len(values)
        next(x for x in descendants(w.pages["hearings-topics"]) if isinstance(x, Gtk.Button) and x.get_label() == "Add topic").emit("clicked")
        self.assertEqual(len(values), count + 1)
        self.assertIn("topic:hearings:" + values[-1]["id"], w._topic_editors)
        self.assertFalse(any(key.startswith("topic:") for key in w._navigation.pages))
        self.assertTrue(w._save())
        self.assertEqual(len(store.load_profile_snapshot(w.editor.base.ref).resource("hearings")), len(values))

    def test_summaries_inline_explanations_and_display_only_unwrapping(self):
        w, store = self.profile_window()
        literal = "Read the complete\nsource carefully.\n\nKeep attribution\nand uncertainty."
        w.editor.resources["hearings"][0]["guidance"] = literal
        w._render()
        originals = copy.deepcopy(w.editor.resources)
        for kind in ("hearings", "reports"):
            page = kind + "-topics"
            w.nav_rows[page].emit("activated")
            drain()
            self.assertEqual(w._navigation.view.get_navigation_stack().get_n_items(), 2)
            disclosure = next(x for x in descendants(w.pages[page])
                              if isinstance(x, Gtk.Expander) and x.get_label() == "About summaries")
            self.assertIsInstance(disclosure.get_child(), Gtk.Box)
            self.assertFalse(any(isinstance(x, Gtk.ScrolledWindow) for x in descendants(disclosure)))
            disclosure.set_expanded(True)
            for topic in w.editor.resources[kind]:
                key = "topic:" + kind + ":" + topic["id"]
                editor = w._topic_editors[key]
                card = w._topic_expanders[key]
                card.set_expanded(True)
                buffer = editor.get_child().get_buffer()
                self.assertEqual(buffer.get_text(*buffer.get_bounds(), True), topic_editor_text(topic["guidance"]))
                self.assertGreaterEqual(editor.get_min_content_height(), 120)
            self.assertFalse(any(isinstance(x, Gtk.Button) and x.get_label() == "Edit instructions"
                                 for x in descendants(w.pages[page])))
        self.assertEqual(w.editor.resources, originals)
        self.assertFalse(w._dirty())
        self.assertFalse(store.registry_path.exists())
        self.assertTrue(w._save())
        saved = store.load_profile_snapshot(w.editor.base.ref)
        self.assertEqual(saved.resource("hearings")[0]["guidance"], literal)
        w._select_page("minutes")
        self.assertIsInstance(w.pages["minutes"], Gtk.ScrolledWindow)
        disclosure = next(x for x in descendants(w.pages["minutes"]) if isinstance(x, Gtk.Expander))
        self.assertIsInstance(disclosure.get_child(), Gtk.Box)
        disclosure.set_expanded(True)
        self.assertIn(SUMMARY_EXPLANATION, '\n'.join(x.get_text() for x in descendants(disclosure.get_child()) if isinstance(x, Gtk.Label)))
        self.assertEqual(topic_editor_text(literal), "Read the complete source carefully.\n\nKeep attribution and uncertainty.")
        for structured in ("- First\n- Second", "# Heading\nText", "Line  \nBreak", "Line\\\nBreak"):
            self.assertEqual(topic_editor_text(structured), structured)

    def test_profile_failed_publication_and_post_save_refresh_feedback(self):
        w, store = self.profile_window()
        w.editor.resources["classification_tasks"]["page_types"]["rt"]["RT_cover"] += " synthetic saved guidance"
        before = copy.deepcopy(w._saved_state)
        with patch.object(type(w.editor), "managed_save", side_effect=OSError("synthetic write failure")):
            self.assertFalse(w._save())
        self.assertEqual(w._saved_state, before)
        self.assertTrue(w._dirty())
        self.assertTrue(w.get_visible())
        self.assertFalse(store.registry_path.exists())
        w.on_saved.side_effect = RuntimeError("synthetic refresh failure")
        self.assertTrue(w._save())
        self.assertTrue(w.saved_apply_failed)
        self.assertFalse(w._dirty())
        self.assertIn("Profile saved;", w.message.get_text())
        self.assertTrue(w.get_visible())

    def test_profile_reopen_uses_application_owned_draft(self):
        from types import SimpleNamespace
        from recordprep.profile_manager_ui import ProfileManagerWindow
        w, _ = self.profile_window()
        w.editor.resources["classification_tasks"]["page_types"]["rt"]["RT_cover"] += " unsaved retained draft"
        menu = SimpleNamespace(parent_window=self.parent, get_ancestor=lambda _type: None)
        self.assertIs(ProfileManagerWindow._edit(menu), w)
        self.assertIn("unsaved retained draft", w.editor.resources["classification_tasks"]["page_types"]["rt"]["RT_cover"])
        self.assertTrue(w._dirty())

    def test_profile_close_only_keep_or_discard(self):
        w, _ = self.profile_window()
        w.editor.resources["classification_tasks"]["page_types"]["rt"]["RT_cover"] += " draft"
        self.assertTrue(w._close_request())
        responses = w.unsaved_dialog
        self.assertTrue(responses.has_response("keep"))
        self.assertTrue(responses.has_response("discard"))
        self.assertFalse(responses.has_response("save"))
        responses.response("keep")
        drain()
        self.assertTrue(w.get_visible())
        w.close()
        w.unsaved_dialog.response("discard")
        self.assertFalse(w.get_visible())
        self.assertFalse(w.store.registry_path.exists())
