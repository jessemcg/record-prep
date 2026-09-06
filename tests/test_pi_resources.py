import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


PROJECT_DIR = Path(__file__).resolve().parent.parent
PI_DIR = PROJECT_DIR / ".pi"
RUNNER = PI_DIR / "scripts/run_recordprep_skill.py"


def _case_overview_text() -> str:
    return """---
artifact: recordprep-case-overview
schema_version: 1
status: nonauthoritative-orientation
---

# Case Overview

> Orientation aid only. Verify every factual claim against mapped source pages before relying on or citing it.

## Parties and Roles

The synthetic record concerns one child and two parents. The summaries distinguish those central parties from relatives, agency personnel, and service providers without listing every person who appeared.

## Procedural Posture

The matter includes an initial hearing, a later review, and a final summarized order. This short overview reports only the posture represented in the generated summaries and does not resolve any factual or legal dispute.

## Key Events

- January 2, 2025: The first summarized hearing occurred.
- February 3, 2025: A report added family and service information.
- March 4, 2025: The court reviewed progress and made another order.
- April 5, 2025: The summaries describe the last included proceeding.

## Principal Issues

The apparent issues involve placement, services, contact, and the orders reflected in the summarized proceedings. Matters omitted from a summary may still appear in an underlying source page.

## Record Scope

The available material includes hearing, report, and minute-order summaries from January through April 2025. The overview does not establish completeness. Every detail must be verified against mapped source pages before use.
"""


def _load_runner_module() -> "object":
    spec = importlib.util.spec_from_file_location(
        "run_recordprep_skill_module", RUNNER
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _runner_environment(
    case_bundle: Path,
    fake_pi: Path,
    cache: Path,
) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "RECORDPREP_CASE_BUNDLE": str(case_bundle),
            "RECORDPREP_PI_PROJECT_DIR": str(PI_DIR),
            "RECORDPREP_PI_COMMAND_ARGC": "1",
            "RECORDPREP_PI_COMMAND_ARG_0": str(fake_pi),
            "XDG_CACHE_HOME": str(cache),
            "PATH": str(fake_pi.parent) + os.pathsep + env.get("PATH", ""),
        }
    )
    return env


class PiResourceTests(unittest.TestCase):
    def test_project_resource_validator(self) -> None:
        result = subprocess.run(
            ["python3", str(RUNNER), "--validate-resources"],
            cwd=PROJECT_DIR,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("sequential PI resources are valid", result.stdout)

    def test_project_has_only_settings_skills_runner_and_auto_exit(self) -> None:
        settings = json.loads((PI_DIR / "settings.json").read_text(encoding="utf-8"))
        self.assertTrue(settings["defaultProvider"])
        self.assertTrue(settings["defaultModel"])
        self.assertTrue(settings["enableSkillCommands"])
        system_prompt = (PI_DIR / "SYSTEM.md").read_text(encoding="utf-8")
        self.assertIn("appellate-record organization", system_prompt)
        self.assertIn("not a coding assistant", system_prompt)
        self.assertFalse((PI_DIR / "agents").exists())
        self.assertFalse((PI_DIR / "workflows").exists())
        extensions = sorted(
            path.name for path in (PI_DIR / "extensions").iterdir()
        )
        self.assertEqual(
            extensions,
            [
                "recordprep-auto-exit.ts",
                "recordprep-summary-tools.ts",
            ],
        )
        extension_text = (
            PI_DIR / "extensions" / "recordprep-auto-exit.ts"
        ).read_text(encoding="utf-8")
        self.assertIn('pi.on("agent_end"', extension_text)
        self.assertIn("ctx.shutdown()", extension_text)
        summary_tools = (
            PI_DIR / "extensions" / "recordprep-summary-tools.ts"
        ).read_text(encoding="utf-8")
        for tool_name in (
            "recordprep_get_source",
            "recordprep_submit_extraction",
            "recordprep_get_facts",
            "recordprep_submit_summary_section",
            "recordprep_finish_summary",
        ):
            self.assertIn(f'"{tool_name}"', summary_tools)
        skills = sorted(path.parent.name for path in (PI_DIR / "skills").glob("*/SKILL.md"))
        self.assertEqual(
            skills,
            [
                "recordprep-build-participant-index",
                "recordprep-build-source-map",
                "recordprep-create-case-overview",
                "recordprep-detect-transcript-layout",
                "recordprep-extract-hearing",
                "recordprep-extract-report",
                "recordprep-number-transcript-pages",
                "recordprep-synthesize-hearings",
                "recordprep-synthesize-reports",
            ],
        )

    def test_runner_stages_one_skill_in_native_interactive_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            case_bundle = temp / "case_bundle"
            (case_bundle / "text_pages").mkdir(parents=True)
            (case_bundle / "text_pages/0001.txt").write_text("one", encoding="utf-8")
            invocation = temp / "fake-pi-invocation.txt"
            fake_pi = temp / "pi"
            fake_pi.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--version" ]]; then
  printf '0.80.10\\n'
  exit 0
fi
{
  printf 'cwd=%s\\n' "$PWD"
  printf 'session=%s\\n' "$PI_CODING_AGENT_SESSION_DIR"
  printf '%s\\n' "$@"
  find .pi -type f | sort
} > "$FAKE_PI_INVOCATION"
mkdir -p "$RECORDPREP_CASE_BUNDLE/artifacts"
printf '%s\\n' '{"schema_version":2,"entries":[{}],"citation_series":[]}' > "$RECORDPREP_CASE_BUNDLE/artifacts/transcript_page_numbers.json"
printf '# Citation series\\n' > "$RECORDPREP_CASE_BUNDLE/artifacts/transcript_page_number_series.md"
printf '\\033[32mNative PI terminal output\\033[0m\\n'
""",
                encoding="utf-8",
            )
            fake_pi.chmod(0o755)
            env = _runner_environment(case_bundle, fake_pi, temp / "cache")
            env["FAKE_PI_INVOCATION"] = str(invocation)

            result = subprocess.run(
                ["python3", str(RUNNER), "number_transcript_pages"],
                cwd=PROJECT_DIR,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Native PI terminal output", result.stdout)
            text = invocation.read_text(encoding="utf-8")
            self.assertNotIn("--mode", text)
            self.assertNotIn("--no-session", text)
            for flag in (
                "--no-extensions",
                "--no-skills",
                "--no-prompt-templates",
                "--no-themes",
                "--no-context-files",
            ):
                self.assertIn(flag, text)
            self.assertIn("--extension", text)
            self.assertIn("--system-prompt", text)
            self.assertIn(".pi/SYSTEM.md", text)
            self.assertIn("recordprep-auto-exit.ts", text)
            self.assertIn("recordprep-number-transcript-pages/SKILL.md", text)
            self.assertNotIn("recordprep-organize-hearing-summary", text)
            self.assertNotIn(".pi/agents", text)
            workspace_line = next(
                line for line in text.splitlines() if line.startswith("cwd=")
            )
            self.assertFalse(Path(workspace_line.split("=", 1)[1]).exists())
            session_line = next(
                line for line in text.splitlines() if line.startswith("session=")
            )
            self.assertIn("/sessions", session_line)

    def test_runner_appends_per_stage_model_overrides(self) -> None:
        """Native stages carry --provider/--model/--thinking from config."""
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            case_bundle = temp / "case_bundle"
            (case_bundle / "text_pages").mkdir(parents=True)
            (case_bundle / "text_pages/0001.txt").write_text("one", encoding="utf-8")
            invocation = temp / "fake-pi-invocation.txt"
            fake_pi = temp / "pi"
            fake_pi.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--version" ]]; then
  printf '0.85.0\\n'
  exit 0
fi
printf '%s\\n' "$@" > "$FAKE_PI_INVOCATION"
mkdir -p "$RECORDPREP_CASE_BUNDLE/artifacts"
printf '%s\\n' '{"schema_version":2,"entries":[{}],"citation_series":[]}' > "$RECORDPREP_CASE_BUNDLE/artifacts/transcript_page_numbers.json"
printf '# Citation series\\n' > "$RECORDPREP_CASE_BUNDLE/artifacts/transcript_page_number_series.md"
""",
                encoding="utf-8",
            )
            fake_pi.chmod(0o755)
            # Stage a full copy of the tracked .pi resources so the config
            # written next to it is a temp file, never the repository's.
            staged_project = temp / "staged-project"
            shutil.copytree(PI_DIR, staged_project / ".pi")
            env = _runner_environment(case_bundle, fake_pi, temp / "cache")
            env["RECORDPREP_PI_PROJECT_DIR"] = str(staged_project / ".pi")
            env["FAKE_PI_INVOCATION"] = str(invocation)
            config_path = staged_project / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "pi_stage_number_transcript_pages_pi_provider": "synthetic",
                        "pi_stage_number_transcript_pages_pi_model": "cheap-fast-model",
                        "pi_stage_number_transcript_pages_pi_thinking": "minimal",
                        "pi_stage_detect_transcript_layout_pi_model": "",
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                ["python3", str(RUNNER), "number_transcript_pages"],
                cwd=PROJECT_DIR,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            argv = invocation.read_text(encoding="utf-8")
            self.assertIn("--provider", argv)
            self.assertIn("synthetic", argv)
            self.assertIn("--model", argv)
            self.assertIn("cheap-fast-model", argv)
            self.assertIn("--thinking", argv)
            self.assertIn("minimal", argv)

    def test_runner_accepts_detect_layout_needs_review_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            case_bundle = temp / "case_bundle"
            (case_bundle / "text_pages").mkdir(parents=True)
            (case_bundle / "image_pages").mkdir(parents=True)
            (case_bundle / "text_pages/0001.txt").write_text("one", encoding="utf-8")
            (case_bundle / "image_pages/0001.png").write_bytes(b"image")
            fake_pi = temp / "pi"
            fake_pi.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--version" ]]; then
  printf '0.80.10\\n'
  exit 0
fi
mkdir -p "$RECORDPREP_CASE_BUNDLE/artifacts"
python3 <<'PYEOF'
import json
payload = {
    "artifact": "recordprep-transcript-layout",
    "schema_version": 1,
    "status": "needs_review",
    "decision_source": "pi-agent",
    "mode": "split",
    "input_page_count": 0,
    "input_signature": "",
    "rt_end_file_page": 1,
    "ct_start_file_page": 2,
    "confidence": "low",
    "method": "text search",
    "search_summary": "Ambiguous boundary markers.",
    "evidence": [],
    "warnings": ["Multiple transitions; cannot choose a single boundary."],
}
import os, hashlib, sys
from pathlib import Path
root = Path(os.environ["RECORDPREP_CASE_BUNDLE"])
digest = hashlib.sha256()
digest.update(b"recordprep-transcript-layout-signature-v1\\n")
for name in sorted(p.name for p in (root/"text_pages").glob("*.txt")):
    digest.update(name.encode())
    digest.update(b"\\n")
    digest.update(str((root/"text_pages"/name).stat().st_size).encode())
    digest.update(b"\\n")
    img = root/"image_pages"/name.replace(".txt", ".png")
    digest.update(img.name.encode())
    digest.update(b":")
    digest.update(str(img.stat().st_size if img.exists() else 0).encode())
    digest.update(b"\\n")
payload["input_page_count"] = len(list((root/"text_pages").glob("*.txt")))
payload["input_signature"] = digest.hexdigest()
(root/"artifacts"/"transcript_layout.json").write_text(json.dumps(payload, indent=2))
PYEOF
printf '\\033[32mDetect complete: needs review\\033[0m\\n'
""",
                encoding="utf-8",
            )
            fake_pi.chmod(0o755)
            env = _runner_environment(case_bundle, fake_pi, temp / "cache")

            result = subprocess.run(
                ["python3", str(RUNNER), "detect_transcript_layout"],
                cwd=PROJECT_DIR,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Detect complete: needs review", result.stdout)
            payload = json.loads(
                (case_bundle / "artifacts/transcript_layout.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload["status"], "needs_review")

    def test_runner_rejects_detect_layout_without_text_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            case_bundle = temp / "case_bundle"
            (case_bundle / "text_pages").mkdir(parents=True)
            fake_pi = temp / "pi"
            fake_pi.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"${1:-}\" == \"--version\" ]]; then echo 0.80.10; fi\n",
                encoding="utf-8",
            )
            fake_pi.chmod(0o755)
            result = subprocess.run(
                ["python3", str(RUNNER), "detect_transcript_layout"],
                cwd=PROJECT_DIR,
                env=_runner_environment(case_bundle, fake_pi, temp / "cache"),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 3)
            self.assertIn("transcript_layout.json is missing", result.stdout)

    def test_resource_validator_rejects_missing_or_empty_system_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp_pi = Path(temporary) / ".pi"
            shutil.copytree(PI_DIR, temp_pi)
            system_prompt = temp_pi / "SYSTEM.md"
            system_prompt.unlink()
            env = os.environ.copy()
            env["RECORDPREP_PI_PROJECT_DIR"] = str(temp_pi)

            missing = subprocess.run(
                ["python3", str(RUNNER), "--validate-resources"],
                cwd=PROJECT_DIR,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(missing.returncode, 1)
            self.assertIn("SYSTEM.md is missing or empty", missing.stdout)

            system_prompt.write_text(" \n", encoding="utf-8")
            empty = subprocess.run(
                ["python3", str(RUNNER), "--validate-resources"],
                cwd=PROJECT_DIR,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(empty.returncode, 1)
            self.assertIn("SYSTEM.md is missing or empty", empty.stdout)

    def test_build_source_map_requires_upstream_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            case_bundle = temp / "case_bundle"
            (case_bundle / "text_pages").mkdir(parents=True)
            fake_pi = temp / "pi"
            fake_pi.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"${1:-}\" == \"--version\" ]]; then echo 0.80.10; fi\n",
                encoding="utf-8",
            )
            fake_pi.chmod(0o755)
            result = subprocess.run(
                ["python3", str(RUNNER), "build_source_map"],
                cwd=PROJECT_DIR,
                env=_runner_environment(case_bundle, fake_pi, temp / "cache"),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("prerequisites failed", result.stdout)

    def test_source_map_builder_is_the_single_manifest_publisher(self) -> None:
        """A mixed RT + CT record publishes validated participant data.

        The former version of this fixture labeled its synthetic
        reporter's-transcript hearing data as a CT-only record; a CT-only
        record now correctly skips participant indexing, so the fixture is a
        split RT + CT record and the participant assertions are unchanged.
        """
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "case_bundle"
            (root / "text_pages").mkdir(parents=True)
            (root / "image_pages").mkdir()
            (root / "artifacts").mkdir()
            (root / "summaries").mkdir()
            (root / "text_pages/0001.txt").write_text("one", encoding="utf-8")
            (root / "text_pages/0002.txt").write_text("two", encoding="utf-8")
            (root / "image_pages/0001.png").write_bytes(b"image")
            (root / "image_pages/0002.png").write_bytes(b"image")
            (root / "summaries/hearings_sum_case.txt").write_text(
                "hearing source",
                encoding="utf-8",
            )
            (root / "summaries/reports_sum_case.txt").write_text(
                "report source",
                encoding="utf-8",
            )
            from recordprep.transcript_layout import apply_manual_override

            apply_manual_override(root, mode="split", rt_end_file_page=1)
            legacy_organized = root / "summaries/hearings_sum_case_organized.txt"
            legacy_organized.write_text("retired derivative", encoding="utf-8")
            (root / "artifacts/transcript_page_number_series.md").write_text(
                "# CT\n",
                encoding="utf-8",
            )
            (root / "artifacts/case_overview.md").write_text(
                _case_overview_text(),
                encoding="utf-8",
            )
            transcript = {
                "schema_version": 2,
                "entries": [
                    {
                        "file_name": "0001.txt",
                        "file_page": 1,
                        "record_type": "RT",
                        "page_type": "RT_other",
                        "transcript_page_number": 1,
                        "transcript_page_label": "1",
                        "citation_series_id": "rt-1",
                        "citation_prefix": "RT",
                        "citation_label": "RT 1",
                        "citation_key": "RT:1",
                        "status": "selected",
                        "confidence": "high",
                        "method": "sequence",
                    },
                    {
                        "file_name": "0002.txt",
                        "file_page": 2,
                        "record_type": "CT",
                        "page_type": "CT_other",
                        "transcript_page_number": 1,
                        "transcript_page_label": "1",
                        "citation_series_id": "ct-1",
                        "citation_prefix": "CT",
                        "citation_label": "CT 1",
                        "citation_key": "CT:1",
                        "status": "selected",
                        "confidence": "high",
                        "method": "sequence",
                    }
                ],
                "citation_series": [
                    {
                        "series_id": "ct-1",
                        "citation_prefix": "CT",
                    },
                    {
                        "series_id": "rt-1",
                        "citation_prefix": "RT",
                    }
                ],
                "anomalies": [],
            }
            (root / "artifacts/transcript_page_numbers.json").write_text(
                json.dumps(transcript),
                encoding="utf-8",
            )
            (root / "artifacts/hearing_boundaries.json").write_text(
                json.dumps([{"id": "hearing:0001", "date": "January 2, 2025", "start_page": "0001", "end_page": "0001"}]),
                encoding="utf-8",
            )
            (root / "artifacts/report_boundaries.json").write_text("[]", encoding="utf-8")
            (root / "artifacts/minutes_boundaries.json").write_text("[]", encoding="utf-8")
            (root / "artifacts/participant_index.json").write_text(
                json.dumps({
                    "schema_version": 2,
                    "source": "record-participant-index",
                    "hearings": [{
                        "id": "hearing:0001", "date": "January 2, 2025",
                        "start_page": 1, "end_page": 1,
                        "witness_status": "none",
                        "witness_evidence": [{"text_path": "text_pages/0001.txt", "file_page": 1, "citation_label": "RT 1", "citation_key": "RT:1", "note": "No witness listed."}],
                        "counsel": [],
                        "participants": [{
                            "id": "participant:hearing:0001:001",
                            "role_id": "relative",
                            "role_label": "Maternal great-aunt",
                            "name": "Janette McKinley",
                            "aliases": ["Ms. McKinley"],
                            "attendance_status": "present",
                            "speaking_status": "spoke",
                            "sworn_status": "unsworn",
                            "evidence": [{"text_path": "text_pages/0001.txt", "file_page": 1, "citation_label": "RT 1", "citation_key": "RT:1", "note": "Addressed the court."}],
                        }],
                        "witnesses": [], "warnings": [],
                    }],
                    "warnings": [],
                }),
                encoding="utf-8",
            )
            manifest = {
                "files": {
                    "summarized_hearings": "summaries/hearings_sum_case.txt",
                    "summarized_reports": "summaries/reports_sum_case.txt",
                    "transcript_layout": "artifacts/transcript_layout.json",
                }
            }
            (root / "manifest.json").write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
            script = (
                PI_DIR
                / "skills/recordprep-build-source-map/scripts/build_source_map.py"
            )
            result = subprocess.run(
                ["python3", str(script), str(root)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            updated = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(legacy_organized.exists())
            self.assertEqual(
                updated["files"]["case_overview"],
                "artifacts/case_overview.md",
            )
            self.assertEqual(
                updated["files"]["transcript_layout"],
                "artifacts/transcript_layout.json",
            )
            self.assertEqual(
                updated["files"]["source_map"],
                "artifacts/source_map.json",
            )
            source_map = json.loads(
                (root / "artifacts/source_map.json").read_text(encoding="utf-8")
            )
            self.assertEqual(source_map["schema_version"], 2)
            self.assertEqual(
                source_map["paths"]["case_overview"],
                "artifacts/case_overview.md",
            )
            self.assertEqual(
                source_map["paths"]["transcript_layout"],
                "artifacts/transcript_layout.json",
            )
            self.assertEqual(source_map["counts"]["pages"], 2)
            self.assertEqual(source_map["citation_series"][0]["citation_prefix"], "CT")
            self.assertEqual(source_map["pages"][0]["hearing_id"], "hearing:0001")
            self.assertEqual(
                source_map["pages"][0]["participants"][0]["name"],
                "Janette McKinley",
            )
            self.assertEqual(
                source_map["lookup"]["by_participant"]["ms. mckinley"][0]["role_id"],
                "relative",
            )
            serialized = json.dumps(source_map)
            for obsolete in (
                "optimized",
                "organized_hearings",
                "organized_reports",
                "vector_database",
                "chunks",
            ):
                self.assertNotIn(obsolete, serialized)
            self.assertIn("case_overview", serialized)

    def test_runner_reports_pids_when_process_group_cannot_be_terminated(self) -> None:
        module = _load_runner_module()
        sleeper = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
        )
        module._active_process = sleeper
        try:
            captured = io.StringIO()
            with mock.patch("os.killpg", side_effect=ProcessLookupError("no group")), \
                    mock.patch.object(sleeper, "terminate", side_effect=OSError("nope")), \
                    contextlib.redirect_stdout(captured):
                result = module._terminate_active_process()
            self.assertFalse(result)
            text = captured.getvalue()
            self.assertIn(f"PI pid {sleeper.pid}", text)
            self.assertIn("runner pid", text)
            self.assertIn("stays Pending", text)
        finally:
            module._active_process = None
            sleeper.kill()
            sleeper.wait(timeout=5)

    def test_runner_detects_stalled_pi_child_and_remains_stoppable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            case_bundle = temp / "case_bundle"
            (case_bundle / "text_pages").mkdir(parents=True)
            (case_bundle / "text_pages/0001.txt").write_text("one", encoding="utf-8")
            fake_pi = temp / "pi"
            fake_pi.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"${1:-}\" == \"--version\" ]]; then\n"
                "  echo 0.80.10\n"
                "  exit 0\n"
                "fi\n"
                "while :; do :; done\n",
                encoding="utf-8",
            )
            fake_pi.chmod(0o755)
            env = _runner_environment(case_bundle, fake_pi, temp / "cache")
            env.update(
                {
                    "RECORDPREP_PI_STALL_TIMEOUT_SECONDS": "4",
                    "RECORDPREP_PI_STALL_POLL_INTERVAL": "0.2",
                    "RECORDPREP_PI_STALL_CPU_WINDOW_SECONDS": "2",
                }
            )
            log_path = temp / "runner.log"
            with log_path.open("w", encoding="utf-8") as log_handle:
                process = subprocess.Popen(
                    ["python3", str(RUNNER), "build_participant_index"],
                    cwd=PROJECT_DIR,
                    env=env,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                try:
                    warning_line: str | None = None
                    deadline = time.monotonic() + 25
                    while time.monotonic() < deadline and process.poll() is None:
                        text = log_path.read_text(encoding="utf-8", errors="ignore")
                        warning_line = next(
                            (line for line in text.splitlines() if "[stalled]" in line),
                            None,
                        )
                        if warning_line is not None:
                            break
                        time.sleep(0.1)
                    output = log_path.read_text(encoding="utf-8", errors="ignore")
                    self.assertIsNotNone(
                        warning_line,
                        "no stalled warning; output:\n" + output,
                    )
                    self.assertIn(
                        "Build participant and witness index", warning_line or ""
                    )
                    self.assertIn("not making progress", warning_line or "")
                    status_path = case_bundle / "temp" / ".pi_stage_status.json"
                    self.assertTrue(status_path.is_file())
                    status = json.loads(status_path.read_text(encoding="utf-8"))
                    self.assertEqual(status["state"], "stalled")
                    self.assertEqual(status["runner_pid"], process.pid)
                    self.assertIn("last_activity", status)

                    # Warning only: no automatic kill.
                    self.assertIsNone(process.poll())

                    # Explicit stop terminates the complete PI process group.
                    pi_pid = status["pi_pid"]
                    process.terminate()
                    process.wait(timeout=10)
                    self.assertEqual(process.returncode, 130)
                    deadline = time.monotonic() + 5
                    while (
                        Path(f"/proc/{pi_pid}").exists()
                        and time.monotonic() < deadline
                    ):
                        time.sleep(0.05)
                    self.assertFalse(Path(f"/proc/{pi_pid}").exists())
                    self.assertFalse(status_path.exists())
                    workspace_parent = temp / "cache" / "recordprep-pi-workspaces"
                    self.assertEqual(list(workspace_parent.glob("skill.*")), [])
                finally:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)

    def test_runner_rejects_participant_template_after_pi_exits(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            case_bundle = temp / "case_bundle"
            (case_bundle / "text_pages").mkdir(parents=True)
            (case_bundle / "artifacts").mkdir()
            (case_bundle / "text_pages/0001.txt").write_text("one", encoding="utf-8")
            fake_pi = temp / "pi"
            fake_pi.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--version" ]]; then
  printf '0.80.10\n'
  exit 0
fi
mkdir -p "$RECORDPREP_CASE_BUNDLE/artifacts"
python3 <<'PYEOF'
import json, os
from pathlib import Path
root = Path(os.environ["RECORDPREP_CASE_BUNDLE"])
payload = {
    "schema_version": 2,
    "generated_at": "2026-01-01T00:00:00+00:00",
    "source": "record-participant-index",
    "hearings": [{
        "id": "hearing:0001",
        "date": "",
        "start_page": 1,
        "end_page": 1,
        "start_citation_label": "",
        "end_citation_label": "",
        "citation_range": "",
        "counsel": [],
        "participants": [],
        "witness_status": "unknown",
        "witness_evidence": [],
        "witnesses": [],
        "warnings": ["Participant review has not been completed."],
    }],
    "warnings": ["Participant review has not been completed."],
}
(root/"artifacts"/"participant_index.json").write_text(json.dumps(payload, indent=2))
PYEOF
printf '\033[32mParticipant template prepared\033[0m\n'
""",
                encoding="utf-8",
            )
            fake_pi.chmod(0o755)
            result = subprocess.run(
                ["python3", str(RUNNER), "build_participant_index"],
                cwd=PROJECT_DIR,
                env=_runner_environment(case_bundle, fake_pi, temp / "cache"),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 3)
            self.assertIn(
                "participant index review has not been completed "
                "(template warning remains).",
                result.stdout,
            )
            self.assertIn(
                "participant index hearing 1 has not been reviewed "
                "(template warning remains).",
                result.stdout,
            )

    def test_runner_termination_cleans_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            case_bundle = temp / "case_bundle"
            (case_bundle / "text_pages").mkdir(parents=True)
            started = temp / "started"
            fake_pi = temp / "pi"
            fake_pi.write_text(
                """#!/usr/bin/env bash
if [[ "${1:-}" == "--version" ]]; then
  echo 0.80.10
  exit 0
fi
touch "$FAKE_PI_STARTED"
trap 'exit 143' TERM INT
sleep 30
""",
                encoding="utf-8",
            )
            fake_pi.chmod(0o755)
            cache = temp / "cache"
            env = _runner_environment(case_bundle, fake_pi, cache)
            env["FAKE_PI_STARTED"] = str(started)
            process = subprocess.Popen(
                ["python3", str(RUNNER), "number_transcript_pages"],
                cwd=PROJECT_DIR,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            deadline = time.monotonic() + 5
            while not started.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(started.exists())
            process.terminate()
            process.communicate(timeout=5)
            workspace_parent = cache / "recordprep-pi-workspaces"
            self.assertEqual(list(workspace_parent.glob("skill.*")), [])


if __name__ == "__main__":
    unittest.main()
