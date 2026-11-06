"""Useful knowledge-work results survive imperfect model output/bookkeeping."""
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from recordprep import classification_review as review
from recordprep.classification_files import final_paths, require_review
import test_classification_review_agent as fixtures


class BestEffortReviewTests(unittest.TestCase):
    setUp = fixtures.ReviewTests.setUp
    prepared = fixtures.ReviewTests.prepared
    continuity = fixtures.ReviewTests.continuity

    def saved(self):
        return review.saved_review(self.root)

    def false_start(self):
        return {"file_name": "0005.txt", "before": {"page_type": "CT_minute_order_first_page", "date": "January 4, 2025"},
                "after": {"page_type": "CT_minute_order", "date": None}, "impact": "false_start",
                "reason": "Page two continues the preceding order, not a separate minute order.",
                "evidence": ["0004.txt", "0005.txt"]}

    def test_unconfirmed_image_read_is_advisory_not_a_lost_correction(self):
        guard, ref, candidate, spec, _ = self.prepared([self.continuity(), self.false_start()])
        journal = Path(json.loads(spec.read_text())["journal"])
        journal.write_text("\n".join(line for line in journal.read_text().splitlines()
                                    if json.loads(line) != str(self.root / "image_pages/0002.png")))
        originals = self.output.read_bytes(), self.output.stat().st_mtime_ns
        raw, reads = candidate.read_bytes(), journal.read_bytes()
        require_review(self.root)
        self.assertEqual(review.publish(self.root, self.project, guard, ref, candidate), (2, 0))
        saved = self.saved()
        self.assertEqual(len(saved["review"]["changes"]), 2)
        notes = saved["review"]["warnings"]
        self.assertEqual(notes[0]["file_name"], "0002.txt")
        self.assertIn("0002.txt", notes[0]["reason"])
        self.assertEqual(final_paths(self.root)[1], self.final_output)
        self.assertEqual((self.output.read_bytes(), self.output.stat().st_mtime_ns), originals)
        archive = self.root / saved["archive"]
        self.assertEqual((archive / "review-candidate.json").read_bytes(), raw)
        self.assertEqual((archive / "review-reads.jsonl").read_bytes(), reads)
        self.assertFalse((archive / "sessions").exists())
        self.assertIn("REVIEW NOTES / LIMITATIONS", review.review_details(saved))
        self.assertIn("1 review note", review.review_summary(saved))

    def test_bad_proposal_does_not_cancel_other_corrections_or_unresolved_findings(self):
        bad = self.false_start()
        bad["before"]["date"] = "wrong before value"
        guard, ref, candidate, _, _ = self.prepared([bad, self.continuity()])
        value = json.loads(candidate.read_text())
        value["unresolved"] = [{"file_name": "0004.txt", "reason": "Check the source date if material."}]
        candidate.write_text(json.dumps(value))
        self.assertEqual(review.publish(self.root, self.project, guard, ref, candidate), (1, 2))
        saved = self.saved()["review"]
        self.assertEqual(saved["not_applied"][0]["change"], bad)
        self.assertEqual(saved["changes"][0]["file_name"], "0002.txt")
        final = [json.loads(line) for line in self.final_output.read_text().splitlines()]
        self.assertEqual(final[-1], self.rows[-1])
        self.assertEqual(final[1]["page_type"], "CT_report")
        self.assertIn("wrong before value", review.review_details(self.saved()))

    def test_duplicate_and_unknown_proposals_are_kept_for_review_not_stage_errors(self):
        duplicate = self.continuity()
        unknown = dict(self.false_start(), file_name="9999.txt")
        guard, ref, candidate, _, _ = self.prepared([self.continuity(), duplicate, unknown])
        self.assertEqual(review.publish(self.root, self.project, guard, ref, candidate), (1, 1))
        self.assertEqual(len(self.saved()["review"]["not_applied"]), 2)
        self.assertTrue(self.saved()["review"]["warnings"])
        self.assertEqual(review.output_issues(self.root), [])

    def test_partial_coverage_and_missing_rules_read_do_not_discard_useful_changes(self):
        guard, ref, candidate, spec, _ = self.prepared([self.continuity()])
        access = json.loads(spec.read_text())
        journal = Path(access["journal"])
        journal.write_text("\n".join(json.dumps(p) for p in access["reads"]
                                    if "block-" not in p and not p.endswith("classification-rules.txt")))
        value = json.loads(candidate.read_text())
        value["reviewed_blocks"] = []
        candidate.write_text(json.dumps(value))
        self.assertEqual(review.publish(self.root, self.project, guard, ref, candidate), (1, 0))
        saved = self.saved()
        self.assertFalse(saved["review"]["coverage"]["complete"])
        self.assertIn("partial review", review.review_summary(saved))
        self.assertEqual(final_paths(self.root)[1], self.final_output)

    def test_png_evidence_identifiers_are_normalized_not_rejected(self):
        change = self.continuity()
        change["evidence"] = [str(self.root / "image_pages/0001.png"), "0002.png", "0003.txt"]
        guard, ref, candidate, _, _ = self.prepared([change])
        self.assertEqual(review.publish(self.root, self.project, guard, ref, candidate), (1, 0))
        self.assertEqual(self.saved()["review"]["changes"][0]["evidence"], ["0001.txt", "0002.txt", "0003.txt"])
        self.assertEqual(self.saved()["review"]["warnings"], [])

    def test_absent_malformed_or_nonadjacent_evidence_is_an_explicit_limitation(self):
        for evidence in ([], None, ["../../unknown"], ["0002.txt", "0004.txt"]):
            with self.subTest(evidence=evidence):
                change = dict(self.continuity(), evidence=evidence)
                guard, ref, candidate, _, _ = self.prepared([change])
                self.assertEqual(review.publish(self.root, self.project, guard, ref, candidate), (1, 0))
                self.assertTrue(self.saved()["review"]["warnings"])

    def test_malformed_findings_do_not_cancel_a_valid_correction(self):
        guard, ref, candidate, _, _ = self.prepared([self.continuity(), None])
        value = json.loads(candidate.read_text())
        value["unresolved"] = [None, {"file_name": "9999.txt", "reason": "Unknown page"},
                               {"file_name": "0004.txt", "reason": "<b>Check date</b>"}]
        candidate.write_text(json.dumps(value))
        self.assertEqual(review.publish(self.root, self.project, guard, ref, candidate), (1, 1))
        self.assertIn("<b>Check date</b>", review.review_details(self.saved()))

    def test_unusable_json_publishes_unchanged_inputs_with_honest_partial_review(self):
        guard, ref, candidate, _, _ = self.prepared()
        candidate.write_text('{"changes":[truncated')
        before = self.output.read_bytes(), self.output.stat().st_mtime_ns
        self.assertEqual(review.publish(self.root, self.project, guard, ref, candidate), (0, 0))
        self.assertEqual(self.final_output.read_bytes(), before[0])
        self.assertEqual((self.output.read_bytes(), self.output.stat().st_mtime_ns), before)
        self.assertIn("partial review", review.review_summary(self.saved()))
        self.assertIn("not usable JSON", review.review_details(self.saved()))
        self.assertEqual((self.root / self.saved()["archive"] / "review-candidate.json").read_bytes(), candidate.read_bytes())

    def test_missing_candidate_is_a_reported_no_edit_result_not_false_full_review(self):
        guard, ref, candidate, _, _ = self.prepared()
        candidate.unlink()
        self.assertEqual(review.publish(self.root, self.project, guard, ref, candidate), (0, 0))
        self.assertIn("partial review", review.review_summary(self.saved()))
        self.assertTrue(self.saved()["review"]["warnings"])

    def test_fenced_json_and_nonessential_schema_fields_do_not_lose_proposals(self):
        guard, ref, candidate, _, _ = self.prepared([self.continuity()])
        value = json.loads(candidate.read_text())
        value.pop("schema_version")
        value["extra_notes"] = "Nonessential model annotation"
        value["changes"][0].pop("impact")
        value["changes"][0]["reason"] = "Short"
        candidate.write_text("```json\n" + json.dumps(value) + "\n```\n")
        self.assertEqual(review.publish(self.root, self.project, guard, ref, candidate), (1, 0))
        self.assertTrue(self.saved()["review"]["warnings"])

    def test_corrupt_or_missing_journal_is_advisory(self):
        for mode in ("corrupt", "missing"):
            with self.subTest(mode=mode):
                guard, ref, candidate, spec, _ = self.prepared([self.continuity()])
                journal = Path(json.loads(spec.read_text())["journal"])
                if mode == "corrupt":
                    with journal.open("a") as handle:
                        handle.write('{"not a path":true}\nnot JSON\n')
                else:
                    journal.unlink()
                self.assertEqual(review.publish(self.root, self.project, guard, ref, candidate), (1, 0))
                self.assertTrue(self.saved()["review"]["warnings"])

    def test_unsafe_journal_is_not_followed_or_allowed_to_cancel_corrections(self):
        guard, ref, candidate, spec, _ = self.prepared([self.continuity()])
        journal = Path(json.loads(spec.read_text())["journal"])
        journal.unlink()
        outside = self.base / "private-journal-canary"
        outside.write_text("Private canary must not be read or copied")
        journal.symlink_to(outside)
        self.assertEqual(review.publish(self.root, self.project, guard, ref, candidate), (1, 0))
        saved = self.saved()
        self.assertIn("not followed", review.review_details(saved))
        self.assertEqual((self.root / saved["archive"] / "review-reads.jsonl").read_bytes(), b"")
        self.assertEqual(outside.read_text(), "Private canary must not be read or copied")

    def test_attempt_preservation_keeps_candidate_and_reads_but_not_full_session(self):
        _, _, candidate, _, _ = self.prepared([self.continuity()])
        (self.workspace / "sessions").mkdir()
        (self.workspace / "sessions/private-session.jsonl").write_text("Synthetic session canary")
        saved = review.preserve_attempt(self.workspace)
        self.assertEqual((saved / candidate.name).read_bytes(), candidate.read_bytes())
        self.assertEqual({p.name for p in saved.iterdir()}, {"review-candidate.json", "review-reads.jsonl"})
        self.assertEqual(saved.stat().st_mode & 0o777, 0o700)

    def test_attempt_preservation_never_follows_unsafe_diagnostic_links(self):
        _, _, candidate, _, _ = self.prepared()
        candidate.unlink()
        outside = self.base / "private-canary"
        outside.write_text("Do not copy this canary")
        candidate.symlink_to(outside)
        saved = review.preserve_attempt(self.workspace)
        self.assertEqual({p.name for p in saved.iterdir()}, {"review-reads.jsonl"})
        self.assertEqual(outside.read_text(), "Do not copy this canary")

    def test_repeated_json_keys_do_not_erase_usable_proposals(self):
        guard, ref, candidate, _, _ = self.prepared([self.continuity()])
        candidate.write_text(candidate.read_text().replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1'))
        self.assertEqual(review.publish(self.root, self.project, guard, ref, candidate), (1, 0))
        self.assertIn("Repeated JSON", review.review_details(self.saved()))

    def test_malformed_lists_are_notes_not_stage_errors(self):
        for changes, unresolved in ((None, []), ([], None), ("bad changes", "bad findings")):
            guard, ref, candidate, _, _ = self.prepared()
            candidate.write_text(json.dumps({"schema_version": 1, "reviewed_blocks": ["block-0001"],
                                             "changes": changes, "unresolved": unresolved}))
            self.assertEqual(review.publish(self.root, self.project, guard, ref, candidate), (0, 0))
            self.assertEqual(self.final_output.read_bytes(), self.output.read_bytes())
            self.assertTrue(self.saved()["review"]["warnings"])

    def runner(self):
        spec = importlib.util.spec_from_file_location("best_effort_review_runner", fixtures.PROJECT / ".pi/scripts/run_recordprep_skill.py")
        runner = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = runner
        spec.loader.exec_module(runner)
        return runner

    def run_child(self, *, exit_code=0, change_inputs=False, stop=False):
        runner = self.runner()
        workspaces = []
        def child(command, *, cwd, env, **kwargs):
            workspace = Path(cwd)
            workspaces.append(workspace)
            access = json.loads(Path(env["RECORDPREP_CLASSIFICATION_REVIEW_ACCESS_SPEC"]).read_text())
            # Deliberately omit an image read: it must not kill a useful result.
            Path(access["journal"]).write_text("\n".join(json.dumps(p) for p in access["reads"]
                                                       if p != str(self.root / "image_pages/0002.png")))
            Path(access["candidate"]).write_text(json.dumps({"schema_version": 1, "reviewed_blocks": ["block-0001"],
                                                            "changes": [self.continuity()], "unresolved": []}))
            if change_inputs:
                (self.root / "text_pages/0002.txt").write_text("Changed after agent read")
            if stop:
                runner._stopped = True
            return SimpleNamespace(pid=os.getpid(), wait=lambda **kwargs: exit_code)
        with patch.object(runner, "_resolve_pi_command", return_value=["/usr/bin/true"]), \
                patch.object(runner, "_check_pi_version"), patch.object(runner, "StageMonitor"), \
                patch.object(runner.sys.stdin, "isatty", return_value=False), \
                patch.object(runner.subprocess, "Popen", side_effect=child), \
                patch("recordprep.run_metrics.instrument", side_effect=lambda command, env, *a: (command, env)):
            code = runner._run_stage(runner.STAGES["correct_classification_agent"], self.root, self.project)
        self.assertTrue(all(not p.exists() for p in workspaces))
        return code

    def test_native_runner_delivers_useful_result_despite_missing_image_read(self):
        self.assertEqual(self.run_child(), 0)
        self.assertEqual(len(self.saved()["review"]["changes"]), 1)
        self.assertTrue(self.saved()["review"]["warnings"])
        self.assertEqual(review.output_issues(self.root), [])

    def test_native_runner_retains_usable_candidate_after_abnormal_child_exit(self):
        self.assertEqual(self.run_child(exit_code=1), 0)
        self.assertEqual(len(self.saved()["review"]["changes"]), 1)
        self.assertIn("partial review", review.review_summary(self.saved()))
        self.assertIn("exited with code 1", review.review_details(self.saved()))

    def test_native_runner_preserves_minimal_attempt_when_inputs_change(self):
        with self.assertRaisesRegex(ValueError, "inputs changed"):
            self.run_child(change_inputs=True)
        attempts = list((self.base / "cache/recordprep-pi-workspaces").glob("review-attempt.*"))
        self.assertEqual(len(attempts), 1)
        self.assertTrue((attempts[0] / "review-candidate.json").is_file())
        self.assertFalse((attempts[0] / "sessions").exists())
        self.assertFalse(self.final_output.exists())

    def test_stop_preserves_attempt_but_never_publishes_or_continues(self):
        self.assertEqual(self.run_child(stop=True), 130)
        self.assertFalse(self.final_output.exists())
        self.assertFalse((self.root / review.RECEIPT).exists())
        self.assertTrue(list((self.base / "cache/recordprep-pi-workspaces").glob("review-attempt.*")))
