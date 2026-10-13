"""Stage-scoped native runtime fingerprints and narrowly reviewed legacy support.

Project code is parsed, never executed, to fingerprint reachable local definitions.
Only literal stage dispatch is specialized; unknown conditions retain both arms.
Compatibility is read-only and requires the exact current reviewed stage-code hash.
"""
from __future__ import annotations

import ast
import json
from functools import lru_cache
from pathlib import Path

STEPS = {"participants": "build_participant_index", "overview": "create_case_overview"}
_UNKNOWN = object()


class _StageProjection(ast.NodeTransformer):
    def __init__(self, stage, runner):
        self.values = {"native_kind": stage, "stage.step_id": STEPS[stage]}
        if not runner:
            self.values["stage"] = stage

    def value(self, node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return self.values.get(node.id, _UNKNOWN)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            return self.values.get(node.value.id + "." + node.attr, _UNKNOWN)
        if isinstance(node, (ast.Set, ast.Tuple, ast.List)):
            values = [self.value(n) for n in node.elts]
            return values if all(v is not _UNKNOWN for v in values) else _UNKNOWN
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left, right = self.value(node.left), self.value(node.comparators[0])
            if left is _UNKNOWN or right is _UNKNOWN:
                return _UNKNOWN
            op = node.ops[0]
            if isinstance(op, (ast.Eq, ast.Is)):
                return left == right
            if isinstance(op, (ast.NotEq, ast.IsNot)):
                return left != right
            if isinstance(op, (ast.In, ast.NotIn)) and isinstance(right, (list, tuple, str)):
                return (left in right) == isinstance(op, ast.In)
        return _UNKNOWN

    def visit_If(self, node):
        value = self.value(node.test)
        if isinstance(value, bool):
            result = []
            for child in node.body if value else node.orelse:
                child = self.visit(child)
                result.extend(child if isinstance(child, list) else [child])
            return result
        return self.generic_visit(node)

    def visit_IfExp(self, node):
        value = self.value(node.test)
        if isinstance(value, bool):
            return self.visit(node.body if value else node.orelse)
        return self.generic_visit(node)


@lru_cache(maxsize=32)
def projected_code(source: str, stage: str, roots: tuple[str, ...], *, runner=False) -> str:
    """Hash reachable definitions, preserving shared code and unknown branches."""
    if stage not in STEPS:
        raise ValueError("Unsupported native freshness stage")
    tree = _StageProjection(stage, runner).visit(ast.parse(source))
    definitions = {}
    imports = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    definitions[target.id] = node
    selected = set()
    pending = list(roots)
    while pending:
        name = pending.pop()
        if name in selected or name not in definitions:
            continue
        selected.add(name)
        pending.extend(n.id for n in ast.walk(definitions[name]) if isinstance(n, ast.Name))
    if not all(name in selected for name in roots):
        raise ValueError("Native fingerprint entry point is missing")
    nodes = [definitions[name] for name in sorted(selected)]
    referenced = {n.id for node in nodes for n in ast.walk(node) if isinstance(n, ast.Name)}
    used_imports = []
    for node in imports:
        names = [alias for alias in node.names if (alias.asname or alias.name.split('.')[0]) in referenced
                 or isinstance(node, ast.ImportFrom) and node.module == '__future__']
        if names:
            used_imports.append(ast.ImportFrom(module=node.module, names=names, level=node.level)
                                if isinstance(node, ast.ImportFrom) else ast.Import(names=names))
    nodes = used_imports + nodes
    if runner:
        declarations = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name) and node.func.id == 'SkillStage'
                        and node.args and isinstance(node.args[0], ast.Constant)
                        and node.args[0].value == STEPS[stage]]
        if len(declarations) != 1:
            raise ValueError('Native stage declaration is missing or ambiguous')
        nodes.append(declarations[0])
    return ast.dump(ast.Module(body=nodes, type_ignores=[]), include_attributes=False)


def stage_code_digest(project_dir: Path, stage: str) -> str:
    from .summary_agents import _resource_sha256, sha256_json
    package = Path(__file__).parent
    roots = (("compile_native", "prepare_participant_context", "participant_input_digest", "participant_metadata")
             if stage == "participants" else ("compile_native", "overview_input_digest", "overview_metadata"))
    runner = project_dir / "scripts/run_recordprep_skill.py"
    return sha256_json({
        "stage": stage,
        "projection": _resource_sha256(Path(__file__)),
        "runner": projected_code(runner.read_text(), stage, ("_run_stage",), runner=True),
        "native": projected_code((package / "native_profiles.py").read_text(), stage, roots),
        "shared": {name: _resource_sha256(package / name) for name in
                   ("profile_artifacts.py", "profile_contract.py")},
        "validation": projected_code((package / "pi_bundle.py").read_text(), stage,
            ("validate_participant_index_output", "validate_transcript_numbering_outputs", "validate_transcript_layout_output")
            if stage == "participants" else
            ("case_overview_prerequisite_issues", "validate_case_overview_text", "validate_case_overview_output")),
        "boundaries": projected_code((package / "boundary_profiles.py").read_text(), stage,
                                     ("require_current_boundaries",)),
        "participant_normalizer": _resource_sha256(package / "participant_candidates.py") if stage == "participants" else None,
    })


def runtime_identity(project_dir: Path) -> dict:
    from .pi_runtime import resolve_stage_model_identity
    from .minute_summaries import _global_settings_path
    from .summary_agents import _resource_sha256
    identity = resolve_stage_model_identity({}, "native", project_dir / "settings.json")
    return {"provider": identity.provider, "model": identity.model_id, "thinking": identity.thinking,
            "inherited": _resource_sha256(_global_settings_path()) if not all((identity.provider, identity.model_id, identity.thinking)) else None,
            "system": _resource_sha256(project_dir / "SYSTEM.md"),
            "auto_exit": _resource_sha256(project_dir / "extensions/recordprep-auto-exit.ts")}


def runtime_digest(project_dir: Path, stage: str) -> str:
    from .summary_agents import sha256_json
    return sha256_json(runtime_identity(project_dir) | {"contract": 2, "stage": stage,
                                                      "code": stage_code_digest(project_dir, stage)})


def runtime_matches(recorded: str, expected: str, project_dir: Path, stage: str) -> bool:
    if recorded == expected:
        return True
    from .summary_agents import sha256_json
    # Shipped, reviewed legacy dependency hashes, never obtained from a case or
    # private configuration. No runtime Git dependency and no metadata migration.
    try:
        compatibility = json.loads((Path(__file__).parent / "resources/native_runtime_compat.json").read_text())
        entry = compatibility.get(stage, {})
        if entry.get("stage_code_sha256") != stage_code_digest(project_dir, stage):
            return False
        identity = runtime_identity(project_dir)
        return any(recorded == sha256_json(identity | legacy) for legacy in entry.get("legacy", []))
    except (OSError, ValueError, TypeError):
        return False
