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
SUMMARY_RESOURCE_MINIMUM_PI_MINOR = 85
AUTO_EXIT_EXTENSION_NAME = "recordprep-auto-exit.ts"
SUMMARY_EXTENSION_NAME = "recordprep-summary-tools.ts"

SUMMARY_STAGE_KINDS = {
    "create_hearing_summaries": "hearings",
    "create_report_summaries": "reports",
}
SUMMARY_SKILL_NAMES = {
    "hearings": {
        "extract": "recordprep-extract-hearing",
        "synthesize": "recordprep-synthesize-hearings",
    },
    "reports": {
        "extract": "recordprep-extract-report",
        "synthesize": "recordprep-synthesize-reports",
    },
}
SUMMARY_TOOL_ALLOWLISTS = {
    "extract": "recordprep_get_source,recordprep_submit_extraction",
    "synthesize": (
        "recordprep_get_facts,recordprep_submit_summary_section,"
        "recordprep_finish_summary"
    ),
}

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


def _ensure_project_importable(project_dir: Path) -> None:
    """Make the recordprep package importable from the runner subprocess.

    The parent of the staged/project `.pi` directory is the RecordPrep project
    root. Native stages patched sys.path lazily inside their validators; the
    summary stages import recordprep directly, so bootstrap it up front. When
    the configured project directory is a staged copy (tests, private
    workspaces), fall back to the runner's own project root, which always
    carries the recordprep package.
    """
    candidates = [project_dir.parent, Path(__file__).resolve().parents[2]]
    for candidate in candidates:
        if (candidate / "recordprep" / "__init__.py").is_file():
            if str(candidate) not in sys.path:
                sys.path.insert(0, str(candidate))
            return


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
    for kind_skills in SUMMARY_SKILL_NAMES.values():
        for skill_name in kind_skills.values():
            skill = project_dir / "skills" / skill_name / "SKILL.md"
            if not skill.is_file():
                issues.append(f"{skill_name}/SKILL.md is missing.")
    extension_dir = project_dir / "extensions"
    auto_exit_extension = extension_dir / AUTO_EXIT_EXTENSION_NAME
    if not auto_exit_extension.is_file():
        issues.append(f"extensions/{AUTO_EXIT_EXTENSION_NAME} is missing.")
    elif {
        path.name
        for path in extension_dir.iterdir()
        if path.is_file() or path.is_dir()
    } != {AUTO_EXIT_EXTENSION_NAME, SUMMARY_EXTENSION_NAME}:
        issues.append(
            "unexpected project-local PI extension resources are present."
        )
    summary_extension = extension_dir / SUMMARY_EXTENSION_NAME
    if not summary_extension.is_file():
        issues.append(f"extensions/{SUMMARY_EXTENSION_NAME} is missing.")
    # Category-guidance resources must parse strictly before any paid work.
    from recordprep import summary_categories

    for kind in summary_categories.CATEGORY_CONTRACTS:
        try:
            summary_categories.load_category_descriptions(kind)
        except summary_categories.SummaryResourceError as exc:
            issues.append(str(exc))
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


def _resolve_pi_command() -> list[str]:
    """Harden executable resolution before any --version or agent spawn.

    A nonexistent configured path is never attempted. Only `pi` or a known
    legacy default location triggers rediscovery; an arbitrary missing custom
    command fails early with the discovered alternative named.
    """
    command = _pi_command()
    if not command or not command[0]:
        raise ValueError("PI command is empty. Set the PI command in Settings.")
    executable = Path(command[0]).expanduser()
    if str(executable) == "pi":
        from recordprep.pi_runtime import discover_pi_agent_command

        discovered = discover_pi_agent_command(path_env=os.environ.get("PATH"))
        resolved = shutil.which("pi", path=os.environ.get("PATH"))
        command[0] = resolved or discovered
        executable = Path(command[0])
    if os.path.sep in str(executable) or executable.is_absolute():
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise ValueError(
                f"PI executable not found at the configured path: {executable}. "
                "Install PI or set the PI command in Settings."
            )
    elif shutil.which(str(executable)) is None:
        from recordprep.pi_runtime import discover_pi_agent_command

        discovered = discover_pi_agent_command(path_env=os.environ.get("PATH"))
        if Path(discovered).is_file():
            raise ValueError(
                f"PI executable {executable!r} was not found on PATH, but the "
                f"discovered PI installation at {discovered} is available; "
                "set the PI command in Settings to that path."
            )
        raise ValueError(
            f"PI executable not found: {executable}. Install PI or set the PI "
            "command in Settings."
        )
    command[0] = str(executable)
    return command


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


# --- Two-stage summary pipeline ---


def _summary_stage_settings(project_dir: Path, kind: str) -> dict[str, Any]:
    """Stage-specific summary overrides (shared composition in summary_agents)."""
    from recordprep import summary_agents as sa

    return sa.summary_stage_settings(project_dir, kind)


def _extraction_config(
    project_dir: Path,
    kind: str,
    settings: dict[str, Any],
) -> Any:
    """Shared effective-guidance composition (summary_agents)."""
    from recordprep import summary_agents as sa

    return sa.effective_extraction_config(project_dir, kind)


def _model_override_flags(phase: str, settings: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    provider = str(settings.get(f"{phase}_provider") or "")
    model = str(settings.get(f"{phase}_model") or "")
    thinking = str(settings.get(f"{phase}_thinking") or "")
    if provider:
        flags.extend(["--provider", provider])
    if model:
        flags.extend(["--model", model])
    if thinking:
        flags.extend(["--thinking", thinking])
    return flags


def _citation_map(root: Path) -> dict[int, str]:
    path = root / "artifacts" / "transcript_page_numbers.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    mapping: dict[int, str] = {}
    for item in payload.get("entries", []):
        if not isinstance(item, dict):
            continue
        page = item.get("file_page")
        try:
            page_number = int(page)
        except (TypeError, ValueError):
            continue
        mapping[page_number] = str(item.get("citation_label") or "")
    return mapping


class _SummaryChildRunner:
    """Run one JSON-mode PI child with sanitized event reporting."""

    def __init__(
        self,
        command: Sequence[str],
        label: str,
        workspace: Path,
        poll_interval: float,
        stall_timeout: float,
        env_overrides: dict[str, str] | None = None,
    ) -> None:
        self.command = list(command)
        self.label = label
        self.workspace = workspace
        self.poll_interval = poll_interval
        self.stall_timeout = stall_timeout
        self.env_overrides = env_overrides or {}
        self.process: subprocess.Popen[str] | None = None
        self._stall_reported = False

    def run(self) -> int:
        global _active_process
        env = os.environ.copy()
        env["TMPDIR"] = str(self.workspace / "tmp")
        env["PI_CODING_AGENT_SESSION_DIR"] = str(self.workspace / "sessions")
        env.update(self.env_overrides)
        (self.workspace / "sessions").mkdir(parents=True, exist_ok=True)
        (self.workspace / "tmp").mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        self.process = subprocess.Popen(
            self.command,
            cwd=self.workspace,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            process_group=0,
        )
        _active_process = self.process
        assert self.process.stdout is not None
        last_activity = time.monotonic()
        while True:
            line = self.process.stdout.readline()
            if line:
                last_activity = time.monotonic()
                self._handle_event(line)
            elif self.process.poll() is not None:
                break
            else:
                time.sleep(self.poll_interval)
            if (
                not self._stall_reported
                and time.monotonic() - last_activity >= self.stall_timeout
            ):
                self._stall_reported = True
                _line(
                    "\033[33m[stalled]\033[0m "
                    f"{self.label}: no PI event activity for "
                    f"{time.monotonic() - last_activity:.0f}s. Use the Stop "
                    "button to terminate it; RecordPrep will not kill "
                    "potentially valid work automatically."
                )
            if _stopped and self.process.poll() is None:
                _terminate_active_process()
        remaining = self.process.stdout.read()
        if remaining:
            for line in remaining.splitlines():
                self._handle_event(line)
        return_code = self.process.wait()
        elapsed = time.monotonic() - started
        _line(
            f"[{self.label}] child exited with code {return_code} after "
            f"{elapsed:.0f}s."
        )
        _active_process = None
        if _stopped:
            return 130
        return return_code

    def _handle_event(self, line: str) -> None:
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            return
        if not isinstance(event, dict):
            return
        event_type = str(event.get("type") or "")
        if event_type == "tool_execution_start":
            _line(f"[{self.label}] tool call: {event.get('toolName', 'unknown')}")
        elif event_type in {"agent_start", "turn_end", "agent_end"}:
            _line(f"[{self.label}] {event_type}")


def _check_stop() -> None:
    if _stopped:
        raise _StopRequested()


class _StopRequested(Exception):
    pass


def _staged_workspace(
    project_dir: Path,
    skill_name: str,
    workspace_parent: Path,
) -> tuple[Path, Path, Path]:
    """Stage SYSTEM.md, one skill, and the summary extension into a workspace."""
    workspace = Path(tempfile.mkdtemp(prefix="summary.", dir=workspace_parent))
    staged_pi = workspace / ".pi"
    staged_skill = staged_pi / "skills" / skill_name
    staged_skill.parent.mkdir(parents=True)
    (staged_pi / "extensions").mkdir(parents=True)
    shutil.copy2(project_dir / "settings.json", staged_pi / "settings.json")
    shutil.copy2(project_dir / "SYSTEM.md", staged_pi / "SYSTEM.md")
    shutil.copytree(project_dir / "skills" / skill_name, staged_skill)
    shutil.copy2(
        project_dir / "extensions" / SUMMARY_EXTENSION_NAME,
        staged_pi / "extensions" / SUMMARY_EXTENSION_NAME,
    )
    return workspace, staged_pi, staged_skill


def _base_child_command(
    pi_command: Sequence[str],
    staged_pi: Path,
    staged_skill: Path,
    tools: str,
    prompt: str,
    settings: dict[str, Any],
    phase: str,
) -> list[str]:
    return [
        *pi_command,
        "--mode",
        "json",
        "--no-session",
        "--approve",
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "--no-themes",
        "--no-context-files",
        "--system-prompt",
        str(staged_pi / "SYSTEM.md"),
        "--extension",
        str(staged_pi / "extensions" / SUMMARY_EXTENSION_NAME),
        "--skill",
        str(staged_skill / "SKILL.md"),
        "--tools",
        tools,
        *_model_override_flags(phase, settings),
        prompt,
    ]


def _report_capacity_decision(decision: Any, label: str) -> None:
    from recordprep import summary_preflight as preflight

    if decision.level == "ok":
        return
    if decision.level == "fail":
        # check_individual_request raises instead; this is a defensive path.
        raise preflight.PreflightError(decision.message)
    _line(f"\033[33m[warn]\033[0m {decision.message}")


# Placeholder used when capacity could not be resolved at all; every check
# reports its estimate as explicitly unknown instead of pretending capacity.
_UNRESOLVED_CAPACITY = None


def _stage_capacity(
    phase: str,
    kind: str,
    settings: dict[str, Any],
    project_dir: Path,
    models: Sequence[Any] | None,
) -> Any:
    """Resolve one phase's capacity once per stage (single discovery).

    Discovery results are reused across every kind/phase identity match;
    matching is provider-qualified on the full model id. Unknown metadata
    stays visibly unknown instead of being treated as verified capacity.
    """
    from recordprep import summary_preflight as preflight

    return preflight.resolve_stage_capacity(
        settings,
        phase,
        project_dir / "settings.json",
        models=models,
    )


def _report_capacity(capacity: Any, phase: str) -> None:
    from recordprep import summary_preflight as preflight

    identity = capacity.identity
    _line(
        f"[{phase}] model: {identity.provider}/{identity.model_id} "
        f"({identity.model_source}; thinking {identity.thinking or 'default'} "
        f"from {identity.thinking_source})"
    )
    if not capacity.known:
        detail = capacity.discovery_error or "no metadata available"
        _line(
            f"\033[33m[warn]\033[0m [{phase}] model capacity metadata is "
            f"unknown ({detail}); PI will enforce its own limit."
        )


def _run_extraction_child(
    root: Path,
    project_dir: Path,
    pi_command: Sequence[str],
    item: Any,
    extraction_config: Any,
    settings: dict[str, Any],
    workspace_parent: Path,
    cache_candidate: Path,
    extract_capacity: Any | None = None,
) -> dict[str, Any]:
    from recordprep import summary_agents as sa

    kind = extraction_config.kind
    skill_name = SUMMARY_SKILL_NAMES[kind]["extract"]
    workspace, staged_pi, staged_skill = _staged_workspace(
        project_dir, skill_name, workspace_parent
    )
    try:
        spec = sa.build_work_spec(
            item, extraction_config, root, cache_candidate, citation_by_page=_citation_map(root)
        )
        spec_path = workspace / "work_spec.json"
        spec_path.write_text(json.dumps(spec, ensure_ascii=True), encoding="utf-8")
        prompt_parts = [
            f"/skill:{skill_name}",
            "Run the loaded extraction skill now for the current document.",
            f"item_id: {item.item_id}",
            f"ordinal: {item.ordinal}",
            f"label: {item.label}",
            f"page range: {item.start_page}-{item.end_page}",
            f"candidate_path: {cache_candidate}",
            "category ids in order: "
            + ", ".join(sa.SUMMARY_CATEGORY_IDS[kind]),
            "",
            "EXTRACTION GUIDANCE — DIGEST CONTRACT",
            extraction_config.guidance,
        ]
        prompt_parts.append("")
        prompt_parts.append("PER-CATEGORY GUIDANCE")
        for definition in sa.summary_category_definitions(kind):
            prompt_parts.append(f"- {definition.identifier}: {definition.guidance}")
        if extraction_config.additional_guidance:
            prompt_parts.extend(
                [
                    "",
                    "ADDITIONAL USER GUIDANCE — lower priority than the built-in "
                    "contracts above:",
                    extraction_config.additional_guidance,
                ]
            )
        prompt_parts.extend(
            [
                "",
                "The work specification file is available to your tools; read the "
                "complete document source, then submit once.",
            ]
        )
        prompt = "\n".join(prompt_parts)
        command = _base_child_command(
            pi_command,
            staged_pi,
            staged_skill,
            SUMMARY_TOOL_ALLOWLISTS["extract"],
            prompt,
            settings,
            "extract",
        )
        # Capacity policy: a known oversized individual source request fails
        # before its paid call; unknown metadata is visibly reported and PI
        # enforces its own limit.
        from recordprep import summary_preflight as preflight

        static = preflight.stage_static_components(project_dir, skill_name)
        request_chars = preflight.extraction_request_chars(
            static,
            source_payload_chars=len(spec["source"]),
            prompt_chars=len(prompt),
        )
        decision = preflight.check_individual_request(
            extract_capacity or _UNRESOLVED_CAPACITY,
            request_chars,
            label=f"{item.item_id} extraction",
        )
        _report_capacity_decision(decision, f"{item.item_id} extraction")
        child = _SummaryChildRunner(
            command=command,
            label=f"{kind} extract {item.ordinal}",
            workspace=workspace,
            poll_interval=_float_env(
                "RECORDPREP_PI_STALL_POLL_INTERVAL", DEFAULT_POLL_INTERVAL_SECONDS
            ),
            stall_timeout=_float_env(
                "RECORDPREP_PI_STALL_TIMEOUT_SECONDS", DEFAULT_STALL_TIMEOUT_SECONDS
            ),
            env_overrides={
                "RECORDPREP_SUMMARY_MODE": "extract",
                "RECORDPREP_SUMMARY_WORK_SPEC": str(spec_path),
            },
        )
        return_code = child.run()
        if _stopped:
            raise _StopRequested()
        if return_code != 0:
            raise ValueError(
                f"Extraction for {item.item_id} failed (exit code {return_code}); "
                "the canonical row is unchanged."
            )
        if not cache_candidate.is_file():
            raise ValueError(
                f"Extraction for {item.item_id} produced no candidate; "
                "the canonical row is unchanged."
            )
        try:
            candidate = json.loads(cache_candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"Extraction candidate for {item.item_id} is unreadable: {exc}"
            ) from exc
        return candidate
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _run_synthesis_child(
    root: Path,
    project_dir: Path,
    pi_command: Sequence[str],
    rows: list[dict[str, Any]],
    synthesis_config: dict[str, Any],
    settings: dict[str, Any],
    kind: str,
    workspace_parent: Path,
    cache_candidate: Path,
    synthesize_capacity: Any | None = None,
) -> list[Any]:
    from recordprep import summary_agents as sa

    skill_name = SUMMARY_SKILL_NAMES[kind]["synthesize"]
    workspace, staged_pi, staged_skill = _staged_workspace(
        project_dir, skill_name, workspace_parent
    )
    try:
        dataset = {
            "artifact": "recordprep-summary-digest-dataset",
            "total_rows": len(rows),
            "rows": rows,
            "documents": [sa.document_markdown_block(row) for row in rows],
            "candidate_path": str(cache_candidate),
            "kind": kind,
        }
        dataset_path = workspace / "dataset.json"
        dataset_path.write_text(json.dumps(dataset, ensure_ascii=True), encoding="utf-8")
        guidance = str(synthesis_config.get("guidance") or "")
        additional_guidance = str(synthesis_config.get("additional_guidance") or "")
        prompt_parts = [
            f"/skill:{skill_name}",
            "Run the loaded synthesis skill now for the complete digest dataset.",
            f"total rows: {len(rows)}",
            "candidate_path: " + str(cache_candidate),
            "",
            guidance,
        ]
        if additional_guidance.strip():
            prompt_parts.extend(
                [
                    "",
                    "ADDITIONAL USER GUIDANCE — lower priority than the built-in "
                    "contracts above:",
                    additional_guidance,
                ]
            )
        prompt = "\n".join(prompt_parts)
        command = _base_child_command(
            pi_command,
            staged_pi,
            staged_skill,
            SUMMARY_TOOL_ALLOWLISTS["synthesize"],
            prompt,
            settings,
            "synthesize",
        )
        # Capacity policy: the aggregate synthesis-history estimate counts
        # model-visible components (overview + Markdown blocks, not the
        # internal JSON rows) plus explicit generated/tool-exchange/reasoning
        # allowances. Above the safety margin it warns and proceeds with
        # agent-managed incremental work — never batching or rejection.
        from recordprep import summary_preflight as preflight

        static = preflight.stage_static_components(project_dir, skill_name)
        history_chars = preflight.synthesis_history_chars(
            static,
            overview_chars=len(
                json.dumps(sa.build_dataset_overview(rows), ensure_ascii=True)
            ),
            document_block_chars=[
                len(sa.document_markdown_block(row)) for row in rows
            ],
        )
        decision = preflight.check_aggregate_history(
            synthesize_capacity or _UNRESOLVED_CAPACITY,
            history_chars,
            label=f"{kind} synthesis history",
        )
        _report_capacity_decision(decision, f"{kind} synthesis")
        child = _SummaryChildRunner(
            command=command,
            label=f"{kind} synthesis",
            workspace=workspace,
            poll_interval=_float_env(
                "RECORDPREP_PI_STALL_POLL_INTERVAL", DEFAULT_POLL_INTERVAL_SECONDS
            ),
            stall_timeout=_float_env(
                "RECORDPREP_PI_STALL_TIMEOUT_SECONDS", DEFAULT_STALL_TIMEOUT_SECONDS
            ),
            env_overrides={
                "RECORDPREP_SUMMARY_MODE": "synthesize",
                "RECORDPREP_SUMMARY_DATASET": str(dataset_path),
            },
        )
        return_code = child.run()
        if _stopped:
            raise _StopRequested()
        if return_code != 0:
            raise ValueError(
                f"Synthesis failed (exit code {return_code}); the prior summary "
                "is unchanged."
            )
        if not cache_candidate.is_file():
            raise ValueError(
                "Synthesis produced no candidate; the prior summary is unchanged."
            )
        try:
            candidate = json.loads(cache_candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Synthesis candidate is unreadable: {exc}") from exc
        sections_payload = candidate.get("sections")
        if not isinstance(sections_payload, list):
            # A candidate without a sections list normalizes to an all-fallback
            # result instead of failing the run.
            sections_payload = []
        return sections_payload
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _minute_page_by_date(root: Path) -> dict[str, int]:
    from recordprep import summary_agents as sa

    try:
        entries = json.loads(
            (root / "artifacts" / "minutes_boundaries.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return {}
    mapping: dict[str, int] = {}
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        raw_start = str(entry.get("start_page") or entry.get("start") or "")
        match = re.search(r"\d+", raw_start)
        if not match:
            continue
        date_value = str(entry.get("date") or "").strip()
        if not date_value:
            continue
        key = sa.format_label_date(date_value).lower()
        if key:
            mapping.setdefault(key, int(match.group()))
    return mapping


def _render_and_validate(
    root: Path,
    kind: str,
    rows: list[dict[str, Any]],
    sections: list[Any],
) -> tuple[str, dict[str, tuple[int, int | None]]]:
    from recordprep import summary_agents as sa

    stem = sa.summary_case_stem(root)
    display_name = stem.replace("_", " ") if stem else ""
    if kind == "hearings":
        minutes_by_date = _minute_page_by_date(root)
        heading_pages: dict[str, tuple[int, int | None]] = {}
        for row in rows:
            date_key = str(row.get("label") or "").lower()
            heading_pages[str(row.get("item_id"))] = (
                int(row.get("start_page") or 0),
                minutes_by_date.get(date_key),
            )
    else:
        heading_pages = {
            str(row.get("item_id")): (int(row.get("start_page") or 0), None)
            for row in rows
        }
    final_text = sa.render_final_summary(
        kind, display_name, rows, sections, heading_pages
    )
    # Structural checks before replacing any prior summary. These cover
    # renderer integrity, not model quality.
    if sa.REPORT_PROPOSAL_SCOPE_DELIMITER.strip() in final_text:
        raise ValueError("rendered summary leaked proposal scope material.")
    if "{{quote:" in final_text:
        raise ValueError("rendered summary contains an unresolved quote placeholder.")
    if "](page:" in final_text:
        raise ValueError("rendered summary contains generated page-link markup.")
    expected_headings = len(rows)
    if kind == "hearings":
        heading_count = sum(
            1
            for row in rows
            if sa.render_hearing_heading(str(row.get("label"))) in final_text
        )
    else:
        # Report headings are the human-readable date/name labels themselves.
        heading_count = sum(
            1
            for row in rows
            if sa.render_report_heading(str(row.get("label"))) in final_text
        )
    if heading_count != expected_headings:
        raise ValueError(
            f"rendered summary has {heading_count} document headings; expected "
            f"{expected_headings}."
        )
    return final_text, heading_pages


def _run_summary_stage(stage: SkillStage, root: Path, project_dir: Path) -> int:
    from recordprep import summary_agents as sa

    # summary_editions pulls in PyMuPDF; the GTK app always has it, but the
    # runner must not hard-fail without it. Skipping the removal is safe:
    # edition hash validation marks a superseded edition stale regardless.
    try:
        from recordprep.summary_editions import remove_summary_edition
    except ImportError:
        remove_summary_edition = None
        _line(
            "\033[33m[warn]\033[0m PyMuPDF is unavailable in this interpreter; "
            "the superseded summary edition was not removed. Hash validation "
            "will still mark it stale until it is rebuilt."
        )

    kind = SUMMARY_STAGE_KINDS[stage.step_id]
    settings = _summary_stage_settings(project_dir, kind)
    extraction_config = _extraction_config(project_dir, kind, settings)

    pi_command = _resolve_pi_command()
    _check_pi_version(pi_command)
    version_result = subprocess.run(
        [*pi_command, "--version"], text=True, capture_output=True, timeout=10
    )
    version_text = (version_result.stdout or version_result.stderr).strip()
    version_match = re.match(r"^0\.(\d+)", version_text)
    if version_match and int(version_match.group(1)) < SUMMARY_RESOURCE_MINIMUM_PI_MINOR:
        raise ValueError(
            f"The summary stages require PI 0.{SUMMARY_RESOURCE_MINIMUM_PI_MINOR} or "
            f"newer; found {version_text or 'unknown'}."
        )

    try:
        items = sa.build_work_items(root, extraction_config)
    except ValueError as exc:
        raise ValueError(
            f"Create {SUMMARY_KIND_LABELS[kind]} summaries prerequisites failed: {exc}"
        ) from exc

    # Resolve model identity and capacity once per stage. One discovery
    # result is reused for both phases; matching is provider-qualified on
    # the full model id (never a basename), and unknown metadata stays
    # visibly unknown instead of passing as verified capacity.
    from recordprep import summary_preflight as preflight

    try:
        discovered_models = preflight.pi_runtime.available_pi_models(pi_command)
    except (
        preflight.pi_runtime.PiRuntimeError,
        OSError,
        subprocess.SubprocessError,
    ) as exc:
        discovered_models = None
        _line(
            f"\033[33m[warn]\033[0m could not query PI model metadata ({exc}); "
            "capacity estimates stay explicitly unknown."
        )
    extract_capacity = _stage_capacity(
        "extract", kind, settings, project_dir, discovered_models
    )
    synthesize_capacity = _stage_capacity(
        "synthesize", kind, settings, project_dir, discovered_models
    )
    _report_capacity(extract_capacity, f"{kind} extract")
    _report_capacity(synthesize_capacity, f"{kind} synthesize")

    _line()
    _line(f"\033[1;36m{stage.title}\033[0m")
    _line(f"Case bundle: {root}")
    _line(f"Documents: {len(items)}")

    cache_root = Path(
        os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")
    ).expanduser()
    workspace_parent = cache_root / "recordprep-pi-workspaces"
    workspace_parent.mkdir(parents=True, exist_ok=True)

    try:
        with sa.SummaryKindLock(root, kind):
            # Legacy v2 digest JSONL converts losslessly to Markdown under the
            # lock before validation; Markdown is authoritative once present.
            migrated = sa.migrate_legacy_digest_jsonl(root, kind)
            if migrated is not None:
                _line(
                    f"[{kind}] converting legacy digest JSONL to Markdown "
                    f"({len(migrated)} rows) without model calls."
                )
                sa.publish_digests(root, kind, items, extraction_config, migrated)
            rows, pending_ids = sa.validate_digest_state(
                root, kind, items, extraction_config
            )
            items_by_id = {item.item_id: item for item in items}
            for index, item_id in enumerate(pending_ids, start=1):
                _check_stop()
                item = items_by_id[item_id]
                _line(
                    f"[{kind}] extraction {index}/{len(pending_ids)}: document "
                    f"{item.ordinal} ({item.item_id})"
                )
                candidate_cache = Path(
                    tempfile.mkdtemp(prefix="candidate.", dir=workspace_parent)
                ) / "candidate.json"
                try:
                    candidate = _run_extraction_child(
                        root,
                        project_dir,
                        pi_command,
                        item,
                        extraction_config,
                        settings,
                        workspace_parent,
                        candidate_cache,
                        extract_capacity,
                    )
                    _check_stop()
                    row_warnings: list[str] = []
                    row = sa.canonicalize_extraction_candidate(
                        candidate,
                        item,
                        root / "text_pages",
                        report_cutoff=(
                            (
                                item.proposal_marker.source_page,
                                item.proposal_marker.offset,
                            )
                            if item.proposal_marker is not None
                            else None
                        ),
                        warnings=row_warnings,
                    )
                    for warning in row_warnings:
                        _line(f"\033[33m[warn]\033[0m {warning}")
                except _StopRequested:
                    raise
                except ValueError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"Extraction for {item.item_id} failed: "
                        f"{type(exc).__name__}; the canonical row is unchanged."
                    ) from exc
                finally:
                    shutil.rmtree(candidate_cache.parent, ignore_errors=True)
                rows = sa.reconcile_digest_rows(
                    [
                        *[existing for existing in rows if existing.get("item_id") != item.item_id],
                        row,
                    ],
                    items,
                )[0]
                sa.publish_digests(root, kind, items, extraction_config, rows)
                _line(f"[{kind}] accepted digest row for {item.item_id}.")

            # Metadata is re-derived even when every row was already current, so a
            # crash between the Markdown and metadata writes self-heals. Stage
            # two then consumes the reloaded, validated on-disk Markdown rather
            # than the pre-publication in-memory rows.
            sa.publish_digests(root, kind, items, extraction_config, rows)
            rows = sa.reload_published_digest_rows(root, kind, items)
            # One effective-guidance contract shared with Settings and the
            # freshness fingerprints: the immutable synthesis contract plus
            # any byte-for-byte custom additional guidance, the effective
            # model identity, and the staged skill/tool-contract hashes.
            synthesis_config = sa.effective_synthesis_config(project_dir, kind)
            if items:
                _check_stop()
                candidate_cache = Path(
                    tempfile.mkdtemp(prefix="candidate.", dir=workspace_parent)
                ) / "candidate.json"
                try:
                    sections_payload = _run_synthesis_child(
                        root,
                        project_dir,
                        pi_command,
                        rows,
                        synthesis_config,
                        settings,
                        kind,
                        workspace_parent,
                        candidate_cache,
                        synthesize_capacity,
                    )
                    _check_stop()
                    sections, section_flags = sa.normalize_synthesis_sections(
                        rows,
                        sections_payload,
                    )
                    for flag in section_flags:
                        _line(f"\033[33m[warn]\033[0m synthesis: {flag}")
                    final_text, heading_pages = _render_and_validate(
                        root, kind, rows, sections
                    )
                    quality_flags = [
                        *section_flags,
                        *sa.rendered_narrative_flags(final_text),
                    ]
                finally:
                    shutil.rmtree(candidate_cache.parent, ignore_errors=True)
            else:
                sections = []
                quality_flags: list[str] = []
                final_text, heading_pages = _render_and_validate(
                    root, kind, rows, sections
                )
            final_path = sa.summary_final_path(root, kind)
            meta = sa.build_final_meta(
                root,
                kind,
                rows,
                final_text,
                synthesis_config,
                heading_pages,
                quality_flags=quality_flags,
            )
            sa._atomic_write(final_path, final_text)
            sa._atomic_write(
                sa.summary_final_meta_path(root, kind),
                json.dumps(meta, ensure_ascii=True, indent=2) + "\n",
            )
            # Legacy v1 fact-inventory artifacts are removed only after the
            # digest pipeline published successfully; the retired digest JSONL
            # is removed only once the new Markdown, metadata, and final
            # summary have all published.
            for removed in sa.cleanup_legacy_facts_artifacts(root, kind):
                _line(f"[{kind}] removed legacy artifact {removed}.")
            for removed in sa.cleanup_legacy_digest_jsonl(root, kind):
                _line(f"[{kind}] removed legacy digest artifact {removed}.")
            if remove_summary_edition is not None:
                remove_summary_edition(final_path)
            _line(f"\033[32m{stage.title} complete.\033[0m")
    except _StopRequested:
        _line(f"\033[33m{stage.title} stopped; the current row stays Pending.\033[0m")
        return 130
    return 0


def _native_stage_override_flags(project_dir: Path, step_id: str) -> list[str]:
    """Per-stage --provider/--model/--thinking flags from RecordPrep config.

    Empty values mean "use the project PI model/reasoning" from the staged
    .pi/settings.json, so no flags are emitted.
    """
    config_path = project_dir.parent / "config.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        config = {}
    config = config if isinstance(config, dict) else {}

    def value(key: str) -> str:
        return str(config.get(key, "") or "").strip()

    flags: list[str] = []
    provider = value(f"pi_stage_{step_id}_pi_provider")
    model = value(f"pi_stage_{step_id}_pi_model")
    thinking = value(f"pi_stage_{step_id}_pi_thinking")
    if provider:
        flags.extend(["--provider", provider])
    if model:
        flags.extend(["--model", model])
    if thinking:
        flags.extend(["--thinking", thinking])
    return flags


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
            *_native_stage_override_flags(project_dir, stage.step_id),
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
    _ensure_project_importable(project_dir)
    if args == ["--validate-resources"]:
        issues = _resource_issues(project_dir)
        if issues:
            for issue in issues:
                _line(f"PI resource validation failed: {issue}")
            return 1
        _line("RecordPrep sequential PI resources are valid.")
        return 0
    known_stages = {*STAGES, *SUMMARY_STAGE_KINDS}
    if len(args) != 1 or args[0] not in known_stages:
        choices = ", ".join(sorted(known_stages))
        _line(f"Usage: {Path(sys.argv[0]).name} <{choices}>")
        return 2
    try:
        if args[0] in SUMMARY_STAGE_KINDS:
            kind = SUMMARY_STAGE_KINDS[args[0]]
            stage = SkillStage(
                step_id=args[0],
                title=(
                    "Create hearing summaries"
                    if kind == "hearings"
                    else "Create report summaries"
                ),
                skill_name=SUMMARY_SKILL_NAMES[kind]["extract"],
                tools=SUMMARY_TOOL_ALLOWLISTS["extract"],
            )
            return _run_summary_stage(stage, _case_bundle(), project_dir)
        return _run_stage(STAGES[args[0]], _case_bundle(), project_dir)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        _line(f"\033[31mRecordPrep PI stage failed:\033[0m {exc}")
        return 2


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    raise SystemExit(main())
