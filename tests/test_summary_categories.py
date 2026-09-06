"""Tests for the tracked summary-category guidance resources and loader."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from recordprep import summary_agents as sa
from recordprep import summary_categories

PROJECT_RUNNER = (
    Path(__file__).resolve().parents[1] / ".pi" / "scripts" / "run_recordprep_skill.py"
)


class CategoryResourceTests(unittest.TestCase):
    def test_tracked_resources_load_in_exact_code_owned_order(self) -> None:
        for kind in ("hearings", "reports"):
            descriptions = summary_categories.load_category_descriptions(kind)
            self.assertEqual(
                list(descriptions), list(sa.SUMMARY_CATEGORY_IDS[kind]), kind
            )
            for identifier, text in descriptions.items():
                self.assertTrue(text.strip(), identifier)

    def test_definitions_use_resource_guidance_and_code_owned_titles(self) -> None:
        definitions = sa.summary_category_definitions("hearings")
        self.assertEqual(
            [definition.identifier for definition in definitions],
            list(sa.SUMMARY_CATEGORY_IDS["hearings"]),
        )
        self.assertEqual(definitions[0].title, "Parent Appearances")
        resource = summary_categories.summary_category_resource_path("hearings")
        self.assertIn("Which parents personally appeared", definitions[0].guidance)
        self.assertEqual(resource.name, "hearings.md")

    def _write_resource(self, directory: Path, kind: str, text: str) -> Path:
        path = directory / summary_categories.RESOURCE_FILENAMES[kind]
        path.write_text(text, encoding="utf-8")
        return path

    def test_missing_resource_is_an_actionable_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(summary_categories.SummaryResourceError, "missing"):
                summary_categories.load_category_descriptions(
                    "hearings", resource_dir=Path(temporary)
                )

    def test_invalid_resources_fail_with_actionable_errors(self) -> None:
        header = (
            "<!-- recordprep:summary-categories "
            f"v{summary_categories.SUMMARY_CATEGORIES_RESOURCE_VERSION} "
            "kind:hearings -->"
        )
        good_section = "\n## parent_appearances\n\nKeep parent appearances accurate.\n"
        cases = {
            "missing header": "No header here.\n",
            "unsupported version": header.replace("v1", "v99") + good_section,
            "kind mismatch": header.replace("kind:hearings", "kind:reports")
            + good_section,
            "duplicate heading": header
            + good_section
            + "\n## parent_appearances\n\nAgain.\n",
            "unknown heading": header
            + "\n## not_a_real_category\n\nText.\n"
            + good_section,
            "empty section": header + "\n## parent_appearances\n\n",
            "reordered sections": header
            + "\n## testimony\n\nText.\n"
            + "\n## parent_appearances\n\nText.\n",
            "missing category": header + "\n## parent_appearances\n\nText.\n",
        }
        for label, text in cases.items():
            with tempfile.TemporaryDirectory() as temporary:
                self._write_resource(Path(temporary), "hearings", text)
                with self.assertRaises(
                    summary_categories.SummaryResourceError, msg=label
                ):
                    summary_categories.load_category_descriptions(
                        "hearings", resource_dir=Path(temporary)
                    )

    def test_changed_kind_descriptions_change_only_that_kind_fingerprint(self) -> None:
        def fingerprint(kind: str) -> str:
            config = sa.ExtractionConfig(kind=kind, guidance="guidance")
            return config.fingerprint

        base = {kind: fingerprint(kind) for kind in ("hearings", "reports")}
        edited = (
            "Which parents personally appeared and how (in person or remotely). "
            "Fork-specific emphasis: note the transport arrangement."
        )
        original = summary_categories.load_category_descriptions

        def fake_loader(kind: str, *, resource_dir: Path | None = None):
            if kind == "hearings":
                descriptions = dict(original(kind))
                descriptions["parent_appearances"] = edited
                return descriptions
            return original(kind)

        with mock.patch.object(
            summary_categories,
            "load_category_descriptions",
            side_effect=fake_loader,
        ):
            sa._CATEGORY_DESCRIPTIONS_CACHE.clear()
            try:
                changed = {kind: fingerprint(kind) for kind in ("hearings", "reports")}
            finally:
                sa._CATEGORY_DESCRIPTIONS_CACHE.clear()
        self.assertNotEqual(changed["hearings"], base["hearings"])
        self.assertEqual(changed["reports"], base["reports"])

    def test_runner_extraction_config_never_reattaches_retired_builtins(self) -> None:
        """The runner composes one effective contract: default + custom only."""
        import importlib.util
        import sys

        spec = importlib.util.spec_from_file_location(
            "recordprep_runner", PROJECT_RUNNER
        )
        assert spec is not None and spec.loader is not None
        runner = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = runner
        try:
            spec.loader.exec_module(runner)
        finally:
            sys.modules.pop(spec.name, None)

        with tempfile.TemporaryDirectory() as temporary:
            project_dir = Path(temporary) / ".pi"
            project_dir.mkdir()
            (project_dir / "settings.json").write_text("{}", encoding="utf-8")

            def config_with(prompt_value: str) -> Path:
                (project_dir.parent / "config.json").write_text(
                    json.dumps({"summarize_hearings_prompt": prompt_value}),
                    encoding="utf-8",
                )
                return project_dir

            # A stored retired built-in advances without reattaching its text.
            config = runner._extraction_config(
                config_with(sa.PRIOR_HEARING_EXTRACTION_GUIDANCE),
                "hearings",
                {},
            )
            self.assertEqual(config.guidance, sa.DEFAULT_HEARING_EXTRACTION_GUIDANCE)
            self.assertEqual(config.additional_guidance, "")

            # Custom text is byte-for-byte subordinate additional guidance.
            custom = "  Keep digests near 200 words.\n"
            config = runner._extraction_config(
                config_with(custom), "hearings", {}
            )
            self.assertEqual(config.guidance, sa.DEFAULT_HEARING_EXTRACTION_GUIDANCE)
            self.assertEqual(config.additional_guidance, custom)

            # An empty stored prompt uses the immutable contract only.
            config = runner._extraction_config(config_with(""), "hearings", {})
            self.assertEqual(config.guidance, sa.DEFAULT_HEARING_EXTRACTION_GUIDANCE)
            self.assertEqual(config.additional_guidance, "")


if __name__ == "__main__":
    unittest.main()
