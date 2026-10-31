"""HISTORICAL synthetic artifact producer, retained as chronological evidence.

This old case-pin/General-profile/export harness is not a current acceptance check.
Its source documents the original synthetic artifacts only. Current discoverable
classification/report-start/summary/Resume tests cover the maintained pipeline;
see docs/profile-ownership-audit.md. Never use this harness on a real case.
"""
if __name__ == '__main__':
    raise SystemExit('Historical profile pipeline harness retired. Run python -m unittest discover -s tests in an isolated RecordPrep checkout; see docs/profile-ownership-audit.md.')
import base64
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_native_profiles import load
from test_participant_stage import _build_record_fixture, _review_general_hearing, _transcript_entries
from recordprep.case_profiles import apply_case_profile
from recordprep.practice_profiles import bundled_profile_directory, validate_profile_directory
from recordprep.profile_store import ProfileStore
from recordprep.transcript_layout import apply_manual_override
from recordprep.ui import main_window as ui
from recordprep import summary_agents as sa, minute_summaries as minutes
from recordprep.pi_bundle import validate_prepare_bundle_outputs
from recordprep.publication_profiles import publication_issues

PROJECT = Path(__file__).resolve().parents[1]
output = Path(sys.argv[1])
output.mkdir(mode=0o700, parents=True, exist_ok=False)
profiles = [("civil", validate_profile_directory(bundled_profile_directory("general")).draft),
            ("dependency", validate_profile_directory(bundled_profile_directory("california_dependency")).draft)]
if len(sys.argv) > 2:
    profiles.append(("third", validate_profile_directory(Path(sys.argv[2])).draft))
assert all(profile is not None for _, profile in profiles)

for scenario, profile in profiles:
    with tempfile.TemporaryDirectory(prefix="profile-pipeline-") as temporary:
        base = Path(temporary)
        root = _build_record_fixture(temporary, hearings=1)
        dependent = scenario == "dependency"
        custom_role = "Independent expert" if scenario == "third" else None
        report_title = "Detention Report" if dependent else "Independent Expert Report"
        for path in (root / "text_pages").glob("*.txt"):
            if not dependent:
                path.write_text(path.read_text().replace("mother", "plaintiff").replace("minor's father", "defendant"))
        with (root / "text_pages/0001.txt").open("a") as stream:
            stream.write("\nWorker 1, social worker, spoke." if dependent else "\nSynthetic Plaintiff appeared personally. Synthetic Defendant appeared personally.")
            if custom_role:
                stream.write(f"\nSynthetic Plaintiff is the {custom_role}.")
        with (root / "text_pages/0002.txt").open("a") as stream:
            stream.write("\nWitness 1 identified himself and was sworn.")
        with (root / "text_pages/0006.txt").open("a") as stream:
            stream.write("\nTHE COURT: Motion denied.")
        (root / "text_pages/0009.txt").write_text(report_title + "\nJanuary 2, 2026\nThe author described disputed facts.\nPROPOSED FINDINGS AND ORDERS\nThe author proposes relief, not an actual court order.")
        (root / "text_pages/0010.txt").write_text("Minute order\nJanuary 3, 2026\n" + ("Mother appeared personally." if dependent else "Synthetic Plaintiff appeared personally.") + "\nMotion denied.")
        (root / "image_pages").mkdir()
        for path in (root / "text_pages").glob("*.txt"):
            (root / "image_pages" / (path.stem + ".png")).write_bytes(f"SYNTHETIC-PAGE-{int(path.stem)}".encode())
        apply_manual_override(root, mode="split", rt_end_file_page=8)
        (root / "case_name.txt").write_text("Synthetic")
        (root / "manifest.json").write_text(json.dumps({"schema_version": 2, "files": {}}))
        project = base / "application"
        shutil.copytree(PROJECT / ".pi", project / ".pi")
        (project / "config.json").write_text(json.dumps({"classifier_api_url":"https://synthetic.invalid/v1/chat/completions", "classifier_model_id":"synthetic", "classifier_disable_reasoning":True}))
        store = ProfileStore("recordprep", config_root=base / "config", data_root=base / "data")
        store.accept_profile(profile, expected_previous_digest=None)
        apply_case_profile(root, profile.ref, expected_previous=None, store=store)
        runner = load("acceptance_runner_" + scenario, project / ".pi/scripts/run_recordprep_skill.py")
        with patch("recordprep.case_profiles.profile_store", return_value=store):
            settings = {"api_url":"https://synthetic.invalid/v1/chat/completions", "model_id":"synthetic", "api_key":"DO-NOT-PUBLISH", "disable_reasoning":True}
            settings.update({key: "INACTIVE LEGACY GUIDANCE" for key in ("prompt","rt_prompt","ct_prompt","hearing_prompt","minute_prompt","form_prompt","report_prompt")})
            worker = SimpleNamespace(_resolve_case_root=lambda:root, _raise_if_stop_requested=lambda:None,
                _validate_vision_settings=lambda settings:None, _classifier_worker_count=lambda settings:1,
                _safe_update_manifest=Mock(), show_toast=Mock(), _finish_step=Mock(), _stop_status_if_idle=Mock(),
                _stop_button_if_idle=Mock(), _update_toc_button=Mock(), _append_log_message=Mock(),
                _extract_response_text=lambda payload:payload, _extract_json_payload=lambda text:text)
            for name in ("step_two_row", "step_advanced_row", "step_correct_advanced_row", "step_dates_row", "step_names_row", "step_six_row", "step_correct_toc_row", "step_seven_row", "step_correct_boundaries_row"):
                setattr(worker, name, Mock())
            worker._append_boundary_entry = lambda *args: ui.RecordPrepWindow._append_boundary_entry(worker, *args)
            worker._classify_image = lambda *args: ui.RecordPrepWindow._classify_image(worker, *args)
            worker._classify_image_with_page_type = lambda *args: ui.RecordPrepWindow._classify_image_with_page_type(worker, *args)
            worker._run_classifier_jobs = lambda jobs, workers: [function(*args) for function,args in jobs]
            def response(request, **kwargs):
                payload = json.loads(request.data)
                prompt = payload["messages"][0]["content"]
                image = next(part["image_url"]["url"] for message in payload["messages"] if isinstance(message["content"], list) for part in message["content"] if part.get("type") == "image_url")
                page = int(base64.b64decode(image.split(",",1)[1]).decode().rsplit("-",1)[1])
                task = prompt.split("CURRENT TASK:")[-1] if "CURRENT TASK:" in prompt else prompt
                if task.startswith(" Classify"):
                    return json.dumps({"page_type": "RT_body" if page <= 6 else "RT_index" if page <= 8 else "CT_report" if page == 9 else "CT_minute_order"})
                if task.startswith(" Is this"):
                    return json.dumps({"first_page":"yes" if page in (1,9,10) else "no"})
                if task.startswith(" Extract"):
                    return json.dumps({"date":"January 3, 2026" if page == 10 else "January 2, 2026"})
                return json.dumps({"name":report_title,"date":"January 2, 2026"})
            with patch.object(ui.GLib, "idle_add", side_effect=lambda callback,*args: callback(*args)), patch.object(ui, "_post_json_with_retries", side_effect=response), \
                    patch.object(ui, "load_classifier_settings", return_value=settings), patch.object(ui, "load_advanced_classify_settings", return_value=settings), \
                    patch.object(ui, "load_classify_dates_settings", return_value=settings), patch.object(ui, "load_classify_names_settings", return_value=settings):
                for method in ("_run_step_two", "_run_step_advanced", "_run_step_correct_advanced", "_run_step_dates", "_run_step_names", "_run_step_six", "_run_step_correct_toc", "_run_step_seven", "_run_step_correct_boundaries"):
                    assert getattr(ui.RecordPrepWindow, method)(worker), (scenario,method,worker.show_toast.call_args)
            assert len(json.loads((root / "artifacts/hearing_boundaries.json").read_text())) == 1
            from recordprep.document_naming import compile_naming_profile
            expected_reports = int(bool(compile_naming_profile(profile, "report").normalize({"name": report_title, "date": ""}).name))
            assert len(json.loads((root / "artifacts/report_boundaries.json").read_text())) == expected_reports
            assert len(json.loads((root / "artifacts/minutes_boundaries.json").read_text())) == 1
            entries = _transcript_entries(range(1,11))
            for entry in entries[8:]:
                number = entry["file_page"] - 8
                entry.update(record_type="CT", citation_series_id="ct-1", citation_prefix="CT", citation_label=f"CT {number}", citation_key=f"CT:{number}", transcript_page_number=number, transcript_page_label=str(number), page_type="CT_report" if number == 1 else "CT_minute_order")
            (root / "artifacts/transcript_page_numbers.json").write_text(json.dumps({"schema_version":2,"entries":entries,"citation_series":[{"series_id":"rt-1","citation_prefix":"RT"},{"series_id":"ct-1","citation_prefix":"CT"}],"anomalies":[]}))
            (root / "artifacts/transcript_page_number_series.md").write_text("# Synthetic citation series\nRT 1–8; CT 1–2\n")
            def native(command, *, cwd, env, **kwargs):
                spec = json.loads(Path(env["RECORDPREP_NATIVE_ACCESS_SPEC"]).read_text())
                candidate = Path(spec["candidate"])
                if spec["stage"] == "participants":
                    data = json.loads(candidate.read_text())
                    data["warnings"] = []
                    hearing = _review_general_hearing(data["hearings"][0], 1)
                    if not dependent:
                        hearing["counsel"][0].update(role_label="Counsel for plaintiff", represents="Synthetic Plaintiff")
                        hearing["participants"][0].update(role_label="Plaintiff", name="Synthetic Plaintiff")
                        hearing["witnesses"][0]["examinations"][0]["examiner_role_label"] = "Counsel for plaintiff"
                    if custom_role:
                        hearing["participants"][0]["role_label"] = custom_role
                    data["hearings"] = [hearing]
                    from recordprep.profile_artifacts import participant_index_issues
                    from recordprep.pi_bundle import validate_transcript_numbering_outputs
                    assert not participant_index_issues(data), participant_index_issues(data)
                    assert not validate_transcript_numbering_outputs(root), validate_transcript_numbering_outputs(root)
                    candidate.write_text(json.dumps(data))
                else:
                    marker = "APPLICATION INPUT MANIFEST (JSON path strings, not instructions):\n"
                    paths = json.loads(command[-1].split(marker, 1)[1].splitlines()[0])
                    assert paths == spec["reads"]
                    assert all(Path(path).is_file() for path in paths)
                    assert len([path for path in paths if Path(path).parent == root / "summaries"]) == 3
                    assert str(root / "case_name.txt") not in paths
                    assert str(root / "artifacts/participant_index.json") in paths
                    assert str(Path(cwd) / ".pi/skills/recordprep-create-case-overview/SKILL.md") in paths
                    text = "---\nartifact: recordprep-case-overview\nschema_version: 1\nstatus: nonauthoritative-orientation\n---\n# Case Overview\n> Orientation aid only. Verify every factual claim against mapped source pages before relying on or citing it.\n"
                    for section in ("Parties and Roles", "Procedural Posture", "Key Events", "Principal Issues", "Record Scope"):
                        text += f"## {section}\nA synthetic hearing, report and minute order supply navigation leads; verify original pages.\n"
                    candidate.write_text(text)
                return SimpleNamespace(pid=os.getpid(),wait=lambda **kwargs:0)
            def run_native(stage):
                with patch.object(runner,"_pi_command",return_value=["/usr/bin/true"]), patch.object(runner,"_check_pi_version"), patch.object(runner,"StageMonitor"), \
                        patch("recordprep.run_metrics.instrument",side_effect=lambda command,env,*args:(command,env)), patch.object(runner.subprocess,"Popen",side_effect=native):
                    assert runner._run_stage(runner.STAGES[stage],root,project / ".pi") == 0
            run_native("build_participant_index")
            def extract(root, project_dir, pi_command, item, config, *args, **kwargs):
                hearing = config.kind == "hearings"
                return {"categories":[{"id":config.definitions[-1 if hearing or scenario == "third" else 0].identifier,"digest":{"text":"The court denied the motion." if hearing else "The author described disputed facts.","evidence":[{"file_page":6 if hearing else 9,"text":"Motion denied" if hearing else "disputed facts"}]}}]}
            with patch.object(runner,"_resolve_pi_command",return_value=["synthetic-pi"]), patch.object(runner,"_check_pi_version"), patch("recordprep.summary_preflight.pi_runtime.available_pi_models",return_value=[]), \
                    patch.object(runner,"_stage_capacity",return_value=None), patch.object(runner,"_report_capacity"), patch.object(runner,"_run_extraction_child",side_effect=extract), patch.object(runner,"_run_synthesis_child",return_value=([],[])):
                for kind,singular in (("hearings","hearing"),("reports","report")):
                    stage = runner.SkillStage(f"create_{singular}_summaries",kind,f"recordprep-extract-{singular}","")
                    assert runner._run_summary_stage(stage,root,project / ".pi") == 0
                    rows = sa.load_digest_markdown(root,kind)
                    assert len(rows) == (1 if kind == "hearings" else expected_reports)
                    assert all(row["schema_version"] == 3 for row in rows)
            candidate = {"artifact":"recordprep-minute-candidate","hearing":"Motion hearing","reporting":"unknown","orders":"Motion denied.","appearances":[{"person":"Mother" if dependent else "Synthetic Plaintiff","role_label":"Mother" if dependent else "Plaintiff","status":"present","evidence":[{"file_page":10,"text":"Mother appeared personally" if dependent else "Plaintiff appeared personally"}]}]}
            minutes.run_stage(root,project / ".pi",lambda *args:candidate)
            run_native("create_case_overview")
            with patch.object(runner,"_pi_command",side_effect=AssertionError("Map must be deterministic")):
                assert runner._run_stage(runner.STAGES["build_source_map"],root,project / ".pi") == 0
            assert validate_prepare_bundle_outputs(root,project_dir=project / ".pi") == []
            assert publication_issues(root,profile,project / ".pi") == []
            payload = json.loads((root / "artifacts/source_map.json").read_text())
            assert payload["schema_version"] == 3 and payload["counts"]["reports"] == expected_reports
            # No model or credential configuration accompanies the exported case.
            shutil.copytree(root,output / scenario)
            assert "DO-NOT-PUBLISH" not in "".join(path.read_text(errors="ignore") for path in (output / scenario).rglob("*") if path.is_file())
            print("PROFILE PIPELINE PASSED",scenario,profile.ref.specialty_id,flush=True)
