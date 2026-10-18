"""Compact minute publication, exact built-in compatibility and stage isolation.

All orders/people are fictional. No model calls or private profile/config access.
"""
from __future__ import annotations

from copy import deepcopy
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from recordprep import minute_summaries as minutes, summary_agents as sa
from recordprep.case_profiles import apply_case_profile
from recordprep.profile_contract import compile_stage_profile
from recordprep.profile_store import ProfileStore
from recordprep.summary_editions import build_summary_edition, validate_edition_payload
from test_minute_summaries import fixture
from test_profile_generation import bundled, changed, seed_profile_preparation


SOURCE = "Applicant Alex Vale present. Respondent Sam Reed represented by counsel."


def candidate():
    return {"artifact": "recordprep-minute-candidate", "hearing": "Motion to compel",
            "appearances": [
                {"person": "Alex Vale", "role_label": "Applicant", "status": "present",
                 "evidence": [{"file_page": 1, "text": "Applicant Alex Vale present."}]},
                {"person": "Sam Reed", "role_label": "Respondent", "status": "unclear", "evidence": []}],
            "orders": "Disclosure ordered by May 21, subject to the protective order; unrestricted disclosure denied.",
            "next_hearing": "Review June 4."}


def item():
    return minutes.MinuteItem("minute:0001", 1, "May 7, 2030", 1, 1,
                              SOURCE, SOURCE, "fictional", ((1, SOURCE),))


def normalized():
    # Location verification is not semantic attendance/attribution acceptance.
    return minutes.normalize_candidate(candidate(), item(), profile=bundled("general"))


class CompactMinuteTests(unittest.TestCase):
    def test_date_and_hearing_share_header_with_only_three_unbulleted_labels(self):
        row = normalized()
        self.assertEqual(minutes.render_compact_entry(item(), row), [
            "May 7, 2030 — Motion to compel",
            "Appearances: Applicant present; Respondent's appearance unclear.",
            "Orders: Disclosure ordered by May 21, subject to the protective order; unrestricted disclosure denied.",
            "Next: Review June 4."])
        self.assertNotIn("positions_unusable", row["quality_flags"])
        self.assertEqual(row["positions"], "")  # Schema-4 compatibility, not a tool requirement.

    def test_next_policy_excludes_reports_across_shared_and_specialty_guidance(self):
        with TemporaryDirectory() as td:
            _root, project = fixture(Path(td), 1)
            skill = (project / "skills" / minutes.SKILL_NAME / "SKILL.md").read_text()
            tool = (project / "extensions/recordprep-profile-minute-tools.ts").read_text()
            self.assertIn("Exclude report-only hearings", skill)
            self.assertIn("even when scheduled earlier", skill)
            self.assertIn("Exclude report-only hearings", tool)
            for specialty in ("general", "california_dependency"):
                profile = bundled(specialty)
                config = minutes.stage_config(project, profile=profile)[1]
                self.assertEqual(config["contract_version"], 8)
                self.assertIn("give only the next substantive hearing type/date", config["guidance"])
                self.assertIn("Exclude report-only hearings", config["guidance"])
                self.assertIn("Do not move that report calendar into orders", config["guidance"])
                self.assertNotIn("useful report date", profile.resource("minutes"))
                self.assertNotIn("report due August", profile.resource("minutes"))

    def test_contract6_report_calendar_stays_readonly_until_explicit_regeneration(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            root, project = fixture(base, 1)
            (root / "text_pages/0001.txt").write_text(
                SOURCE + " Report receipt May 21; report due May 28; review June 4.")
            profile = bundled("general")
            store = ProfileStore("recordprep", config_root=base / "config", data_root=base / "data")
            store.accept_profile(profile, expected_previous_digest=None)
            apply_case_profile(root, profile.ref, expected_previous=None, store=store)
            settings, config = minutes.stage_config(project, profile=profile)
            previous = config | {"contract_version": 6, "presentation": minutes.LEGACY_COMPACT_PRESENTATION}
            old_candidate = candidate() | {"next_hearing": "Report receipt May 21; report due May 28; review June 4."}
            with patch("recordprep.case_profiles.profile_store", return_value=store):
                seed_profile_preparation(root, profile, project)
                with patch.object(minutes, "stage_config", return_value=(settings, previous)):
                    minutes.run_stage(root, project, Mock(return_value=old_candidate))
                final = sa.summary_final_path(root, "minutes")
                protected = (final, minutes.meta_path(root), minutes.checkpoint_path(root),
                             store.registry_path, project.parent / "config.json")
                before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in protected}
                self.assertTrue(minutes.freshness_issues(root, project))
                self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in protected})
                generator = Mock(return_value=candidate())  # Offline protocol check, not model-quality proof.
                minutes.run_stage(root, project, generator)
                generator.assert_called_once()
                self.assertIn("Next: Review June 4.", final.read_text())
                self.assertNotIn("Report receipt May 21", final.read_text())
                self.assertNotIn("report due May 28", final.read_text())
                self.assertEqual(minutes.freshness_issues(root, project), [])
                generator.reset_mock()
                minutes.run_stage(root, project, generator)
                generator.assert_not_called()
                for p in protected[-2:]:
                    self.assertEqual(before[p], (p.read_bytes(), p.stat().st_mtime_ns))

    def test_appearances_keep_individual_identity_when_roles_are_not_unique(self):
        row = normalized()
        row["appearances"][1]["role_label"] = "Applicant"
        row["appearances"][1]["status"] = "not_present"
        self.assertIn("Alex Vale present; Sam Reed absent.", minutes.render_compact_entry(item(), row)[1])
        row["appearances"] = []
        self.assertEqual(minutes.render_compact_entry(item(), row)[1], "Appearances: Not established.")
        row["appearances"] = [{"person": "Unknown", "role_label": "Unknown", "status": "unclear", "evidence": []}]
        self.assertEqual(minutes.render_compact_entry(item(), row)[1], "Appearances: Not established.")
        row["appearances"][0]["role_label"] = "Respondent"
        self.assertIn("Respondent's appearance unclear.", minutes.render_compact_entry(item(), row)[1])

    def test_no_mechanical_outcome_truncation_or_loss_of_compatibility_positions(self):
        row = normalized()
        row["orders"] = "An independently consequential ruling. " * 12
        row["positions"] = "Respondent objected to this ruling."
        self.assertEqual(minutes.render_compact_entry(item(), row)[2],
                         "Orders: " + row["orders"] + " " + row["positions"])
        for old, short in (("Next hearing not stated.", "Not stated."), ("Next hearing unclear.", "Unclear.")):
            row["next_hearing"] = old
            self.assertEqual(minutes.render_compact_entry(item(), row)[3], "Next: " + short)

    def test_legacy_rendering_default_remains_paragraph_based(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            row = normalized()
            old = minutes.render_final(root, [item()], [row])
            new = minutes.render_final(root, [item()], [row], presentation=minutes.COMPACT_PRESENTATION)
            self.assertIn(minutes.render_paragraph(row), old)
            self.assertNotIn("- Main rulings:", old)
            self.assertIn("May 7, 2030 — Motion to compel\nAppearances:", new)
            self.assertEqual(new.count("Orders:"), 1)
            legacy = minutes.render_final(root, [item()], [row], presentation=minutes.LEGACY_COMPACT_PRESENTATION)
            self.assertIn("\n- Main rulings: " + row["orders"], legacy)
            self.assertNotIn("\nOrders:", legacy)

    def test_all_exact_predecessor_builtins_resolve_readonly_but_custom_bytes_survive(self):
        for text, specialty in minutes._HISTORICAL_MINUTE_GUIDANCE.items():
            with self.subTest(specialty=specialty, prefix=text[:60]):
                profile = changed(bundled(specialty), "minutes", text)
                original = deepcopy(profile.files)
                self.assertEqual(minutes.minute_profile_text(profile), bundled(specialty).resource("minutes"))
                self.assertEqual(profile.files, original)
                self.assertEqual(profile.resource("minutes"), text)
        custom = "Custom specialty priorities. Keep my own prose, punctuation and spacing.\n"
        profile = changed(bundled("general"), "minutes", custom)
        original = deepcopy(profile.files)
        self.assertEqual(minutes.minute_profile_text(profile), custom)
        self.assertEqual(profile.files, original)
        old = next(text for text, specialty in minutes._HISTORICAL_MINUTE_GUIDANCE.items()
                   if specialty == "general" and text.startswith("Summarize each"))
        near = changed(bundled("general"), "minutes", old + " Custom emphasis.")
        self.assertEqual(minutes.minute_profile_text(near), old + " Custom emphasis.")

    def test_cached_status_watches_resolved_public_focus_without_private_writes(self):
        from recordprep.practice_profiles import bundled_profile_directory
        with TemporaryDirectory() as td:
            base = Path(td)
            root, project = fixture(base, 1)
            (root / "text_pages/0001.txt").write_text(SOURCE)
            defaults = base / "public-defaults"
            shutil.copytree(bundled_profile_directory("general"), defaults)
            old_text = next(text for text, name in minutes._HISTORICAL_MINUTE_GUIDANCE.items()
                            if name == "general" and text.startswith("Summarize each"))
            historical = changed(bundled("general"), "minutes", old_text)
            store = ProfileStore("recordprep", config_root=base / "config", data_root=base / "data")
            store.accept_profile(historical, expected_previous_digest=None)
            apply_case_profile(root, historical.ref, expected_previous=None, store=store)
            with patch("recordprep.case_profiles.profile_store", return_value=store), \
                    patch("recordprep.practice_profiles.bundled_profile_directory", return_value=defaults):
                seed_profile_preparation(root, historical, project)
                minutes.run_stage(root, project, Mock(return_value=candidate()))
                self.assertTrue(minutes.stage_complete(root, project))  # Warm the cache.
                protected = (sa.summary_final_path(root, "minutes"), minutes.meta_path(root),
                             minutes.checkpoint_path(root), store.registry_path,
                             store.data_root / "snapshots" / historical.ref.content_sha256 / "minutes.md")
                before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in protected}
                focus = defaults / "minutes.md"
                focus.write_text(focus.read_text() + "\nFictional additional specialty emphasis.\n")
                self.assertFalse(minutes.stage_complete(root, project))  # No manual cache clearing.
                self.assertTrue(minutes.freshness_issues(root, project))
                self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in protected})

    def test_bundled_resource_changes_are_minute_only(self):
        for specialty in ("general", "california_dependency"):
            current = bundled(specialty)
            old_text = next(text for text, name in minutes._HISTORICAL_MINUTE_GUIDANCE.items()
                            if name == specialty and text.startswith("Summarize each"))
            old = changed(current, "minutes", old_text)
            for stage in ("classification", "participants", "hearing_extraction", "hearing_synthesis",
                          "report_extraction", "report_synthesis", "overview", "naming"):
                with self.subTest(specialty=specialty, stage=stage):
                    a = compile_stage_profile(old, stage, core_contract=b"unchanged")
                    b = compile_stage_profile(current, stage, core_contract=b"unchanged")
                    self.assertEqual(a.component_sha256, b.component_sha256)
            self.assertNotEqual(compile_stage_profile(old, "minutes", core_contract=b"unchanged").component_sha256,
                                compile_stage_profile(current, "minutes", core_contract=b"unchanged").component_sha256)

    def test_old_prose_stays_readonly_until_explicit_compact_generation_and_pdf(self):
        for specialty in ("general", "california_dependency"):
            with self.subTest(specialty=specialty), TemporaryDirectory() as td:
                base = Path(td)
                root, project = fixture(base, 2)
                boundaries = root / "artifacts/minutes_boundaries.json"
                data = json.loads(boundaries.read_text())
                for record in data:
                    record["date"] = "May 7, 2030"
                boundaries.write_text(json.dumps(data))
                for source in (root / "text_pages").glob("*.txt"):
                    source.write_text(SOURCE)
                store = ProfileStore("recordprep", config_root=base / "config", data_root=base / "data")
                profile = bundled(specialty)
                store.accept_profile(profile, expected_previous_digest=None)
                apply_case_profile(root, profile.ref, expected_previous=None, store=store)
                current_settings, current_config = minutes.stage_config(project, profile=profile)
                previous_config = {key: value for key, value in current_config.items() if key != "presentation"}
                previous_config["contract_version"] = 5
                def generate(current, *_args):
                    result = candidate()
                    result["appearances"][0]["evidence"][0]["file_page"] = current.start
                    return result
                with patch("recordprep.case_profiles.profile_store", return_value=store):
                    seed_profile_preparation(root, profile, project)
                    with patch.object(minutes, "stage_config", return_value=(current_settings, previous_config)):
                        minutes.run_stage(root, project, Mock(side_effect=generate))
                    final = sa.summary_final_path(root, "minutes")
                    self.assertNotIn("- Main rulings:", final.read_text())
                    protected = (final, minutes.checkpoint_path(root), minutes.meta_path(root),
                                 store.registry_path, project.parent / "config.json")
                    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in protected}
                    self.assertTrue(minutes.freshness_issues(root, project))
                    self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in protected})
                    with self.assertRaisesRegex(RuntimeError, "synthetic candidate failure"):
                        minutes.run_stage(root, project, Mock(side_effect=RuntimeError("synthetic candidate failure")))
                    self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in protected})
                    generator = Mock(side_effect=generate)
                    minutes.run_stage(root, project, generator)
                    self.assertEqual(generator.call_count, 2)
                    text = final.read_text()
                    # Same-date orders remain separate despite navigation date deduplication.
                    self.assertEqual(text.count("May 7, 2030 — Motion to compel"), 2)
                    for label in ("Appearances:", "Orders:", "Next:"):
                        self.assertEqual(text.count(label), 2)
                    self.assertEqual(json.loads(minutes.meta_path(root).read_text())["schema_version"], 4)
                    self.assertEqual(minutes.freshness_issues(root, project), [])
                    generator.reset_mock()
                    minutes.run_stage(root, project, generator)
                    generator.assert_not_called()
                    for p in protected[-2:]:
                        self.assertEqual(before[p], (p.read_bytes(), p.stat().st_mtime_ns))
                    if specialty == "general":
                        edition = build_summary_edition("minutes", final, root)
                        self.assertEqual(validate_edition_payload(edition.page_map, kind="minutes", root_dir=root,
                                                                source_text=text, pdf_bytes=edition.pdf_bytes), [])
                        printable = "\n".join(page["text"] for page in edition.page_map["pages"])
                        for label in ("Motion to compel", "Appearances:", "Orders:", "Next:"):
                            self.assertEqual(printable.count(label), 2)


if __name__ == "__main__":
    unittest.main()
