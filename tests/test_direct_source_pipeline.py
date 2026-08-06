import tempfile
import unittest
from pathlib import Path

from recordprep.ui.main_window import (
    _cleanup_legacy_generated_artifacts,
    _hearing_context_lines,
    _hearing_summary_validation_issue,
    _render_summary_window_payload,
    _summary_page_windows,
)


class DirectSourcePipelineTests(unittest.TestCase):
    def test_retired_artifact_pipeline_is_not_exposed_or_depended_on(self) -> None:
        project = Path(__file__).resolve().parents[1]
        source = (project / "recordprep/ui/main_window.py").read_text(encoding="utf-8")
        dependencies = (project / "pyproject.toml").read_text(encoding="utf-8")

        for obsolete in (
            'title="Create raw"',
            'title="Create pre-optimized"',
            'title="Create optimized"',
            'title="Case overview"',
            'title="Create RAG index"',
            "def _run_step_eight",
            "def _run_step_preoptimized",
            "def _run_step_nine",
            "def _run_step_eleven",
            "def _run_step_twelve",
        ):
            self.assertNotIn(obsolete, source)
        for dependency in ("chromadb", "langchain", "voyageai", "isaacus"):
            self.assertNotIn(dependency, dependencies.casefold())

    def test_summary_windows_cover_every_primary_page_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            text_dir = Path(temporary) / "text_pages"
            text_dir.mkdir()
            for page in range(1, 8):
                (text_dir / f"{page:04d}.txt").write_text(
                    f"Material detail on page {page}.\n", encoding="utf-8"
                )

            windows = _summary_page_windows(
                text_dir,
                1,
                7,
                target_pages=3,
                preferred_breaks={4, 6},
            )

            primary = [page for window in windows for page in window["primary_pages"]]
            self.assertEqual(primary, list(range(1, 8)))
            self.assertEqual(len(primary), len(set(primary)))
            self.assertIsNone(windows[0]["context_page"])
            self.assertEqual(windows[1]["context_page"], windows[0]["primary_end"])
            payload = _render_summary_window_payload(
                windows[1], {page: f"2RT {page}" for page in range(1, 8)}
            )
            self.assertIn("CONTEXT ONLY — DO NOT SUMMARIZE", payload)
            self.assertIn("PRIMARY SOURCE PAGES", payload)

    def test_context_lines_distinguish_counsel_and_verified_testimony(self) -> None:
        hearing = {
            "witness_status": "verified",
            "counsel": [
                {
                    "role_id": "mothers_counsel",
                    "role_label": "Mother’s counsel",
                    "name": "Jane Smith",
                }
            ],
            "witnesses": [
                {
                    "name": "Father",
                    "description": "presumed father",
                    "examinations": [
                        {
                            "type": "direct",
                            "examiner_role_id": "fathers_counsel",
                            "start_citation_label": "2RT 101",
                            "end_citation_label": "2RT 118",
                        }
                    ],
                }
            ],
        }

        counsel, testimony = _hearing_context_lines(hearing)

        self.assertEqual(counsel, "Counsel: Mother’s counsel — Jane Smith.")
        self.assertIn("Father (presumed father)", testimony)
        self.assertIn("direct by Father’s counsel", testimony)
        self.assertIn("2RT 101–2RT 118", testimony)

    def test_summary_validation_rejects_false_testimony_and_bare_counsel_name(self) -> None:
        hearing = {
            "witness_status": "none",
            "witnesses": [],
            "counsel": [
                {
                    "role_id": "mothers_counsel",
                    "role_label": "Mother’s counsel",
                    "name": "Jane Smith",
                    "aliases": ["Ms. Smith"],
                }
            ],
        }

        self.assertIn(
            "witness status is none",
            _hearing_summary_validation_issue("The father testified.", hearing) or "",
        )
        self.assertIn(
            "without the party role",
            _hearing_summary_validation_issue("Jane Smith objected.", hearing) or "",
        )
        self.assertIn(
            "without the party role",
            _hearing_summary_validation_issue("Ms. Smith objected.", hearing) or "",
        )
        self.assertIsNone(
            _hearing_summary_validation_issue("Mother’s counsel (Jane Smith) objected.", hearing)
        )

    def test_cleanup_removes_only_known_legacy_generated_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "artifacts" / "optimized").mkdir(parents=True)
            (root / "artifacts" / "optimized" / "0001.txt").write_text("old")
            (root / "rag" / "vector_database").mkdir(parents=True)
            source = root / "text_pages" / "0001.txt"
            source.parent.mkdir()
            source.write_text("source")
            unrelated = root / "notes.txt"
            unrelated.write_text("keep")

            removed = _cleanup_legacy_generated_artifacts(root)

            self.assertIn("artifacts/optimized", removed)
            self.assertIn("rag", removed)
            self.assertTrue(source.is_file())
            self.assertTrue(unrelated.is_file())


if __name__ == "__main__":
    unittest.main()
