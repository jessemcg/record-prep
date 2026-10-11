import json
import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from recordprep import summary_agents as sa
from recordprep.case_profiles import apply_case_profile, read_case_profile_ref, resolve_case_profile
from recordprep.practice_profiles import bundled_profile_directory, validate_profile_directory
from recordprep.profile_contract import json_bytes, validate_contents, ProfileError
from recordprep.profile_store import ProfileStore
from recordprep.summary_profiles import compile_summary


def bundled(name):
    result = validate_profile_directory(bundled_profile_directory(name))
    assert result.draft is not None
    return result.draft


def changed(snapshot, resource, value):
    files = dict(snapshot.files)
    files[snapshot.manifest["resources"][resource]] = value.encode() if isinstance(value, str) else json_bytes(value)
    return validate_contents(tuple(files.items()), "recordprep")


def seed_profile_preparation(root, profile, project_dir):
    """Offline upstream fixtures; the GUI-worker tests cover actual classification."""
    from recordprep.classification_profiles import ClassificationRun, STAGES, output_names, load_model_settings
    from recordprep.boundary_profiles import boundary_inputs, publish_boundaries, FILES
    from recordprep.transcript_layout import read_resolved_layout, apply_manual_override
    prior = read_resolved_layout(root) or {"mode": "ct_only"}
    images = root / "image_pages"
    images.mkdir(exist_ok=True)
    paths = sorted((root / "text_pages").glob("*.txt"))
    for path in paths:
        (images / (path.stem + ".png")).write_bytes(b"synthetic upstream image")
    apply_manual_override(root, mode=prior["mode"], rt_end_file_page=prior.get("rt_end_file_page"))
    payloads = {name: json.loads((root / "artifacts" / name).read_text()) if (root / "artifacts" / name).exists() else [] for name in FILES}
    settings = load_model_settings(project_dir)
    for stage in STAGES:
        run = ClassificationRun.begin(root, stage, settings)
        for kind, name in zip(("RT", "CT"), output_names(stage)):
            rows = [{"file_name": path.name, "page_type": "RT_body" if kind == "RT" else "CT_report"}
                    for path in paths if (kind == "RT") == (prior["mode"] == "rt_only")]
            if rows:
                (run.directory / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
        run.publish(settings)
    expected = boundary_inputs(root, profile, settings)
    publish_boundaries(root, profile, expected, settings, payloads)


class ProfileGenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "artifacts").mkdir()
        (self.root / "text_pages").mkdir()
        (self.root / "case_name.txt").write_text("Synthetic")
        (self.root / "artifacts/report_boundaries.json").write_text(json.dumps([
            {"start_page": 1, "end_page": 2, "report_name": "Synthetic Report"}]))
        (self.root / "text_pages/0001.txt").write_text("The author described disputed facts.")
        (self.root / "text_pages/0002.txt").write_text("PROPOSED FINDINGS AND ORDERS\nThe court is asked to grant relief.")

    def test_profiles_have_independent_categories_and_scope(self):
        configs = [sa.ExtractionConfig("reports", "ignored legacy text", profile=bundled(name))
                   for name in ("general", "california_dependency")]
        general, dependency = [sa.build_work_items(self.root, config)[0] for config in configs]
        self.assertIsNone(general.proposal_marker)
        self.assertIsNotNone(dependency.proposal_marker)
        self.assertNotIn("ignored legacy text", configs[0].guidance)
        self.assertEqual(len(configs[0].definitions), 7)
        self.assertEqual(len(configs[1].definitions), 12)
        self.assertEqual(len(configs[0].definitions), 7)
        for config, item in zip(configs, (general, dependency)):
            row = sa.canonicalize_extraction_candidate({}, item, self.root / "text_pages")
            self.assertEqual(row["schema_version"], 3)
            self.assertEqual([r["id"] for r in row["categories"]], [d.identifier for d in config.definitions])
            self.assertEqual(sa.validate_digest_row(row), [])

    def test_custom_categories_publish_and_reload_without_global_mutation(self):
        profile = changed(bundled("general"), "reports", [{"id": "custom_issue", "title": "Custom Issue", "guidance": "Material issues only."}])
        config = sa.ExtractionConfig("reports", "", profile=profile)
        items = sa.build_work_items(self.root, config)
        row = sa.canonicalize_extraction_candidate({"categories": [{"id": "custom_issue", "digest": {
            "text": "Relief was proposed, not ordered.", "evidence": [{"text": "grant relief", "file_page": 2}]}}]},
            items[0], self.root / "text_pages")
        meta = sa.publish_digests(self.root, "reports", items, config, [row])
        self.assertTrue(meta["complete"])
        self.assertEqual(meta["schema_version"], 5)
        self.assertEqual(sa.load_digest_markdown(self.root, "reports"), [row])
        self.assertEqual(len(sa.SUMMARY_CATEGORY_IDS["reports"]), 12)
        # Unrelated hearing guidance does not stale report work or require model calls.
        revised = changed(profile, "hearing_extraction", "New hearing-only instructions.")
        newconfig = sa.ExtractionConfig("reports", "", profile=revised)
        self.assertEqual(config.fingerprint, newconfig.fingerprint)
        newitems = sa.build_work_items(self.root, newconfig)
        self.assertEqual(items[0].generation_sha256, newitems[0].generation_sha256)
        self.assertTrue(sa.publish_digests(self.root, "reports", newitems, newconfig, [row])["complete"])
        self.assertEqual(sa.load_digest_markdown(self.root, "reports")[0]["profile_metadata"]["profile_provenance"]["profile_ref"]["content_sha256"], revised.ref.content_sha256)

    def test_gui_generated_category_ids_keep_canonical_quote_roundtrips(self):
        identifier = "item-ae631c0cda6c4f408cb0e675165d62c7"
        profile = changed(bundled("general"), "reports", [{"id": identifier, "title": "Custom Issue", "guidance": "Material issues."}])
        config = sa.ExtractionConfig("reports", "", profile=profile)
        items = sa.build_work_items(self.root, config)
        row = sa.canonicalize_extraction_candidate({"categories": [{"id": identifier, "digest": {
            "text": "The author described disputed facts.", "evidence": [{"text": "disputed facts", "file_page": 1}]}}]},
            items[0], self.root / "text_pages")
        sa.publish_digests(self.root, "reports", items, config, [row])
        self.assertEqual(sa.load_digest_markdown(self.root, "reports"), [row])

    def test_empty_profile_document_and_changed_components(self):
        profile = bundled("general")
        config = sa.ExtractionConfig("reports", "", profile=profile)
        (self.root / "artifacts/report_boundaries.json").write_text("[]")
        meta = sa.publish_digests(self.root, "reports", [], config, [])
        parsed = sa.load_digest_markdown(self.root, "reports")
        self.assertEqual(parsed, [])
        self.assertIsNotNone(parsed.profile_metadata)
        self.assertTrue(meta["complete"])
        revised = changed(profile, "report_extraction", "Changed report salience.")
        self.assertNotEqual(config.fingerprint, sa.ExtractionConfig("reports", "", profile=revised).fingerprint)
        self.assertEqual(compile_summary(profile, "hearings", "extract").component_sha256,
                         compile_summary(revised, "hearings", "extract").component_sha256)

    def test_actual_runner_uses_pinned_profile_and_resumes_without_calls(self):
        source = Path(__file__).resolve().parents[1]
        project = self.root / "project"
        shutil.copytree(source / ".pi", project / ".pi")
        (project / "config.json").write_text("{}")
        spec = importlib.util.spec_from_file_location("profile_generation_runner", project / ".pi/scripts/run_recordprep_skill.py")
        runner = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = runner
        spec.loader.exec_module(runner)
        store = ProfileStore("recordprep", config_root=self.root / "config", data_root=self.root / "data")
        profile = bundled("general")
        store.accept_profile(profile, expected_previous_digest=None)
        apply_case_profile(self.root, profile.ref, expected_previous=None, store=store)
        stage = runner.SkillStage("create_report_summaries", "Create report summaries", "recordprep-extract-report", "")
        with patch("recordprep.case_profiles.profile_store", return_value=store), \
             patch.object(runner, "_resolve_pi_command", return_value=["synthetic-pi"]), \
             patch.object(runner, "_check_pi_version"), \
             patch("recordprep.summary_preflight.pi_runtime.available_pi_models", return_value=[]), \
             patch.object(runner, "_stage_capacity", return_value=None), \
             patch.object(runner, "_report_capacity"), \
             patch.object(runner, "_run_extraction_child", return_value={"categories": []}) as extract, \
             patch.object(runner, "_run_synthesis_child", return_value=([], [])) as synthesize:
            seed_profile_preparation(self.root, profile, project / ".pi")
            self.assertEqual(runner._run_summary_stage(stage, self.root, project / ".pi"), 0)
            self.assertEqual(extract.call_count, 1)
            self.assertEqual(synthesize.call_count, 1)
            self.assertEqual(sa.validate_summary_agent_outputs(self.root, "reports"), [])
            self.assertEqual(sa.summary_stage_freshness_issues(self.root, "reports", project_dir=project / ".pi"), [])
            self.assertEqual(runner._run_summary_stage(stage, self.root, project / ".pi"), 0)
            self.assertEqual(extract.call_count, 1)
            self.assertEqual(synthesize.call_count, 1)
            # Unchanged boundary bytes are not proof that upstream classification
            # is current under a newly selected practice guide.
            revised = changed(profile, "classification", "Revised source-grounded classification guidance.\n")
            store.accept_profile(revised, expected_previous_digest=profile.ref.content_sha256)
            apply_case_profile(self.root, revised.ref, expected_previous=profile.ref, store=store)
            old_final = sa.summary_final_path(self.root, "reports").read_bytes()
            with self.assertRaisesRegex(ValueError, "classification/naming"):
                runner._run_summary_stage(stage, self.root, project / ".pi")
            self.assertEqual(extract.call_count, 1)
            self.assertEqual(synthesize.call_count, 1)
            self.assertEqual(sa.summary_final_path(self.root, "reports").read_bytes(), old_final)
            from recordprep.summary_preflight import collect_kind_report
            diagnostic = collect_kind_report(root=self.root, kind="reports", project_dir=project / ".pi",
                                             extract_capacity=None, synthesize_capacity=None)
            self.assertIn("classification/naming", diagnostic["error"])
            self.assertTrue(sa.summary_stage_freshness_issues(self.root, "reports", project_dir=project / ".pi"))

    def test_profile_minute_policies_and_actual_resume(self):
        from recordprep import minute_summaries as minutes
        profile = bundled("general")
        (self.root / "text_pages/0002.txt").write_text("Synthetic Plaintiff appeared in person. Motion denied.")
        (self.root / "artifacts/minutes_boundaries.json").write_text(json.dumps([{"start_page": 1, "end_page": 2}]))
        project = self.root / "minute-project"
        shutil.copytree(Path(__file__).resolve().parents[1] / ".pi", project / ".pi")
        (project / "config.json").write_text("{}")
        _, config = minutes.stage_config(project / ".pi", profile=profile)
        item = minutes.build_items(self.root, config)[0]
        candidate = {"artifact": "recordprep-minute-candidate", "hearing": "Review", "reporting": "reported",
                     "orders": "Motion denied.", "appearances": [{"person": "Synthetic Plaintiff", "role_id": "plaintiff",
                     "status": "present", "evidence": [{"file_page": 2, "text": "Plaintiff appeared in person"}]}]}
        self.assertEqual(minutes.normalize_candidate(candidate, item, profile=profile)["appearances"][0]["status"], "present")
        first_only = changed(profile, "policies", profile.resource("policies") | {"attendance": "legacy_first_page_parents"})
        self.assertEqual(minutes.normalize_candidate(candidate, item, profile=first_only)["appearances"][0]["status"], "unclear")
        store = ProfileStore("recordprep", config_root=self.root / "config", data_root=self.root / "data")
        store.accept_profile(profile, expected_previous_digest=None)
        apply_case_profile(self.root, profile.ref, expected_previous=None, store=store)
        calls = []
        def generate(*args):
            calls.append(1)
            return candidate
        with patch("recordprep.case_profiles.profile_store", return_value=store):
            seed_profile_preparation(self.root, profile, project / ".pi")
            minutes.run_stage(self.root, project / ".pi", generate)
            self.assertEqual(len(calls), 1)
            self.assertEqual(minutes.freshness_issues(self.root, project / ".pi"), [])
            self.assertNotIn("Parent", sa.summary_final_path(self.root, "minutes").read_text())
            self.assertEqual(json.loads(minutes.checkpoint_path(self.root).read_text())["schema_version"], 2)
            minutes.run_stage(self.root, project / ".pi", generate)
            self.assertEqual(len(calls), 1)
            revised = changed(profile, "report_extraction", "Unrelated report changes.")
            store.accept_profile(revised, expected_previous_digest=profile.ref.content_sha256)
            apply_case_profile(self.root, revised.ref, expected_previous=profile.ref, store=store)
            minutes.run_stage(self.root, project / ".pi", generate)
            self.assertEqual(len(calls), 1)

    def test_publication_serializes_against_case_binding_changes(self):
        import threading
        from recordprep.case_profiles import case_profile_publication
        general, dependency = bundled("general"), bundled("california_dependency")
        store = ProfileStore("recordprep", config_root=self.root / "config", data_root=self.root / "data")
        for profile in (general, dependency):
            store.accept_profile(profile, expected_previous_digest=None)
        apply_case_profile(self.root, general.ref, expected_previous=None, store=store)
        started, finished = threading.Event(), threading.Event()
        errors = []
        def change():
            started.set()
            try:
                apply_case_profile(self.root, dependency.ref, expected_previous=general.ref, store=store)
            except Exception as exc:
                errors.append(exc)
            finally:
                finished.set()
        with case_profile_publication(self.root, general.ref):
            thread = threading.Thread(target=change)
            thread.start()
            self.assertTrue(started.wait(1))
            self.assertFalse(finished.wait(0.05))
            self.assertEqual(read_case_profile_ref(self.root), general.ref)
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(read_case_profile_ref(self.root), dependency.ref)
        with self.assertRaises(ProfileError):
            with case_profile_publication(self.root, general.ref):
                self.fail("Stale publisher must never enter the publication section.")

    def test_case_binding_is_explicit_private_and_compare_and_swap(self):
        store = ProfileStore("recordprep", config_root=self.root / "config", data_root=self.root / "data")
        profile = bundled("general")
        self.assertIsNone(read_case_profile_ref(self.root))
        self.assertFalse((self.root / ".recordprep").exists())
        with self.assertRaises(ProfileError):
            apply_case_profile(self.root, profile.ref, expected_previous=None, store=store)
        self.assertFalse((self.root / ".recordprep").exists())
        store.accept_profile(profile, expected_previous_digest=None)
        apply_case_profile(self.root, profile.ref, expected_previous=None, store=store)
        self.assertEqual(resolve_case_profile(self.root, store=store), profile)
        revised = changed(profile, "report_extraction", "New accepted revision.")
        store.accept_profile(revised, expected_previous_digest=profile.ref.content_sha256)
        store.set_default(revised.ref)
        self.assertEqual(resolve_case_profile(self.root, store=store), profile)
        with self.assertRaises(ProfileError):
            apply_case_profile(self.root, revised.ref, expected_previous=None, store=store)
        apply_case_profile(self.root, revised.ref, expected_previous=profile.ref, store=store)
        self.assertEqual(resolve_case_profile(self.root, store=store), revised)
        self.assertEqual((self.root / ".recordprep/practice-profile.json").stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.root / "artifacts/practice_profile_provenance.json").exists())


if __name__ == "__main__":
    unittest.main()
