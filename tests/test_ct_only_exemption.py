"""CT-only participant-index exemption tests.

A fresh, resolved CT-only transcript layout skips participant indexing:
the participant stage is a successful no-op (no PI process, no placeholder
file), hearing summaries publish zero items without model calls, and the
case overview / final source map complete without a participant artifact.
Missing, malformed, stale, or needs-review layouts never authorize the
exemption, and RT-only/mixed records keep the participant requirement.

All fixtures are synthetic; no real case material appears here.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from recordprep import pi_bundle, summary_agents as sa  # noqa: E402
from recordprep.transcript_layout import (  # noqa: E402
    apply_manual_override,
    draft_layout_payload,
    finalize_layout_draft,
    is_ct_only,
)
from tests.summary_agent_fixtures import publish_valid_summary, synthetic_facts_row  # noqa: E402
from tests.test_pi_bundle import _case_overview_text  # noqa: E402

RUNNER = PROJECT_DIR / ".pi" / "scripts" / "run_recordprep_skill.py"
SOURCE_MAP_SCRIPT = (
    PROJECT_DIR
    / ".pi/skills/recordprep-build-source-map/scripts/build_source_map.py"
)


def _make_pages(root: Path, count: int, text: str = "clerk page") -> None:
    (root / "text_pages").mkdir(parents=True, exist_ok=True)
    (root / "image_pages").mkdir(parents=True, exist_ok=True)
    for page in range(1, count + 1):
        (root / "text_pages" / f"{page:04d}.txt").write_text(
            f"{text} {page}\n", encoding="utf-8"
        )
        (root / "image_pages" / f"{page:04d}.png").write_bytes(b"image")


def _write_transcript_numbering(root: Path, pages: int, prefix: str = "CT") -> None:
    (root / "artifacts" / "transcript_page_numbers.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "entries": [
                    {
                        "file_name": f"{number:04d}.txt",
                        "file_page": number,
                        "record_type": prefix,
                        "page_type": f"{prefix}_other",
                        "transcript_page_number": number,
                        "transcript_page_label": str(number),
                        "citation_series_id": "ct-1" if prefix == "CT" else "rt-1",
                        "citation_prefix": prefix,
                        "citation_label": f"{prefix} {number}",
                        "citation_key": f"{prefix}:{number}",
                        "status": "selected",
                        "confidence": "high",
                        "method": "sequence",
                    }
                    for number in range(1, pages + 1)
                ],
                "citation_series": [
                    {
                        "series_id": "ct-1" if prefix == "CT" else "rt-1",
                        "citation_prefix": prefix,
                    }
                ],
                "anomalies": [],
            }
        ),
        encoding="utf-8",
    )
    (root / "artifacts" / "transcript_page_number_series.md").write_text(
        f"# {prefix} series\n", encoding="utf-8"
    )


def _publish_zero_item_hearing_summary(root: Path) -> None:
    """Publish the header-only hearing digest/title-only summary shape."""
    publish_valid_summary(
        root,
        "hearings",
        [],
        "Hearings Summary\n\nSynCase\n",
    )


def _ct_only_bundle(root: Path, *, pages: int = 2) -> None:
    """A synthetic CT-only bundle without any participant artifact."""
    _make_pages(root, pages)
    (root / "artifacts").mkdir(parents=True, exist_ok=True)
    (root / "summaries").mkdir(parents=True, exist_ok=True)
    apply_manual_override(root, mode="ct_only")
    (root / "case_name.txt").write_text("SynCase", encoding="utf-8")
    (root / "artifacts/hearing_boundaries.json").write_text("[]", encoding="utf-8")
    (root / "artifacts/report_boundaries.json").write_text(
        json.dumps(
            [
                {
                    "date": "March 3, 2025",
                    "report_name": "Report",
                    "report_date": "March 3, 2025",
                    "report_label": "March 3, 2025 - Report",
                    "start_page": 1,
                    "end_page": 2,
                }
            ]
        ),
        encoding="utf-8",
    )
    (root / "artifacts/minutes_boundaries.json").write_text("[]", encoding="utf-8")
    _write_transcript_numbering(root, pages)
    report_row = synthetic_facts_row(
        "reports", start=1, end=2, label="March 3, 2025 - Report"
    )
    publish_valid_summary(
        root,
        "reports",
        [report_row],
        "Reports Summary\n\nMarch 3, 2025 - Report\n\nProse.\n",
    )
    _publish_zero_item_hearing_summary(root)
    overview = root / "artifacts/case_overview.md"
    overview.write_text(_case_overview_text(), encoding="utf-8")
    source_map = root / "artifacts/source_map.json"
    source_map.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "paths": {"case_overview": "artifacts/case_overview.md"},
                "pages": [],
                "citation_series": [],
            }
        ),
        encoding="utf-8",
    )
    manifest = {
        "files": {
            "transcript_layout": "artifacts/transcript_layout.json",
            "summarized_hearings": "summaries/hearings_sum_SynCase.txt",
            "summarized_reports": "summaries/reports_sum_SynCase.txt",
            "transcript_page_numbers": "artifacts/transcript_page_numbers.json",
            "transcript_page_number_series": (
                "artifacts/transcript_page_number_series.md"
            ),
            "case_overview": "artifacts/case_overview.md",
            "source_map": "artifacts/source_map.json",
        }
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    summaries = sorted(
        (root / "summaries").glob("*.txt"), key=lambda path: path.stat().st_mtime
    )
    newest = max(path.stat().st_mtime for path in summaries)
    os.utime(overview, (newest + 1, newest + 1))
    os.utime(source_map, (newest + 2, newest + 2))


def _write_needs_review_layout(root: Path) -> None:
    draft = draft_layout_payload(
        mode=None,
        status="needs_review",
        decision_source="manual",
        confidence="manual",
        method="manual override",
        warnings=["Ambiguous record structure."],
    )
    finalize_layout_draft(root, draft)


def _runner_env(root: Path, *, pi_path: str = "/nonexistent/recordprep-pi") -> dict:
    env = os.environ.copy()
    env["RECORDPREP_CASE_BUNDLE"] = str(root)
    env["RECORDPREP_PI_PROJECT_DIR"] = str(PROJECT_DIR / ".pi")
    env["RECORDPREP_PI_COMMAND_ARGC"] = "1"
    env["RECORDPREP_PI_COMMAND_ARG_0"] = pi_path
    cache = Path(tempfile.mkdtemp(prefix="rp-ct-only-cache."))
    env["XDG_CACHE_HOME"] = str(cache)
    return env


class CtOnlyExemptionTests(unittest.TestCase):
    def test_manual_and_detected_ct_only_layouts_grant_the_exemption(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manual_root = Path(temporary) / "manual"
            _make_pages(manual_root, 2)
            apply_manual_override(manual_root, mode="ct_only")
            self.assertTrue(is_ct_only(manual_root))

            detected_root = Path(temporary) / "detected"
            _make_pages(detected_root, 2)
            draft = draft_layout_payload(
                mode="ct_only",
                status="resolved",
                decision_source="pi-agent",
                confidence="high",
                method="text search",
                ct_start_file_page=1,
                search_summary="Clerk's markers throughout.",
                evidence=[{"path": "text_pages/0001.txt", "kind": "text"}],
                warnings=[],
            )
            finalize_layout_draft(detected_root, draft)
            self.assertTrue(is_ct_only(detected_root))

    def test_missing_malformed_stale_or_review_layouts_never_exempt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _make_pages(root, 2)
            # Missing.
            self.assertFalse(is_ct_only(root))

            # Malformed.
            (root / "artifacts").mkdir()
            (root / "artifacts/transcript_layout.json").write_text(
                "{not json", encoding="utf-8"
            )
            self.assertFalse(is_ct_only(root))

            # Needs review.
            _write_needs_review_layout(root)
            self.assertFalse(is_ct_only(root))
            self.assertEqual(
                json.loads(
                    (root / "artifacts/transcript_layout.json").read_text(
                        encoding="utf-8"
                    )
                )["status"],
                "needs_review",
            )

            # Stale: a resolved CT-only layout whose signature no longer
            # matches the current pages.
            apply_manual_override(root, mode="ct_only")
            self.assertTrue(is_ct_only(root))
            (root / "text_pages/0001.txt").write_text(
                "externally changed", encoding="utf-8"
            )
            self.assertFalse(is_ct_only(root))

            # RT-only and split never match.
            apply_manual_override(root, mode="rt_only")
            self.assertFalse(is_ct_only(root))
            apply_manual_override(root, mode="split", rt_end_file_page=1)
            self.assertFalse(is_ct_only(root))

    def test_ct_only_bundle_completes_without_participant_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _ct_only_bundle(root)
            self.assertFalse((root / "artifacts/participant_index.json").exists())

            # Explicit validation of the artifact itself still rejects it.
            self.assertTrue(pi_bundle.validate_participant_index_output(root))

            # Stage applicability: the participant step is satisfied.
            self.assertEqual(
                pi_bundle.validate_pi_step_outputs("build_participant_index", root),
                [],
            )
            self.assertTrue(pi_bundle.pi_step_complete("build_participant_index", root))

            # Overview and source-map prerequisites apply without participants.
            self.assertEqual(pi_bundle.case_overview_prerequisite_issues(root), [])
            self.assertEqual(pi_bundle.source_map_prerequisite_issues(root), [])
            self.assertEqual(pi_bundle.validate_prepare_bundle_outputs(root), [])
            self.assertTrue(pi_bundle.prepare_bundle_complete(root))

    def test_ct_only_rejects_published_participant_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _ct_only_bundle(root)
            source_map_path = root / "artifacts/source_map.json"
            source_map = json.loads(source_map_path.read_text(encoding="utf-8"))
            source_map["paths"]["participant_index"] = (
                "artifacts/participant_index.json"
            )
            source_map_path.write_text(json.dumps(source_map), encoding="utf-8")

            issues = pi_bundle.validate_prepare_bundle_outputs(root)
            self.assertTrue(
                any("paths.participant_index" in issue for issue in issues),
                issues,
            )

            source_map_path.unlink()
            source_map_path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "paths": {"case_overview": "artifacts/case_overview.md"},
                        "pages": [],
                        "citation_series": [],
                    }
                ),
                encoding="utf-8",
            )
            manifest_path = root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["participant_index"] = (
                "artifacts/participant_index.json"
            )
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            issues = pi_bundle.validate_prepare_bundle_outputs(root)
            self.assertTrue(
                any("files.participant_index" in issue for issue in issues),
                issues,
            )

    def test_preexisting_participant_file_is_ignored_and_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _ct_only_bundle(root)
            participant = root / "artifacts/participant_index.json"
            original_bytes = b'{"schema_version": 2, "hearings": [{"broken"'
            participant.write_bytes(original_bytes)
            future = participant.stat().st_mtime + 600
            os.utime(participant, (future, future))

            # Malformed/ignored artifact does not affect any CT-only
            # completion predicate or overview freshness.
            self.assertEqual(pi_bundle.validate_prepare_bundle_outputs(root), [])
            self.assertEqual(pi_bundle.case_overview_prerequisite_issues(root), [])

            # Byte-for-byte preserved.
            self.assertEqual(participant.read_bytes(), original_bytes)

    def test_layout_change_invalidates_the_overview(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _ct_only_bundle(root)
            layout = root / "artifacts/transcript_layout.json"
            future = layout.stat().st_mtime + 600
            os.utime(layout, (future, future))

            issues = pi_bundle.validate_case_overview_output(root)
            self.assertIn("artifacts/case_overview.md is stale.", issues)

    def test_rt_records_keep_the_participant_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _ct_only_bundle(root)
            # Convert the same synthetic record to RT-only: the hearing
            # data now requires participant indexing.
            apply_manual_override(root, mode="rt_only")
            issues = pi_bundle.validate_pi_step_outputs("build_participant_index", root)
            self.assertTrue(
                any("participant_index.json" in issue for issue in issues),
                issues,
            )
            self.assertFalse(pi_bundle.pi_step_complete("build_participant_index", root))
            self.assertTrue(pi_bundle.case_overview_prerequisite_issues(root))


class CtOnlySummaryTests(unittest.TestCase):
    def test_zero_hearing_items_without_participants(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _ct_only_bundle(root)
            config = sa.effective_extraction_config(
                sa.DEFAULT_PROJECT_PI_DIR, "hearings"
            )
            items = sa.build_work_items(root, config)
            self.assertEqual(items, [])
            # Reports are unaffected and keep building items.
            report_config = sa.effective_extraction_config(
                sa.DEFAULT_PROJECT_PI_DIR, "reports"
            )
            self.assertEqual(len(sa.build_work_items(root, report_config)), 1)

    def test_ct_only_with_nonempty_hearing_boundaries_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _ct_only_bundle(root)
            (root / "artifacts/hearing_boundaries.json").write_text(
                json.dumps([{"date": "March 3, 2025", "start_page": 1, "end_page": 2}]),
                encoding="utf-8",
            )
            config = sa.effective_extraction_config(
                sa.DEFAULT_PROJECT_PI_DIR, "hearings"
            )
            with self.assertRaises(ValueError) as raised:
                sa.build_work_items(root, config)
            self.assertIn("Transcript layout inconsistency", str(raised.exception))
            issues = sa.summary_stage_freshness_issues(root, "hearings")
            self.assertTrue(
                any("freshness is unproven" in issue for issue in issues),
                issues,
            )

    def test_unresolved_layout_keeps_the_participant_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _make_pages(root, 2)
            (root / "artifacts").mkdir()
            (root / "artifacts/hearing_boundaries.json").write_text(
                "[]", encoding="utf-8"
            )
            config = sa.effective_extraction_config(
                sa.DEFAULT_PROJECT_PI_DIR, "hearings"
            )
            with self.assertRaises(ValueError) as raised:
                sa.build_work_items(root, config)
            self.assertIn("Participant index", str(raised.exception))

            # A stale CT-only layout is equally unauthorized.
            apply_manual_override(root, mode="ct_only")
            (root / "text_pages/0001.txt").write_text("changed", encoding="utf-8")
            (root / "artifacts/participant_index.json").unlink(missing_ok=True)
            with self.assertRaises(ValueError) as raised:
                sa.build_work_items(root, config)
            self.assertIn("Participant index", str(raised.exception))

    def test_layout_change_invalidates_cached_summary_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _ct_only_bundle(root)
            complete = sa.summary_stage_status(root, "hearings")
            self.assertTrue(complete.complete)
            # Nonempty boundaries make the CT-only record inconsistent; the
            # cached snapshot must not keep reporting complete.
            (root / "artifacts/hearing_boundaries.json").write_text(
                json.dumps([{"date": "March 3, 2025", "start_page": 1, "end_page": 2}]),
                encoding="utf-8",
            )
            changed = sa.summary_stage_status(root, "hearings")
            self.assertFalse(changed.complete)

    def test_published_rows_stale_after_layout_switch_to_ct_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _ct_only_bundle(root)
            # Simulate rows published before the layout became CT-only.
            digest_path = sa.summary_digest_path(root, "hearings")
            markdown = digest_path.read_text(encoding="utf-8")
            digest_path.write_text(
                markdown.replace(
                    "## Documents",
                    "## Documents",
                ),
                encoding="utf-8",
            )
            # Re-publish a nonempty row set the way a prior split-mode run
            # would have, then flip the layout to CT-only.
            from tests.summary_agent_fixtures import write_facts_bundle

            row = synthetic_facts_row("hearings", start=1, end=1)
            write_facts_bundle(root, "hearings", [row])
            issues = sa.summary_stage_freshness_issues(root, "hearings")
            self.assertTrue(
                any(
                    "no longer match the current document boundaries" in issue
                    for issue in issues
                ),
                issues,
            )


class CtOnlyRunnerTests(unittest.TestCase):
    def test_direct_runner_skips_participant_stage_without_pi(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "case_bundle"
            _ct_only_bundle(root)
            result = subprocess.run(
                [sys.executable, str(RUNNER), "build_participant_index"],
                env=_runner_env(root),
                text=True,
                capture_output=True,
                check=False,
                timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Skipped", result.stdout)
            self.assertIn("clerk's transcript", result.stdout)
            # No placeholder participant file was created.
            self.assertFalse(
                (root / "artifacts/participant_index.json").exists()
            )

    def test_runner_participant_stage_still_requires_pi_for_rt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "case_bundle"
            _ct_only_bundle(root)
            apply_manual_override(root, mode="rt_only")
            result = subprocess.run(
                [sys.executable, str(RUNNER), "build_participant_index"],
                env=_runner_env(root),
                text=True,
                capture_output=True,
                check=False,
                timeout=120,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_zero_item_hearing_stage_publishes_without_pi(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "case_bundle"
            _ct_only_bundle(root)
            # Remove the published zero-item artifacts; the stage must
            # republish them with no PI available at all.
            sa.summary_digest_path(root, "hearings").unlink()
            sa.summary_digest_meta_path(root, "hearings").unlink()
            sa.summary_final_path(root, "hearings").unlink()
            sa.summary_final_meta_path(root, "hearings").unlink()
            result = subprocess.run(
                [sys.executable, str(RUNNER), "create_hearing_summaries"],
                env=_runner_env(root),
                text=True,
                capture_output=True,
                check=False,
                timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(
                sa.load_digest_meta(root, "hearings")["complete"], True
            )
            self.assertTrue(sa.summary_final_path(root, "hearings").is_file())
            self.assertEqual(
                pi_bundle.validate_pi_step_outputs("create_hearing_summaries", root),
                [],
            )


class CtOnlyUiStateTests(unittest.TestCase):
    def _harness(self, root: Path) -> tuple[mock.Mock, mock.Mock]:
        harness = mock.Mock()
        harness._resolve_case_root.return_value = root
        harness._run_pi_skill_step.return_value = True
        return harness, harness._run_pi_skill_step

    def test_participant_step_short_circuits_before_any_launch(self) -> None:
        from recordprep.ui import main_window

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _ct_only_bundle(root)
            harness, run_skill = self._harness(root)
            with mock.patch(
                "recordprep.ui.main_window.GLib.idle_add",
                side_effect=lambda function, *args: function(*args),
            ):
                completed = main_window.RecordPrepWindow._run_step_build_participant_index(
                    harness
                )
            self.assertTrue(completed)
            run_skill.assert_not_called()
            finish_args = harness._finish_step.call_args.args
            self.assertIs(finish_args[0], harness.step_build_participant_index_row)
            self.assertEqual(finish_args[1], "Skipped")

    def test_participant_step_still_launches_for_rt_records(self) -> None:
        from recordprep.ui import main_window

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _ct_only_bundle(root)
            apply_manual_override(root, mode="rt_only")
            harness, run_skill = self._harness(root)
            run_skill.return_value = True
            with mock.patch(
                "recordprep.ui.main_window.GLib.idle_add",
                side_effect=lambda function, *args: function(*args),
            ):
                completed = main_window.RecordPrepWindow._run_step_build_participant_index(
                    harness
                )
            self.assertTrue(completed)
            run_skill.assert_called_once_with(
                "build_participant_index",
                harness.step_build_participant_index_row,
            )

    def test_refresh_shows_skipped_not_done_for_ct_only(self) -> None:
        from recordprep.ui import main_window

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _ct_only_bundle(root)
            harness = mock.Mock()
            harness._pipeline_running = False
            harness._resolve_case_root.return_value = root
            row = mock.Mock()
            harness._pipeline_steps.return_value = [
                ("build_participant_index", row, lambda: True)
            ]
            recorded: list[tuple[object, str]] = []
            harness._set_step_status.side_effect = lambda row, status: recorded.append(
                (row, status)
            )
            main_window.RecordPrepWindow._refresh_step_statuses_from_artifacts(harness)
            self.assertIn((row, "Skipped"), recorded)
            self.assertNotIn((row, "Done"), recorded)

    def test_refresh_shows_done_for_rt_records(self) -> None:
        from recordprep.ui import main_window

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _ct_only_bundle(root)
            apply_manual_override(root, mode="rt_only")
            (root / "artifacts/participant_index.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "source": "record-participant-index",
                        "hearings": [],
                    }
                ),
                encoding="utf-8",
            )
            harness = mock.Mock()
            harness._pipeline_running = False
            harness._resolve_case_root.return_value = root
            row = mock.Mock()
            harness._pipeline_steps.return_value = [
                ("build_participant_index", row, lambda: True)
            ]
            recorded: list[tuple[object, str]] = []
            harness._set_step_status.side_effect = lambda row, status: recorded.append(
                (row, status)
            )
            main_window.RecordPrepWindow._refresh_step_statuses_from_artifacts(harness)
            self.assertIn((row, "Done"), recorded)


class CtOnlySourceMapTests(unittest.TestCase):
    def test_ct_only_source_map_omits_participants_and_warns(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "case_bundle"
            _ct_only_bundle(root)
            participant = root / "artifacts/participant_index.json"
            stale_bytes = b'{"schema_version": 2, "hearings": [{"stale"'
            participant.write_bytes(stale_bytes)

            result = subprocess.run(
                [sys.executable, str(SOURCE_MAP_SCRIPT), str(root)],
                text=True,
                capture_output=True,
                check=False,
                timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(
                (root / "artifacts/source_map.json").read_text(encoding="utf-8")
            )
            # No participant-file reference anywhere.
            self.assertNotIn("participant_index", payload["paths"])
            self.assertNotIn(
                "participant_index",
                json.loads((root / "manifest.json").read_text(encoding="utf-8"))[
                    "files"
                ],
            )
            embedded = payload["participant_index"]
            self.assertEqual(embedded.get("hearings"), [])
            self.assertEqual(payload["counts"]["participants"], 0)
            for page in payload["pages"]:
                self.assertEqual(page["participants"], [])
                self.assertEqual(page["witnesses"], [])
                self.assertEqual(page["examinations"], [])
                self.assertEqual(page["counsel_roles"], [])
            self.assertEqual(payload["lookup"]["by_participant"], {})
            self.assertEqual(payload["lookup"]["by_witness"], {})
            self.assertEqual(payload["lookup"]["by_counsel"], {})
            self.assertTrue(
                any(
                    "attribution is unavailable" in warning
                    and "not a finding that no participants or witnesses" in warning
                    for warning in payload["warnings"]
                ),
                payload["warnings"],
            )
            # Stale on-disk artifact preserved byte-for-byte and unreferenced.
            self.assertEqual(participant.read_bytes(), stale_bytes)

            # The published final bundle validates without the participant
            # artifact. (Restamp the map newest, as a real run's publication
            # order guarantees.)
            newest = max(
                path.stat().st_mtime
                for path in root.rglob("*")
                if path.is_file() and path != root / "artifacts/source_map.json"
            )
            os.utime(
                root / "artifacts/source_map.json", (newest + 5, newest + 5)
            )
            self.assertEqual(pi_bundle.validate_prepare_bundle_outputs(root), [])

    def test_source_map_fallback_predicate_matches_layout_module(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "ct_only_build_source_map", SOURCE_MAP_SCRIPT
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _ct_only_bundle(root)
            self.assertTrue(module._ct_only_exempt(root))
            self.assertTrue(module._fallback_ct_only_exempt(root))
            apply_manual_override(root, mode="rt_only")
            self.assertFalse(module._ct_only_exempt(root))
            self.assertFalse(module._fallback_ct_only_exempt(root))
            apply_manual_override(root, mode="ct_only")
            (root / "text_pages/0001.txt").write_text("stale", encoding="utf-8")
            self.assertFalse(module._ct_only_exempt(root))
            self.assertFalse(module._fallback_ct_only_exempt(root))

    def test_rt_source_map_requires_and_publishes_the_participant_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "case_bundle"
            _ct_only_bundle(root)
            apply_manual_override(root, mode="rt_only")
            participant = root / "artifacts/participant_index.json"
            participant.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "source": "record-participant-index",
                        "hearings": [
                            {
                                "id": "hearing:0001",
                                "start_page": 1,
                                "end_page": 1,
                                "witness_status": "none",
                                "witness_evidence": [
                                    {
                                        "text_path": "text_pages/0001.txt",
                                        "file_page": 1,
                                        "citation_label": "RT 1",
                                        "citation_key": "RT:1",
                                        "note": "Explicit no-witness index.",
                                    }
                                ],
                                "counsel": [],
                                "participants": [],
                                "witnesses": [],
                                "warnings": [],
                            }
                        ],
                        "warnings": [],
                    }
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SOURCE_MAP_SCRIPT), str(root)],
                text=True,
                capture_output=True,
                check=False,
                timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(
                (root / "artifacts/source_map.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                payload["paths"]["participant_index"],
                "artifacts/participant_index.json",
            )
            self.assertEqual(
                json.loads((root / "manifest.json").read_text(encoding="utf-8"))[
                    "files"
                ]["participant_index"],
                "artifacts/participant_index.json",
            )

            # Validation rejects an RT source map without the participant
            # path.
            payload["paths"].pop("participant_index")
            (root / "artifacts/source_map.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            issues = pi_bundle.validate_prepare_bundle_outputs(root)
            self.assertTrue(
                any("paths.participant_index" in issue for issue in issues),
                issues,
            )


if __name__ == "__main__":
    unittest.main()
