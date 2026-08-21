#!/usr/bin/env python3
"""Run one RecordPrep PI skill in PI's native interactive terminal UI."""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence


MINIMUM_PI_MINOR = 80
AUTO_EXIT_EXTENSION_NAME = "recordprep-auto-exit.ts"

STAGE_STATUS_ARTIFACT = "recordprep-pi-stage-status"
STAGE_STATUS_RELATIVE = Path("temp") / ".pi_stage_status.json"

DEFAULT_POLL_INTERVAL_SECONDS = 1.0
DEFAULT_STALL_TIMEOUT_SECONDS = 300.0
DEFAULT_STALL_CPU_PER_CORE = 0.25
DEFAULT_STALL_CPU_WINDOW_SECONDS = 30.0
DEFAULT_FORCE_KILL_AFTER_SECONDS = 3.0
try:
    USER_HZ = float(os.sysconf("SC_CLK_TCK"))
except (OSError, TypeError, ValueError):
    USER_HZ = 100.0
STATUS_WRITE_INTERVAL_SECONDS = 10.0
ACTIVITY_RESCAN_SECONDS = 5.0
SESSION_TAIL_BYTES = 65_536


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
            "detect_transcript_layout",
            "Detect transcript layout",
            "recordprep-detect-transcript-layout",
            "read,bash,grep,find,ls,write,edit",
        ),
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


def _float_env(name: str, default: float) -> float:
    raw = str(os.environ.get(name, "") or "").strip()
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


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
            "\nProcess one hearing at a time. Use the temporary evidence worklist "
            f"({root / 'temp' / '.participant_worklist.json'}) and read only the "
            "original pages it scopes. Keep each read to a single page file and "
            "never concatenate the complete RT or request large multi-hundred-page "
            "reads. Persist completed hearings incrementally and validate every "
            "batch of up to 5 hearings with --partial before continuing. Preserve "
            "explicit uncertainty as unknown or conflict with hearing-specific "
            "warnings rather than exhaustively loading the record; never infer "
            "testimony from Q/A alone."
        )
    elif stage.step_id == "create_case_overview":
        instruction += (
            f"\nThe exact required output path is: {root / 'artifacts' / 'case_overview.md'}"
            "\nCreate only a concise nonauthoritative orientation aid. Do not "
            "modify manifest.json."
        )
    elif stage.step_id == "detect_transcript_layout":
        instruction += (
            "\nSearch text pages first and open only targeted page images as "
            "needed. Publish needs_review instead of guessing when the record "
            "structure is ambiguous. Only the detect skill may write "
            "artifacts/transcript_layout.json."
        )
    elif stage.step_id == "build_source_map":
        instruction += (
            "\nDo not proceed unless transcript numbering, participant indexing, "
            "the source summaries, the transcript layout, and the case overview "
            "already validate. This is the final Agent Search preparation step."
        )
    return instruction


def _terminate_active_process() -> bool:
    """Terminate the PI process group; report PIDs when it cannot be done."""
    process = _active_process
    if process is None or process.poll() is not None:
        return True
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (OSError, ProcessLookupError) as exc:
        _line(f"[stop] failed to signal PI process group {process.pid}: {exc}")
        try:
            process.terminate()
        except OSError as terminate_exc:
            _line(
                "[stop] PI pid {} (runner pid {}) did not terminate: {}; "
                "the active row stays Pending.".format(
                    process.pid, os.getpid(), terminate_exc
                )
            )
        else:
            _line(
                "[stop] signaled PI pid {} directly, but complete process-group "
                "termination could not be guaranteed; runner pid {} and the "
                "active row stays Pending.".format(process.pid, os.getpid())
            )
        return False
    return True


def _handle_stop(_signum: int, _frame: object) -> None:
    global _stopped
    _stopped = True
    if not _terminate_active_process():
        if _active_process is not None:
            _line(
                "[stop] report these PIDs: runner {} and PI {}.".format(
                    os.getpid(), _active_process.pid
                )
            )


def _set_terminal_foreground_process_group(process_group: int) -> None:
    if not sys.stdin.isatty():
        return
    previous_handler = signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    try:
        os.tcsetpgrp(sys.stdin.fileno(), process_group)
    finally:
        signal.signal(signal.SIGTTOU, previous_handler)


def _proc_group_ticks(process_group: int) -> int:
    """Total CPU ticks for every process in PI's process group."""
    total = 0
    found = False
    try:
        stat_paths = Path("/proc").glob("[0-9]*/stat")
        for stat_path in stat_paths:
            try:
                data = stat_path.read_text(encoding="ascii", errors="ignore")
                fields = data.rsplit(")", 1)[1].split()
                if len(fields) < 13 or int(fields[2]) != process_group:
                    continue
                found = True
                total += int(fields[11]) + int(fields[12])
            except (OSError, IndexError, ValueError):
                continue
    except OSError:
        return -1
    return total if found else -1


def _proc_state(pid: int) -> str:
    try:
        data = Path(f"/proc/{pid}/stat").read_text(encoding="ascii", errors="ignore")
        return data.rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return ""


def _session_snapshot(session_dir: Path) -> tuple[float, int]:
    """Return (latest mtime, total size) of session files; (0, 0) when absent."""
    latest = 0.0
    total = 0
    try:
        for path in session_dir.rglob("*"):
            if not path.is_file():
                continue
            try:
                size = path.stat().st_size
                total += size
                latest = max(latest, path.stat().st_mtime)
            except OSError:
                continue
    except OSError:
        pass
    return latest, total


def _event_text(obj: Any) -> str:
    if not isinstance(obj, dict):
        return ""
    for key in ("content", "text", "output", "message", "summary"):
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            inner = _event_text(value)
            if inner:
                return inner
    for key in ("type", "event", "role", "name"):
        label = obj.get(key)
        if isinstance(label, str) and label.strip():
            return f"<{label}>"
    return ""


def _summarize_session_line(line: str) -> str:
    try:
        obj = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return line.strip()[:200]
    text = _event_text(obj)
    return (text if text else line.strip())[:300]


def _last_session_activity(session_dir: Path) -> str:
    newest: Path | None = None
    newest_mtime = 0.0
    try:
        for path in session_dir.rglob("*"):
            if not path.is_file():
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime > newest_mtime:
                newest, newest_mtime = path, mtime
    except OSError:
        return ""
    if newest is None:
        return ""
    try:
        with newest.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - SESSION_TAIL_BYTES))
            tail = handle.read(SESSION_TAIL_BYTES)
        lines = tail.decode("utf-8", errors="ignore").splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        if line.strip():
            return _summarize_session_line(line)
    return ""


@dataclass(slots=True)
class StageMonitor:
    """Watch the embedded PI for sustained CPU spin with no session progress.

    The monitor never kills the child; it reports a stalled state once so the
    user can decide. Stop remains the only termination path.
    """

    stage: SkillStage
    root: Path
    session_dir: Path
    pi_pid: int
    runner_pid: int
    poll_interval: float
    stall_timeout: float
    cpu_per_core: float
    cpu_window_seconds: float
    force_kill_after: float
    status_path: Path = field(init=False)
    _last_progress: tuple[float, int] | None = field(default=None, init=False)
    _last_progress_time: float = field(default=0.0, init=False)
    _cpu_window: deque[tuple[float, int]] = field(default_factory=deque, init=False)
    _stall_reported: bool = field(default=False, init=False)
    _stall_message: str | None = field(default=None, init=False)
    _last_activity: str = field(default="started", init=False)
    _last_session_scan: float = field(default=0.0, init=False)
    _last_status_write: float = field(default=0.0, init=False)
    _started_at: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self.status_path = self.root / STAGE_STATUS_RELATIVE

    def start(self) -> None:
        self._started_at = time.monotonic()
        self._last_progress_time = self._started_at
        self._write_status("running")

    def _write_status(self, state: str, message: str | None = None) -> None:
        payload = {
            "artifact": STAGE_STATUS_ARTIFACT,
            "schema_version": 1,
            "stage": self.stage.step_id,
            "stage_title": self.stage.title,
            "state": state,
            "runner_pid": self.runner_pid,
            "pi_pid": self.pi_pid,
            "last_activity": self._last_activity,
        }
        if message is not None:
            payload["message"] = message
        try:
            self.status_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.status_path.with_name(
                f".{self.status_path.name}.{os.getpid()}.tmp"
            )
            temp.write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )
            os.replace(temp, self.status_path)
            self._last_status_write = time.monotonic()
        except OSError:
            pass

    def _cpu_rate(self) -> float:
        now = time.monotonic()
        while self._cpu_window and now - self._cpu_window[0][0] > self.cpu_window_seconds:
            self._cpu_window.popleft()
        if len(self._cpu_window) < 2:
            return 0.0
        elapsed = self._cpu_window[-1][0] - self._cpu_window[0][0]
        if elapsed <= 0:
            return 0.0
        return (self._cpu_window[-1][1] - self._cpu_window[0][1]) / elapsed

    def tick(self) -> None:
        now = time.monotonic()
        session = _session_snapshot(self.session_dir)
        if session != self._last_progress and session[0] > 0:
            self._last_progress = session
            self._last_progress_time = now
            if now - self._last_session_scan >= ACTIVITY_RESCAN_SECONDS:
                self._last_session_scan = now
                activity = _last_session_activity(self.session_dir)
                if activity:
                    self._last_activity = activity
        self._cpu_window.append((now, _proc_group_ticks(self.pi_pid)))
        idle_seconds = now - self._last_progress_time
        cpu_rate = self._cpu_rate()
        spin = cpu_rate >= self.cpu_per_core * USER_HZ
        hang = cpu_rate <= 0.0 and idle_seconds >= self.stall_timeout * 2
        if (spin or hang) and idle_seconds >= self.stall_timeout and not self._stall_reported:
            self._stall_reported = True
            state = _proc_state(self.pi_pid)
            message = (
                f"No session activity for {idle_seconds:.0f}s while PI pid "
                f"{self.pi_pid} (state {state or 'unknown'}, CPU {cpu_rate:.0f} "
                f"ticks/s) is not making progress."
            )
            self._stall_message = message
            self._write_status("stalled", message)
            _line()
            _line(
                "\033[33m[stalled]\033[0m " + self.stage.title
                + f"; PI pid {self.pi_pid} is not making progress. "
                + f"Last recorded action: {self._last_activity!r}"
            )
            _line(
                "[stalled] RecordPrep is waiting for you: use the Stop button "
                "to terminate PI; RecordPrep will not kill potentially valid "
                "work automatically."
            )
        elif now - self._last_status_write >= STATUS_WRITE_INTERVAL_SECONDS:
            self._write_status(
                "stalled" if self._stall_reported else "running",
                self._stall_message if self._stall_reported else None,
            )

    def finish(self) -> None:
        try:
            self.status_path.unlink(missing_ok=True)
        except OSError:
            pass


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
        poll_interval = _float_env(
            "RECORDPREP_PI_STALL_POLL_INTERVAL", DEFAULT_POLL_INTERVAL_SECONDS
        )
        monitor = StageMonitor(
            stage=stage,
            root=root,
            session_dir=workspace / "sessions",
            pi_pid=_active_process.pid,
            runner_pid=os.getpid(),
            poll_interval=poll_interval,
            stall_timeout=_float_env(
                "RECORDPREP_PI_STALL_TIMEOUT_SECONDS",
                DEFAULT_STALL_TIMEOUT_SECONDS,
            ),
            cpu_per_core=_float_env(
                "RECORDPREP_PI_STALL_CPU_PER_CORE",
                DEFAULT_STALL_CPU_PER_CORE,
            ),
            cpu_window_seconds=_float_env(
                "RECORDPREP_PI_STALL_CPU_WINDOW_SECONDS",
                DEFAULT_STALL_CPU_WINDOW_SECONDS,
            ),
            force_kill_after=_float_env(
                "RECORDPREP_PI_FORCE_KILL_AFTER",
                DEFAULT_FORCE_KILL_AFTER_SECONDS,
            ),
        )
        monitor.start()
        _line(f"PI pid {_active_process.pid} started.")
        force_kill_at: float | None = None
        try:
            while True:
                try:
                    return_code = _active_process.wait(timeout=poll_interval)
                except subprocess.TimeoutExpired:
                    return_code = None
                if return_code is not None:
                    break
                if _stopped:
                    if force_kill_at is None:
                        force_kill_at = time.monotonic() + monitor.force_kill_after
                        _line(
                            "\033[33mStop requested; terminating the PI process "
                            "group.\033[0m"
                        )
                        _terminate_active_process()
                    elif (
                        time.monotonic() >= force_kill_at
                        and _active_process.poll() is None
                    ):
                        force_kill_at = float("inf")
                        try:
                            os.killpg(_active_process.pid, signal.SIGKILL)
                        except (OSError, ProcessLookupError):
                            pass
                        else:
                            _line(
                                "\033[31mPI did not exit after SIGTERM; forced "
                                "SIGKILL of the process group.\033[0m"
                            )
                    continue
                monitor.tick()
        finally:
            monitor.finish()
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
