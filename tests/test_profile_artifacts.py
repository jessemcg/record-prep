"""Common reader contract; synthetic metadata, no profile-store access."""
import copy
import importlib
import unittest
from pathlib import Path

PACKAGE = "focus" if (Path(__file__).resolve().parents[1] / "focus").is_dir() else "recordprep"
a = importlib.import_module(f"{PACKAGE}.profile_artifacts")


def provenance(stage="participants"):
    return {"schema_version": 1, "profile_ref": {"specialty_id": "synthetic-civil", "application": "recordprep",
            "version": "1", "profile_api": 1, "content_sha256": "a" * 64}, "components": {stage: "b" * 64}}


def roles():
    return {group: [{"id": "unknown", "label": "Unknown"}, {"id": "other", "label": "Other"},
                    {"id": role, "label": label}]
            for group, role, label in (("counsel", "plaintiffs_counsel", "Plaintiff Counsel"),
                                      ("participants", "plaintiff", "Plaintiff"))}


def participant():
    return {"schema_version": 3, "source": "record-participant-index", "role_catalog": roles(),
            "profile_provenance": provenance(), "warnings": [], "hearings": [{
                "id": "hearing:0001", "start_page": 1, "end_page": 3, "warnings": [],
                "witness_status": "unknown", "witness_evidence": [], "witnesses": [],
                "counsel": [{"name": "Synthetic Counsel", "role_id": "plaintiffs_counsel", "aliases": [],
                             "organization": "", "appearance_status": "present", "evidence": [{"text_path": "text_pages/0001.txt"}]}],
                "participants": [{"id": "person-1", "name": "Synthetic Party", "role_id": "plaintiff",
                                  "role_label": "Plaintiff", "aliases": [], "attendance_status": "unknown",
                                  "speaking_status": "unknown", "sworn_status": "unknown", "evidence": [{"text_path": "text_pages/0001.txt"}]}]}]}


class ArtifactContractTests(unittest.TestCase):
    def test_new_roles_need_no_installed_profile(self):
        data = participant()
        before = copy.deepcopy(data)
        self.assertEqual(a.participant_index_issues(data), [])
        self.assertEqual(data, before)
        data["role_catalog"]["participants"][-1] = {"id": "claimant", "label": "Claimant"}
        data["hearings"][0]["participants"][0].update(role_id="claimant", role_label="Claimant")
        self.assertEqual(a.participant_index_issues(data), [])
        self.assertEqual(a.participant_index_issues(before), [])

    def test_evidence_and_witness_safeguards_still_apply(self):
        for mutate in (
            lambda h: h["participants"][0].update(evidence=[]),
            lambda h: h["participants"][0].update(attendance_status="assumed"),
            lambda h: h["participants"][0].update(role_label="Wrong label"),
            lambda h: h["participants"][0].update(role_id=[]),
            lambda h: h.update(witness_status="verified"),
            lambda h: h.update(warnings=[a.PARTICIPANT_TEMPLATE_WARNING]),
            lambda h: h["counsel"][0].update(role_id="undeclared"),
            lambda h: h["participants"][0].update(evidence=[{"text_path": "../outside"}]),
            lambda h: h["participants"][0].update(evidence=["not an evidence object"]),
        ):
            data = participant()
            mutate(data["hearings"][0])
            self.assertTrue(a.participant_index_issues(data))

    def test_legacy_roles_are_frozen(self):
        data = participant()
        data["schema_version"] = 2
        del data["role_catalog"], data["profile_provenance"]
        self.assertTrue(a.participant_index_issues(data))
        data["hearings"][0]["counsel"][0]["role_id"] = "mothers_counsel"
        data["hearings"][0]["participants"][0]["role_id"] = "mother"
        self.assertEqual(a.participant_index_issues(data), [])

    def test_descriptor_bounds_and_instruction_rejection(self):
        invalid = [[], [{"id": "x", "title": "X", "guidance": "do things"}],
                   [{"id": "x", "title": "X"}] * 2, [{"id": "x", "title": "X\nheader"}],
                   [{"id": "x", "title": "x" * 161}], [{"id": "../x", "title": "X"}]]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                a.descriptors(value)
        data = roles()
        data["counsel"].pop(0)
        with self.assertRaises(ValueError):
            a.validate_role_descriptor(data)

    def test_source_map_profile_and_future_versions(self):
        data = {"schema_version": 3, "pages": [], "preparation_provenance": provenance(),
                "participant_index": participant()}
        self.assertEqual(a.source_map_profile_metadata(data), provenance())
        for version in (True, "3", 4, 99):
            with self.assertRaises(ValueError):
                a.source_map_profile_metadata(data | {"schema_version": version})
        with self.assertRaises(ValueError):
            a.source_map_profile_metadata(data | {"preparation_provenance": None})
        with self.assertRaises(ValueError):
            a.source_map_profile_metadata(data | {"schema_version": 2})
        self.assertIsNone(a.source_map_profile_metadata({"schema_version": 2, "pages": []}))
        self.assertIsNone(a.source_map_profile_metadata({"pages": []}))

    def test_provenance_no_paths_or_instructions(self):
        for value in (provenance() | {"path": "/tmp/untrusted"}, provenance() | {"components": {"execute": "b" * 64}},
                      provenance() | {"schema_version": True}, provenance() | {"components": {"participants": "bad"}}):
            with self.assertRaises(ValueError):
                a.preparation_provenance(value)
        data = provenance()
        data["profile_ref"]["application"] = "focus"
        with self.assertRaises(ValueError):
            a.preparation_provenance(data)

    def test_ct_only_allows_empty_but_does_not_invent_participants(self):
        data = participant()
        data["hearings"] = []
        self.assertTrue(a.participant_index_issues(data))
        self.assertEqual(a.participant_index_issues(data, allow_empty=True), [])
        self.assertEqual(data["hearings"], [])


if __name__ == "__main__":
    unittest.main()
