"""Fictional review scenarios and offline native-runner publication tests."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock

from recordprep import classification_review as review
from recordprep.output_presence import step_outputs_present

PROJECT = Path(__file__).resolve().parents[1]


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "bundle"
        for folder in ("classification", "text_pages", "image_pages"):
            (self.root / folder).mkdir(parents=True)
        self.project = self.base / ".pi"
        shutil.copytree(PROJECT / ".pi", self.project)
        self.workspace = self.base / "workspace"
        (self.workspace / ".pi/skills" / review.SKILL).mkdir(parents=True, mode=0o700)
        self.workspace.chmod(0o700)
        shutil.copyfile(self.project / "skills" / review.SKILL / "SKILL.md", self.workspace / ".pi/skills" / review.SKILL / "SKILL.md")
        self.rows = [
            {"file_name": "0001.txt", "page_type": "CT_report_first_page", "report_first_page": "yes", "name": "Synthetic Report", "date": "January 3, 2025"},
            {"file_name": "0002.txt", "page_type": "CT_other", "custom_preserved": "unchanged"},
            {"file_name": "0003.txt", "page_type": "CT_report", "report_first_page": "no"},
            {"file_name": "0004.txt", "page_type": "CT_minute_order_first_page", "date": "January 4, 2025"},
            {"file_name": "0005.txt", "page_type": "CT_minute_order_first_page", "date": "January 4, 2025"},
        ]
        self.filename = "CT_basic_advanced_dates_names.jsonl"
        self.output = self.root / "classification" / self.filename
        self.final_output = self.root / "classification/CT_basic_advanced_dates_names_corrected.jsonl"
        self.output.write_text("\n".join(json.dumps(r) for r in self.rows) + "\n")
        for row in self.rows:
            name = row["file_name"]
            (self.root / "text_pages" / name).write_text("Fictional source for isolated tests")
            # A real minimal synthetic PNG, no private-record-derived fixture.
            import base64
            (self.root / "image_pages" / (Path(name).stem + ".png")).write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aY4sAAAAASUVORK5CYII="))
        for target, value in (("resolve_case_profile", None), ("read_case_profile_ref", None)):
            mock = patch.object(review, target, return_value=value)
            mock.start(); self.addCleanup(mock.stop)
        # Use an isolated no-op selection lock, never the real settings store.
        from contextlib import nullcontext
        lock = patch.object(review, "case_profile_publication", side_effect=lambda *a: nullcontext())
        lock.start(); self.addCleanup(lock.stop)
        env = patch.dict(os.environ, {"PI_CODING_AGENT_DIR": str(self.base / "agent"),
            "RECORDPREP_CONFIG_DIR": str(self.base / "config"), "XDG_CACHE_HOME": str(self.base / "cache"), "PI_RUN_METRICS_ENABLED": "0"})
        env.start(); self.addCleanup(env.stop)

    def prepared(self, changes=None):
        guard, ref, candidate, spec, prompt = review.stage_inputs(self.root, self.project, self.workspace)
        access = json.loads(spec.read_text())
        Path(access["journal"]).write_text("\n".join(json.dumps(p) for p in access["reads"]) + "\n")
        value = {"schema_version": 1, "reviewed_blocks": ["block-0001"], "changes": changes or [], "unresolved": []}
        candidate.write_text(json.dumps(value))
        return guard, ref, candidate, spec, prompt

    def continuity(self):
        return {"file_name": "0002.txt", "before": {"page_type": "CT_other", "report_first_page": None},
                "after": {"page_type": "CT_report", "report_first_page": "no"}, "impact": "report_continuity",
                "reason": "Continuing report text and internal pagination restore the named report range.",
                "evidence": ["0001.txt", "0002.txt", "0003.txt"]}

    def test_report_gap_and_false_start_apply_archive_and_audit(self):
        false_start = {"file_name": "0005.txt", "before": {"page_type": "CT_minute_order_first_page", "date": "January 4, 2025"},
            "after": {"page_type": "CT_minute_order", "date": None}, "impact": "false_start",
            "reason": "Printed page two continues the preceding minute order, not a new order.", "evidence": ["0004.txt", "0005.txt"]}
        before = self.output.read_bytes()
        guard, ref, candidate, _, _ = self.prepared([self.continuity(), false_start])
        self.assertEqual(review.publish(self.root, self.project, guard, ref, candidate), (2, 0))
        self.assertEqual(self.output.read_bytes(), before)
        rows = [json.loads(l) for l in self.final_output.read_text().splitlines()]
        self.assertEqual(rows[1]["custom_preserved"], "unchanged")
        self.assertEqual(rows[1]["page_type"], "CT_report")
        self.assertNotIn("date", rows[4])
        receipt = json.loads((self.root / review.RECEIPT).read_text())
        self.assertEqual((self.root / receipt["archive"] / self.filename).read_bytes(), before)
        self.assertEqual(review.output_issues(self.root), [])
        self.assertTrue(step_outputs_present("correct_classification_agent", self.root))
        self.assertFalse((self.root / review.PENDING).exists())

    def test_no_changes_preserves_bytes_and_records_review(self):
        before = self.output.read_bytes(), self.output.stat().st_mtime_ns
        guard, ref, candidate, _, _ = self.prepared()
        self.assertEqual(review.publish(self.root, self.project, guard, ref, candidate), (0, 0))
        self.assertEqual((self.output.read_bytes(), self.output.stat().st_mtime_ns), before)

    def test_rt_transition_hints_recover_start_with_date_without_adjacency_mutation(self):
        from recordprep.classification_files import names
        self.output.unlink()
        raw = self.root / 'classification' / names('names')[0]
        rows = [{'file_name':f'{i:04d}.txt','page_type':kind} for i,kind in enumerate(
            ['RT_cover','RT_body','RT_body','RT_body_first_page','RT_body_first_page'],1)]
        raw.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        before = raw.read_bytes()
        hints = review.prioritized_worklist({r['file_name']:r for r in rows})['priority_1_rt_transition_checks']
        self.assertEqual([h['page'] for h in hints], ['0002.txt','0005.txt'])
        self.assertEqual(rows[1]['page_type'],'RT_body')
        change = {'file_name':'0002.txt','before':{'page_type':'RT_body','date':None},
                  'after':{'page_type':'RT_body_first_page','date':'January 3, 2025'},
                  'impact':'missed_document','reason':'Fictional opening identifies a separate dated hearing.',
                  'evidence':['0001.txt','0002.txt']}
        guard,ref,candidate,_,_ = self.prepared([change])
        self.assertEqual(review.publish(self.root,self.project,guard,ref,candidate),(1,0))
        final = self.root / 'classification' / names('final')[0]
        result = [json.loads(line) for line in final.read_text().splitlines()]
        self.assertEqual(result[1]['date'],'January 3, 2025')
        self.assertEqual(result[4]['page_type'],'RT_body_first_page')
        self.assertEqual(raw.read_bytes(),before)

    def test_separate_zero_change_final_and_manual_final_backup_on_retry(self):
        from recordprep.classification_files import require_review, final_paths
        guard,ref,candidate,_,_ = self.prepared()
        review.publish(self.root,self.project,guard,ref,candidate)
        self.assertEqual(self.output.read_bytes(),self.final_output.read_bytes())
        before = self.final_output.stat().st_mtime_ns
        guard,ref,candidate,_,_ = self.prepared()
        review.publish(self.root,self.project,guard,ref,candidate)
        self.assertEqual(self.final_output.stat().st_mtime_ns,before)
        manual = self.final_output.read_text().replace('unchanged','manual final edit')
        self.final_output.write_text(manual)
        require_review(self.root)
        guard,ref,candidate,_,_ = self.prepared()
        atomic = review._atomic_write
        def fail_receipt(path, text):
            if path == self.root / review.RECEIPT and text != old_receipt:
                raise OSError('synthetic publication failure')
            return atomic(path,text)
        old_receipt = (self.root / review.RECEIPT).read_text()
        with patch.object(review,'_atomic_write',side_effect=fail_receipt), self.assertRaises(OSError):
            review.publish(self.root,self.project,guard,ref,candidate)
        self.assertEqual(self.final_output.read_text(),manual)
        self.assertEqual((self.root / review.RECEIPT).read_text(),old_receipt)
        with self.assertRaises(ValueError): final_paths(self.root)
        self.assertFalse(step_outputs_present('correct_classification_agent',self.root))
        self.assertFalse((self.root / review.PENDING).exists())

    def test_bad_proposals_preserve_output(self):
        cases = []
        for mutation in (
            lambda c: c["after"].update(page_type="RT_body"),
            lambda c: c["after"].update(report_first_page="yes"),
            lambda c: c["before"].update(page_type="CT_form"),
            lambda c: c.update(evidence=["0002.txt"]),
            lambda c: c.update(evidence=["../../outside"]),
            lambda c: c.update(impact="cosmetic"),
            lambda c: c["after"].update(file_name="0006.txt"),
            lambda c: c.update(file_name="9999.txt"),
        ):
            c = self.continuity(); mutation(c); cases.append([c])
        cases.append([self.continuity(), self.continuity()])
        original = self.output.read_bytes()
        for changes in cases:
            with self.subTest(changes=changes):
                guard, ref, candidate, _, _ = self.prepared(changes)
                with self.assertRaises(ValueError):
                    review.publish(self.root, self.project, guard, ref, candidate)
                self.assertEqual(self.output.read_bytes(), original)

    def test_missing_evidence_coverage_invalid_json_and_stale_inputs(self):
        for mode in ("image", "block", "coverage", "duplicate_key", "source", "output", "model", "stop"):
            with self.subTest(mode=mode):
                guard, ref, candidate, spec, _ = self.prepared([self.continuity()])
                access = json.loads(spec.read_text())
                if mode in ("image", "block"):
                    Path(access["journal"]).write_text("\n".join(json.dumps(p) for p in access["reads"] if ("image_pages" not in p if mode == "image" else "block-" not in p)))
                elif mode == "coverage":
                    value = json.loads(candidate.read_text()); value["reviewed_blocks"] = []; candidate.write_text(json.dumps(value))
                elif mode == "duplicate_key": candidate.write_text('{"changes":[],"changes":[]}')
                elif mode == "source": (self.root / "text_pages/0002.txt").write_text("Changed synthetic source")
                elif mode == "output": self.output.write_text(self.output.read_text() + "\n")
                elif mode == "model": guard["model"] = [{"defaultModel": "different"}]
                before = self.output.read_bytes()
                def stop():
                    if mode == "stop": raise ValueError("Stopped")
                with self.assertRaises(ValueError): review.publish(self.root, self.project, guard, ref, candidate, check_stop=stop)
                self.assertEqual(self.output.read_bytes(), before)

    def test_pending_blocks_new_work_and_failed_publication_rolls_back(self):
        before = self.output.read_bytes()
        guard, ref, candidate, _, _ = self.prepared([self.continuity()])
        real_write = review._atomic_write
        def fail_receipt(path, data):
            if path == self.root / review.RECEIPT: raise OSError("Synthetic write failure")
            return real_write(path, data)
        with patch.object(review, "_atomic_write", side_effect=fail_receipt):
            with self.assertRaises(OSError): review.publish(self.root, self.project, guard, ref, candidate)
        self.assertEqual(self.output.read_bytes(), before)
        self.assertFalse((self.root / review.PENDING).exists())
        (self.root / review.PENDING).write_text('{}')
        with self.assertRaisesRegex(ValueError, "Interrupted"): review.capture(self.root, self.project)

    def test_symlinks_and_incomplete_coverage_fail_closed(self):
        guard, ref, candidate, _, _ = self.prepared()
        outside = self.base / "outside"; outside.write_text("Canary")
        candidate.unlink(); candidate.symlink_to(outside)
        with self.assertRaises((OSError, ValueError)): review.publish(self.root, self.project, guard, ref, candidate)
        page = self.root / "image_pages/0001.png"
        page.unlink(); page.symlink_to(outside)
        with self.assertRaises((OSError, ValueError)): review.capture(self.root, self.project)
        self.assertEqual(outside.read_text(), "Canary")

    def test_native_runner_shared_settings_and_private_guard(self):
        spec = importlib.util.spec_from_file_location("review_test_runner", PROJECT / ".pi/scripts/run_recordprep_skill.py")
        runner = importlib.util.module_from_spec(spec); sys.modules[spec.name] = runner; spec.loader.exec_module(runner)
        workspaces = []
        def child(command, *, cwd, env, **kwargs):
            workspaces.append(Path(cwd))
            self.assertEqual(command[command.index("--tools")+1], "read,write,edit")
            self.assertTrue(any(str(v).endswith(review.EXTENSION) for v in command))
            self.assertFalse(any(v in command for v in ("--model", "--provider", "--thinking")))
            self.assertIn('/skill:' + review.SKILL + ' ', command[-1])
            access = json.loads(Path(env["RECORDPREP_CLASSIFICATION_REVIEW_ACCESS_SPEC"]).read_text())
            Path(access["journal"]).write_text("\n".join(json.dumps(p) for p in access["reads"]))
            Path(access["candidate"]).write_text(json.dumps({"schema_version":1,"reviewed_blocks":["block-0001"],"changes":[],"unresolved":[]}))
            return SimpleNamespace(pid=os.getpid(), wait=lambda **kwargs: 0)
        with patch.object(runner, "_resolve_pi_command", return_value=["/usr/bin/true"]), patch.object(runner, "_check_pi_version"), patch.object(runner, "StageMonitor"), patch.object(runner.sys.stdin, "isatty", return_value=False), patch.object(runner.subprocess, "Popen", side_effect=child), patch("recordprep.run_metrics.instrument", side_effect=lambda command, env, *a:(command,env)):
            self.assertEqual(runner._run_stage(runner.STAGES["correct_classification_agent"], self.root, self.project),0)
        self.assertTrue(all(not p.exists() for p in workspaces))
        self.assertEqual(review.output_issues(self.root), [])

    def test_real_extension_guard_offline(self):
        import subprocess
        if not shutil.which("node"):
            self.skipTest("Node unavailable")
        result = subprocess.run(["node", "tests/classification_review_tools_contract.mjs"], cwd=PROJECT,
            env=os.environ | {"RECORDPREP_GUARD_TEST_ROOT": str(self.base / "guard")}, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_stale_date_and_unapproved_name_are_rejected(self):
        cases = [
            {"file_name":"0005.txt", "before":{"page_type":"CT_minute_order_first_page"},
             "after":{"page_type":"CT_minute_order"}, "impact":"false_start",
             "reason":"Page two continues the preceding minute order.", "evidence":["0004.txt","0005.txt"]},
            {"file_name":"0001.txt", "before":{"name":"Synthetic Report"},
             "after":{"name":"Invented Report"}, "impact":"date_or_name",
             "reason":"A proposed name must match an actual approved catalog entry.", "evidence":["0001.txt"]},
        ]
        for change in cases:
            guard, ref, candidate, _, _ = self.prepared([change])
            before = self.output.read_bytes()
            with self.assertRaises(ValueError): review.publish(self.root,self.project,guard,ref,candidate)
            self.assertEqual(self.output.read_bytes(),before)

    def test_unresolved_only_is_a_completed_nonmutating_review(self):
        guard, ref, candidate, _, _ = self.prepared()
        value=json.loads(candidate.read_text())
        value["unresolved"]=[{"file_name":"0002.txt","reason":"The image is ambiguous; manually check the neighboring report before changing its range."}]
        candidate.write_text(json.dumps(value))
        before=self.output.read_bytes()
        self.assertEqual(review.publish(self.root,self.project,guard,ref,candidate),(0,1))
        self.assertEqual(self.output.read_bytes(),before)

    def test_rt_only_and_mixed_retention(self):
        ct_before=self.output.read_bytes()
        rt_name="RT_basic_advanced_dates_names.jsonl"
        rt=self.root / "classification" / rt_name
        rt.write_text('{"file_name":"0006.txt","page_type":"RT_body_first_page","date":"January 5, 2025"}\n')
        (self.root / "text_pages/0006.txt").write_text("Fictional hearing opening")
        (self.root / "image_pages/0006.png").write_bytes((self.root / "image_pages/0001.png").read_bytes())
        rt_before=rt.read_bytes()
        guard,ref,candidate,_,_=self.prepared()
        review.publish(self.root,self.project,guard,ref,candidate)
        self.assertEqual(self.output.read_bytes(),ct_before)
        self.assertEqual(rt.read_bytes(),rt_before)
        self.output.unlink()
        for row in self.rows:
            (self.root / "text_pages" / row["file_name"]).unlink()
            (self.root / "image_pages" / (Path(row["file_name"]).stem+".png")).unlink()
        guard,ref,candidate,_,_=self.prepared()
        review.publish(self.root,self.project,guard,ref,candidate)
        self.assertEqual(rt.read_bytes(),rt_before)

    def test_priorities_use_selection_not_taxonomy_cleanup(self):
        rows = {r["file_name"]: r for r in self.rows}
        rows["0006.txt"] = {"file_name":"0006.txt", "page_type":"CT_report_first_page", "report_first_page":"yes"}
        plan = review.prioritized_worklist(rows)
        report = plan["priority_1_selected_report_boundaries"][0]
        self.assertEqual((report["start"],report["end"]),("0001.txt","0001.txt"))
        self.assertIn("0002.txt", report["ending_neighbors"])
        self.assertEqual(plan["priority_2_unnamed_report_starts"],["0006.txt"])
        self.assertTrue(plan["priority_1_hearing_and_minute_starts"][1]["same_date_as_previous_start"])
        _,_,_,_,_=self.prepared()
        self.assertEqual(json.loads((self.workspace / "review-worklist.json").read_text())["priorities"],review.prioritized_worklist({r["file_name"]:r for r in self.rows}))

    def test_no_effect_cleanup_is_not_published_or_lost_from_audit(self):
        self.rows[2].update(page_type="CT_report_first_page",report_first_page="yes")
        self.output.write_text("\n".join(json.dumps(r) for r in self.rows)+"\n")
        change={"file_name":"0003.txt","before":{"page_type":"CT_report_first_page","report_first_page":"yes"},
                "after":{"page_type":"CT_other","report_first_page":None},"impact":"document_identity",
                "reason":"An isolated unnamed synthetic attachment appears to be raw results.","evidence":["0002.txt","0003.txt"]}
        original=self.output.read_bytes(),self.output.stat().st_mtime_ns
        guard,ref,candidate,_,_=self.prepared([change])
        self.assertEqual(review.publish(self.root,self.project,guard,ref,candidate),(0,0))
        self.assertEqual((self.output.read_bytes(),self.output.stat().st_mtime_ns),original)
        saved=review.saved_review(self.root)
        self.assertEqual(saved["review"]["not_applied"][0]["change"],change)
        self.assertIn("NOT APPLIED: 1",review.review_details(saved))

    def test_joint_gap_repairs_and_unnamed_boundaries_remain_effective(self):
        rows={r["file_name"]:dict(r) for r in self.rows}
        rows["0003.txt"]={"file_name":"0003.txt","page_type":"CT_other"}
        rows["0004.txt"]={"file_name":"0004.txt","page_type":"CT_report","report_first_page":"no"}
        corrected={n:dict(r) for n,r in rows.items()}
        for n in ("0002.txt","0003.txt"):
            corrected[n].update(page_type="CT_report",report_first_page="no")
        candidate={"changes":[{"file_name":n} for n in ("0002.txt","0003.txt")],"unresolved":[]}
        retained,audit=review.retain_effective_changes(rows,corrected,candidate)
        self.assertEqual(len(audit["changes"]),2)
        self.assertEqual(review.selected_documents(retained)[0]["end"],"0004.txt")
        # An unnamed genuine start inside a named run must still split it.
        original=retained
        changed={n:dict(r) for n,r in original.items()}
        changed["0003.txt"].update(page_type="CT_report_first_page",report_first_page="yes")
        _,audit=review.retain_effective_changes(original,changed,{"changes":[{"file_name":"0003.txt"}],"unresolved":[]})
        self.assertEqual(len(audit["changes"]),1)

    def test_missing_eligible_document_can_be_added_outside_selected_ranges(self):
        change={"file_name":"0002.txt","before":{"page_type":"CT_other","report_first_page":None,"name":None},
                "after":{"page_type":"CT_report_first_page","report_first_page":"yes","name":"New Report"},
                "impact":"missed_document","reason":"A distinct catalog-eligible report opening would otherwise be omitted.",
                "evidence":["0001.txt","0002.txt"]}
        _,_,candidate,spec,_=self.prepared([change])
        rows={r["file_name"]:r for r in self.rows}
        corrected,audit=review.validate_candidate(candidate.read_bytes(),rows,
            {"report":SimpleNamespace(allowed_names=["New Report"])},
            set(json.loads(spec.read_text())["reads"]),self.workspace,self.root)
        corrected,audit=review.retain_effective_changes(rows,corrected,audit)
        self.assertEqual(len(audit["changes"]),1)
        self.assertIn("New Report",[d["name"] for d in review.selected_documents(corrected)])

    def test_selection_projection_preserves_legacy_names_and_ignores_unused_fields(self):
        rows={"0001.txt":{"file_name":"0001.txt","page_type":"CT_report","report_name":"Legacy Report","report_date":"January 1, 2025"},
              "0002.txt":{"file_name":"0002.txt","page_type":"CT_report"},
              "0003.txt":{"file_name":"0003.txt","page_type":"CT_form_first_page","form_name":"Synthetic Form","date":"January 2, 2025"}}
        documents=review.selected_documents(rows)
        self.assertEqual(documents[0]["end"],"0002.txt")
        self.assertEqual(documents[0]["name"],"Legacy Report")
        self.assertEqual(documents[1]["date"],"")
        changed={n:dict(r) for n,r in rows.items()}
        changed["0003.txt"].pop("date")
        _,audit=review.retain_effective_changes(rows,changed,{"changes":[{"file_name":"0003.txt"}],"unresolved":[]})
        self.assertEqual(audit["changes"],[])
        changed["0003.txt"]["name"]="New Form"
        _,audit=review.retain_effective_changes(rows,changed,{"changes":[{"file_name":"0003.txt"}],"unresolved":[]})
        self.assertEqual(len(audit["changes"]),1)

    def test_confident_type_correction_does_not_require_resolving_form_date(self):
        change={"file_name":"0005.txt","before":{"page_type":"CT_minute_order_first_page","date":"January 4, 2025"},
                "after":{"page_type":"CT_form_first_page","date":None},"impact":"false_start",
                "reason":"The synthetic page is a form, not a minute record; conflicting form dates do not prevent removing the false start.",
                "evidence":["0004.txt","0005.txt"]}
        guard,ref,candidate,_,_=self.prepared([change])
        value=json.loads(candidate.read_text())
        value["unresolved"]=[{"file_name":"0005.txt","reason":"A potentially eligible form's identity needs a manual check; the false minute-order start is independently corrected."}]
        candidate.write_text(json.dumps(value))
        self.assertEqual(review.publish(self.root,self.project,guard,ref,candidate),(1,1))
        final=json.loads(self.final_output.read_text().splitlines()[-1])
        self.assertEqual(final["page_type"],"CT_form_first_page")
        self.assertNotIn("date",final)

    def test_telemetry_and_readonly_old_receipt_presentation(self):
        guard,ref,candidate,spec,_=self.prepared()
        journal=Path(json.loads(spec.read_text())["journal"])
        with journal.open("a") as f:
            for _ in range(2): f.write(json.dumps(str(self.root / "image_pages/0001.png"))+"\n")
        with patch.object(review.time,"monotonic",return_value=100):
            review.publish(self.root,self.project,guard,ref,candidate,started_at=20,agent_elapsed_seconds=60)
        value=review.saved_review(self.root)
        self.assertEqual(value["telemetry"]["elapsed_to_publication_seconds"],80)
        self.assertEqual(value["telemetry"]["source_reads"]["image_pages"],{"calls":7,"unique_pages":5})
        self.assertIn("Agent process: 60.0",review.review_details(value))
        # Historical receipt presentation must not migrate or require telemetry.
        value.pop("telemetry");value["review"].pop("not_applied")
        value["review"]["unresolved"]=[{"file_name":"0002.txt","reason":"<b>Literal untrusted text</b>"}]
        path=self.root / review.RECEIPT;path.write_text(json.dumps(value))
        before=path.read_bytes(),path.stat().st_mtime_ns
        self.assertIn("older review",review.review_details(review.saved_review(self.root)))
        self.assertIn("<b>Literal untrusted text</b>",review.review_details(value))
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)
        self.assertIn("1 finding needs review",review.review_summary(value))
        self.assertLess(review.review_details(value).index("FINDINGS NEEDING REVIEW"),review.review_details(value).index("APPLIED CORRECTIONS"))

    def test_ui_saved_review_refresh_clear_and_malformed_are_independent_of_badges(self):
        from recordprep.ui.main_window import RecordPrepWindow
        owner=SimpleNamespace(step_classification_agent_row=Mock(),_classification_review_button=Mock(),_resolve_case_root=lambda:self.root)
        guard,ref,candidate,_,_=self.prepared()
        review.publish(self.root,self.project,guard,ref,candidate)
        with patch.object(review,"capture",side_effect=AssertionError("Presentation must not validate current inputs")):
            RecordPrepWindow._refresh_classification_review_result(owner)
        owner.step_classification_agent_row.set_subtitle.assert_called_with("0 pages corrected · 0 findings need review")
        owner._classification_review_button.set_sensitive.assert_called_with(True)
        (self.root / review.RECEIPT).write_text("invalid")
        RecordPrepWindow._refresh_classification_review_result(owner)
        self.assertIn("could not be read",owner.step_classification_agent_row.set_subtitle.call_args.args[0])
        self.assertTrue(step_outputs_present("correct_classification_agent",self.root))
        owner._resolve_case_root=lambda:None
        RecordPrepWindow._refresh_classification_review_result(owner)
        owner._classification_review_button.set_sensitive.assert_called_with(False)
        self.assertIn("Review consequential",owner.step_classification_agent_row.set_subtitle.call_args.args[0])

    def test_review_window_is_readonly_and_opens_at_top(self):
        from recordprep.ui.main_window import Adw, Gtk, ClassificationReviewWindow
        if not Gtk.init_check():
            self.skipTest("GTK display unavailable")
        Adw.init()
        value={"review":{"changes":[],"unresolved":[{"file_name":"0002.txt","reason":"Literal <b>source data</b> "*200}]}}
        window=ClassificationReviewWindow(None,self.root,value)
        try:
            self.assertFalse(window.text_view.get_editable())
            buffer=window.text_view.get_buffer()
            self.assertEqual(buffer.get_iter_at_mark(buffer.get_insert()).get_offset(),0)
            self.assertIn("Literal <b>source data</b>",buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),True))
        finally:
            window.destroy()

    def test_ui_order_and_no_classifier_endpoint_dependency(self):
        from recordprep.ui import main_window as ui
        steps = next(ids for phase, _, ids in ui.PIPELINE_PHASES if phase == "classify")
        self.assertEqual(steps[-2:], ("classify_names", "correct_classification_agent"))
        self.assertNotIn("correct_classification_agent", ui.VISION_CLASSIFICATION_STEP_IDS)


if __name__ == "__main__":
    unittest.main()
