"""Minute-order presentation and fixed attendance; synthetic source only."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from recordprep import minute_summaries as minutes, summary_agents as sa
from test_profile_generation import bundled, changed


class MinuteProfileSummaryTests(unittest.TestCase):
    def setUp(self):
        self.profile = bundled("california_dependency")
        self.page1 = "Six-month review hearing. Mother appeared by video. Mother objects to termination of services."
        self.page2 = "Father did not appear. Services continued. Twelve-month review set for June 10, 2026 at 9:00 a.m."
        self.item = minutes.MinuteItem("minute:0001", 1, "December 10, 2025", 1, 2,
            self.page1 + "\n" + self.page2, self.page1, "synthetic-fingerprint", ((1, self.page1), (2, self.page2)))
        self.candidate = {
            "artifact": "recordprep-minute-candidate", "hearing": "Six-month review hearing",
            "appearances": [
                {"person": "Mother", "role_label": "Mother", "status": "present",
                 "evidence": [{"file_page": 1, "text": "Mother appeared by video"}]},
                {"person": "Father", "role_label": "Father", "status": "not_present",
                 "evidence": [{"file_page": 2, "text": "Father did not appear"}]},
            ],
            "positions": "Mother objected to termination of services.",
            "orders": "The court continued services.",
            "next_hearing": "Twelve-month review set for June 10, 2026 at 9:00 a.m.",
        }

    def row(self, candidate=None, profile=None):
        return minutes.normalize_candidate(candidate or self.candidate, self.item, profile=profile or self.profile)

    def test_complete_paragraph_in_requested_order_without_reporting(self):
        paragraph = minutes.render_paragraph(self.row())
        self.assertEqual(paragraph, "Six-month review hearing. Mother appeared. Father did not appear. "
            "Mother objected to termination of services. The court continued services. "
            "Twelve-month review set for June 10, 2026 at 9:00 a.m.")
        self.assertNotIn("reporting", self.row())
        self.assertNotIn("\n", paragraph)

    def test_later_page_attendance_ignores_all_historical_policy_choices(self):
        for policy in ("legacy_first_page_parents", "explicit_complete_order"):
            revised = changed(self.profile, "policies", {"attendance": policy})
            self.assertEqual(self.row(profile=revised), self.row())
            self.assertEqual(minutes.profile_guidance(revised), minutes.profile_guidance(self.profile))
            self.assertEqual(minutes._profile_provenance(revised)["components"],
                             minutes._profile_provenance(self.profile)["components"])
        self.assertEqual(self.row()["appearances"][1]["status"], "not_present")

    def test_unverified_present_and_absent_remain_unclear(self):
        for status in ("present", "not_present"):
            candidate = copy.deepcopy(self.candidate)
            candidate["appearances"][0].update(status=status, evidence=[{"file_page": 99, "text": "Mother appeared"}])
            row = self.row(candidate)
            self.assertEqual(row["appearances"][0]["status"], "unclear")
            self.assertIn("Mother appearance unclear.", minutes.render_paragraph(row))
        prompt = minutes.profile_guidance(self.profile)
        self.assertIn("Counsel appearing\nalone establishes neither a client's presence nor absence", prompt)
        self.assertIn("A missing name is not\nproof of absence", prompt)
        self.assertIn("Do not invent arguments or assume silence means agreement", ' '.join(prompt.split()))
        self.assertNotIn("ATTENDANCE POLICY:", prompt)

    def test_no_positions_or_next_setting_are_not_invented(self):
        candidate = self.candidate | {"positions": "", "next_hearing": "Next hearing not stated."}
        paragraph = minutes.render_paragraph(self.row(candidate))
        self.assertNotIn("Mother objected", paragraph)
        self.assertTrue(paragraph.endswith("Next hearing not stated."))
        missing = dict(candidate)
        missing.pop("next_hearing")
        row = self.row(missing)
        self.assertEqual(row["next_hearing"], "Next hearing unclear.")
        self.assertIn("next_hearing_unusable", row["quality_flags"])

    def test_exact_old_default_is_readable_and_resolved_without_modification(self):
        legacy_text = next(text for text, specialty in minutes._HISTORICAL_MINUTE_GUIDANCE.items()
                           if specialty == "california_dependency") + "\n"
        historical = changed(self.profile, "minutes", legacy_text)
        original = historical.files
        guidance = minutes.profile_guidance(historical)
        self.assertNotIn("selected legacy policy", guidance)
        self.assertIn("alternatives to guide selection", guidance)
        self.assertIn("short type only", guidance)
        self.assertEqual(historical.files, original)
        self.assertEqual(historical.resource("minutes"), legacy_text)
        custom = changed(self.profile, "minutes", "Synthetic personal minute guidance.\n")
        self.assertEqual(minutes.minute_profile_text(custom), custom.resource("minutes"))

    def test_new_checkpoint_roundtrip_and_old_reader_compatibility(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "case_name.txt").write_text("Synthetic")
            row = self.row()
            minutes.publish_rows(root, [row], profile=self.profile)
            payload = json.loads(minutes.checkpoint_path(root).read_text())
            self.assertEqual(payload["schema_version"], 4)
            self.assertNotIn("attendance_policy", payload)
            self.assertNotIn("role_catalog", payload)
            self.assertEqual(minutes.load_rows(root), [row])
            # Freeze a historical schema-2 row, including its former reporting output.
            old = copy.deepcopy(row)
            roles = [{"id": label.lower(), "label": label} for label in ("Mother", "Father", "Unknown", "Other")]
            for person in old["appearances"]:
                person["role_id"] = person.pop("role_label").lower()
            payload["role_catalog"] = {"counsel": roles, "participants": roles}
            # Schema 3 is still read as written, too.
            payload.update(schema_version=3, rows=[old], rows_sha256=sa.sha256_json([old]),
                           attendance_policy="explicit_complete_order")
            minutes.checkpoint_path(root).write_text(json.dumps(payload))
            self.assertEqual(minutes.load_rows(root), [old])
            old.pop("positions")
            old.pop("next_hearing")
            old["reporting"] = "reported"
            payload.update(schema_version=2, rows=[old], rows_sha256=sa.sha256_json([old]),
                           attendance_policy="legacy_first_page_parents")
            source = json.dumps(payload)
            minutes.checkpoint_path(root).write_text(source)
            self.assertEqual(minutes.load_rows(root), [old])
            self.assertIn("Reported.", minutes.render_paragraph(old))
            self.assertEqual(minutes.checkpoint_path(root).read_text(), source)
            with self.assertRaises(ValueError):
                minutes.publish_rows(root, [row])

    def test_new_checkpoint_requires_positions_next_hearing_and_fixed_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "case_name.txt").write_text("Synthetic")
            minutes.publish_rows(root, [self.row()], profile=self.profile)
            path = minutes.checkpoint_path(root)
            payload = json.loads(path.read_text())
            payload["attendance_policy"] = "legacy_first_page_parents"
            path.write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                minutes.load_rows(root)
            payload.pop("attendance_policy")
            payload["rows"][0].pop("positions")
            payload["rows_sha256"] = sa.sha256_json(payload["rows"])
            path.write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                minutes.load_rows(root)


if __name__ == "__main__":
    unittest.main()
