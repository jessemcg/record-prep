#!/usr/bin/env python3
"""RecordPrep source maintenance. Stdlib only; never imports the GUI or reads documents.

Every destructive path is derived independently, then compared to a private receipt.
No package cleanup is inferred from dependency names or run with autoremove.
"""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import fcntl
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

SCHEMA = 1
INSTALL_STAGES = 8
INSTALL_SUCCESS = "RecordPrep is installed. Open it from your applications menu."
REPOSITORY = "https://github.com/jessemcg/record-prep"
UV_VERSION = "0.11.8"
APP_ID = "com.mcglaw.RecordPrep"
MARKER = ".recordprep-install.json"
PACKAGES = {
    "apt": ("git", "curl", "ca-certificates", "python3", "build-essential", "pkg-config",
            "python3-dev", "libgirepository-2.0-dev", "libcairo2-dev", "gir1.2-gtk-4.0",
            "gir1.2-adw-1", "gir1.2-gdkpixbuf-2.0", "gir1.2-vte-3.91", "libvte-2.91-gtk4-0",
            "desktop-file-utils", "hicolor-icon-theme", "xdg-utils", "libpoppler-cpp-dev"),
    "dnf": ("git", "curl", "ca-certificates", "python3", "gcc", "pkgconf-pkg-config",
            "python3-devel", "glib2-devel", "gobject-introspection-devel", "cairo-devel", "cairo-gobject-devel",
            "gtk4", "libadwaita", "gdk-pixbuf2", "vte291-gtk4", "desktop-file-utils",
            "hicolor-icon-theme", "xdg-utils", "poppler-cpp-devel", "gcc-c++"),
}


class MaintenanceError(RuntimeError):
    pass


def styled_terminal(stream) -> bool:
    return (stream.isatty() and os.environ.get("TERM", "dumb") != "dumb"
            and "NO_COLOR" not in os.environ)


def terminal_symbols(stream) -> bool:
    try:
        "✓✗→●!━─".encode(stream.encoding or "ascii")
        return True
    except (UnicodeError, LookupError):
        return False


def status_text(kind: str, message: str, stream) -> str:
    """Append-only styling: no cursor tricks, hidden output or fake time estimates."""
    if not styled_terminal(stream):
        return f"[{kind}] {message}"
    colors = {"CHECK": "36", "OK": "32", "ACTION": "34", "WAIT": "33",
              "WARN": "33", "FAIL": "31", "INFO": "36"}
    symbols = {"CHECK": "●", "OK": "✓", "ACTION": "→", "WAIT": "→",
               "WARN": "!", "FAIL": "✗", "INFO": "●"}
    unicode = terminal_symbols(stream)
    label = f"{symbols.get(kind, '●')} {kind}" if unicode else kind
    text = f"\033[1;{colors.get(kind, '36')}m{label}\033[0m  {message}"
    stage = re.match(rf"(\d+)/{INSTALL_STAGES}\s", message) if kind == "CHECK" else None
    complete = kind == "OK" and message == INSTALL_SUCCESS
    if stage or complete:
        # Filled cells mean stages passed, not elapsed time or download percentage.
        done = INSTALL_STAGES if complete else max(0, min(INSTALL_STAGES - 1, int(stage.group(1)) - 1))
        filled, empty = ("━", "─") if unicode else ("#", "-")
        bar = filled * done + empty * (INSTALL_STAGES - done)
        text = f"\n\033[36m[{bar}]\033[0m {done}/{INSTALL_STAGES} stages passed\n{text}"
    return text


def say(kind: str, message: str) -> None:
    print(status_text(kind, message, sys.stdout), flush=True)


def welcome() -> None:
    if styled_terminal(sys.stdout):
        print("\n\033[1;36mRecordPrep\033[0m  \033[1mLet's get you set up.\033[0m\n"
              "We'll install RecordPrep first. Optional Pi setup comes afterward.\n",
              flush=True)


def approve(message: str, exact: str = "yes") -> None:
    try:
        # Text update mode requires seeking; terminals are not seekable.
        with open("/dev/tty", "r") as reader, open("/dev/tty", "w") as writer:
            prompt = f"Type {exact!r} to continue: " if exact else "Press Enter to continue, or Ctrl+C to cancel: "
            writer.write(status_text("WAIT", message, writer) + "\n" + prompt); writer.flush()
            line = reader.readline()
            if not line:
                raise MaintenanceError("Canceled; retained changes remain resumable")
            value = line.strip()
    except OSError as exc:
        raise MaintenanceError("No controlling terminal; explicit approval required") from exc
    if value != exact:
        raise MaintenanceError("Canceled; retained changes remain resumable")


def execute(command: list[str], *, env: dict | None = None, cwd: Path | None = None,
            capture: bool = False, check: bool = True, announce: bool = True) -> subprocess.CompletedProcess:
    if announce:
        say("ACTION" if not capture else "CHECK", shlex.join(str(c) for c in command))
    result = subprocess.run(command, env=env, cwd=cwd, capture_output=capture, text=True,
                            check=False, timeout=120 if capture else None)
    if check and result.returncode:
        raise MaintenanceError(f"Command failed ({result.returncode}): {shlex.join(command)}")
    return result


def safe_path(path: Path, *, home: Path | None = None) -> Path:
    """Do not canonicalize away a malicious symlink. Inspect every existing ancestor."""
    path = Path(os.path.abspath(path.expanduser()))
    if path == Path(path.anchor) or path == Path.home() or any(c in str(path) for c in "\n\r\0"):
        raise MaintenanceError(f"Unsafe destination: {path}")
    for part in reversed((path, *path.parents)):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode):
            raise MaintenanceError(f"Symlinked ownership path: {part}")
        if part == path and info.st_uid != os.getuid():
            raise MaintenanceError(f"Foreign ownership: {part}")
        if part != path and not stat.S_ISDIR(info.st_mode):
            raise MaintenanceError(f"Non-directory ancestor: {part}")
        if info.st_uid not in (0, os.getuid()) or (info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX):
            raise MaintenanceError(f"Untrusted writable ancestor: {part}")
    if home is not None and home not in path.parents:
        raise MaintenanceError(f"Ownership root must be machine-local below HOME: {path}")
    return path


def atomic_json(path: Path, data: dict) -> None:
    safe_path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".recordprep-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w") as out:
            json.dump(data, out, indent=2, sort_keys=True); out.write("\n"); out.flush(); os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def private_json(path: Path) -> dict:
    safe_path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_nlink != 1:
        raise MaintenanceError(f"Nonprivate or nonregular receipt: {path}")
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise MaintenanceError(f"Malformed ownership record: {path}") from exc
    if not isinstance(data, dict):
        raise MaintenanceError("Ownership record is not an object")
    return data


def layout(source: Path, *, home: Path | None = None, environ: dict | None = None) -> dict[str, Path]:
    env = os.environ if environ is None else environ
    home = (home or Path.home()).absolute()
    data = Path(env.get("XDG_DATA_HOME") or home / ".local/share")
    state = Path(env.get("XDG_STATE_HOME") or home / ".local/state")
    config = Path(env.get("XDG_CONFIG_HOME") or home / ".config")
    cache = Path(env.get("XDG_CACHE_HOME") or home / ".cache")
    paths = {"source": source, "environment": home / ".local/share/uv/project-envs/RecordPrep",
             "python": home / ".local/share/uv/project-python/RecordPrep", "tools": home / ".local/share/recordprep/tools",
             "config": config / "recordprep", "state": state / "recordprep", "maintenance": data / "recordprep/installer",
             "cache": cache / "recordprep", "command": home / ".local/bin/recordprep",
             "uninstall_command": home / ".local/bin/recordprep-uninstall",
             "desktop": data / f"applications/{APP_ID}.desktop",
             "svg": data / f"icons/hicolor/scalable/apps/{APP_ID}.svg",
             "symbolic": data / f"icons/hicolor/scalable/apps/{APP_ID}-symbolic.svg",
             "png": data / f"icons/hicolor/512x512/apps/{APP_ID}.png"}
    result = {key: safe_path(value, home=None if key == "source" else home) for key, value in paths.items()}
    if len(set(result.values())) != len(result):
        raise MaintenanceError("Overlapping destinations")
    for key, path in result.items():
        for other, candidate in result.items():
            if key != other and path in candidate.parents:
                raise MaintenanceError(f"Nested destinations: {key}, {other}")
    # Broad source roots must never be recursively purgeable (e.g. ~/.local).
    for root in (data, state, config, cache, home / ".local", home / "Dropbox"):
        if result["source"] == root or result["source"] in root.parents:
            raise MaintenanceError("Source destination contains an ownership or document root")
    if home / "Dropbox" in result["environment"].parents:
        raise MaintenanceError("Runtime cannot be synchronized")
    return result


def detect_platform(release: dict[str, str] | None = None, arch: str | None = None,
                    immutable: bool | None = None) -> str:
    if release is None:
        release = platform.freedesktop_os_release()
    if immutable is None:
        immutable = Path("/run/ostree-booted").exists() or Path("/sysroot/ostree").exists()
    identities = {release.get("ID", ""), release.get("VARIANT_ID", ""), *release.get("ID_LIKE", "").split()}
    if immutable or identities.intersection({"bazzite", "silverblue", "kinoite", "coreos"}):
        raise MaintenanceError("Immutable/rpm-ostree provisioning is unsupported; no layering or reboot")
    if (arch or platform.machine()) not in {"x86_64", "aarch64"}:
        raise MaintenanceError("Only x86_64 and aarch64 are supported")
    if "ubuntu" in identities:
        version = release.get("UBUNTU_VERSION_ID", release.get("VERSION_ID", ""))
        if version not in {"24.04", "26.04"}:
            codename = release.get("UBUNTU_CODENAME", "")
            if release.get("ID") == "ubuntu" or codename not in {"noble", "resolute"}:
                raise MaintenanceError("Ubuntu base must be 24.04 or 26.04")
        return "apt"
    if "fedora" in identities:
        version = release.get("FEDORA_VERSION_ID", release.get("VERSION_ID", ""))
        if version not in {"43", "44"}:
            raise MaintenanceError("Fedora base must be 43 or 44")
        return "dnf"
    raise MaintenanceError("Unsupported distribution/base; requires mutable Ubuntu or Fedora")


class Packages:
    def __init__(self, family: str):
        self.family = family

    def snapshot(self) -> set[str]:
        cmd = (["dpkg-query", "-W", "-f=${binary:Package}\t${db:Status-Status}\n"] if self.family == "apt"
               else ["rpm", "-qa", "--qf", "%{NAME}\n"])
        output = execute(cmd, capture=True).stdout
        if self.family == "apt":
            return {line.split("\t")[0].split(":")[0] for line in output.splitlines() if line.endswith("\tinstalled")}
        return set(output.splitlines())

    def missing(self) -> list[str]:
        installed = self.snapshot()
        return [name for name in PACKAGES[self.family] if name not in installed]

    def preview(self, names: list[str], *, remove: bool = False) -> str:
        if self.family == "apt":
            for name in names:
                candidate = execute(["apt-cache", "policy", name], capture=True).stdout
                if not remove and ("Candidate: (none)" in candidate or "Candidate:" not in candidate):
                    raise MaintenanceError(f"Official repositories do not provide {name}. Enable required official components explicitly, then resume")
            command = ["apt-get", "--simulate", "remove" if remove else "install", *names]
        else:
            command = ["dnf", "--assumeno", "remove" if remove else "install", *names]
        result = execute(command, env={**os.environ, "LC_ALL": "C"}, capture=True, check=False)
        print(result.stdout)
        if self.family == "apt" and result.returncode:
            raise MaintenanceError("Package preview failed (availability/lock); no packages changed")
        if self.family == "dnf" and (result.returncode not in (0, 1) or
                any(term in (result.stdout + result.stderr) for term in ("No match for argument", "Unable to find", "Failed to", "Error:"))):
            raise MaintenanceError("dnf transaction unavailable; no packages changed")
        removals = self.removals(result.stdout)
        if not remove and removals:
            raise MaintenanceError(f"Refusing dependency transaction that removes packages: {removals}")
        if remove and not removals.issubset(set(names)):
            raise MaintenanceError("Removal would affect unrelated packages; automated cleanup refused")
        return result.stdout

    def removals(self, output: str) -> set[str]:
        if self.family == "apt":
            return {m.group(1).split(":")[0] for m in re.finditer(r"^Remv (\S+)", output, re.M)}
        # dnf tables change across releases. Unknown tables fail closed for removals.
        removal_lines = re.search(r"(?:Removing(?: packages)?:|Removing dependent packages:)(.*?)(?:Transaction Summary|$)", output, re.S)
        if removal_lines:
            return {line.split()[0] for line in removal_lines.group(1).splitlines()
                    if line.strip() and not line.endswith(":")}
        return set()

    def install(self, names: list[str]) -> None:
        if not names:
            say("OK", "Native packages already installed"); return
        self.preview(names)
        approve("Install the previewed native dependencies. sudo may ask separately.", "")
        execute(["sudo", "apt-get" if self.family == "apt" else "dnf", "install", *names])

    def cleanup(self, introduced: list[str]) -> None:
        names = sorted(set(introduced) & self.snapshot())
        if not names:
            return
        say("WARN", f"Shared native packages retained by default: {', '.join(names)}")
        approve("Preview optional removal of ONLY introduced packages? Decline to retain")
        preview = self.preview(names, remove=True)
        if not self.removals(preview):
            raise MaintenanceError("Cannot establish bounded removal set; clean up manually")
        approve("Remove the previewed introduced packages? They may now serve other apps")
        execute(["sudo", "apt-get" if self.family == "apt" else "dnf", "remove", *names])


def native_meets(library: str, minimum: str) -> bool:
    if library == "girepository-2.0":
        return execute(["pkg-config", f"--atleast-version={minimum}", library], capture=True, check=False).returncode == 0
    soname, prefix = {"gtk4": ("libgtk-4.so.1", "gtk"), "libadwaita-1": ("libadwaita-1.so.0", "adw")}[library]
    try:
        native = ctypes.CDLL(soname)
        version = tuple(getattr(native, f"{prefix}_get_{component}_version")() for component in ("major", "minor", "micro"))
        return version >= tuple(int(n) for n in minimum.split("."))
    except (OSError, AttributeError):
        return False


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(source: Path) -> str:
    return hashlib.sha256(b"".join((source / name).read_bytes() for name in ("pyproject.toml", "uv.lock"))).hexdigest()


def python_environment(paths: dict[str, Path]) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("UV_") and key not in {"VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE", "PYTHONSTARTUP", "CONDA_PREFIX"}}
    env.update(UV_PROJECT_ENVIRONMENT=str(paths["environment"]), UV_PYTHON_INSTALL_DIR=str(paths["python"]),
               UV_CACHE_DIR=str(paths["cache"] / "uv"))
    return env


def marker(path: Path, installation: str, source: Path) -> None:
    atomic_json(path / MARKER, {"schema": SCHEMA, "installation_id": installation, "source": str(source)})


def bound(path: Path, installation: str, source: Path) -> None:
    value = private_json(path / MARKER)
    if value != {"schema": SCHEMA, "installation_id": installation, "source": str(source)}:
        raise MaintenanceError(f"Resource belongs to another checkout/installation: {path}")


@contextlib.contextmanager
def lock(state: Path):
    safe_path(state); state.mkdir(mode=0o700, parents=True, exist_ok=True)
    if state.stat().st_mode & 0o077:
        raise MaintenanceError("Maintenance state directory must be private (0700)")
    target = state / "maintenance.lock"; safe_path(target)
    fd = os.open(target, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if (info.st_uid != os.getuid() or info.st_nlink != 1
                or not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077
                or info.st_size != 0):
            raise MaintenanceError("Unsafe lock file")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise MaintenanceError("Another RecordPrep maintenance operation is running") from exc
        yield
    finally:
        os.close(fd)


def validate_receipt(data: dict, paths: dict[str, Path]) -> None:
    if data.get("schema") != SCHEMA or not re.fullmatch(r"[0-9a-f]{32}", str(data.get("installation_id", ""))):
        raise MaintenanceError("Unknown/malformed receipt version or identity")
    if data.get("phase") not in {"preflight", "native", "source", "environment", "desktop", "complete", "uninstalled"}:
        raise MaintenanceError("Unknown installation phase")
    if not isinstance(data.get("tool_versions", {}), dict) or not isinstance(data.get("config_created", False), bool):
        raise MaintenanceError("Malformed installation metadata")
    if "source_ref" in data and data["source_ref"] != "main":
        raise MaintenanceError("Malformed source ref")
    if data.get("paths") != {k: str(v) for k, v in paths.items()}:
        raise MaintenanceError("Receipt destinations disagree with independently derived paths")
    if not isinstance(data.get("files"), dict) or not isinstance(data.get("created"), list):
        raise MaintenanceError("Malformed resource ownership")
    previous = data.get("previous_files", {})
    if not isinstance(previous, dict) or any(key not in data["files"] or not re.fullmatch(r"[0-9a-f]{64}", str(value)) for key, value in previous.items()):
        raise MaintenanceError("Malformed pending file ownership")
    if not all(isinstance(name, str) for name in data["created"]):
        raise MaintenanceError("Malformed created resources")
    allowed = set(paths) - {"source", "state", "config"}
    if not set(data["created"]).issubset(allowed | {"source"}):
        raise MaintenanceError("Unknown owned resource")
    for name, value in data["files"].items():
        if name not in {"command", "uninstall_command", "desktop", "svg", "symbolic", "png", "engine"} or not re.fullmatch(r"[0-9a-f]{64}", str(value)):
            raise MaintenanceError("Malformed file ownership")
    introduced = data.get("introduced_pi_resources", [])
    agent = data.get("pi_agent_dir", str(Path.home() / ".pi/agent"))
    if not isinstance(agent, str) or not Path(agent).is_absolute():
        raise MaintenanceError("Malformed Pi directory")
    node = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "pi-node"
    allowed_pi = {str(Path(agent) / "install"), str(Path(agent) / "bin/pi"), str(node)}
    if not isinstance(introduced, list) or not all(isinstance(path, str) for path in introduced) or not set(introduced).issubset(allowed_pi):
        raise MaintenanceError("Malformed Pi/Node ownership delta")
    packages = data.get("introduced_packages", [])
    if not isinstance(packages, list) or any(not isinstance(p, str) or not re.fullmatch(r"[a-zA-Z0-9+_.-]+", p) for p in packages):
        raise MaintenanceError("Malformed package delta")


def receipt_paths(data: dict) -> dict[str, Path]:
    raw = data.get("paths", {})
    if not isinstance(raw, dict) or not isinstance(raw.get("source"), str):
        raise MaintenanceError("Malformed source path")
    paths = layout(Path(raw["source"]))
    validate_receipt(data, paths)
    return paths


def verify_environment(paths: dict[str, Path], installation: str | None = None) -> dict:
    source = paths["source"]; environment = paths["environment"]
    safe_path(source); safe_path(environment)
    binding = private_json(environment / MARKER)
    if binding.get("source") != str(source) or (installation and binding.get("installation_id") != installation):
        raise MaintenanceError("Environment is associated with another checkout")
    contract = private_json(environment / "recordprep-env.json")
    if contract.get("fingerprint") != fingerprint(source):
        raise MaintenanceError("Dependencies changed; explicitly run scripts/recordprep-env sync")
    python = environment / "bin/python"
    # uv's interpreter symlinks are expected; ownership roots, not internal links, are forbidden.
    base = python.resolve(strict=True)
    if paths["python"] not in base.parents:
        raise MaintenanceError("Interpreter is outside RecordPrep's private managed Python store")
    result = execute([str(python), "-I", "-c",
        "import sys; assert sys.version_info[:2] == (3,13); assert sys.prefix != sys.base_prefix"], capture=True)
    if result.returncode:
        raise MaintenanceError("Invalid interpreter binding")
    return contract


def locate_uv(paths: dict[str, Path], data: dict, save) -> str:
    candidate = shutil.which("uv")
    if candidate:
        result = execute([candidate, "--version"], capture=True, check=False)
        numbers = tuple(int(n) for n in re.findall(r"\d+", result.stdout)[:3])
        if result.returncode == 0 and numbers >= (0, 11, 8):
            data["tool_versions"]["uv"] = result.stdout.strip(); save(); return candidate
    private = paths["tools"] / "uv"
    if private.exists():
        return str(private)
    with tempfile.TemporaryDirectory(prefix="recordprep-uv-") as temp:
        script = Path(temp) / "install.sh"
        execute(["curl", "-fL", "--proto", "=https", "--tlsv1.2", f"https://astral.sh/uv/{UV_VERSION}/install.sh", "-o", str(script)])
        env = python_environment(paths); env["UV_UNMANAGED_INSTALL"] = str(paths["tools"])
        execute(["sh", str(script)], env=env)
    marker(paths["tools"], data["installation_id"], paths["source"])
    data["tool_versions"]["uv"] = UV_VERSION; save()
    return str(private)


def synchronize(paths: dict[str, Path], data: dict, save, *, dev: bool = False) -> None:
    for name in ("environment", "python", "tools", "cache"):
        path = paths[name]
        if path.exists():
            bound(path, data["installation_id"], paths["source"])
        else:
            # Ownership published BEFORE external commands, including interrupted provisioning.
            path.mkdir(mode=0o700, parents=True); marker(path, data["installation_id"], paths["source"])
            data["created"].append(name); save()
    uv = locate_uv(paths, data, save)
    env = python_environment(paths)
    execute([uv, "python", "install", "--no-bin", "3.13"], env=env)
    say("CHECK", "6/8 Locked editable dependencies")
    command = [uv, "sync", "--project", str(paths["source"]), "--python", "3.13", "--managed-python",
               "--locked", "--no-default-groups"]
    if dev:
        say("INFO", "RecordPrep uses stdlib unittest; no separate test dependencies")
    if not (paths["environment"] / "bin/python").exists():
        execute([uv, "venv", "--allow-existing", "--python", "3.13", "--managed-python", str(paths["environment"])], env=env)
    execute(command, env=env)
    marker(paths["environment"], data["installation_id"], paths["source"])
    atomic_json(paths["environment"] / "recordprep-env.json", {"schema": 1, "source": str(paths["source"]),
                "fingerprint": fingerprint(paths["source"]), "dev": dev})
    data["dependency_fingerprint"] = fingerprint(paths["source"]); save()
    verify_environment(paths, data["installation_id"])


def shell_value(value: Path | str) -> str:
    return shlex.quote(str(value))


def desktop_value(value: Path | str) -> str:
    # Desktop Entry uses a first escaping pass before Exec's quoted-argument parser.
    text = "".join(("\\" * 4 if char == "\\" else "\\" * 2 + char if char in '\"`$'
                    else "%%" if char == "%" else char) for char in str(value))
    return '"' + text + '"'


def render(template: str, values: dict[str, str]) -> bytes:
    for name, value in values.items():
        template = template.replace("@" + name + "@", value)
    if re.search(r"@[A-Z_]+@", template):
        raise MaintenanceError("Unresolved template variable")
    return template.encode()


def owned_file(key: str, target: Path, content: bytes, data: dict, save, mode: int = 0o644) -> None:
    safe_path(target)
    if target.exists():
        expected = data["files"].get(key)
        previous = data.get("previous_files", {}).get(key)
        if not expected or digest(target) not in {expected, previous}:
            raise MaintenanceError(f"Collision/modified owned file: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Record intent/hash before publication so a crash after replacement is resumable.
    if target.exists():
        data.setdefault("previous_files", {})[key] = digest(target)
    data["files"][key] = hashlib.sha256(content).hexdigest(); save()
    fd, temporary = tempfile.mkstemp(prefix=".recordprep-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content); stream.flush(); os.fsync(stream.fileno())
        os.chmod(temporary, mode); os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def desktop_environment(paths: dict[str, Path], data: dict) -> dict[str, str]:
    env = {key: os.environ[key] for key in ("HOME", "USER", "LOGNAME", "LANG", "TERM", "DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY",
           "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME") if key in os.environ}
    env.update(PATH="/usr/local/bin:/usr/bin:/bin", RECORDPREP_CONFIG_DIR=str(paths["config"]), PI_RUN_METRICS_ENABLED="0")
    if data.get("pi_agent_dir"):
        env["PI_CODING_AGENT_DIR"] = data["pi_agent_dir"]
    return env


def integration(paths: dict[str, Path], data: dict, save) -> None:
    source = paths["source"]; templates = source / "scripts/desktop"
    values = {"ENGINE": shell_value(paths["maintenance"] / "recordprep_maintenance.py"),
              "CONFIG": shell_value(paths["config"]), "SOURCE": shell_value(source),
              "PI_AGENT_DIR": shell_value(data.get("pi_agent_dir", str(Path.home() / ".pi/agent"))),
              "COMMAND_EXEC": desktop_value(paths["command"]), "ICON": str(paths["svg"]).replace("\\", "\\\\")}
    for key, name, mode in (("command", "recordprep.sh.in", 0o755), ("uninstall_command", "recordprep-uninstall.sh.in", 0o755),
                            ("desktop", "com.mcglaw.RecordPrep.desktop.in", 0o644)):
        owned_file(key, paths[key], render((templates / name).read_text(), values), data, save, mode)
    for key, asset in (("svg", "recordprep_icon.svg"), ("symbolic", "recordprep_icon-symbolic.svg"), ("png", "recordprep_icon.png")):
        owned_file(key, paths[key], (source / asset).read_bytes(), data, save)
    execute(["desktop-file-validate", str(paths["desktop"])])
    refresh_caches(paths)


def refresh_caches(paths: dict[str, Path]) -> None:
    for command in (["update-desktop-database", str(paths["desktop"].parent)],
                    ["gtk-update-icon-cache", "--force", "--ignore-theme-index", str(paths["svg"].parents[2])]):
        if shutil.which(command[0]):
            execute(command, check=False)


def active_processes(paths: dict[str, Path]) -> list[int]:
    active = []
    for directory in Path("/proc").glob("[0-9]*"):
        pid = int(directory.name)
        if pid in {os.getpid(), os.getppid()}:
            continue
        try:
            if directory.stat().st_uid != os.getuid():
                continue
            cmd = (directory / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            env = (directory / "environ").read_bytes().split(b"\0")
            is_recordprep = (str(paths["environment"]) in cmd and "recordprep" in cmd) or any(
                entry.startswith(b"RECORDPREP_AGENT_CASE_ROOT=") or entry == f"RECORDPREP_CONFIG_DIR={paths['config']}".encode() for entry in env)
            if is_recordprep:
                active.append(pid)
        except (OSError, ValueError):
            continue
    return active


def source_changes(source: Path) -> list[str]:
    if not (source / ".git").is_dir():
        return ["Missing or unfamiliar Git checkout"]
    status = execute(["git", "-C", str(source), "status", "--porcelain", "--untracked-files=all", "--ignored"], capture=True).stdout
    changes = [line for line in status.splitlines() if line[3:] != MARKER]
    branches = execute(["git", "-C", str(source), "for-each-ref", "--format=%(refname)", "refs/heads"], capture=True).stdout.splitlines()
    changes.extend(f"Local branch: {branch}" for branch in branches if branch != "refs/heads/recordprep-install")
    commits = execute(["git", "-C", str(source), "rev-list", "--branches", "--not", "--remotes"], capture=True).stdout.strip()
    if commits:
        changes.append("Local commits not represented by remote refs")
    return changes


def assert_purgeable(path: Path) -> None:
    protected = {"text_pages", "image_pages", "text_record", "saved-answers", "case_name.txt",
                 "source_map.json", "manifest.json", "registry.json", "snapshots", "practice-profiles"}
    for directory, subdirs, names in os.walk(path, followlinks=False):
        documents = any(Path(name).suffix.lower() in {".pdf", ".odt", ".doc", ".docx", ".rtf"} for name in names)
        if protected.intersection(subdirs) or protected.intersection(names) or documents:
            raise MaintenanceError(f"User record/document/profile layout detected; never purge: {directory}")


def purge_settings(paths: dict[str, Path], data: dict) -> None:
    """Only the two explicitly selected preference files; profiles are durable."""
    root = paths["config"]
    if not data.get("config_created"):
        say("WARN", "Pre-existing settings retained; installer does not own them")
        return
    bound(root, data["installation_id"], paths["source"])
    for relative in ("config.json", "pi/settings.json"):
        target = safe_path(root / relative)
        if target.exists():
            if not target.is_file() or target.stat().st_nlink != 1:
                raise MaintenanceError(f"Unsafe settings file: {target}")
            # A profile registry or other user data is never an app preference file.
            value = json.loads(target.read_text())
            if not isinstance(value, dict) or {"accepted", "heads", "schema_version"}.issubset(value):
                raise MaintenanceError(f"Unfamiliar settings content retained: {target}")
            approve("Delete this application preference file? Profiles and other files remain", str(target))
            target.unlink()
    say("OK", f"Retain settings directory and all personal profiles: {root}")


def remove_tree(path: Path) -> None:
    safe_path(path)
    if path.exists():
        assert_purgeable(path)
        # Python rmtree is fd-relative/symlink-attack-resistant on supported Linux.
        if not shutil.rmtree.avoids_symlink_attacks:
            raise MaintenanceError("Safe recursive deletion unavailable")
        shutil.rmtree(path)


def uninstall(args) -> int:
    state = safe_path(Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "recordprep")
    if not (state / "receipt.json").exists():
        raise MaintenanceError("No RecordPrep receipt; nothing removed")
    with lock(state):
        data = private_json(state / "receipt.json"); paths = receipt_paths(data)
        running = active_processes(paths)
        if running:
            raise MaintenanceError(f"Close RecordPrep and embedded sessions first (PIDs {running}); no process killed")
        trees = [name for name in ("environment", "python", "tools", "cache") if name in data["created"]]
        for name in trees:
            if paths[name].exists():
                bound(paths[name], data["installation_id"], paths["source"])
        files = {key: paths[key] if key != "engine" else paths["maintenance"] / "recordprep_maintenance.py" for key in data["files"]}
        for key, path in files.items():
            safe_path(path)
            if path.exists() and digest(path) not in {data["files"][key], data.get("previous_files", {}).get(key)}:
                raise MaintenanceError(f"Owned file changed; refusing removal: {path}")
        for name in trees:
            say("ACTION", f"Remove owned tree: {paths[name]}")
        for key, path in files.items():
            if key != "engine" or args.purge:
                say("ACTION", f"Remove owned file: {path}")
        for name in ("source", "config", "maintenance", "state"):
            say("ACTION" if args.purge else "OK", f"{'Offer purge of' if args.purge else 'Retain'}: {paths[name]}")
        if args.purge and "source" in data["created"] and paths["source"].exists():
            bound(paths["source"], data["installation_id"], paths["source"])
            assert_purgeable(paths["source"])
            say("WARN", f"Source changes (including ignored additions): {source_changes(paths['source'])}")
        if args.cleanup_packages:
            packages = Packages(data["package_family"])
            names = sorted(set(data.get("introduced_packages", [])) & packages.snapshot())
            if names:
                packages.preview(names, remove=True)
            else:
                say("OK", "No introduced native packages remain to remove")
        else:
            say("WARN", f"Retain shared native dependencies: {data.get('introduced_packages', [])}")
        say("OK", "Case bundles, bookmarks, source records, saved answers and Pi credentials are never removed")
        say("WARN", f"Pi/Node introduced resources {'require separate cleanup consent' if args.cleanup_pi else 'retained separately'}: {data.get('introduced_pi_resources', [])}")
        if args.dry_run:
            return 0
        approve("Apply the normal removal preview? Source and settings still retained")
        for key, path in files.items():
            if key != "engine":
                path.unlink(missing_ok=True)
        for name in trees:
            if name == "cache":
                # Native build caches can include upstream sample PDFs. Retain
                # rather than guessing whether any document is expendable.
                try:
                    assert_purgeable(paths[name])
                except MaintenanceError as exc:
                    say("WARN", f"Cache retained for document safety: {exc}")
                    continue
            remove_tree(paths[name])
        data["phase"] = "uninstalled"; atomic_json(state / "receipt.json", data)
        refresh_caches(paths)
        # Source, settings, and maintenance have independent, path-specific consent.
        if args.purge:
            if "source" in data["created"] and paths["source"].exists():
                bound(paths["source"], data["installation_id"], paths["source"])
                changes = source_changes(paths["source"])
                say("WARN", f"Source changes (including ignored additions): {changes}")
                approve("Delete installer-created Git checkout, including ALL listed changes?", str(paths["source"]))
                remove_tree(paths["source"])
            if paths["config"].exists():
                purge_settings(paths, data)
            if args.cleanup_pi:
                say("WARN", "Pi/Node may serve unrelated work. Credential/session stores will remain")
                introduced = data.get("introduced_pi_resources", [])
                agent = Path(data.get("pi_agent_dir", str(Path.home() / ".pi/agent")))
                if str(agent / "install") in introduced:
                    approve("Run Pi's supported official uninstaller (choose uninstall in its menu)?")
                    # No transcript capture, no guessed npm/rm command.
                    with tempfile.TemporaryDirectory(prefix="recordprep-pi-remove-") as temp:
                        script = Path(temp) / "install.sh"
                        execute(["curl", "-fL", "https://pi.dev/install.sh", "-o", str(script)])
                        env = desktop_environment(paths, data); env["PATH"] = str(agent / "bin") + ":" + env["PATH"]
                        with open("/dev/tty", "r+b", buffering=0) as tty:
                            subprocess.run(["sh", str(script)], env=env, cwd=temp, stdin=tty, stdout=tty, stderr=tty, check=True)
                node_root = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "pi-node"
                if str(node_root) in introduced and node_root.exists():
                    safe_path(node_root, home=Path.home())
                    approve("Delete installer-introduced Node runtime? It may now serve unrelated coding work", str(node_root))
                    # The normal process guard covers RecordPrep; shared Node has its own guard.
                    for proc in Path("/proc").glob("[0-9]*/exe"):
                        try:
                            if node_root in proc.resolve().parents:
                                raise MaintenanceError("A shared Node process is running; close it manually first")
                        except OSError:
                            continue
                    remove_tree(node_root)
                else:
                    say("OK", "Pre-existing Node retained")
            # Keep curl/system Python available until supported Pi cleanup finishes.
            if args.cleanup_packages:
                Packages(data["package_family"]).cleanup(data.get("introduced_packages", []))
            approve("Delete maintenance utilities, receipt and private logs?", str(paths["state"]))
            if (paths["maintenance"] / MARKER).exists():
                bound(paths["maintenance"], data["installation_id"], paths["source"])
                remove_tree(paths["maintenance"])
            remove_tree(paths["state"])
        say("OK", "RecordPrep removal finished; retained shared dependencies/documents were not touched")
    return 0


def continue_pi_install() -> bool:
    """Optional after-success prompt: EOF, skip and Ctrl+C all leave RecordPrep ready."""
    try:
        with open("/dev/tty", "r") as reader, open("/dev/tty", "w") as writer:
            writer.write("Press Enter to install Pi, or type skip to finish: ")
            writer.flush()
            answer = reader.readline()
            return bool(answer) and not answer.strip()
    except (OSError, KeyboardInterrupt):
        return False


def install_optional_pi(env: dict[str, str]) -> None:
    """Run the official installer only after RecordPrep has finished; no GUI handoff."""
    with tempfile.TemporaryDirectory(prefix="recordprep-optional-pi-") as directory:
        script = Path(directory) / "install.sh"
        execute(["curl", "--fail", "--location", "--proto", "=https", "--tlsv1.2",
                 "https://pi.dev/install.sh", "--output", str(script)], env=env, announce=False)
        with open("/dev/tty", "r+b", buffering=0) as tty:
            subprocess.run(["sh", str(script)], cwd=directory, env=env,
                           stdin=tty, stdout=tty, stderr=tty, check=True)


def offer_pi_install(paths: dict[str, Path], data: dict, save, env: dict[str, str]) -> None:
    python = str(paths["environment"] / "bin/python")
    found = execute([python, "-c", "from recordprep.pi_runtime import find_pi; print(find_pi() or '')"],
                    env=env, capture=True, announce=False).stdout.strip()
    if found:
        say("OK", "Pi is already installed.")
    else:
        say("INFO", "For AI features, install Pi next. This is optional.")
    print("In Pi, use /login to enter an API key or sign in.\n"
          "Then choose an available model in RecordPrep Model settings.\n"
          "Classification requires its separate endpoint, model and any required authentication.", flush=True)
    if found:
        return
    if not continue_pi_install():
        say("OK", "Pi skipped. You can install it later.")
        return
    pi_root = Path(data["pi_agent_dir"])
    node_root = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "pi-node"
    candidates = [pi_root / "install", pi_root / "bin/pi", node_root]
    previous = data.setdefault("pi_preexisting", {str(path): path.exists() or path.is_symlink() for path in candidates})
    save()
    say("ACTION", "Starting the Pi installer...")
    try:
        install_optional_pi(env)
    finally:
        data["introduced_pi_resources"] = sorted(set(data.get("introduced_pi_resources", [])) |
                                                  {path for path, existed in previous.items() if not existed and Path(path).exists()})
        save()  # Ownership only; never turn the completed receipt back into 'pi'.
    say("OK", "Pi installer finished.")
    print("Next: use /login in Pi, then choose a model in RecordPrep Model settings.", flush=True)


def install(args) -> int:
    if os.getuid() == 0:
        raise MaintenanceError("Run as the desktop user, not root; sudo is only for approved native transactions")
    welcome()
    say("CHECK", "1/8 Platform, permissions and destinations")
    family = detect_platform()
    source = Path(args.source_dir or Path.home() / "RecordPrep")
    paths = layout(source)
    receipt = paths["state"] / "receipt.json"
    say("CHECK", "2/8 Proposed changes (no RecordPrep binary package, no sibling projects)")
    for name, path in paths.items():
        print(f"  {name}: {path}")
    if args.dry_run:
        if receipt.exists():
            data = private_json(receipt); validate_receipt(data, paths)
        else:
            for name in ("source", "environment", "python", "tools", "maintenance", "command", "uninstall_command", "desktop", "svg", "symbolic", "png"):
                if paths[name].exists():
                    raise MaintenanceError(f"Unowned destination already exists: {paths[name]}")
        Packages(family).preview(Packages(family).missing())
        say("OK", "Dry-run only; Pi is optional and not required to install RecordPrep")
        return 0
    if not receipt.exists():
        for name in ("source", "environment", "python", "tools", "cache", "maintenance", "command", "uninstall_command", "desktop", "svg", "symbolic", "png"):
            if paths[name].exists():
                raise MaintenanceError(f"Unowned destination already exists: {paths[name]}")
    with lock(paths["state"]):
        if receipt.exists():
            data = private_json(receipt); validate_receipt(data, paths)
            if not (args.resume or args.repair):
                raise MaintenanceError("Receipt exists; use --resume or --repair")
        else:
            for name in ("source", "environment", "python", "tools", "cache", "maintenance", "command", "uninstall_command", "desktop", "svg", "symbolic", "png"):
                if paths[name].exists():
                    raise MaintenanceError(f"Unowned destination already exists: {paths[name]}")
            # A canceled first approval leaves only our empty lock, not a receipt.
            # Reuse its inode under the lock; unlinking it could split concurrency.
            if any(path.name != "maintenance.lock" for path in paths["state"].iterdir()):
                raise MaintenanceError("Unowned nonempty maintenance state; refusing takeover")
            approve("Continue with these paths. Dependency installation has a separate confirmation. Pi is optional.", "")
            ref = "main"
            data = {"schema": SCHEMA, "installation_id": uuid.uuid4().hex, "phase": "preflight",
                    "paths": {key: str(value) for key, value in paths.items()}, "source_ref": ref,
                    "created": [], "files": {}, "tool_versions": {}, "package_family": family,
                    "introduced_packages": os.environ.get("RECORDPREP_BOOTSTRAP_PACKAGES", "").split(), "config_created": not paths["config"].exists(),
                    "pi_agent_dir": os.environ.get("PI_CODING_AGENT_DIR") or str(Path.home() / ".pi/agent")}
        def save():
            atomic_json(receipt, data)
        def stage(name: str):
            data["phase"] = name; save()
            log = paths["state"] / "maintenance.log"
            safe_path(log)
            fd = os.open(log, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "w") as stream:
                stream.write(f"{int(time.time())} phase={name}\n")
        save()
        # Install durable maintenance BEFORE packages/source/auth so partial failure
        # is uninstallable even if the downloaded bootstrap disappears.
        if not paths["maintenance"].exists():
            paths["maintenance"].mkdir(parents=True, mode=0o700)
            marker(paths["maintenance"], data["installation_id"], paths["source"])
            data["created"].append("maintenance"); save()
        bound(paths["maintenance"], data["installation_id"], paths["source"])
        owned_file("engine", paths["maintenance"] / "recordprep_maintenance.py", Path(__file__).read_bytes(), data, save, 0o755)
        partial_uninstall = ("#!/bin/sh\n# Installed maintenance works even when the source is missing.\n"
                             f"exec /usr/bin/python3 -I {shell_value(paths['maintenance'] / 'recordprep_maintenance.py')} uninstall \"$@\"\n")
        owned_file("uninstall_command", paths["uninstall_command"], partial_uninstall.encode(), data, save, 0o755)
        try:
            say("CHECK", "3/8 Native dependencies")
            stage("native")
            packages = Packages(family)
            before = set(data.get("packages_before", packages.snapshot()))
            data["packages_before"] = sorted(before); save()
            try:
                needed = set(packages.missing())
                abi_packages = {"apt": {"girepository-2.0": "libgirepository-2.0-dev", "gtk4": "gir1.2-gtk-4.0", "libadwaita-1": "gir1.2-adw-1"},
                                "dnf": {"girepository-2.0": "glib2-devel", "gtk4": "gtk4", "libadwaita-1": "libadwaita"}}
                if shutil.which("pkg-config"):
                    for library, minimum in (("girepository-2.0", "2.80"), ("gtk4", "4.12"), ("libadwaita-1", "1.4")):
                        if not native_meets(library, minimum):
                            needed.add(abi_packages[family][library])
                packages.install(sorted(needed))
            finally:
                data["introduced_packages"] = sorted(set(data.get("introduced_packages", [])) | (packages.snapshot() - before)); save()
            # Explicit ABI checks catch installed-but-insufficient native libraries.
            for library, minimum in (("girepository-2.0", "2.80"), ("gtk4", "4.12"), ("libadwaita-1", "1.4")):
                if not native_meets(library, minimum):
                    raise MaintenanceError(f"Native {library} requires {minimum}+. No blanket upgrade; correct official repositories then resume")
            say("CHECK", "4/8 Editable Git source")
            stage("source")
            if paths["source"].exists():
                bound(paths["source"], data["installation_id"], paths["source"])
                if not (paths["source"] / ".git").exists():
                    raise MaintenanceError("Incomplete source destination; inspect before retry; no reset/clean")
            else:
                paths["source"].parent.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(prefix=".recordprep-clone-", dir=paths["source"].parent) as temp:
                    clone = Path(temp) / "source"
                    execute(["git", "clone", REPOSITORY, str(clone)])
                    execute(["git", "-C", str(clone), "switch", "--create", "recordprep-install",
                             "origin/main"])
                    marker(clone, data["installation_id"], paths["source"])
                    data["created"].append("source"); save()
                    os.rename(clone, paths["source"])
            revision = execute(["git", "-C", str(paths["source"]), "rev-parse", "HEAD"], capture=True).stdout.strip()
            data["source_revision"] = revision; save(); say("OK", f"Actual source commit: {revision}")
            for asset in ("uv.lock", "scripts/recordprep_maintenance.py", ".pi/SYSTEM.md"):
                if not (paths["source"] / asset).is_file():
                    raise MaintenanceError(f"Installation revision lacks {asset}")
            # Keep uninstall usable before any Pi/authentication work, even if source disappears.
            if not paths["maintenance"].exists():
                paths["maintenance"].mkdir(parents=True, mode=0o700)
                marker(paths["maintenance"], data["installation_id"], paths["source"])
                data["created"].append("maintenance"); save()
            bound(paths["maintenance"], data["installation_id"], paths["source"])
            owned_file("engine", paths["maintenance"] / "recordprep_maintenance.py", Path(__file__).read_bytes(), data, save, 0o755)
            values = {"ENGINE": shell_value(paths["maintenance"] / "recordprep_maintenance.py")}
            owned_file("uninstall_command", paths["uninstall_command"], render(
                (paths["source"] / "scripts/desktop/recordprep-uninstall.sh.in").read_text(), values), data, save, 0o755)
            say("CHECK", "5/8 uv and managed Python")
            stage("environment"); synchronize(paths, data, save)
            env = desktop_environment(paths, data)
            if data.get("config_created") and not paths["config"].exists():
                paths["config"].mkdir(parents=True, mode=0o700)
                marker(paths["config"], data["installation_id"], paths["source"])
            python = str(paths["environment"] / "bin/python")
            execute([python, "-m", "recordprep.native_check"], env=env)
            version = execute([python, "--version"], env=env, capture=True)
            data["tool_versions"]["python"] = version.stdout.strip(); save()
            say("CHECK", "7/8 Desktop entry, existing icons and commands")
            stage("desktop"); integration(paths, data, save)
            say("CHECK", "8/8 Final RecordPrep checks (no Pi or AI account required)")
            verify_environment(paths, data["installation_id"])
            execute([str(paths["command"]), "--help"], env=env, capture=True)
            stage("complete")
            say("OK", INSTALL_SUCCESS)
        except (Exception, KeyboardInterrupt):
            say("FAIL", f"Incomplete at {data['phase']}; owned changes retained, credentials not rolled back")
            print(f"Resume: {shlex.quote(str(paths['source'] / 'install.sh'))} --source-dir {shlex.quote(str(paths['source']))} --resume\n"
                  f"Uninstall: /usr/bin/python3 {shlex.quote(str(paths['maintenance'] / 'recordprep_maintenance.py'))} uninstall --dry-run\n"
                  f"Receipt: {receipt}")
            raise
        # RecordPrep is already complete. Optional third-party work must never change
        # that result or require resuming the RecordPrep install.
        try:
            offer_pi_install(paths, data, save, env)
        except (Exception, KeyboardInterrupt) as exc:
            say("WARN", f"Pi setup stopped: {exc}. RecordPrep remains installed.")
    return 0


def run_environment(args) -> int:
    state = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "recordprep"
    data = private_json(state / "receipt.json"); paths = receipt_paths(data)
    if args.operation == "sync" and "--dev" in args.arguments:
        args.dev = True
        args.arguments.remove("--dev")
    if args.project and safe_path(Path(args.project)) != paths["source"]:
        raise MaintenanceError("Helper checkout differs from receipt-bound source")
    if args.operation == "sync":
        with lock(state):
            synchronize(paths, data, lambda: atomic_json(state / "receipt.json", data), dev=args.dev)
        return 0
    verify_environment(paths, data["installation_id"])
    if args.operation == "check":
        say("OK", "Environment bound, dependency contract current; no provisioning")
        return 0
    command = list(args.arguments)
    if command and command[0] == "--":
        command.pop(0)
    if not command:
        command = ["recordprep"]
    name = command[0]
    if Path(name).name != name or not (paths["environment"] / "bin" / name).is_file():
        raise MaintenanceError("Run selects an installed environment command by name")
    executable = paths["environment"] / "bin" / name
    env = desktop_environment(paths, data)
    env.update(UV_PROJECT_ENVIRONMENT=str(paths["environment"]),
               UV_PYTHON_INSTALL_DIR=str(paths["python"]), UV_CACHE_DIR=str(paths["cache"] / "uv"),
               UV_NO_SYNC="1", UV_PYTHON_DOWNLOADS="never", UV_OFFLINE="1")
    os.chdir(paths["source"])
    os.execve(executable, [str(executable), *command[1:]], env)
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="action", required=True)
    install_parser = sub.add_parser("install")
    for name in ("source-dir", "payload-root"):
        install_parser.add_argument("--" + name)
    for name in ("dry-run", "resume", "repair"):
        install_parser.add_argument("--" + name, action="store_true")
    removal = sub.add_parser("uninstall")
    for name in ("dry-run", "purge", "cleanup-packages", "cleanup-pi"):
        removal.add_argument("--" + name, action="store_true")
    helper = sub.add_parser("env")
    helper.add_argument("--project")
    helper.add_argument("operation", choices=("check", "sync", "run"))
    helper.add_argument("--dev", action="store_true")
    helper.add_argument("arguments", nargs=argparse.REMAINDER)
    return result


def main(argv=None) -> int:
    os.umask(0o077)
    args = parser().parse_args(argv)
    try:
        if args.action == "install":
            return install(args)
        if args.action == "uninstall":
            if (args.cleanup_packages or args.cleanup_pi) and not args.purge:
                raise MaintenanceError("Shared dependency cleanup requires --purge and its separate confirmations")
            if os.getuid() == 0:
                raise MaintenanceError("Run uninstall as the desktop user")
            return uninstall(args)
        return run_environment(args)
    except (MaintenanceError, OSError, ValueError, subprocess.SubprocessError, KeyboardInterrupt) as exc:
        say("FAIL", str(exc)); return 1


if __name__ == "__main__":
    raise SystemExit(main())
