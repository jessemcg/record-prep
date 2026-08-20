import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from recordprep.transcript_layout import (
    ARTIFACT_NAME,
    TranscriptLayoutError,
    apply_manual_override,
    detection_status,
    draft_layout_payload,
    finalize_layout_draft,
    input_signature,
    layout_display_summary,
    legacy_manifest_split,
    read_resolved_layout,
    resolve_rt_ct_split,
    validate_payload,
)
from recordprep.ui.main_window import (
    OBSOLETE_PIPELINE_CONFIG_KEYS,
    _read_config,
    _write_config,
)


def _make_pages(root: Path, count: int) -> None:
    (root / "text_pages").mkdir(parents=True)
    (root / "image_pages").mkdir()
    for page in range(1, count + 1):
        (root / "text_pages" / f"{page:04d}.txt").write_text(
            f"page {page} content\n", encoding="utf-8"
        )
        (root / "image_pages" / f"{page:04d}.png").write_bytes(b"image")


def _resolved_draft(
    *,
    mode: str,
    status: str = "resolved",
    decision_source: str = "pi-agent",
    confidence: str = "high",
    rt_end: int | None = None,
    ct_start: int | None = None,
    method: str = "text search",
    evidence: list[dict] | None = None,
    warnings: list[str] | None = None,
    _stamp: bool = True,
) -> dict:
    payload = draft_layout_payload(
        mode=mode,
        status=status,
        decision_source=decision_source,
        confidence=confidence,
        method=method,
        rt_end_file_page=rt_end,
        ct_start_file_page=ct_start,
        search_summary="Structural markers found at start/end pages.",
        evidence=[{"path": "text_pages/0002.txt", "kind": "text"}]
        if evidence is None
        else evidence,
        warnings=warnings,
    )
    if _stamp:
        payload["input_page_count"] = 4
        payload["input_signature"] = "stamped-test-signature"
    return payload


class TranscriptLayoutArtifactTests(unittest.TestCase):
    def test_rt_only_round_trip_and_routing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _make_pages(root, 4)
            draft = _resolved_draft(mode="rt_only", rt_end=4)
            finalize_layout_draft(root, draft)

            resolved = read_resolved_layout(root)
            self.assertIsNotNone(resolved)
            self.assertEqual(resolved["mode"], "rt_only")
            self.assertEqual(resolved["rt_end_file_page"], 4)
            self.assertIsNone(resolved["ct_start_file_page"])
            self.assertEqual(
                resolve_rt_ct_split(root, root / "text_pages"),
                (4, 0, True, False, "rt_only"),
            )
            self.assertEqual(detection_status(root), ("resolved", "rt_only"))
            self.assertIn("Reporter's transcript only", layout_display_summary(root))
            self.assertIn("automatic", layout_display_summary(root))

    def test_ct_only_round_trip_and_routing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _make_pages(root, 3)
            draft = _resolved_draft(mode="ct_only", ct_start=1)
            finalize_layout_draft(root, draft)

            self.assertEqual(
                resolve_rt_ct_split(root, root / "text_pages"),
                (0, 1, False, True, "ct_only"),
            )
            self.assertIn("Clerk's transcript only", layout_display_summary(root))

    def test_split_exact_adjacent_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _make_pages(root, 6)
            draft = _resolved_draft(mode="split", rt_end=4, ct_start=5)
            finalize_layout_draft(root, draft)

            resolved = read_resolved_layout(root)
            self.assertEqual(resolved["rt_end_file_page"], 4)
            self.assertEqual(resolved["ct_start_file_page"], 5)
            self.assertEqual(
                resolve_rt_ct_split(root, root / "text_pages"),
                (4, 5, True, True, "split"),
            )
            summary = layout_display_summary(root)
            self.assertIn("RT + CT", summary)
            self.assertIn("through page 4", summary)

    def test_split_boundary_must_be_adjacent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _make_pages(root, 6)
            draft = _resolved_draft(mode="split", rt_end=3, ct_start=5)
            issues = validate_payload(draft)
            self.assertTrue(
                any("rt_end_file_page" in issue for issue in issues)
            )
            self.assertTrue(
                any("ct_start_file_page" in issue for issue in issues)
            )

    def test_split_out_of_range_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _make_pages(root, 6)
            draft = _resolved_draft(mode="split", rt_end=6, ct_start=7)
            issues = validate_payload(draft)
            self.assertTrue(any("rt_end_file_page" in issue for issue in issues))
            with self.assertRaises(TranscriptLayoutError):
                finalize_layout_draft(root, draft)

    def test_agent_result_requires_high_confidence_to_resolve(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _make_pages(root, 3)
            draft = _resolved_draft(
                mode="ct_only",
                ct_start=1,
                confidence="medium",
            )
            self.assertTrue(
                any("high confidence" in issue for issue in validate_payload(draft))
            )

    def test_manual_override_is_resolved_without_model_confidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _make_pages(root, 5)
            (root / "manifest.json").write_text(
                json.dumps({}), encoding="utf-8"
            )
            output = apply_manual_override(
                root, mode="split", rt_end_file_page=2, note="Verified by user."
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "resolved")
            self.assertEqual(payload["decision_source"], "manual")
            self.assertEqual(payload["confidence"], "manual")
            self.assertEqual(payload["ct_start_file_page"], 3)
            self.assertEqual(legacy_manifest_split(root), ("split", 2))

    def test_manual_override_out_of_range_rejected_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _make_pages(root, 5)
            with self.assertRaises(TranscriptLayoutError):
                apply_manual_override(root, mode="split", rt_end_file_page=5)
            self.assertFalse((root / "artifacts" / "transcript_layout.json").exists())

    def test_manual_override_requires_create_files_first(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(TranscriptLayoutError):
                apply_manual_override(root, mode="rt_only")

    def test_needs_review_is_structurally_valid_but_not_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _make_pages(root, 3)
            draft = _resolved_draft(
                mode=None,
                status="needs_review",
                confidence="low",
                rt_end=None,
                ct_start=None,
                warnings=["Multiple transitions; cannot choose a single boundary."],
            )
            self.assertEqual(validate_payload(draft), [])
            finalize_layout_draft(root, draft)

            self.assertEqual(detection_status(root), ("needs_review", None))
            self.assertEqual(read_resolved_layout(root), None)
            self.assertIn("Needs review", layout_display_summary(root))
            with self.assertRaises(TranscriptLayoutError):
                resolve_rt_ct_split(root, root / "text_pages")

    def test_needs_review_requires_a_warning(self) -> None:
        draft = _resolved_draft(
            mode=None,
            status="needs_review",
            confidence="low",
            warnings=[],
        )
        self.assertTrue(
            any("needs_review requires at least one warning" in issue for issue in validate_payload(draft))
        )

    def test_malformed_and_unsafe_evidence_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _make_pages(root, 3)
            malformed = {"artifact": "wrong", "schema_version": 9, "mode": "sideways"}
            self.assertTrue(validate_payload(malformed))
            with self.assertRaises(TranscriptLayoutError):
                finalize_layout_draft(root, malformed)
            unsafe = _resolved_draft(
                mode="rt_only",
                rt_end=3,
                evidence=[{"path": "../other_case/secret.txt", "kind": "text"}],
                _stamp=False,
            )
            unsafe["input_page_count"] = 3
            unsafe["input_signature"] = "stamped"
            with self.assertRaises(TranscriptLayoutError):
                finalize_layout_draft(root, dict(unsafe))
            safe = _resolved_draft(
                mode="rt_only",
                rt_end=3,
                evidence=[{"path": "text_pages/0001.txt", "kind": "text"}],
            )
            finalized = finalize_layout_draft(root, safe)
            payload = json.loads(finalized.read_text(encoding="utf-8"))
            self.assertEqual(
                payload["evidence"][0]["path"], "text_pages/0001.txt"
            )
            self.assertEqual(validate_payload(payload), [])

    def test_stale_signature_rejected_after_page_regeneration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _make_pages(root, 3)
            draft = _resolved_draft(mode="ct_only", ct_start=1)
            finalize_layout_draft(root, draft)
            self.assertIsNotNone(read_resolved_layout(root))

            (root / "text_pages" / "0001.txt").write_text(
                "changed content\n", encoding="utf-8"
            )
            self.assertEqual(detection_status(root), ("pending", "ct_only"))
            self.assertIsNone(read_resolved_layout(root))
            with self.assertRaises(TranscriptLayoutError):
                resolve_rt_ct_split(root, root / "text_pages")

    def test_stale_page_count_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _make_pages(root, 3)
            draft = _resolved_draft(mode="ct_only", ct_start=1)
            finalize_layout_draft(root, draft)
            (root / "text_pages" / "0004.txt").write_text("new", encoding="utf-8")
            (root / "image_pages" / "0004.png").write_bytes(b"image")
            self.assertIsNone(read_resolved_layout(root))

    def test_input_signature_changes_with_text_and_image_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _make_pages(root, 2)
            first = input_signature(root)
            (root / "image_pages" / "0001.png").write_bytes(b"bigger-image")
            self.assertNotEqual(input_signature(root), first)

    def test_resolved_payload_requires_evidence_and_search_summary(self) -> None:
        draft = _resolved_draft(mode="rt_only", rt_end=2, evidence=[])
        issues = validate_payload(draft)
        self.assertTrue(any("supporting evidence" in issue for issue in issues))
        draft = _resolved_draft(mode="rt_only", rt_end=2)
        draft["search_summary"] = ""
        issues = validate_payload(draft)
        self.assertTrue(any("search_summary" in issue for issue in issues))

    def test_freshness_of_manual_override_signature(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _make_pages(root, 4)
            apply_manual_override(root, mode="split", rt_end_file_page=2)
            self.assertEqual(detection_status(root), ("resolved", "split"))
            payload = json.loads(
                (root / "artifacts" / "transcript_layout.json").read_text(encoding="utf-8")
            )
            self.assertEqual(payload["artifact"], ARTIFACT_NAME)
            self.assertEqual(payload["schema_version"], 1)


class TranscriptLayoutConfigTests(unittest.TestCase):
    def test_obsolete_rt_ct_split_config_key_is_removed_on_load(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_path = Path(temporary) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "rt_ct_split_page": 191,
                        "summarize_model_id": "kept-model",
                        "run_until_step": None,
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch(
                "recordprep.ui.main_window.CONFIG_FILE", config_path
            ):
                config = _read_config()
            self.assertNotIn("rt_ct_split_page", config)
            self.assertEqual(config["summarize_model_id"], "kept-model")
            persisted = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertNotIn("rt_ct_split_page", persisted)
            self.assertIn("rt_ct_split_page", OBSOLETE_PIPELINE_CONFIG_KEYS)

    def test_write_config_never_restores_split_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_path = Path(temporary) / "config.json"
            config_path.write_text(json.dumps({"rt_ct_split_page": 191}), encoding="utf-8")
            with mock.patch(
                "recordprep.ui.main_window.CONFIG_FILE", config_path
            ):
                _write_config({"rt_ct_split_page": 999, "case_name": "A"})
            persisted = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertNotIn("rt_ct_split_page", persisted)
            self.assertEqual(persisted["case_name"], "A")


if __name__ == "__main__":
    unittest.main()
