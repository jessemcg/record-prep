import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from recordprep.case_profiles import read_historical_case_profile_ref
from recordprep.practice_profiles import bundled_profile_directory, validate_profile_directory
from recordprep.profile_store import ProfileStore
from recordprep.ui import main_window as ui


class NewCaseProfileTests(unittest.TestCase):
    def run_create(self, directory, store, *, pending=None):
        pdf = directory / "synthetic.pdf"
        pdf.write_bytes(b"Synthetic test placeholder; PDF extraction is mocked.")
        owner = SimpleNamespace(selected_pdfs=[pdf], _rt_ct_split_pending=None, _rt_ct_split_mode_pending=None,
                                _bundle_reset_required=False, _pending_preparation_profile=pending,
                                _raise_if_stop_requested=Mock(), _safe_update_manifest=Mock(), _load_rt_ct_split=Mock(),
                                _finish_step=Mock(), _stop_status_if_idle=Mock(), _stop_button_if_idle=Mock(),
                                _step_artifact_complete=Mock(return_value=False),
                                step_one_row=Mock(), show_toast=Mock())
        owner._has_layout_dependent_work = lambda root: ui.RecordPrepWindow._has_layout_dependent_work(owner, root)
        with patch("recordprep.practice_profiles.profile_store", return_value=store), \
                patch("recordprep.case_profiles.profile_store", return_value=store), \
                patch.object(ui, "_bundle_inputs_changed", return_value=False), \
                patch.object(ui, "_write_manifest"), \
                patch.object(ui, "load_text_source_setting", return_value="synthetic-pdf-text"), \
                patch.object(ui, "_generate_text_files"), patch.object(ui, "_generate_image_page_files"), \
                patch.object(ui.GLib, "idle_add", side_effect=lambda function, *args: function(*args)):
            result = ui.RecordPrepWindow._run_step_one(owner)
        return result, owner

    def test_actual_create_flow_never_pins_profiles_or_changes_application_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            store = ProfileStore("recordprep", config_root=base / "config", data_root=base / "data")
            general = validate_profile_directory(bundled_profile_directory("general")).draft
            dependency = validate_profile_directory(bundled_profile_directory("california_dependency")).draft
            for name in ("fresh", "old", "pending"):
                (base / name).mkdir()
            old = base / "old/case_bundle"
            old.mkdir()
            sentinel = old / "prior.txt"
            sentinel.write_bytes(b"Prior readable material")
            self.assertTrue(self.run_create(base / "fresh", store)[0])
            self.assertIsNone(read_historical_case_profile_ref(base / "fresh/case_bundle"))
            self.assertTrue(self.run_create(base / "old", store)[0])
            self.assertIsNone(read_historical_case_profile_ref(old))
            self.assertEqual(sentinel.read_bytes(), b"Prior readable material")
            store.accept_profile(dependency, expected_previous_digest=None)
            store.set_default(dependency.ref)
            before = store.registry_path.read_bytes()
            root = base / "pending/case_bundle"
            success, owner = self.run_create(base / "pending", store, pending=(root, dependency.ref))
            self.assertTrue(success)
            self.assertIsNone(read_historical_case_profile_ref(root))
            self.assertIsNone(owner._pending_preparation_profile)
            self.assertEqual(store.registry_path.read_bytes(), before)
            store.accept_profile(general, expected_previous_digest=None)
            store.set_default(general.ref)
            before = store.registry_path.read_bytes()
            self.assertTrue(self.run_create(base / "pending", store)[0])
            self.assertIsNone(read_historical_case_profile_ref(root))
            self.assertEqual(store.registry_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
