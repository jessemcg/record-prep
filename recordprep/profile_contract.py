"""Practice-profile contract v1; stdlib only, no discovery or execution.

This file is intentionally vendored in Focus and RecordPrep. Keep the copies
byte-identical and update the common conformance tests with contract changes.
Application resources, selection and storage remain independent.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

MAX_FILE_BYTES = 256 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024
MAX_FILES = 256
IDENTIFIER = re.compile(r"[a-z][a-z0-9_-]{0,95}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")

# Resource names and stage dependencies are application-owned, never supplied
# by a profile. Adding a policy or pipeline stage requires a code change.
RESOURCE_TYPES = {
    "focus": {"research": "md", "answer_guidance": "md", "search": "json"},
    "recordprep": {
        "classification": "md", "naming": "json", "roles": "json",
        "hearings": "json", "reports": "json", "policies": "json",
        "hearing_extraction": "md", "report_extraction": "md",
        "hearing_synthesis": "md", "report_synthesis": "md",
        "minutes": "md", "participants": "md", "overview": "md",
        "classification_tasks": "json", "case_name": "md",
    },
}
# Required only by historical content schemas 1/2, never compiled into summaries.
RETIRED_SUMMARY_RESOURCES = frozenset({
    "hearing_extraction", "report_extraction", "hearing_synthesis", "report_synthesis",
})
RETIRED_PARTICIPANT_RESOURCES = frozenset({"roles", "participants"})
RETIRED_OVERVIEW_RESOURCES = frozenset({"overview"})
STAGE_RESOURCES = {
    "focus": {"research": ("research", "answer_guidance", "search")},
    "recordprep": {
        "classification": ("classification",),
        "naming": ("naming",),
        "participants": (),  # Identification is application-owned for every specialty.
        # Historical instructions/catalogs remain readable, never compiled.
        "hearing_extraction": ("hearings",),
        "report_extraction": ("reports",),
        "hearing_synthesis": ("hearings",),
        "report_synthesis": ("reports",),
        "minutes": ("minutes",),
        "overview": (),  # Orientation method is fixed; summaries are runtime inputs.
    },
}
CAPABILITIES = {"focus": {"research-v1"}, "recordprep": {"preparation-v1"}}

# Structural vocabulary belongs to the application, not a legal specialty.
# Shared by the RecordPrep runtime and the vendored profile editor; changing
# these labels requires corresponding pipeline support, never private migration.
CLASSIFICATION_PAGE_TYPES = {
    "rt": ("RT_cover", "RT_index", "RT_body", "RT_certificate", "RT_other"),
    "ct": ("CT_cover", "CT_index", "CT_minute_order", "CT_report", "CT_form",
           "CT_certificate", "CT_motion", "CT_notice", "CT_proof_of_service", "CT_other"),
}
CLASSIFICATION_FIRST_PAGE_TYPES = {
    "first_hearing": "RT_body_first_page",
    "first_minute": "CT_minute_order_first_page",
    "first_form": "CT_form_first_page",
}


def classification_guidance_warning(text: str, task: str) -> str:
    """Advisory token lint, not semantic validation or a profile-load gate.

    References can be comparisons/negations, so never block Save or rewrite
    guidance. CR is included to catch a common mistaken CT prefix. This cannot
    detect every natural-language contradiction or replace model validation.
    """
    known = set(sum(CLASSIFICATION_PAGE_TYPES.values(), ())) | set(CLASSIFICATION_FIRST_PAGE_TYPES.values())
    allowed = set(CLASSIFICATION_PAGE_TYPES.get(task, ())) or known
    references = set(re.findall(r"\b(?:RT|CT|CR)_[a-z0-9_]+\b", text, re.IGNORECASE))
    suspicious = sorted(value for value in references if value.casefold() not in {item.casefold() for item in allowed})
    if not suspicious:
        return ""
    # Bounded, literal label text only; never interpret profile text as markup.
    labels = ", ".join(value[:80] for value in suspicious[:12])
    return ("Review page-type references: " + labels + ". These are not supported outputs for this task. "
            "Use the application labels shown above; customize recognition clues, not the labels. "
            "Comparisons or instructions not to use a label may be intentional. This warning does not block Save.")


@dataclass(frozen=True)
class Issue:
    code: str
    location: str


class ProfileError(ValueError):
    """Sanitized structural issue; never includes profile instruction text."""

    def __init__(self, code: str, location: str = "profile"):
        self.issue = Issue(code, location)
        super().__init__(f"{code}: {location}")


def _require(condition: bool, code: str, location: str) -> None:
    if not condition:
        raise ProfileError(code, location)


def _object(value: Any, fields: set[str], location: str) -> dict:
    _require(isinstance(value, dict) and set(value) == fields, "invalid_fields", location)
    return value


def _text(value: Any, location: str, limit: int = 8192, *, empty: bool = False) -> str:
    _require(isinstance(value, str), "invalid_text", location)
    _require(len(value) <= limit and (empty or bool(value.strip())), "invalid_text", location)
    _require("\x00" not in value, "invalid_text", location)
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ProfileError("invalid_utf8", location) from exc
    return value


def _identifier(value: Any, location: str) -> str:
    _require(isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None,
             "invalid_identifier", location)
    return value


def _json(data: bytes, location: str) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate_json_key", location)
            result[key] = value
        return result

    def constant(_value):
        raise ProfileError("nonfinite_json", location)

    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, ProfileError):
            raise
        raise ProfileError("invalid_json", location) from exc


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _path(value: Any, location: str, suffix: str) -> str:
    _text(value, location, 240)
    path = PurePosixPath(value)
    _require(not path.is_absolute() and str(path) == value and
             all(part not in {"..", ".", ""} for part in value.split("/")) and
             "\\" not in value and path.suffix == "." + suffix and len(path.parts) <= 8,
             "unsafe_resource_path", location)
    return value


def read_file_at(root_fd: int, relative: str, *, limit: int = MAX_FILE_BYTES) -> bytes:
    """Bounded, descriptor-relative read; never follow a resource symlink/FIFO."""
    parts = relative.split("/")
    _require(all(part not in {"", ".", ".."} for part in parts), "unsafe_resource_path", "resource")
    current = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            os.close(current)
            current = child
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
        try:
            before = os.fstat(fd)
            _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                     "not_regular_private_file", "resource")
            _require(not before.st_mode & 0o111, "executable_resource", "resource")
            _require(before.st_size <= limit, "file_too_large", "resource")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                data = stream.read(limit + 1)
            after = os.fstat(fd)
            _require(len(data) <= limit, "file_too_large", "resource")
            _require((before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                     (after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                     "concurrent_edit", "resource")
            return data
        finally:
            os.close(fd)
    except OSError as exc:
        raise ProfileError("unreadable_or_unsafe_path", "resource") from exc
    finally:
        os.close(current)


def _catalog(value: Any, location: str, *, roles: bool = False) -> None:
    _require(isinstance(value, list) and 1 <= len(value) <= 128, "invalid_catalog", location)
    seen = set()
    label = "label" if roles else "title"
    for item in value:
        _object(item, {"id", label, "guidance"}, location)
        identifier = _identifier(item["id"], location)
        _require(identifier not in seen, "duplicate_id", location)
        seen.add(identifier)
        _text(item[label], location, 160)
        _text(item["guidance"], location)
    if roles:
        _require({"unknown", "other"} <= seen, "missing_role_fallback", location)


def _terms(value: Any, location: str) -> None:
    _require(isinstance(value, list) and len(value) <= 256, "invalid_terms", location)
    seen = set()
    for term in value:
        _text(term, location, 160)
        _require(term == term.strip() and "\n" not in term and "\r" not in term,
                 "invalid_term", location)
        _require(term.casefold() not in seen, "duplicate_term", location)
        seen.add(term.casefold())


def naming_prompt_titles(prompt: str) -> tuple[str, ...]:
    """Approved names live once, as bold bullets in the editable instructions."""
    _text(prompt, "naming")
    names = []
    for line in prompt.splitlines():
        if line.startswith("- **"):
            match = re.fullmatch(r"- \*\*(.+?)\*\*(?: — .*)?", line)
            _require(match is not None, "invalid_approved_name", "naming")
            names.append(match[1])
    _terms(names, "naming")
    return tuple(names)


def _structured(name: str, value: Any) -> None:
    if name in {"hearings", "reports"}:
        _catalog(value, name)
    elif name == "roles":
        _object(value, {"counsel", "participants"}, name)
        for catalog in value.values():
            _catalog(catalog, name, roles=True)
    elif name == "policies":
        _require(isinstance(value, dict) and set(value) <= {"attendance", "report_scope"},
                 "invalid_fields", name)
        # Accept the retired field only to keep existing snapshot bytes readable.
        # It is not compiled or consulted by any producer.
        if "report_scope" in value:
            _require(value["report_scope"] in ("include_attributed_proposals", "exclude_formal_proposals"),
                     "unsupported_policy", name)
        if "attendance" in value:
            _require(value["attendance"] in ("explicit_complete_order", "legacy_first_page_parents"),
                     "unsupported_policy", name)
    elif name == "naming":
        _require(isinstance(value, dict), "invalid_fields", name)
        if value.get("schema_version") == 3:
            _object(value, {"schema_version", "report_guidance", "form_guidance"}, name)
            _require(type(value["schema_version"]) is int, "unsupported_version", name)
            for field in ("report_guidance", "form_guidance"):
                naming_prompt_titles(value[field])
            return
        if "schema_version" not in value:
            # Frozen foundation revisions remain loadable without rewriting
            # accepted snapshots or pretending they required form codes.
            _object(value, {"mode", "report_titles", "form_titles", "guidance"}, name)
            _terms(value["form_titles"], name)
            _text(value["guidance"], name)
        else:
            _require(type(value["schema_version"]) is int and value["schema_version"] == 2,
                     "unsupported_version", name)
            _object(value, {"schema_version", "mode", "report_titles", "form_rules",
                            "report_guidance", "form_guidance"}, name)
            _text(value["report_guidance"], name)
            _text(value["form_guidance"], name)
            rules = value["form_rules"]
            _require(isinstance(rules, list) and len(rules) <= 256, "invalid_catalog", name)
            names, codes = [], []
            for rule in rules:
                _object(rule, {"name", "title", "code"}, name)
                _terms([rule["title"]], name)
                names.append(rule["name"])
                codes.append(rule["code"])
            # One canonical output per code in v2. Aliases/regex matchers are
            # intentionally not implicit; adding them needs a new contract.
            _terms(names, name)
            _terms(codes, name)
        _require(value["mode"] in ("source_title", "approved_titles"), "unsupported_policy", name)
        _terms(value["report_titles"], name)
    elif name == "classification_tasks":
        _object(value, {"rt", "ct", "first_hearing", "first_minute", "first_form",
                        "date_hearing", "date_minute"}, name)
        for task, guidance in value.items():
            _text(guidance, task, MAX_FILE_BYTES)
    elif name == "search":
        _object(value, {"query_terms", "document_terms", "passage_terms", "later_history_terms"}, name)
        for terms in value.values():
            _terms(terms, name)


@dataclass(frozen=True)
class ProfileRef:
    specialty_id: str
    application: str
    version: str
    profile_api: int
    content_sha256: str

    @classmethod
    def from_dict(cls, value: Any) -> ProfileRef:
        _object(value, {"specialty_id", "application", "version", "profile_api", "content_sha256"}, "reference")
        _identifier(value["specialty_id"], "reference")
        _require(value["application"] in ("focus", "recordprep"), "wrong_application", "reference")
        _text(value["version"], "reference", 64)
        _require(type(value["profile_api"]) is int and value["profile_api"] == 1,
                 "unsupported_version", "reference")
        _require(isinstance(value["content_sha256"], str) and DIGEST.fullmatch(value["content_sha256"]) is not None,
                 "invalid_digest", "reference")
        return cls(**value)


@dataclass(frozen=True)
class ProfileSnapshot:
    """All bytes are frozen. Parsed JSON properties return fresh mutable copies."""

    ref: ProfileRef
    files: tuple[tuple[str, bytes], ...]

    @property
    def manifest(self) -> dict:
        return _json(dict(self.files)["profile.json"], "manifest")

    def resource(self, name: str) -> str | dict | list:
        manifest = self.manifest
        data = dict(self.files)[manifest["resources"][name]]
        if RESOURCE_TYPES[self.ref.application][name] == "json":
            return _json(data, name)
        return data.decode("utf-8")


@dataclass(frozen=True)
class ValidationResult:
    draft: ProfileSnapshot | None
    issues: tuple[Issue, ...]


def _manifest(data: bytes, application: str) -> dict:
    value = _json(data, "manifest")
    _object(value, {"schema_version", "profile_api", "specialty_id", "application", "display_name",
                    "description", "version", "required_capabilities", "resources"}, "manifest")
    _require(type(value["profile_api"]) is int and value["profile_api"] == 1,
             "unsupported_version", "profile_api")
    _require(type(value["schema_version"]) is int and value["schema_version"] in
             ((1, 2, 3, 4, 5) if application == "recordprep" else (1,)), "unsupported_version", "schema_version")
    _require(value["application"] == application, "wrong_application", "application")
    _identifier(value["specialty_id"], "specialty_id")
    _text(value["display_name"], "display_name", 160)
    _text(value["description"], "description", 4096, empty=True)
    _text(value["version"], "version", 64)
    caps = value["required_capabilities"]
    _require(isinstance(caps, list) and len(caps) <= 32 and all(isinstance(c, str) for c in caps),
             "unsupported_capabilities", "required_capabilities")
    _require(len(set(caps)) == len(caps) and set(caps) == CAPABILITIES[application],
             "unsupported_capabilities", "required_capabilities")
    types = dict(RESOURCE_TYPES[application])
    if application == "recordprep":
        if value["schema_version"] == 1:
            for name in ("classification_tasks", "case_name"):
                types.pop(name)
        if value["schema_version"] >= 3:
            for name in RETIRED_SUMMARY_RESOURCES:
                types.pop(name)
        if value["schema_version"] >= 4:
            for name in RETIRED_PARTICIPANT_RESOURCES:
                types.pop(name)
        if value["schema_version"] >= 5:
            for name in RETIRED_OVERVIEW_RESOURCES:
                types.pop(name)
    resources = _object(value["resources"], set(types), "resources")
    paths = set()
    for name, suffix in types.items():
        path = _path(resources[name], name, suffix)
        _require(path != "profile.json" and path not in paths, "duplicate_resource_path", name)
        paths.add(path)
    _require(len(paths) <= MAX_FILES, "too_many_resources", "resources")
    return value


def _content_digest(files: tuple[tuple[str, bytes], ...]) -> str:
    digest = hashlib.sha256(b"court-record-profile-v1\0")
    for name, data in sorted(files):
        encoded = name.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def validate_contents(files: tuple[tuple[str, bytes], ...], application: str) -> ProfileSnapshot:
    _require(application in RESOURCE_TYPES, "wrong_application", "application")
    _require(len(files) <= MAX_FILES + 1, "too_many_resources", "resources")
    mapping = dict(files)
    _require(len(mapping) == len(files) and "profile.json" in mapping, "invalid_files", "profile")
    _require(all(isinstance(data, bytes) and len(data) <= MAX_FILE_BYTES for data in mapping.values()),
             "file_too_large", "profile")
    _require(sum(map(len, mapping.values())) <= MAX_TOTAL_BYTES, "profile_too_large", "profile")
    manifest = _manifest(mapping["profile.json"], application)
    _require(set(mapping) == {"profile.json", *manifest["resources"].values()}, "invalid_files", "profile")
    for name, path in manifest["resources"].items():
        data = mapping[path]
        if RESOURCE_TYPES[application][name] == "json":
            _structured(name, _json(data, name))
        else:
            try:
                _text(data.decode("utf-8"), name, MAX_FILE_BYTES)
            except UnicodeError as exc:
                raise ProfileError("invalid_utf8", name) from exc
    files = tuple(sorted(files))
    return ProfileSnapshot(ProfileRef(manifest["specialty_id"], application, manifest["version"],
                                      1, _content_digest(files)), files)


def validate_profile_directory(path: Path, application: str) -> ValidationResult:
    """Explicit read only. No case discovery, settings access or acceptance."""
    root_fd = None
    try:
        _require(application in RESOURCE_TYPES, "wrong_application", "application")
        root_fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        manifest_bytes = read_file_at(root_fd, "profile.json")
        manifest = _manifest(manifest_bytes, application)
        files = [("profile.json", manifest_bytes)]
        total = len(manifest_bytes)
        for relative in manifest["resources"].values():
            data = read_file_at(root_fd, relative)
            files.append((relative, data))
            total += len(data)
            _require(total <= MAX_TOTAL_BYTES, "profile_too_large", "profile")
        # Catch an editor replacing one file or its manifest during validation.
        for relative, data in files:
            _require(read_file_at(root_fd, relative) == data, "concurrent_edit", "profile")
        return ValidationResult(validate_contents(tuple(files), application), ())
    except ProfileError as exc:
        return ValidationResult(None, (exc.issue,))
    except OSError:
        return ValidationResult(None, (Issue("unreadable_or_unsafe_path", "profile"),))
    finally:
        if root_fd is not None:
            os.close(root_fd)


@dataclass(frozen=True)
class CompiledStage:
    profile_ref: ProfileRef
    stage: str
    component_sha256: str
    resources: tuple[tuple[str, bytes], ...]


def compile_stage_profile(snapshot: ProfileSnapshot, stage: str, *, core_contract: bytes) -> CompiledStage:
    """Select only the stage's declarations; never compose or relax core rules.

    The caller supplies its effective core resources/version bytes. Selection
    provenance changes independently of component freshness. Source/model/input
    dependencies must also be included by the eventual pipeline caller.
    """
    validated = validate_contents(snapshot.files, snapshot.ref.application)
    _require(validated.ref == snapshot.ref, "snapshot_hash_mismatch", "profile")
    task_stages = {"classification_basic": ("rt", "ct"),
                   "classification_advanced": ("first_hearing", "first_minute", "first_form"),
                   "classification_corrected": ("rt", "ct", "first_hearing", "first_minute", "first_form"),
                   "classification_dates": ("date_hearing", "date_minute")}
    extended = snapshot.ref.application == "recordprep" and snapshot.manifest["schema_version"] >= 2
    _require(stage in STAGE_RESOURCES[snapshot.ref.application] or
             (extended and stage in {*task_stages, "case_name"}), "unsupported_stage", "stage")
    _require(isinstance(core_contract, bytes) and bool(core_contract), "missing_core_contract", "stage")
    resources = []
    names = (("classification", "classification_tasks") if stage in task_stages else
             ("case_name",) if stage == "case_name" else STAGE_RESOURCES[snapshot.ref.application][stage])
    if stage == "classification" and extended:
        names += ("classification_tasks",)
    for name in names:
        value = snapshot.resource(name)
        if name == "classification_tasks" and stage in task_stages:
            value = {task: value[task] for task in task_stages[stage]}
        data = value.encode("utf-8") if isinstance(value, str) else json_bytes(value)
        resources.append((name, data))
    digest = _content_digest(tuple(resources) + (("@core", core_contract),
                             ("@application", snapshot.ref.application.encode()), ("@stage", stage.encode())))
    return CompiledStage(snapshot.ref, stage, digest, tuple(resources))


def identity_descriptor(snapshot: ProfileSnapshot) -> bytes:
    validated = validate_contents(snapshot.files, snapshot.ref.application)
    _require(validated.ref == snapshot.ref, "snapshot_hash_mismatch", "profile")
    manifest = snapshot.manifest
    return json_bytes({"schema_version": 1, "specialty_id": snapshot.ref.specialty_id,
                       "display_name": manifest["display_name"], "description": manifest["description"]})


def parse_identity_descriptor(data: bytes) -> dict:
    _require(len(data) <= MAX_FILE_BYTES, "file_too_large", "identity")
    value = _json(data, "identity")
    _object(value, {"schema_version", "specialty_id", "display_name", "description"}, "identity")
    _require(type(value["schema_version"]) is int and value["schema_version"] == 1,
             "unsupported_version", "identity")
    _identifier(value["specialty_id"], "identity")
    _text(value["display_name"], "identity", 160)
    _text(value["description"], "identity", 4096, empty=True)
    return value


def validation_report(result: ValidationResult) -> dict:
    return {"valid": result.draft is not None, "issues": [asdict(issue) for issue in result.issues],
            "profile_ref": asdict(result.draft.ref) if result.draft else None}
