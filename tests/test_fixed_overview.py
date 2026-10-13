"""Fixed orientation method; synthetic profiles and inputs only."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from recordprep.native_profiles import compile_native, overview_input_digest
from recordprep.profile_contract import validate_contents, json_bytes
from recordprep.profile_workflows import ProfileEditor
from recordprep.pi_bundle import validate_case_overview_text
from recordprep import summary_agents as sa, minute_summaries as minutes
from test_profile_generation import bundled
from test_practice_profiles import historical_snapshot

PROJECT = Path(__file__).resolve().parents[1]


class FixedOverviewTests(unittest.TestCase):
    def test_all_profiles_use_same_method_and_no_profile_resources(self):
        base = bundled("general")
        prompt, metadata = compile_native(base, "overview", PROJECT / ".pi")
        for version in (1, 2, 3, 4):
            old = historical_snapshot(base, version)
            original = old.files
            editor = ProfileEditor(old)
            editor.resources["overview"] = "RETIRED_OVERVIEW_CANARY"
            editor.resources["hearings"][0]["guidance"] = "TOPIC_CANARY"
            revised = editor.snapshot()
            actual, meta = compile_native(revised, "overview", PROJECT / ".pi")
            self.assertEqual(actual, prompt)
            self.assertEqual(meta["components"], metadata["components"])
            self.assertNotIn("CANARY", actual)
            self.assertEqual(validate_contents(old.files, "recordprep").files, original)
        other, meta = compile_native(bundled("california_dependency"), "overview", PROJECT / ".pi")
        self.assertEqual(other, prompt)
        self.assertEqual(meta["components"], metadata["components"])

    def test_new_profiles_omit_overview_and_reject_reintroduced_resource(self):
        for name in ("general", "california_dependency"):
            profile = bundled(name)
            self.assertEqual(profile.manifest["schema_version"], 5)
            self.assertNotIn("overview", profile.manifest["resources"])
            self.assertNotIn("overview.md", dict(profile.files))
        old = historical_snapshot(bundled("general"), 4)
        manifest = old.manifest
        manifest["schema_version"] = 5
        files = dict(old.files) | {"profile.json": json_bytes(manifest)}
        with self.assertRaises(ValueError):
            validate_contents(tuple(files.items()), "recordprep")

    def test_orientation_method_is_identical_in_both_runtime_workflows(self):
        bound = (PROJECT / ".pi/resources/profile-overview.md").read_text()
        legacy = (PROJECT / ".pi/skills/recordprep-create-case-overview/SKILL.md").read_text()
        method = bound.split("## Orientation method", 1)[1]
        self.assertEqual(method, legacy.split("## Orientation method", 1)[1])
        for phrase in ("Read each selected summary completely", "continue from later offsets",
                       "latest supplied materials", "Do not assume an order is on appeal",
                       "never as independent support for substantive events", "chronological order",
                       "matters the summaries only suggest", "Do not treat silence as proof",
                       "no numerical word minimum, maximum", "allegations", "actual court findings/orders",
                       "reporter-transcript attribution is unavailable", "Verify before submission"):
            self.assertIn(phrase, method)
        for old_quota in ("150–700", "900 words", "five to ten"):
            self.assertNotIn(old_quota, method)
        self.assertIn("Python independently validates", bound)

    def test_compact_selection_contract_in_both_runtime_skills(self):
        for resource in ("resources/profile-overview.md",
                         "skills/recordprep-create-case-overview/SKILL.md"):
            prompt = (PROJECT / ".pi" / resource).read_text()
            with self.subTest(resource=resource):
                for phrase in (
                    "Read comprehensively; output selectively",
                    "Use short Markdown bullets under every section",
                    "State each fact in its best section",
                    "A small, simple record warrants a small overview",
                    "not page count, summary length",
                    "never invent content to balance the sections",
                    "unless they change the orientation",
                    "Preserve any qualification needed to avoid misleading",
                    "Omission from this selective map does not establish irrelevance or absence",
                    "neutral topic labels with brief research leads",
                    "Perform a final selection pass",
                    "without word quotas or mechanical truncation",
                ):
                    self.assertIn(phrase, prompt)

    def test_synthetic_examples_teach_selection_without_weakening_fidelity(self):
        for resource in ("resources/profile-overview.md",
                         "skills/recordprep-create-case-overview/SKILL.md"):
            prompt = (PROJECT / ".pi" / resource).read_text()
            with self.subTest(resource=resource):
                for phrase in (
                    "Parties: name and central role only",
                    "Posture: latest stage and operative result only",
                    "Events: date and turning point, not a hearing synopsis",
                    "Issues: topic and a short indication of what to investigate",
                    "Scope: material types, coverage and consequential limitations",
                    "These fictional examples illustrate selection and brevity",
                    "do not sacrifice a material qualification",
                    "Attribute status to each included claim or issue",
                    'collectively as "not adjudicated" or "unresolved."',
                    "required CT-only attribution limitation",
                    "Do not copy fictional example facts",
                    "remove evidence inventories and unnecessary negative checklists",
                ):
                    self.assertIn(phrase, prompt)
                examples = prompt.split("### Synthetic compression examples", 1)[1].split("### Content rules", 1)[0]
                for section in ("Party", "Posture", "Event", "Issue", "Scope"):
                    self.assertIn(f"**{section} —", examples)
                self.assertEqual(examples.count("- Too detailed:"), 5)
                self.assertEqual(examples.count("- Prefer:"), 5)

    def test_short_bullet_overview_is_valid_in_both_modes(self):
        text = "---\nartifact: recordprep-case-overview\nschema_version: 1\nstatus: nonauthoritative-orientation\n---\n# Case Overview\n"
        text += "> Orientation aid only. Verify every factual claim against mapped source pages before relying on or citing it.\n"
        sections = {
            "Parties and Roles": "Claimant: Morgan; respondent: Example Company.",
            "Procedural Posture": "Latest supplied order: motion denied; trial not yet recorded.",
            "Key Events": "2025-01-10 — Motion hearing.",
            "Principal Issues": "Notice: parties dispute receipt; inspect motion materials.",
            "Record Scope": "One hearing and order; later outcomes not supplied.",
        }
        for heading, bullet in sections.items():
            text += f"## {heading}\n- {bullet}\n"
        for profile_mode in (False, True):
            self.assertEqual(validate_case_overview_text(text, profile_mode=profile_mode), [])

    def test_format_stays_compatible_without_word_limits(self):
        text = "---\nartifact: recordprep-case-overview\nschema_version: 1\nstatus: nonauthoritative-orientation\n---\n# Case Overview\n"
        text += "> Orientation aid only. Verify every factual claim against mapped source pages before relying on or citing it.\n"
        for heading in ("Parties and Roles", "Procedural Posture", "Key Events", "Principal Issues", "Record Scope"):
            text += f"## {heading}\n"
        for profile_mode in (False, True):
            self.assertTrue(validate_case_overview_text(text, profile_mode=profile_mode))
            self.assertEqual(validate_case_overview_text(text + "The supplied summaries do not establish the posture.\n", profile_mode=profile_mode), [])
            self.assertEqual(validate_case_overview_text(text + "Substantive synthetic orientation. " * 400, profile_mode=profile_mode), [])
            self.assertTrue(validate_case_overview_text(text.replace("## Key Events", "## Wrong") + "Substance.", profile_mode=profile_mode))

    def test_overview_freshness_tracks_summary_inputs_not_retired_instructions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "artifacts").mkdir()
            (root / "summaries").mkdir()
            (root / "case_name.txt").write_text("Synthetic")
            (root / "artifacts/transcript_layout.json").write_text('{}')
            for kind in ("hearings", "reports", "minutes"):
                sa.summary_final_path(root, kind).write_text("Synthetic summary")
                path = minutes.meta_path(root) if kind == "minutes" else sa.summary_final_meta_path(root, kind)
                path.write_text('{}')
            with patch("recordprep.transcript_layout.is_ct_only", return_value=True):
                before = overview_input_digest(root)
                sa.summary_final_path(root, "reports").write_text("Updated substantive summary")
                self.assertNotEqual(before, overview_input_digest(root))
                before = overview_input_digest(root)
                (root / "artifacts/participant_index.json").write_text("Ignored stale CT-only index")
                self.assertEqual(before, overview_input_digest(root))


if __name__ == "__main__":
    unittest.main()
