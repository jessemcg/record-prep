"""Shared offline conformance suite; synthetic profiles and temporary stores only."""
from __future__ import annotations

import dataclasses
import io
import importlib
import json
import os
import shutil
import subprocess
import sys
import stat
import tempfile
import unittest
from contextlib import redirect_stdout
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

# One identical conformance suite in both independent repositories.
PACKAGE = "focus" if (Path(__file__).resolve().parents[1] / "focus").is_dir() else "recordprep"
contract = importlib.import_module(f"{PACKAGE}.profile_contract")
api = importlib.import_module(f"{PACKAGE}.practice_profiles")
ProfileStore = importlib.import_module(f"{PACKAGE}.profile_store").ProfileStore


def synthetic_files(application="focus"):
    manifest = {
        "schema_version": 1, "profile_api": 1, "specialty_id": "synthetic-employment",
        "application": application, "display_name": "Synthetic Employment",
        "description": "Synthetic fixture only.", "version": "1.0",
        "required_capabilities": sorted(contract.CAPABILITIES[application]),
        "resources": {name: f"resources/{name}.{suffix}"
                      for name, suffix in contract.RESOURCE_TYPES[application].items()},
    }
    catalog = [{"id": "material_facts", "title": "Material facts", "guidance": "Attribute material facts."}]
    roles = [{"id": role, "label": role.title(), "guidance": "Use explicit source evidence."}
             for role in ("plaintiff", "defendant", "unknown", "other")]
    structured = {
        "hearings": catalog, "reports": catalog,
        "roles": {"counsel": roles, "participants": roles},
        "policies": {"report_scope": "include_attributed_proposals", "attendance": "explicit_complete_order"},
        "naming": {"mode": "source_title", "report_titles": [], "form_titles": [],
                   "guidance": "Use the source title."},
        "search": {"query_terms": ["termination"], "document_terms": ["order"], "passage_terms": [],
                   "later_history_terms": []},
    }
    files = {"profile.json": contract.json_bytes(manifest)}
    for name, path in manifest["resources"].items():
        files[path] = contract.json_bytes(structured[name]) if name in structured else b"  Preserve custom whitespace.\n\n"
    return files


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.profile = self.root / "profile"
        self.files = synthetic_files()
        self.write_profile(self.files)
        self.store = ProfileStore("focus", config_root=self.root / "config",
                                  data_root=self.root / "data")

    def write_profile(self, files):
        self.profile.mkdir(exist_ok=True)
        for relative, data in files.items():
            path = self.profile / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def draft(self, files=None, app="focus"):
        return contract.validate_contents(tuple((files or self.files).items()), app)

    def manifest_edit(self, **changes):
        files = self.files.copy()
        manifest = json.loads(files["profile.json"])
        manifest.update(changes)
        files["profile.json"] = contract.json_bytes(manifest)
        return files

    def assert_invalid(self, files, code=None, app="focus"):
        with self.assertRaises(contract.ProfileError) as caught:
            self.draft(files, app)
        if code:
            self.assertEqual(caught.exception.issue.code, code)

    def test_naming_v2_rules_and_legacy_snapshots(self):
        legacy_files = synthetic_files("recordprep")
        legacy = self.draft(legacy_files, "recordprep")
        naming = {"schema_version": 2, "mode": "approved_titles", "report_titles": ["Synthetic Report"],
                  "form_rules": [{"name": "Synthetic Output", "title": "Synthetic Heading", "code": "XY-10"}],
                  "report_guidance": "Require a prominent heading.", "form_guidance": "Require heading and code."}
        files = legacy_files | {"resources/naming.json": contract.json_bytes(naming)}
        current = self.draft(files, "recordprep")
        self.assertNotEqual(legacy.ref, current.ref)
        store = ProfileStore("recordprep", config_root=self.root / "prep-config", data_root=self.root / "prep-data")
        store.accept_profile(legacy, expected_previous_digest=None)
        store.accept_profile(current, expected_previous_digest=legacy.ref.content_sha256)
        self.assertEqual(store.load_profile_snapshot(legacy.ref), legacy)
        self.assertEqual(store.load_profile_snapshot(current.ref), current)
        invalid = [naming | {"schema_version": True}, naming | {"schema_version": 3},
                   naming | {"form_rules": ["flat legacy title"]},
                   naming | {"form_rules": naming["form_rules"] * 2},
                   naming | {"form_rules": [{"name": "Output", "title": "Heading"}]},
                   naming | {"form_rules": [{"name": "Output", "title": "Heading", "code": ""}]},
                   naming | {"form_rules": [{"name": "Output", "title": "Heading", "code": "XY-10", "regex": True}]},
                   naming | {"form_guidance": ""}]
        for value in invalid:
            with self.subTest(value=value):
                self.assert_invalid(legacy_files | {"resources/naming.json": contract.json_bytes(value)}, app="recordprep")

    def test_valid_app_profiles_are_independent(self):
        focus = self.draft()
        prep = self.draft(synthetic_files("recordprep"), "recordprep")
        self.assertEqual(focus.ref.specialty_id, prep.ref.specialty_id)
        self.assertNotEqual(focus.ref.content_sha256, prep.ref.content_sha256)
        self.assertEqual(contract.validate_profile_directory(self.profile, "focus").draft, focus)
        self.assert_invalid(self.files, "wrong_application", "recordprep")

    def test_hash_is_order_independent_but_byte_sensitive(self):
        original = self.draft()
        reversed_files = dict(reversed(list(self.files.items())))
        self.assertEqual(original.ref, self.draft(reversed_files).ref)
        changed = self.files.copy()
        changed["resources/research.md"] += b"\n"
        self.assertNotEqual(original.ref, self.draft(changed).ref)

    def test_frozen_snapshot_returns_json_copies(self):
        draft = self.draft()
        draft.manifest["version"] = "changed"
        search = draft.resource("search")
        search["query_terms"].append("injected")
        self.assertEqual(draft.manifest["version"], "1.0")
        self.assertEqual(draft.resource("search")["query_terms"], ["termination"])
        with self.assertRaises(dataclasses.FrozenInstanceError):
            draft.files = ()
        self.assertEqual(draft.resource("research"), "  Preserve custom whitespace.\n\n")

    def test_unknown_fields_versions_and_caps(self):
        for changes, code in [({"schema_version": True}, "unsupported_version"),
                              ({"profile_api": 2}, "unsupported_version"),
                              ({"command": "do-not-execute"}, "invalid_fields"),
                              ({"required_capabilities": ["shell"]}, "unsupported_capabilities"),
                              ({"required_capabilities": [["nested"]]}, "unsupported_capabilities"),
                              ({"specialty_id": "../escape"}, "invalid_identifier")]:
            with self.subTest(changes=changes):
                self.assert_invalid(self.manifest_edit(**changes), code)

    def test_missing_duplicate_and_undeclared_resources(self):
        files = self.files.copy()
        files.pop("resources/search.json")
        self.assert_invalid(files, "invalid_files")
        files = self.files | {"secret.txt": b"not allowed"}
        self.assert_invalid(files, "invalid_files")
        manifest = json.loads(self.files["profile.json"])
        manifest["resources"]["answer_guidance"] = manifest["resources"]["research"]
        self.assert_invalid(self.manifest_edit(resources=manifest["resources"]), "duplicate_resource_path")

    def test_json_and_utf8_are_strict_and_sanitized(self):
        bad_values = [b'{"query_terms": [], "query_terms": []}', b'{"value": NaN}',
                      b'"\xff"', b'{"private-client-text":', b'[' * 2000]
        for data in bad_values:
            files = self.files | {"resources/search.json": data}
            with self.subTest(data=data[:30]):
                self.assert_invalid(files)
                self.write_profile(files)
                report = contract.validation_report(contract.validate_profile_directory(self.profile, "focus"))
                self.assertFalse(report["valid"])
                self.assertNotIn("private-client-text", json.dumps(report))
        files = self.files | {"resources/research.md": b"\xff"}
        self.assert_invalid(files, "invalid_utf8")

    def test_paths_are_bounded_and_nonexecutable(self):
        manifest = json.loads(self.files["profile.json"])
        for path in ("/tmp/x.md", "../x.md", "a/../x.md", "a//x.md", "./x.md", "a\\x.md", "x.py"):
            resources = manifest["resources"] | {"research": path}
            with self.subTest(path=path):
                self.assert_invalid(self.manifest_edit(resources=resources), "unsafe_resource_path")

    def test_symlinks_hardlinks_and_executable_modes_fail(self):
        target = self.profile / "resources/research.md"
        saved = target.read_bytes()
        external = self.root / "external.md"
        external.write_bytes(saved)
        target.unlink()
        target.symlink_to(external)
        self.assertIsNone(contract.validate_profile_directory(self.profile, "focus").draft)
        target.unlink()
        os.link(external, target)
        self.assertIsNone(contract.validate_profile_directory(self.profile, "focus").draft)
        target.unlink()
        target.write_bytes(saved)
        target.chmod(0o700)
        result = contract.validate_profile_directory(self.profile, "focus")
        self.assertEqual(result.issues[0].code, "executable_resource")

    def test_symlink_directory_and_root_fail(self):
        resources = self.profile / "resources"
        moved = self.root / "moved"
        resources.rename(moved)
        resources.symlink_to(moved, target_is_directory=True)
        self.assertIsNone(contract.validate_profile_directory(self.profile, "focus").draft)
        link = self.root / "link"
        link.symlink_to(self.profile, target_is_directory=True)
        self.assertIsNone(contract.validate_profile_directory(link, "focus").draft)

    def test_fifo_is_rejected_without_blocking(self):
        target = self.profile / "resources/research.md"
        target.unlink()
        os.mkfifo(target)
        result = contract.validate_profile_directory(self.profile, "focus")
        self.assertEqual(result.issues[0].code, "not_regular_private_file")

    def test_size_bounds(self):
        files = self.files | {"resources/research.md": b"x" * (contract.MAX_FILE_BYTES + 1)}
        self.assert_invalid(files, "file_too_large")
        self.write_profile(files)
        self.assertIsNone(contract.validate_profile_directory(self.profile, "focus").draft)
        with patch.object(contract, "MAX_TOTAL_BYTES", 10):
            self.assert_invalid(self.files, "profile_too_large")

    def test_invalid_structured_data(self):
        base = synthetic_files("recordprep")
        cases = {
            "hearings": [{"id": "x", "title": "X", "guidance": "Guide"}] * 2,
            "roles": {"counsel": [], "participants": []},
            "policies": {"report_scope": "run_shell", "attendance": "explicit_complete_order"},
            "naming": {"mode": "regex", "report_titles": [], "form_titles": [], "guidance": "Guide"},
        }
        for name, value in cases.items():
            with self.subTest(name=name):
                self.assert_invalid(base | {f"resources/{name}.json": contract.json_bytes(value)}, app="recordprep")
        files = self.files | {"resources/search.json": contract.json_bytes(
            {"query_terms": ["same", "SAME"], "document_terms": [], "passage_terms": [], "later_history_terms": []})}
        self.assert_invalid(files, "duplicate_term")

    def test_acceptance_roundtrip_is_private_and_explicit(self):
        self.assertFalse(self.store.config_root.exists())
        self.assertEqual(self.store.read_registry()["accepted"], [])
        self.assertFalse(self.store.config_root.exists())
        draft = self.draft()
        with self.assertRaises(contract.ProfileError):
            self.store.load_profile_snapshot(draft.ref)
        ref = self.store.accept_profile(draft, expected_previous_digest=None, source_path=self.profile)
        self.assertEqual(self.store.load_profile_snapshot(ref), draft)
        self.assertIsNone(self.store.read_registry()["default"])
        self.store.set_default(ref)
        self.assertEqual(self.store.read_registry()["default"], dataclasses.asdict(ref))
        for base in (self.store.config_root, self.store.data_root):
            for path in (base, *base.rglob("*")):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700 if path.is_dir() else 0o600)

    def test_nested_snapshot_directories_are_private(self):
        files = self.files.copy()
        manifest = json.loads(files["profile.json"])
        manifest["resources"]["research"] = "a/b/c/research.md"
        files["a/b/c/research.md"] = files.pop("resources/research.md")
        files["profile.json"] = contract.json_bytes(manifest)
        draft = self.draft(files)
        ref = self.store.accept_profile(draft, expected_previous_digest=None)
        self.assertEqual(self.store.load_profile_snapshot(ref), draft)

    def test_external_edit_does_not_change_accepted_revision(self):
        draft = self.draft()
        ref = self.store.accept_profile(draft, expected_previous_digest=None)
        (self.profile / "resources/research.md").write_text("Edited externally.")
        self.assertEqual(self.store.load_profile_snapshot(ref), draft)
        self.assertNotEqual(contract.validate_profile_directory(self.profile, "focus").draft.ref, ref)

    def test_stale_save_and_old_snapshot_retention(self):
        old = self.draft()
        self.store.accept_profile(old, expected_previous_digest=None)
        self.store.set_default(old.ref)
        new = self.draft(self.files | {"resources/research.md": b"New guidance."})
        with self.assertRaisesRegex(contract.ProfileError, "stale_profile_revision"):
            self.store.accept_profile(new, expected_previous_digest=None)
        self.store.accept_profile(new, expected_previous_digest=old.ref.content_sha256)
        self.assertEqual(self.store.load_profile_snapshot(old.ref), old)
        self.assertEqual(self.store.load_profile_snapshot(new.ref), new)
        self.assertEqual(self.store.read_registry()["default"], dataclasses.asdict(old.ref))

    def test_snapshot_corruption_fails_without_replacement(self):
        draft = self.draft()
        self.store.accept_profile(draft, expected_previous_digest=None)
        resource = self.store.data_root / "snapshots" / draft.ref.content_sha256 / "resources/research.md"
        resource.write_bytes(b"corrupted")
        with self.assertRaisesRegex(contract.ProfileError, "snapshot_hash_mismatch"):
            self.store.load_profile_snapshot(draft.ref)
        with self.assertRaises(contract.ProfileError):
            self.store.accept_profile(draft, expected_previous_digest=draft.ref.content_sha256)
        self.assertEqual(resource.read_bytes(), b"corrupted")

    def test_registry_corruption_never_resets(self):
        self.store.accept_profile(self.draft(), expected_previous_digest=None)
        self.store.registry_path.write_bytes(b"{broken")
        with self.assertRaises(contract.ProfileError):
            self.store.accept_profile(self.draft(), expected_previous_digest=None)
        self.assertEqual(self.store.registry_path.read_bytes(), b"{broken")

    def test_interrupted_acceptance_never_authorizes_snapshot(self):
        draft = self.draft()
        module = __import__(ProfileStore.__module__, fromlist=["_atomic_json"])
        with patch.object(module, "_atomic_json", side_effect=OSError("synthetic failure")):
            with self.assertRaises(OSError):
                self.store.accept_profile(draft, expected_previous_digest=None)
        self.assertEqual(self.store.read_registry()["accepted"], [])
        with self.assertRaisesRegex(contract.ProfileError, "unaccepted_reference"):
            self.store.load_profile_snapshot(draft.ref)
        self.store.accept_profile(draft, expected_previous_digest=None)
        self.assertEqual(self.store.load_profile_snapshot(draft.ref), draft)

    def test_untrusted_reference_and_forged_draft_fail(self):
        draft = self.draft()
        malicious = dataclasses.replace(draft.ref, content_sha256="../../escape")
        with self.assertRaises(contract.ProfileError):
            self.store.load_profile_snapshot(malicious)
        forged = dataclasses.replace(draft, ref=dataclasses.replace(draft.ref, specialty_id="forged"))
        with self.assertRaises(contract.ProfileError):
            self.store.accept_profile(forged, expected_previous_digest=None)
        self.assertFalse(self.store.config_root.exists())

    def test_store_symlink_and_permissions_fail(self):
        outside = self.root / "outside"
        outside.mkdir(mode=0o700)
        self.store.config_root.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(contract.ProfileError):
            self.store.accept_profile(self.draft(), expected_previous_digest=None)
        self.assertEqual(list(outside.iterdir()), [])
        self.store.config_root.unlink()
        self.store.config_root.mkdir(mode=0o755)
        with self.assertRaises(contract.ProfileError):
            self.store.accept_profile(self.draft(), expected_previous_digest=None)

    def test_compilation_is_scoped_and_includes_core(self):
        files = synthetic_files("recordprep")
        original = self.draft(files, "recordprep")
        def compile(draft, stage="report_extraction", core=b"core-v1"):
            return contract.compile_stage_profile(draft, stage, core_contract=core)
        before = compile(original)
        changed = files | {"resources/hearing_synthesis.md": b"Changed hearing synthesis."}
        after = self.draft(changed, "recordprep")
        self.assertNotEqual(original.ref, after.ref)
        self.assertEqual(before.component_sha256, compile(after).component_sha256)
        self.assertNotEqual(before.component_sha256, compile(original, core=b"core-v2").component_sha256)
        policies = json.loads(files["resources/policies.json"])
        policies["attendance"] = "legacy_first_page_parents"
        policy_change = self.draft(files | {"resources/policies.json": contract.json_bytes(policies)}, "recordprep")
        self.assertEqual(before.component_sha256, compile(policy_change).component_sha256)
        self.assertNotEqual(compile(original, "minutes").component_sha256,
                            compile(policy_change, "minutes").component_sha256)
        with self.assertRaises(contract.ProfileError):
            compile(original, "shell")
        with self.assertRaises(contract.ProfileError):
            compile(original, core=b"")

    def test_identity_exchange_contains_no_resources_or_paths(self):
        descriptor = contract.identity_descriptor(self.draft())
        value = contract.parse_identity_descriptor(descriptor)
        self.assertEqual(set(value), {"schema_version", "specialty_id", "display_name", "description"})
        self.assertEqual(value["specialty_id"], "synthetic-employment")
        for extra in ("instructions", "path", "application", "command"):
            with self.assertRaises(contract.ProfileError):
                contract.parse_identity_descriptor(contract.json_bytes(value | {extra: "not allowed"}))
        with self.assertRaises(contract.ProfileError):
            contract.parse_identity_descriptor(contract.json_bytes(value | {"schema_version": True}))

    def test_cli_is_read_only_and_does_not_import_gui(self):
        module_name = api.APPLICATION
        modules_before = set(__import__("sys").modules)
        cli = __import__(f"{module_name}.cli", fromlist=["main"])
        self.write_profile(synthetic_files(module_name))
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.root / "xdg-config"),
                                     "XDG_DATA_HOME": str(self.root / "xdg-data")}):
            output = io.StringIO()
            with redirect_stdout(output):
                status = cli.main(["profiles", "validate", str(self.profile), "--json"])
            self.assertEqual(status, 0)
            self.assertTrue(json.loads(output.getvalue())["valid"])
            self.assertFalse((self.root / "xdg-config").exists())
            self.assertFalse((self.root / "xdg-data").exists())
            newly_imported = set(__import__("sys").modules) - modules_before
            self.assertNotIn(f"{module_name}.app", newly_imported)
            self.assertNotIn("gi", newly_imported)
            output = io.StringIO()
            with redirect_stdout(output):
                status = cli.main(["profiles", "validate", str(self.root / "missing"), "--json"])
            self.assertEqual(status, 1)
            self.assertFalse(json.loads(output.getvalue())["valid"])

    def test_concurrent_accepts_only_one_winner(self):
        import threading
        barrier = threading.Barrier(2)
        one = self.draft()
        two = self.draft(self.files | {"resources/research.md": b"Different revision."})
        # Provision the roots so the test exercises CAS rather than first-mkdir races.
        self.store.config_root.mkdir(mode=0o700)
        def accept(draft):
            barrier.wait(timeout=5)
            try:
                return self.store.accept_profile(draft, expected_previous_digest=None)
            except contract.ProfileError as exc:
                return exc.issue.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(accept, (one, two)))
        self.assertEqual(sum(isinstance(value, contract.ProfileRef) for value in outcomes), 1)
        self.assertIn("stale_profile_revision", outcomes)
        self.assertEqual(len(self.store.read_registry()["accepted"]), 1)

    def test_two_profiles_and_two_stores_do_not_contaminate(self):
        one = self.draft()
        two = self.draft(self.manifest_edit(specialty_id="another-specialty"))
        self.store.accept_profile(one, expected_previous_digest=None)
        self.store.accept_profile(two, expected_previous_digest=None)
        prep = ProfileStore("recordprep", config_root=self.root / "prep-config", data_root=self.root / "prep-data")
        prep_draft = self.draft(synthetic_files("recordprep"), "recordprep")
        prep.accept_profile(prep_draft, expected_previous_digest=None)
        prep.set_default(prep_draft.ref)
        self.assertIsNone(self.store.read_registry()["default"])
        self.assertEqual(self.store.load_profile_snapshot(one.ref), one)
        self.assertEqual(self.store.load_profile_snapshot(two.ref), two)
        with self.assertRaises(contract.ProfileError):
            prep.load_profile_snapshot(one.ref)

    def test_concurrent_source_edit_is_rejected(self):
        reader = contract.read_file_at
        reads = 0
        def changing_reader(fd, relative, **kwargs):
            nonlocal reads
            reads += 1
            if reads == 5:
                (self.profile / "resources/research.md").write_text("Changed during read.")
            return reader(fd, relative, **kwargs)
        with patch.object(contract, "read_file_at", side_effect=changing_reader):
            result = contract.validate_profile_directory(self.profile, "focus")
        self.assertEqual(result.issues[0].code, "concurrent_edit")

    def test_bundled_profiles_validate_and_do_not_activate(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.root / "c"), "XDG_DATA_HOME": str(self.root / "d")}):
            for name in api.BUNDLED_PROFILES:
                with self.subTest(name=name):
                    result = api.validate_profile_directory(api.bundled_profile_directory(name))
                    self.assertEqual(result.issues, ())
                    self.assertEqual(result.draft.ref.application, api.APPLICATION)
                    for stage in contract.STAGE_RESOURCES[api.APPLICATION]:
                        compiled = contract.compile_stage_profile(result.draft, stage, core_contract=b"synthetic core")
                        self.assertTrue(compiled.resources)
            self.assertFalse((self.root / "c").exists())
            self.assertFalse((self.root / "d").exists())
        with self.assertRaises(contract.ProfileError):
            api.bundled_profile_directory("../escape")

    def test_package_resources_work_without_sibling_checkout(self):
        standalone = self.root / "standalone"
        standalone.mkdir()
        source = Path(api.__file__).parent
        shutil.copytree(source, standalone / api.APPLICATION, ignore=shutil.ignore_patterns("__pycache__"))
        script = ("import pathlib,sys; from " + api.APPLICATION + " import practice_profiles as p; "
                  "assert pathlib.Path(p.__file__).is_relative_to(pathlib.Path.cwd()); "
                  "assert all(p.validate_profile_directory(p.bundled_profile_directory(n)).draft "
                  "for n in p.BUNDLED_PROFILES); assert 'gi' not in sys.modules")
        result = subprocess.run([sys.executable, "-c", script], cwd=standalone,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        other = "recordprep" if api.APPLICATION == "focus" else "focus"
        self.assertFalse((standalone / other).exists())

    def test_golden_common_contract(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/practice_profiles/conformance-v1.json").read_text())
        for app, expected in fixture["synthetic_profile_digests"].items():
            self.assertEqual(self.draft(synthetic_files(app), app).ref.content_sha256, expected)

    def test_xdg_storage_is_application_owned(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.root / "c"), "XDG_DATA_HOME": str(self.root / "d")}):
            store = api.profile_store()
            self.assertEqual(store.application, api.APPLICATION)
            self.assertEqual(store.config_root, self.root / "c" / api.APPLICATION / "practice-profiles")
            self.assertFalse(store.config_root.exists())


if __name__ == "__main__":
    unittest.main()
