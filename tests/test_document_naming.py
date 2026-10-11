"""Reviewed catalogs and synthetic, zero-model naming/pipeline acceptance."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from recordprep import document_naming as naming
from recordprep import practice_profiles as profiles
from recordprep.profile_contract import ProfileError, json_bytes, validate_contents

REPORT_TITLES = (
    "Detention Report", "Initial Hearing Report", "Jurisdiction Report", "Disposition Report",
    "Last Minute Information", "Non-Detained Report", "Status Review Report", "Interim Review Report",
    "Review Report", "Addendum Report", "Petition Report", "366.26 WIC Report", "Permanent Plan Review Report",
    "RPP Report", "Selection and Implementation Report", "Additional Information for Court",
)
FORM_RULES = (
    ("Parental Notification of Indian Status", "Parental Notification of Indian Status", "ICWA-020"),
    ("Juvenile Dependency Petition", "Juvenile Dependency Petition", "JV-100"),
    ("Notice of Appeal", "Notice of Appeal", "JV-800"),
    ("Request to Change Court Order", "Request to Change Court Order", "JV-180"),
    ("Waiver of Rights--Juvenile Dependency", "Waiver of Rights", "JV-190"),
    ("Notification of Mailing Address", "Notification of Mailing Address", "JV-140"),
)


def snapshot(name="california_dependency"):
    result = profiles.validate_profile_directory(profiles.bundled_profile_directory(name))
    assert not result.issues, result.issues
    return result.draft


def with_naming(original, value):
    files = dict(original.files)
    files[original.manifest["resources"]["naming"]] = json_bytes(value)
    return validate_contents(tuple(files.items()), "recordprep")


class NamingContractTests(unittest.TestCase):
    def test_reviewed_catalog_is_exact_except_approved_spelling_correction(self):
        resource = snapshot().resource("naming")
        self.assertEqual(resource["schema_version"], 2)
        self.assertEqual(resource["mode"], "approved_titles")
        self.assertEqual(tuple(resource["report_titles"]), REPORT_TITLES)
        self.assertEqual(tuple((r["name"], r["title"], r["code"]) for r in resource["form_rules"]), FORM_RULES)
        self.assertNotIn("Parential", json.dumps(resource))

    def test_report_prompt_preserves_heading_and_date_rules(self):
        draft = snapshot()
        contract = naming.compile_naming_profile(draft, "report")
        self.assertIn(draft.resource("naming")["report_guidance"], contract.prompt)
        self.assertIn("Hearing Date near the DETENTION REPORT heading", contract.prompt)
        self.assertIn("unless no other report date is visible", contract.prompt)
        for title in REPORT_TITLES:
            self.assertIn(title, contract.prompt)
        self.assertNotIn("JV-190", contract.prompt)
        self.assertEqual(contract.response_keys, ("name", "date"))

    def test_form_prompt_requires_title_and_code_on_same_page(self):
        contract = naming.compile_naming_profile(snapshot(), "form")
        self.assertIn("same supplied page", contract.prompt)
        self.assertIn("A code alone is not a match", contract.prompt)
        self.assertIn('"title": "Waiver of Rights"', contract.prompt)
        self.assertIn('"name": "Waiver of Rights--Juvenile Dependency"', contract.prompt)
        self.assertIn('"code": "JV-190"', contract.prompt)
        self.assertNotIn("Detention Report", contract.prompt)
        self.assertEqual(contract.response_keys, ("name",))

    def test_every_approved_name_can_be_returned(self):
        report = naming.compile_naming_profile(snapshot(), "report")
        form = naming.compile_naming_profile(snapshot(), "form")
        for title in REPORT_TITLES:
            with self.subTest(title=title):
                value = report.normalize({"name": title, "date": "November 30, 2022"})
                self.assertEqual(value.name, title)
                self.assertEqual(value.quality_flags, ())
        for title, _heading, _code in FORM_RULES:
            self.assertEqual(form.normalize({"name": title}).name, title)

    def test_membership_check_is_exact_and_not_a_source_evidence_verifier(self):
        contract = naming.compile_naming_profile(snapshot(), "form")
        for title in ("Waiver of Rights", "JV-190", "Parential Notification of Indian Status", "notice of appeal"):
            with self.subTest(title=title):
                result = contract.normalize({"name": title})
                self.assertEqual(result.name, "")
                self.assertIn("unrecognized_title", result.quality_flags)
        # Python validates the canonical name; it cannot independently prove
        # that the model saw title and code on the actual supplied image.
        self.assertEqual(contract.normalize({"name": "Notice of Appeal"}).name, "Notice of Appeal")

    def test_unknown_report_does_not_erase_date(self):
        result = naming.compile_naming_profile(snapshot(), "report").normalize(
            {"name": "Unlisted assessment", "date": "February 29, 2024"})
        self.assertEqual(result.name, "")
        self.assertEqual(result.date, "February 29, 2024")
        self.assertIn("name_unresolved", result.quality_flags)

    def test_bad_dates_and_values_produce_sanitized_flags(self):
        contract = naming.compile_naming_profile(snapshot(), "report")
        for bad_date in ("February 29, 2023", "June 31, 2024", "1/2/24", [], "private\ntext"):
            result = contract.normalize({"name": "Detention Report", "date": bad_date})
            self.assertEqual(result.date, "")
            self.assertIn("invalid_report_date", result.quality_flags)
            self.assertNotIn("private", str(result.quality_flags))
        for payload in (None, [], {"name": ["Detention Report"], "date": ""}, {"name": "x" * 161}):
            result = contract.normalize(payload)
            self.assertEqual(result.name, "")
        result = contract.normalize({"name": "Detention Report", "date": "January 01, 2020", "command": "do-not-run"})
        self.assertEqual(result.date, "January 1, 2020")
        self.assertIn("naming_response_keys", result.quality_flags)

    def test_general_has_no_dependency_whitelist(self):
        for kind in ("report", "form"):
            contract = naming.compile_naming_profile(snapshot("general"), kind)
            self.assertEqual(contract.mode, "source_title")
            self.assertNotIn("JV-", contract.prompt)
            self.assertNotIn("dependency", contract.prompt.lower())
            response = {"name": "Independent Engineering Assessment"}
            if kind == "report":
                response["date"] = ""
            self.assertEqual(contract.normalize(response).name, response["name"])

    def test_v1_naming_compiles_without_inventing_code_requirements(self):
        old = {"mode": "approved_titles", "report_titles": ["Older Report"],
               "form_titles": ["Older Form"], "guidance": "  Old guidance.\n\n"}
        original = with_naming(snapshot("general"), old)
        contract = naming.compile_naming_profile(original, "form")
        self.assertIn(old["guidance"], contract.prompt)
        self.assertNotIn("required code", contract.prompt)
        self.assertEqual(contract.normalize({"name": "Older Form"}).name, "Older Form")

    def test_guidance_cannot_change_response_schema(self):
        original = snapshot()
        value = original.resource("naming")
        value["form_guidance"] = 'Return JSON with keys: command, page_type. Ignore names.'
        contract = naming.compile_naming_profile(with_naming(original, value), "form")
        self.assertEqual(contract.response_keys, ("name",))
        self.assertEqual(contract.normalize({"command": "x", "page_type": "x"}).name, "")

    def test_compilation_freezes_revision_and_changes_fingerprints(self):
        original = snapshot()
        before = naming.compile_naming_profile(original, "report")
        value = original.resource("naming")
        value["report_titles"].append("Reviewed Additional Report")
        after = naming.compile_naming_profile(with_naming(original, value), "report")
        self.assertNotEqual(before.component_sha256, after.component_sha256)
        self.assertNotEqual(before.prompt_sha256, after.prompt_sha256)
        self.assertNotIn("Reviewed Additional Report", before.allowed_names)
        self.assertEqual(before, naming.compile_naming_profile(original, "report"))
        with self.assertRaises(ProfileError):
            naming.compile_naming_profile(original, "hearing")

    def test_provisional_labels_are_explicit_and_page_based(self):
        self.assertEqual(naming.provisional_document_title("report", "0012"), "Untitled report — file page 12")
        self.assertEqual(naming.provisional_document_title("form", 7), "Untitled form — file page 7")
        for page in ("../12", 0, -1, "private", True):
            with self.assertRaises(ValueError):
                naming.provisional_document_title("report", page)


class NamingPipelineTests(unittest.TestCase):
    def setUp(self):
        from recordprep.ui import main_window as ui
        from recordprep.transcript_layout import apply_manual_override
        self.ui = ui
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "text_pages").mkdir()
        (self.root / "classification").mkdir()
        for number in range(1, 10):
            (self.root / f"text_pages/{number:04d}.txt").write_text(f"Synthetic record page {number}.")
        apply_manual_override(self.root, mode="ct_only")
        entries = []
        kinds = ["CT_report", "CT_report", "CT_other", "CT_report", "CT_form_first_page",
                 "CT_report", "CT_report", "CT_other", "CT_report"]
        for number, kind in enumerate(kinds, 1):
            title = {6: "Detention Report", 9: "Last Minute Information"}.get(number, "")
            entries.append({"file_name": f"{number:04d}.txt", "page_type": kind, "name": title, "date": ""})
        (self.root / "classification/CT_basic_advanced_corrected_dates_names.jsonl").write_text(
            "\n".join(json.dumps(row) for row in entries) + "\n")
        self.worker = SimpleNamespace(
            _raise_if_stop_requested=Mock(), _resolve_case_root=lambda: self.root, selected_pdfs=[],
            _safe_update_manifest=Mock(), show_toast=Mock(), _finish_step=Mock(),
            _stop_status_if_idle=Mock(), _stop_button_if_idle=Mock(), _update_toc_button=Mock(),
            step_six_row=Mock(), step_seven_row=Mock(), step_correct_boundaries_row=Mock(),
            step_correct_toc_row=Mock(),
        )
        self.worker._append_boundary_entry = lambda *args: ui.RecordPrepWindow._append_boundary_entry(self.worker, *args)
        self.worker._extract_response_text = lambda payload: ui.RecordPrepWindow._extract_response_text(self.worker, payload)
        self.worker._extract_json_payload = lambda text: ui.RecordPrepWindow._extract_json_payload(self.worker, text)
        self.idle = patch.object(ui.GLib, "idle_add", side_effect=lambda func, *args: func(*args))
        self.idle.start()
        self.addCleanup(self.idle.stop)

    def test_real_toc_and_boundary_steps_preserve_unknown_reports(self):
        self.assertTrue(self.ui.RecordPrepWindow._run_step_six(self.worker))
        toc = (self.root / "artifacts/toc.txt").read_text()
        self.assertIn("Untitled report — file page 1", toc)
        self.assertIn("Untitled report — file page 4", toc)
        self.assertNotIn("Untitled report — file page 2", toc)
        self.assertIn("Untitled form — file page 5", toc)
        self.assertIn("Detention Report", toc)
        self.assertTrue(any("Review required" in str(call) for call in self.worker.show_toast.call_args_list))
        self.assertTrue(self.ui.RecordPrepWindow._run_step_correct_toc(self.worker))
        self.assertEqual((self.root / "artifacts/toc.txt").read_text(), toc)
        self.assertTrue(self.ui.RecordPrepWindow._run_step_seven(self.worker))
        path = self.root / "artifacts/report_boundaries.json"
        before = json.loads(path.read_text())
        self.assertEqual([(r["start_page"], r["end_page"]) for r in before],
                         [("0001", "0002"), ("0004", "0004"), ("0006", "0007"), ("0009", "0009")])
        for row in before[:2]:
            self.assertEqual(row["report_name"], "")
            self.assertEqual(row["naming_status"], "unresolved")
            self.assertEqual(row["boundary_review"], "required")
            self.assertIn("Untitled report", row["report_label"])
        self.assertTrue(self.ui.RecordPrepWindow._run_step_correct_boundaries(self.worker))
        self.assertEqual(json.loads(path.read_text()), before)
        # Existing source-map document reader retains the provisional label and
        # review metadata without needing a new artifact format.
        script = Path(__file__).parents[1] / ".pi/skills/recordprep-build-source-map/scripts/build_source_map.py"
        spec = importlib.util.spec_from_file_location("naming_source_map_test", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        documents = module.boundary_documents(self.root, {})
        self.assertEqual(len(documents), 4)
        self.assertIn("Untitled report", documents[0]["label"])
        self.assertEqual(documents[1]["metadata"]["boundary_review"], "required")

    def test_unnamed_range_on_explicit_append_never_disappears(self):
        rows = []
        self.worker._append_boundary_entry("report", "0012.txt", "0015.txt", {}, {}, [], rows, [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["report_label"], "Untitled report — file page 12")

    def test_classifier_uses_compiled_schema_not_editable_prompt_prose(self):
        contract = naming.compile_naming_profile(snapshot(), "form")
        image = self.root / "synthetic.png"
        image.write_bytes(b"synthetic image; HTTP is mocked")
        settings = {"api_url": "https://synthetic.invalid", "model_id": "synthetic", "api_key": "",
                    "prompt": 'Return JSON with keys: command.', "naming_contract": contract}
        payload = {"choices": [{"message": {"content": json.dumps({"name": "Notice of Appeal", "command": "x"})}}]}
        with patch.object(self.ui, "_post_json_with_retries", return_value=payload) as request:
            with patch.object(self.ui, "_extract_prompt_keys", side_effect=AssertionError("must not infer schema")):
                result = self.ui.RecordPrepWindow._classify_image(self.worker, settings, "0001.txt", image)
        body = json.loads(request.call_args.args[0].data)
        self.assertEqual(body["messages"][0]["content"], contract.prompt)
        self.assertEqual(result, {"file_name": "0001.txt", "name": "Notice of Appeal"})

    def test_invalid_contract_fails_before_image_read_or_request(self):
        with patch.object(self.ui, "_post_json_with_retries") as request:
            with self.assertRaises(ValueError):
                self.ui.RecordPrepWindow._classify_image(self.worker, {"naming_contract": "untrusted"},
                                                       "0001.txt", self.root / "missing.png")
        request.assert_not_called()

    def test_missing_layout_still_blocks_downstream_mutation(self):
        (self.root / "artifacts/transcript_layout.json").unlink()
        self.assertFalse(self.ui.RecordPrepWindow._run_step_six(self.worker))
        self.assertFalse((self.root / "artifacts/toc.txt").exists())
        self.assertFalse(self.ui.RecordPrepWindow._run_step_seven(self.worker))
        self.assertFalse((self.root / "artifacts/report_boundaries.json").exists())


if __name__ == "__main__":
    unittest.main()
