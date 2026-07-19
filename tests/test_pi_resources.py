import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
PI_DIR = PROJECT_DIR / ".pi"
RUNNER = PI_DIR / "scripts/run_recordprep_skill.py"


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

    def test_project_has_only_settings_skills_and_runner(self) -> None:
        settings = json.loads((PI_DIR / "settings.json").read_text(encoding="utf-8"))
        self.assertTrue(settings["defaultProvider"])
        self.assertTrue(settings["defaultModel"])
        self.assertTrue(settings["enableSkillCommands"])
        self.assertFalse((PI_DIR / "agents").exists())
        self.assertFalse((PI_DIR / "workflows").exists())
        self.assertFalse((PI_DIR / "extensions").exists())
        skills = sorted(path.parent.name for path in (PI_DIR / "skills").glob("*/SKILL.md"))
        self.assertEqual(
            skills,
            [
                "recordprep-build-source-map",
                "recordprep-number-transcript-pages",
                "recordprep-organize-hearing-summary",
                "recordprep-organize-report-summary",
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
            self.assertNotIn("--no-themes", text)
            self.assertNotIn("--no-context-files", text)
            self.assertIn("--no-extensions", text)
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

    def test_build_source_map_requires_the_first_three_outputs(self) -> None:
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
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "case_bundle"
            (root / "text_pages").mkdir(parents=True)
            (root / "artifacts").mkdir()
            (root / "summaries").mkdir()
            (root / "text_pages/0001.txt").write_text("one", encoding="utf-8")
            (root / "summaries/hearings_sum_case.txt").write_text(
                "hearing source",
                encoding="utf-8",
            )
            (root / "summaries/reports_sum_case.txt").write_text(
                "report source",
                encoding="utf-8",
            )
            (root / "summaries/hearings_sum_case_organized.txt").write_text(
                "hearing organized",
                encoding="utf-8",
            )
            (root / "summaries/reports_sum_case_organized.txt").write_text(
                "report organized",
                encoding="utf-8",
            )
            (root / "artifacts/transcript_page_number_series.md").write_text(
                "# CT\n",
                encoding="utf-8",
            )
            transcript = {
                "schema_version": 2,
                "entries": [
                    {
                        "file_name": "0001.txt",
                        "file_page": 1,
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
                    }
                ],
                "anomalies": [],
            }
            (root / "artifacts/transcript_page_numbers.json").write_text(
                json.dumps(transcript),
                encoding="utf-8",
            )
            manifest = {
                "files": {
                    "summarized_hearings": "summaries/hearings_sum_case.txt",
                    "summarized_reports": "summaries/reports_sum_case.txt",
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
            self.assertEqual(
                updated["files"]["organized_hearings"],
                "summaries/hearings_sum_case_organized.txt",
            )
            self.assertEqual(
                updated["files"]["organized_reports"],
                "summaries/reports_sum_case_organized.txt",
            )
            self.assertEqual(
                updated["files"]["source_map"],
                "artifacts/source_map.json",
            )
            source_map = json.loads(
                (root / "artifacts/source_map.json").read_text(encoding="utf-8")
            )
            self.assertEqual(source_map["counts"]["pages"], 1)
            self.assertEqual(source_map["citation_series"][0]["citation_prefix"], "CT")

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
