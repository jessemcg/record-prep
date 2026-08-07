#!/usr/bin/env python3
"""Run one RecordPrep PI skill in PI's native interactive terminal UI."""

from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


MINIMUM_PI_MINOR = 80
AUTO_EXIT_EXTENSION_NAME = "recordprep-auto-exit.ts"


@dataclass(frozen=True, slots=True)
class SkillStage:
    step_id: str
    title: str
    skill_name: str
    tools: str


STAGES = {
    stage.step_id: stage
    for stage in (
        SkillStage(
            "number_transcript_pages",
            "Number transcript pages",
            "recordprep-number-transcript-pages",
            "read,bash,grep,find,ls,write,edit",
        ),
        SkillStage(
            "build_participant_index",
            "Build participant and witness index",
            "recordprep-build-participant-index",
            "read,bash,grep,find,ls,write,edit",
        ),
        SkillStage(
            "create_case_overview",
            "Create case overview",
            "recordprep-create-case-overview",
            "read,bash,grep,find,ls,write,edit",
        ),
        SkillStage(
            "build_source_map",
            "Build source map",
            "recordprep-build-source-map",
            "read,bash,grep,find,ls",
        ),
    )
}

_active_process: subprocess.Popen[str] | None = None
_stopped = False


def _write(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def _line(text: str = "") -> None:
    _write(text.rstrip("\n") + "\n")


def _project_dir() -> Path:
    configured = str(os.environ.get("RECORDPREP_PI_PROJECT_DIR", "") or "").strip()
    if configured:
        return Path(configured).expanduser().resolve(strict=False)
    return Path(__file__).resolve().parents[1]


def _case_bundle() -> Path:
    configured = str(os.environ.get("RECORDPREP_CASE_BUNDLE", "") or "").strip()
    if not configured:
        raise ValueError("RECORDPREP_CASE_BUNDLE is not set.")
    root = Path(configured).expanduser().resolve(strict=False)
    if not (root / "text_pages").is_dir():
        raise ValueError(f"RecordPrep case bundle is missing or invalid: {root}")
    return root


def _pi_command() -> list[str]:
    raw_count = str(os.environ.get("RECORDPREP_PI_COMMAND_ARGC", "0") or "0")
    try:
        count = int(raw_count)
    except ValueError:
        count = 0
    command = [
        str(os.environ.get(f"RECORDPREP_PI_COMMAND_ARG_{index}", "") or "")
        for index in range(max(0, count))
    ]
    command = [value for value in command if value]
    return command or ["pi"]


def _resource_issues(project_dir: Path) -> list[str]:
    issues: list[str] = []
    system_prompt_path = project_dir / "SYSTEM.md"
    try:
        system_prompt = system_prompt_path.read_text(encoding="utf-8")
    except OSError:
        system_prompt = ""
    if not system_prompt.strip():
        issues.append("SYSTEM.md is missing or empty.")
    if not (project_dir / "settings.json").is_file():
        issues.append("settings.json is missing.")
    for stage in STAGES.values():
        skill = project_dir / "skills" / stage.skill_name / "SKILL.md"
        if not skill.is_file():
            issues.append(f"{stage.skill_name}/SKILL.md is missing.")
    extension_dir = project_dir / "extensions"
    auto_exit_extension = extension_dir / AUTO_EXIT_EXTENSION_NAME
    if not auto_exit_extension.is_file():
        issues.append(f"extensions/{AUTO_EXIT_EXTENSION_NAME} is missing.")
    elif {
        path.name
        for path in extension_dir.iterdir()
        if path.is_file() or path.is_dir()
    } != {AUTO_EXIT_EXTENSION_NAME}:
        issues.append("unexpected project-local PI extension resources are present.")
    for obsolete in ("agents", "workflows"):
        if (project_dir / obsolete).exists():
            issues.append(f"obsolete .pi/{obsolete}/ resources are still present.")
    return issues


def _check_pi_version(command: Sequence[str]) -> None:
    result = subprocess.run(
        [*command, "--version"],
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    version = (result.stdout or result.stderr).splitlines()
    first_line = version[0].strip() if version else ""
    match = re.match(r"^0\.(\d+)", first_line)
    if result.returncode != 0 or match is None or int(match.group(1)) < MINIMUM_PI_MINOR:
        raise ValueError(
            f"RecordPrep requires PI 0.{MINIMUM_PI_MINOR} or newer; "
            f"found {first_line or 'unknown'}."
        )


def _stage_prompt(stage: SkillStage, root: Path, project_dir: Path) -> str:
    project_root = project_dir.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    instruction = (
        f"/skill:{stage.skill_name}\n"
        f"Run the loaded {stage.skill_name} skill now against the absolute case "
        f"bundle in RECORDPREP_CASE_BUNDLE ({root}). Follow the skill completely, "
        "validate its outputs, and finish with a concise result."
    )
    if stage.step_id == "build_participant_index":
        instruction += (
            "\nInspect RT_index pages, appearances, and actual sworn/examination "
            "evidence. Preserve uncertainty and never infer testimony from Q/A alone."
        )
    elif stage.step_id == "create_case_overview":
        instruction += (
            f"\nThe exact required output path is: {root / 'artifacts' / 'case_overview.md'}"
            "\nCreate only a concise nonauthoritative orientation aid. Do not "
            "modify manifest.json."
        )
    elif stage.step_id == "build_source_map":
        instruction += (
            "\nDo not proceed unless transcript numbering, participant indexing, "
            "the source summaries, and the case overview already validate. This is "
            "the final Agent Search preparation step."
        )
    return instruction


def _terminate_active_process() -> None:
    process = _active_process
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        process.terminate()


def _handle_stop(_signum: int, _frame: object) -> None:
    global _stopped
    _stopped = True
    _terminate_active_process()


def _set_terminal_foreground_process_group(process_group: int) -> None:
    if not sys.stdin.isatty():
        return
    previous_handler = signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    try:
        os.tcsetpgrp(sys.stdin.fileno(), process_group)
    finally:
        signal.signal(signal.SIGTTOU, previous_handler)


def _validate_stage(stage: SkillStage, root: Path, project_dir: Path) -> list[str]:
    project_root = project_dir.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from recordprep.pi_bundle import validate_pi_step_outputs

    return validate_pi_step_outputs(stage.step_id, root)


def _run_stage(stage: SkillStage, root: Path, project_dir: Path) -> int:
    global _active_process

    resource_issues = _resource_issues(project_dir)
    if resource_issues:
        raise ValueError(" ".join(resource_issues))
    if stage.step_id in {"create_case_overview", "build_source_map"}:
        project_root = project_dir.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from recordprep.pi_bundle import (
            case_overview_prerequisite_issues,
            source_map_prerequisite_issues,
        )

        if stage.step_id == "create_case_overview":
            preflight = case_overview_prerequisite_issues(root)
            failure_label = "Create case overview prerequisites failed: "
        else:
            preflight = source_map_prerequisite_issues(root)
            failure_label = "Build source map prerequisites failed: "
        if preflight:
            raise ValueError(failure_label + " ".join(preflight))

    pi_command = _pi_command()
    _check_pi_version(pi_command)
    cache_root = Path(
        os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")
    ).expanduser()
    workspace_parent = cache_root / "recordprep-pi-workspaces"
    workspace_parent.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="skill.", dir=workspace_parent))
    try:
        staged_pi = workspace / ".pi"
        staged_skill = staged_pi / "skills" / stage.skill_name
        staged_extension = staged_pi / "extensions" / AUTO_EXIT_EXTENSION_NAME
        staged_skill.parent.mkdir(parents=True)
        staged_extension.parent.mkdir(parents=True)
        shutil.copy2(project_dir / "settings.json", staged_pi / "settings.json")
        shutil.copy2(project_dir / "SYSTEM.md", staged_pi / "SYSTEM.md")
        shutil.copytree(project_dir / "skills" / stage.skill_name, staged_skill)
        shutil.copy2(
            project_dir / "extensions" / AUTO_EXIT_EXTENSION_NAME,
            staged_extension,
        )
        (workspace / "tmp").mkdir()
        (workspace / "sessions").mkdir()
        env = os.environ.copy()
        env["TMPDIR"] = str(workspace / "tmp")
        env["PI_CODING_AGENT_SESSION_DIR"] = str(workspace / "sessions")
        executable = Path(pi_command[0]).expanduser()
        if executable.is_absolute():
            env["PATH"] = str(executable.parent) + os.pathsep + env.get("PATH", "")
        command = [
            *pi_command,
            "--approve",
            "--no-extensions",
            "--no-skills",
            "--no-prompt-templates",
            "--no-themes",
            "--no-context-files",
            "--system-prompt",
            str(staged_pi / "SYSTEM.md"),
            "--extension",
            str(staged_extension),
            "--skill",
            str(staged_skill / "SKILL.md"),
            "--tools",
            stage.tools,
            _stage_prompt(stage, root, project_dir),
        ]
        _line()
        _line(f"\033[1;36m{stage.title}\033[0m")
        _line(f"Skill: {stage.skill_name}")
        _line(f"Case bundle: {root}")
        _line()
        runner_process_group = os.getpgrp()
        _active_process = subprocess.Popen(
            command,
            cwd=workspace,
            env=env,
            process_group=0,
        )
        if sys.stdin.isatty():
            _set_terminal_foreground_process_group(_active_process.pid)
            os.killpg(_active_process.pid, signal.SIGCONT)
        try:
            return_code = _active_process.wait()
        finally:
            _set_terminal_foreground_process_group(runner_process_group)
        _active_process = None
        if _stopped:
            return 130
        if return_code != 0:
            _line(f"\033[31mPI exited with code {return_code}.\033[0m")
            return return_code
        issues = _validate_stage(stage, root, project_dir)
        if issues:
            for issue in issues:
                _line(f"\033[31m[validation]\033[0m {issue}")
            return 3
        _line(f"\033[32m{stage.title} complete.\033[0m")
        return 0
    finally:
        _active_process = None
        shutil.rmtree(workspace, ignore_errors=True)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    project_dir = _project_dir()
    if args == ["--validate-resources"]:
        issues = _resource_issues(project_dir)
        if issues:
            for issue in issues:
                _line(f"PI resource validation failed: {issue}")
            return 1
        _line("RecordPrep sequential PI resources are valid.")
        return 0
    if len(args) != 1 or args[0] not in STAGES:
        choices = ", ".join(STAGES)
        _line(f"Usage: {Path(sys.argv[0]).name} <{choices}>")
        return 2
    try:
        return _run_stage(STAGES[args[0]], _case_bundle(), project_dir)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        _line(f"\033[31mRecordPrep PI stage failed:\033[0m {exc}")
        return 2


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    raise SystemExit(main())
