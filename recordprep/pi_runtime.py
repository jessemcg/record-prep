from __future__ import annotations

import json
import os
import select
import shlex
import shutil
import subprocess
import time
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


from .paths import (SOURCE_ROOT, resource_root, pi_settings_path, config_dir,
                    DEFAULT_PUBLIC_PI_SETTINGS, atomic_private_json, stage_pi_settings)

PROJECT_DIR = SOURCE_ROOT
PROJECT_PI_DIR = resource_root()
PROJECT_PI_SETTINGS_PATH = pi_settings_path()
DEFAULT_PI_AGENT_COMMAND = "pi"
PI_MODEL_DISCOVERY_TIMEOUT_SECONDS = 10
PI_THINKING_LEVELS = (
    "off",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
)


class PiRuntimeError(RuntimeError):
    pass


class PiSettingsError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PiModel:
    provider: str
    model_id: str
    name: str
    context_window: int | None = None
    max_output_tokens: int | None = None

    @property
    def label(self) -> str:
        return f"{self.name} — {self.provider}"

    @property
    def settings_key(self) -> tuple[str, str]:
        return self.provider, self.model_id


def find_pi(
    home: Path | None = None,
    *,
    path_env: str | None = None,
) -> str | None:
    """Filesystem-only discovery: None means absent, not the fallback string 'pi'."""
    executable = shutil.which("pi", path=path_env)
    if executable:
        return executable
    home_dir = (home or Path.home()).expanduser()
    agent = Path(os.environ.get("PI_CODING_AGENT_DIR") or home_dir / ".pi/agent")
    data = Path(os.environ.get("XDG_DATA_HOME") or home_dir / ".local/share")
    candidates = [agent / "bin/pi", home_dir / ".pi/agent/bin/pi", home_dir / ".local/bin/pi"]
    candidates.extend(sorted((data / "pi-node").glob("node-*/bin/pi"),
                             key=lambda p: p.stat().st_mtime, reverse=True))
    installer_candidates = list(
        (home_dir / ".local" / "share" / "pi-node").glob("node-*/bin/pi")
    )
    installer_candidates.sort(
        key=lambda candidate: candidate.stat().st_mtime if candidate.exists() else 0,
        reverse=True,
    )
    candidates.extend(installer_candidates)
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def discover_pi_agent_command(home: Path | None = None, *, path_env: str | None = None) -> str:
    return find_pi(home, path_env=path_env) or DEFAULT_PI_AGENT_COMMAND


def resolve_pi_agent_argv(command: str, *, path_env: str | None = None) -> list[str]:
    argv = shlex.split(command)
    if not argv:
        return []
    if argv[0] == "pi":
        argv[0] = discover_pi_agent_command(path_env=path_env)
    return argv


PI_INCOMPATIBLE_AGENT_FLAGS = frozenset(
    {
        "-p",
        "--print",
        "--mode",
        "--no-session",
        "--continue",
        "-c",
        "--resume",
        "-r",
        "--session",
        "--session-id",
        "--session-dir",
        "--fork",
        "--model",
        "--provider",
        "--tools",
        "--no-tools",
        "--no-extensions",
        "-ne",
        "--extension",
        "-e",
        "--no-skills",
        "-ns",
        "--skill",
        "--prompt-template",
        "--no-prompt-templates",
        "-np",
        "--theme",
        "--no-themes",
        "--no-context-files",
        "-nc",
        "--system-prompt",
        "--append-system-prompt",
        "--approve",
        "--no-approve",
        "--cwd",
    }
)


def incompatible_pi_agent_flag(argv: Sequence[str]) -> str | None:
    for arg in argv[1:]:
        flag = str(arg).split("=", 1)[0]
        if flag in PI_INCOMPATIBLE_AGENT_FLAGS:
            return flag
    return None


def _pi_process_environment(command: Sequence[str]) -> dict[str, str]:
    env = os.environ.copy()
    if not command:
        return env
    executable = Path(command[0]).expanduser()
    if executable.is_absolute():
        env["PATH"] = str(executable.parent) + os.pathsep + env.get("PATH", "")
    return env


def _pi_discovery_command(pi_command: Sequence[str]) -> list[str]:
    base_command = [str(arg) for arg in pi_command if str(arg)]
    if not base_command:
        raise PiRuntimeError("PI command is empty.")
    return [
        *base_command,
        "--mode",
        "rpc",
        "--offline",
        "--no-session",
        "--approve",
        "--no-tools",
        "--no-skills",
        "--no-extensions",
        "--no-prompt-templates",
        "--no-themes",
        "--no-context-files",
    ]


def _pi_rpc_response(command: list[str], request: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    # Pi must not discover the source checkout's unrelated model preferences.
    if config_dir() is not None:
        with tempfile.TemporaryDirectory(prefix="recordprep-models-") as temporary:
            workspace = Path(temporary)
            stage_pi_settings(PROJECT_PI_DIR, workspace / ".pi/settings.json")
            return _query_pi_rpc(command, request, timeout=timeout, cwd=workspace)
    return _query_pi_rpc(command, request, timeout=timeout, cwd=PROJECT_DIR)


def _query_pi_rpc(
    command: list[str], request: dict[str, Any], *, timeout: float, cwd: Path,
) -> dict[str, Any]:
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=_pi_process_environment(command),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except OSError as exc:
        raise PiRuntimeError(f"Unable to start PI model query: {exc}") from exc

    output_lines: list[str] = []
    response: dict[str, Any] | None = None
    timed_out = False
    io_error: OSError | ValueError | None = None
    try:
        if process.stdin is None or process.stdout is None:
            raise PiRuntimeError("Unable to open PI RPC input and output.")
        process.stdin.write(json.dumps(request, ensure_ascii=True) + "\n")
        process.stdin.flush()
        deadline = time.monotonic() + timeout
        while response is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            ready, _writable, _errors = select.select(
                [process.stdout],
                [],
                [],
                remaining,
            )
            if not ready:
                timed_out = True
                break
            line = process.stdout.readline()
            if not line:
                break
            output_lines.append(line.rstrip())
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                isinstance(payload, dict)
                and payload.get("type") == "response"
                and payload.get("command") == request.get("type")
            ):
                response = payload
    except (OSError, ValueError) as exc:
        io_error = exc
    finally:
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
        if timed_out and process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
        if process.stdout is not None and not process.stdout.closed:
            try:
                remainder = process.stdout.read()
            except OSError as exc:
                if io_error is None:
                    io_error = exc
            else:
                if remainder:
                    output_lines.extend(remainder.splitlines())
            process.stdout.close()

    if timed_out:
        raise PiRuntimeError(f"PI model query timed out after {timeout:g} seconds.")
    if io_error is not None:
        raise PiRuntimeError(
            f"PI model query communication failed: {io_error}"
        ) from io_error
    if response is not None:
        return response
    detail = "\n".join(output_lines).strip()
    if len(detail) > 500:
        detail = detail[-500:]
    if process.returncode:
        raise PiRuntimeError(
            f"PI model query failed with exit code {process.returncode}"
            + (f": {detail}" if detail else ".")
        )
    raise PiRuntimeError("PI did not return an available-model response.")


def available_pi_models(
    pi_command: Sequence[str],
    *,
    timeout: float = PI_MODEL_DISCOVERY_TIMEOUT_SECONDS,
) -> list[PiModel]:
    response = _pi_rpc_response(
        _pi_discovery_command(pi_command),
        {"type": "get_available_models"},
        timeout=timeout,
    )
    if response.get("success") is not True:
        error = str(response.get("error") or "unknown RPC error").strip()
        raise PiRuntimeError(f"PI could not list available models: {error}")
    data = response.get("data")
    raw_models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(raw_models, list):
        raise PiRuntimeError("PI returned an invalid available-model response.")

    models: dict[tuple[str, str], PiModel] = {}
    for raw_model in raw_models:
        if not isinstance(raw_model, dict):
            continue
        provider = str(raw_model.get("provider") or "").strip()
        model_id = str(raw_model.get("id") or "").strip()
        if not provider or not model_id:
            continue
        name = str(raw_model.get("name") or model_id).strip() or model_id

        def _optional_int(raw_value: Any) -> int | None:
            try:
                value = int(raw_value)
            except (TypeError, ValueError):
                return None
            return value if value > 0 else None

        context_window = _optional_int(
            raw_model.get("contextWindow", raw_model.get("context_window"))
        )
        max_output = _optional_int(
            raw_model.get("maxOutputTokens", raw_model.get("max_output_tokens"))
        )
        model = PiModel(
            provider=provider,
            model_id=model_id,
            name=name,
            context_window=context_window,
            max_output_tokens=max_output,
        )
        models[model.settings_key] = model
    return sorted(
        models.values(),
        key=lambda model: (
            model.provider.casefold(),
            model.name.casefold(),
            model.model_id.casefold(),
        ),
    )


def _read_pi_settings(path: Path) -> dict[str, Any]:
    try:
        from ._model_store import read_ordinary
        raw = read_ordinary(path)
    except FileNotFoundError as exc:
        if config_dir() is not None and path == pi_settings_path():
            return dict(DEFAULT_PUBLIC_PI_SETTINGS)
        raise PiSettingsError(f"PI project settings not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise PiSettingsError(f"Unable to read PI project settings: {exc}") from exc
    if not isinstance(raw, dict):
        raise PiSettingsError("PI project settings must contain a JSON object.")
    return raw


def current_project_pi_model(
    path: Path | None = None,
) -> tuple[str, str] | None:
    settings = _read_pi_settings(path if path is not None else pi_settings_path())
    provider = str(settings.get("defaultProvider") or "").strip()
    model_id = str(settings.get("defaultModel") or "").strip()
    if not provider or not model_id:
        return None
    return provider, model_id


def current_project_pi_thinking_level(
    path: Path | None = None,
) -> str | None:
    settings = _read_pi_settings(path if path is not None else pi_settings_path())
    raw_level = settings.get("defaultThinkingLevel")
    if raw_level is None:
        return None
    level = str(raw_level).strip().lower()
    if level not in PI_THINKING_LEVELS:
        raise PiSettingsError(
            f"PI project settings contain an invalid thinking level: {raw_level}"
        )
    return level


def _write_pi_settings(settings: dict[str, Any], path: Path) -> None:
    try:
        from ._model_store import save_ordinary
        save_ordinary(path, settings)
    except (OSError, ValueError) as exc:
        raise PiSettingsError(f"Unable to save PI project settings: {exc}") from exc


def save_project_pi_model(
    model: PiModel,
    path: Path | None = None,
) -> None:
    path = path if path is not None else pi_settings_path()
    settings = _read_pi_settings(path)
    settings["defaultProvider"] = model.provider
    settings["defaultModel"] = model.model_id
    _write_pi_settings(settings, path)


def save_project_pi_thinking_level(
    level: str | None,
    path: Path | None = None,
) -> None:
    path = path if path is not None else pi_settings_path()
    settings = _read_pi_settings(path)
    if level is None:
        settings.pop("defaultThinkingLevel", None)
    else:
        normalized = str(level).strip().lower()
        if normalized not in PI_THINKING_LEVELS:
            raise PiSettingsError(f"Unsupported PI thinking level: {level}")
        settings["defaultThinkingLevel"] = normalized
    _write_pi_settings(settings, path)


SUMMARY_CONTEXT_CAPACITY_FRACTION = 0.8
SUMMARY_CHARS_PER_TOKEN = 4


def preflight_summary_context(
    model: PiModel,
    input_chars: int,
    output_chars: int,
    *,
    label: str = "summary request",
) -> None:
    """Conservatively preflight one complete request against context capacity.

    Fails before a paid call with an actionable message when the estimated
    complete item/dataset plus expected output exceeds 80% of the model's
    context window. Models without metadata pass through so PI enforces its
    own limit without damaging existing artifacts.
    """
    if not model.context_window or model.context_window <= 0:
        return
    input_tokens = max(0, int(input_chars)) // SUMMARY_CHARS_PER_TOKEN
    output_tokens = max(0, int(output_chars)) // SUMMARY_CHARS_PER_TOKEN
    capacity = int(model.context_window * SUMMARY_CONTEXT_CAPACITY_FRACTION)
    if input_tokens + output_tokens > capacity:
        raise PiRuntimeError(
            f"{label} does not fit conservatively within 80% of "
            f"{model.label}'s context window (estimated {input_tokens + output_tokens} "
            f"tokens vs capacity {capacity}). Choose a larger-context model for "
            "this stage in Settings."
        )


# --- Effective stage model identity (provider-qualified) ---


@dataclass(frozen=True, slots=True)
class PiModelIdentity:
    """Effective provider, full model id, and thinking level with sources.

    Explicit per-stage overrides win; empty values inherit the staged
    project PI settings environment. Matching is provider-qualified: the
    full model id is never reduced to a basename.
    """

    provider: str
    model_id: str
    thinking: str
    provider_source: str
    model_source: str
    thinking_source: str

    def payload(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "model_id": self.model_id,
            "thinking": self.thinking,
            "provider_source": self.provider_source,
            "model_source": self.model_source,
            "thinking_source": self.thinking_source,
        }


def resolve_stage_model_identity(
    settings: dict[str, Any],
    phase: str,
    project_settings_path: Path,
) -> PiModelIdentity:
    """Resolve one phase's effective model identity from override settings.

    ``settings`` carries ``<phase>_provider``/``<phase>_model``/
    ``<phase>_thinking`` override values (empty means inherit).
    """
    settings = settings if isinstance(settings, dict) else {}
    override_provider = str(settings.get(f"{phase}_provider") or "").strip()
    override_model = str(settings.get(f"{phase}_model") or "").strip()
    override_thinking = str(settings.get(f"{phase}_thinking") or "").strip()

    project_provider = ""
    project_model = ""
    try:
        resolved = current_project_pi_model(project_settings_path)
        if resolved is not None:
            project_provider, project_model = resolved
    except PiSettingsError:
        project_provider, project_model = "", ""
    try:
        project_thinking = current_project_pi_thinking_level(project_settings_path) or ""
    except PiSettingsError:
        project_thinking = ""

    return PiModelIdentity(
        provider=override_provider or project_provider,
        model_id=override_model or project_model,
        thinking=override_thinking or project_thinking,
        provider_source="override" if override_provider else "project-settings",
        model_source="override" if override_model else "project-settings",
        thinking_source="override" if override_thinking else "project-settings",
    )


def match_model_identity(
    identity: PiModelIdentity,
    models: Sequence[PiModel],
) -> PiModel | None:
    """Match provider plus full model id; ambiguous ids never match silently."""
    for model in models:
        if (
            model.provider.casefold() == identity.provider.casefold()
            and model.model_id.casefold() == identity.model_id.casefold()
        ):
            return model
    return None
