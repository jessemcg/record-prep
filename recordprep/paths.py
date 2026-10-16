"""GTK-independent separation of tracked resources and selected preferences.

Only RECORDPREP_CONFIG_DIR opts into external preferences. Never infer a migration
from the existence of an XDG directory, and never use it as the Pi resource root.
Explicit resource/test roots retain their checkout-local behavior without that opt-in.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

SOURCE_ROOT = Path(__file__).resolve().parent.parent
# Application policy, not a copy of a developer's provider/model preferences.
DEFAULT_PUBLIC_PI_SETTINGS = {"enableSkillCommands": True, "defaultThinkingLevel": "high"}


def config_dir() -> Path | None:
    value = os.environ.get("RECORDPREP_CONFIG_DIR", "")
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("RECORDPREP_CONFIG_DIR must be absolute")
    return path


def resource_root(project_dir: Path | None = None) -> Path:
    if project_dir is not None:
        return Path(project_dir)
    return Path(os.environ.get("RECORDPREP_PI_PROJECT_DIR") or SOURCE_ROOT / ".pi")


def application_config_path(project_dir: Path | None = None) -> Path:
    selected = config_dir()
    return (selected if selected is not None else resource_root(project_dir).parent) / "config.json"


def pi_settings_path(project_dir: Path | None = None) -> Path:
    selected = config_dir()
    return selected / "pi/settings.json" if selected is not None else resource_root(project_dir) / "settings.json"


def read_json_object(path: Path, *, missing: dict | None = None) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return dict(missing or {})
    if not isinstance(data, dict):
        raise ValueError(f"Settings must contain a JSON object: {path}")
    return data


def effective_pi_settings(project_dir: Path | None = None) -> dict[str, Any]:
    return read_json_object(pi_settings_path(project_dir),
                            missing=DEFAULT_PUBLIC_PI_SETTINGS if config_dir() is not None else {})


def atomic_private_json(path: Path, data: dict) -> None:
    """Explicit save only. Refuse malformed existing files; never repair on startup."""
    if path.exists():
        read_json_object(path)
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=True, indent=2)
            stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def stage_pi_settings(project_dir: Path, destination: Path) -> None:
    settings = effective_pi_settings(project_dir)
    if config_dir() is None:
        # Preserve the established exact legacy staging behavior, including bytes.
        shutil.copy2(pi_settings_path(project_dir), destination)
    else:
        atomic_private_json(destination, settings)


def startup_log_path() -> Path:
    if config_dir() is None:
        return Path("/tmp/recordprep_startup.log")
    state = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "recordprep"
    state.mkdir(parents=True, mode=0o700, exist_ok=True)
    return state / "startup.log"
