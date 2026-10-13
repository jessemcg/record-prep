"""General identification contracts, no private records or live model calls."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from recordprep import minute_summaries as minutes, summary_agents as sa
from recordprep.native_profiles import compile_native
from recordprep.profile_contract import compile_stage_profile, validate_contents, json_bytes
from recordprep.profile_workflows import ProfileEditor
from test_practice_profiles import historical_snapshot
from test_profile_generation import bundled
from test_profile_artifacts import general_participant
from test_native_profiles import load, PROJECT
from test_participant_stage import _review_general_hearing


class GeneralParticipantTests(unittest.TestCase):
    def test_historical_role_and_identification_settings_are_inert_everywhere(self):
        current = bundled("general")
        old = historical_snapshot(current)
        original = old.files
        editor = ProfileEditor(old)
        editor.resources["participants"] = "RETIRED_IDENTIFICATION_CANARY"
        for group in editor.resources["roles"].values():
            for role in group:
                role["guidance"] = "RETIRED_ROLE_CANARY"
        edited = editor.snapshot()
        for profile in (current, old, edited):
            prompt, meta = compile_native(profile, "participants", PROJECT / ".pi")
            self.assertEqual(prompt, compile_native(current, "participants", PROJECT / ".pi")[0])
            self.assertNotIn("CANARY", prompt)
            self.assertEqual(meta["components"], compile_native(current, "participants", PROJECT / ".pi")[1]["components"])
            self.assertEqual(minutes.profile_guidance(profile), minutes.profile_guidance(current))
            for stage in ("participants", "minutes", "hearing_extraction", "hearing_synthesis", "overview"):
                compiled = compile_stage_profile(profile, stage, core_contract=b"synthetic-fixed-core")
                self.assertEqual(compiled.component_sha256,
                    compile_stage_profile(current, stage, core_contract=b"synthetic-fixed-core").component_sha256)
                self.assertFalse({"roles", "participants"}.intersection(dict(compiled.resources)))
        self.assertEqual(old.files, original)
        self.assertEqual(validate_contents(old.files, "recordprep").files, original)

    def test_schema_four_rejects_retired_resources(self):
        old = historical_snapshot(bundled("general"))
        files = dict(old.files)
        manifest = old.manifest
        manifest["schema_version"] = 4
        files["profile.json"] = json_bytes(manifest)
        with self.assertRaises(ValueError):
            validate_contents(tuple(files.items()), "recordprep")

    def test_general_metadata_survives_summary_and_source_map_navigation(self):
        data = general_participant()
        hearing = _review_general_hearing({"id": "hearing:0001", "start_page": 1, "end_page": 6}, 1)
        hearing["counsel"][0].update(role_label="Counsel for intervenor", represents="Synthetic Union")
        hearing["participants"][0]["role_label"] = "Court-appointed technical adviser"
        hearing["witnesses"][0]["examinations"][0]["examiner_role_label"] = "Counsel for intervenor"
        data["hearings"] = [hearing]
        context = sa._hearing_participant_context(hearing)
        for text in ("represents: Synthetic Union", "Counsel for intervenor", "Court-appointed technical adviser", "Attorney 1"):
            self.assertIn(text, context)
        helper = load("general_map_helper", PROJECT / ".pi/skills/recordprep-build-source-map/scripts/build_source_map.py")
        lookup = helper.build_lookup([], [], data)
        self.assertIn("synthetic union", lookup["by_counsel"])
        self.assertIn("counsel for intervenor", lookup["by_counsel"])
        self.assertIn("court-appointed technical adviser", lookup["by_participant"])
        pages = {n: {"document_ids": [], "hearing_id": "", "witnesses": [], "examinations": []} for n in range(1, 7)}
        helper.annotate_pages(pages, [], data)
        self.assertEqual(pages[3]["examinations"][0]["examiner_role_label"], "Counsel for intervenor")
        self.assertIn("Counsel for intervenor", pages[1]["counsel_roles"])

    def test_general_witness_and_examination_safeguards(self):
        from recordprep.profile_artifacts import participant_index_issues
        data = general_participant()
        data["hearings"] = [_review_general_hearing({"id": "hearing:0001", "start_page": 1, "end_page": 6}, 1)]
        self.assertEqual(participant_index_issues(data), [])
        for mutate in (
            lambda h: h["witnesses"][0]["examinations"][0].update(start_file_page=99),
            lambda h: h["witnesses"][0]["examinations"][0].update(examiner_role_id="mother"),
            lambda h: h["witnesses"][0]["examinations"][0].update(examiner_role_label=[]),
            lambda h: h["witnesses"][0]["examinations"][0].update(type="invented"),
            lambda h: h["witnesses"][0].update(name=h["counsel"][0]["name"]),
            lambda h: h["witnesses"][0].update(examinations=[]),
        ):
            bad = copy.deepcopy(data)
            mutate(bad["hearings"][0])
            self.assertTrue(participant_index_issues(bad))
        data["hearings"][0]["witnesses"][0]["name"] = data["hearings"][0]["counsel"][0]["name"]
        data["hearings"][0].update(witness_status="conflict", warnings=["Counsel independently sworn; review unusual evidence."])
        self.assertEqual(participant_index_issues(data), [])

    def test_minute_roles_come_only_from_order_not_index_or_profile_catalog(self):
        source = "The receiver appeared remotely. Distribution approved."
        item = minutes.MinuteItem("minute:0001", 1, "Synthetic", 1, 1, source, source, "fingerprint", ((1, source),))
        candidate = {"artifact": "recordprep-minute-candidate", "hearing": "Distribution hearing",
                     "appearances": [{"person": "Receiver", "role_label": "Court-appointed receiver", "status": "present",
                                      "evidence": [{"file_page": 1, "text": "The receiver appeared remotely"}]}],
                     "positions": "", "orders": "Distribution approved.", "next_hearing": "Next hearing not stated."}
        profile = bundled("general")
        with patch.object(sa, "_participant_index", side_effect=AssertionError("Minute stage must not read index")):
            row = minutes.normalize_candidate(candidate, item, profile=profile)
            self.assertEqual(row["appearances"][0]["role_label"], "Court-appointed receiver")
            self.assertEqual(row["appearances"][0]["status"], "present")
            self.assertNotIn("role_id", row["appearances"][0])
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "case_name.txt").write_text("Synthetic")
                minutes.publish_rows(root, [row], profile=profile)
                self.assertEqual(minutes.load_rows(root), [row])
                self.assertNotIn("role_catalog", json.loads(minutes.checkpoint_path(root).read_text()))
        invalid = copy.deepcopy(candidate)
        invalid["appearances"][0].pop("role_label")
        row = minutes.normalize_candidate(invalid, item, profile=profile)
        self.assertEqual(row["appearances"][0]["role_label"], "Unknown")
        self.assertIn("unresolved_role", row["quality_flags"])


if __name__ == "__main__":
    unittest.main()
