import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from recordprep import minute_summaries as minutes, pi_bundle, summary_agents as sa
from recordprep.profile_artifacts import participant_index_issues
from summary_agent_fixtures import synthetic_facts_row, write_facts_bundle, write_final_summary
from test_profile_artifacts import participant, provenance, roles


def metadata():
    return {"category_catalog": [{"id": "custom_relief", "title": "Relief <proposed>"}],
            "profile_provenance": provenance("report_extraction")}


def row():
    result = synthetic_facts_row("reports")
    result.update(schema_version=3, profile_metadata=metadata(),
                  categories=[{"id": "custom_relief", "digest": {"text": "Synthetic request, not an order.", "evidence": []}}])
    return result


class ProfileArtifactReaderTests(unittest.TestCase):
    def test_digest_new_roundtrip_without_profile_or_guidance_files(self):
        value = row()
        with patch.object(sa, "summary_category_definitions", side_effect=AssertionError("Must use recorded categories")):
            text = sa.serialize_digest_markdown("reports", "synthetic", [value])
            parsed = sa.parse_digest_markdown(text, "reports", "synthetic")
            self.assertEqual(parsed, [value])
            self.assertEqual(sa.serialize_digest_markdown("reports", "synthetic", parsed), text)
            self.assertIn("custom_relief", sa.document_markdown_block(parsed[0]))
            self.assertNotIn("profile_provenance", sa.document_markdown_block(parsed[0]))
            self.assertEqual(sa.validate_digest_row(parsed[0]), [])

    def test_empty_profile_digest_keeps_header(self):
        text = sa.serialize_digest_markdown("reports", "synthetic", [], profile_metadata=metadata())
        parsed = sa.parse_digest_markdown(text, "reports", "synthetic")
        self.assertEqual(parsed, [])
        self.assertEqual(parsed.profile_metadata, metadata())
        self.assertEqual(sa.serialize_digest_markdown("reports", "synthetic", parsed), text)

    def test_legacy_roundtrip_is_independent_of_new_categories(self):
        legacy = synthetic_facts_row("reports")
        original = sa.serialize_digest_markdown("reports", "synthetic", [legacy])
        sa.serialize_digest_markdown("reports", "synthetic", [row()])
        with patch.object(sa, "summary_category_definitions", side_effect=AssertionError("No guidance required for reads")):
            self.assertEqual(sa.parse_digest_markdown(original, "reports", "synthetic"), [legacy])
            self.assertEqual(sa.serialize_digest_markdown("reports", "synthetic", [legacy]), original)

    def test_reject_mixed_and_future_descriptors(self):
        current = row()
        other = copy.deepcopy(current)
        other["profile_metadata"]["category_catalog"][0]["title"] = "Changed"
        with self.assertRaises(ValueError):
            sa.serialize_digest_markdown("reports", "synthetic", [current, other])
        for mutate in (lambda r: r.update(schema_version=4),
                       lambda r: r["profile_metadata"]["category_catalog"][0].update(guidance="private instructions"),
                       lambda r: r.update(schema_version=2),
                       lambda r: r["categories"][0].update(id="other_category")):
            value = row()
            mutate(value)
            self.assertTrue(sa.validate_digest_row(value))
        text = sa.serialize_digest_markdown("reports", "synthetic", [current])
        with self.assertRaises(ValueError):
            sa.parse_digest_markdown(text.replace('"format_version": 2', '"format_version": 99'), "reports", "synthetic")

    def test_metadata_five_integrity_is_not_legacy_freshness(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "case_name.txt").write_text("synthetic")
            rows = [row()]
            write_facts_bundle(root, "reports", rows)
            write_final_summary(root, "reports", rows, "Synthetic summary.\n", synthesis_config={})
            path = sa.summary_digest_meta_path(root, "reports")
            meta = json.loads(path.read_text())
            meta.update(schema_version=5, markdown_format_version=2, profile_metadata=metadata())
            path.write_text(json.dumps(meta))
            path = sa.summary_final_meta_path(root, "reports")
            final = json.loads(path.read_text())
            final.update(schema_version=5, markdown_format_version=2, profile_provenance=provenance("report_synthesis"))
            path.write_text(json.dumps(final))
            self.assertEqual(sa.validate_summary_agent_outputs(root, "reports"), [])
            with self.assertRaises(ValueError):
                sa.publish_digests(root, "reports", [], sa.ExtractionConfig("reports", "synthetic"), [])
            with patch.object(sa, "effective_extraction_config", side_effect=AssertionError("No live config")):
                self.assertTrue(sa.summary_stage_freshness_issues(root, "reports"))
            with self.assertRaises(ValueError):
                sa.build_work_items(root, sa.ExtractionConfig("reports", "synthetic"))
            final["profile_provenance"]["components"] = {}
            path.write_text(json.dumps(final))
            self.assertTrue(sa.validate_summary_agent_outputs(root, "reports"))

    def test_generic_minutes_read_without_parent_language_or_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "case_name.txt").write_text("synthetic")
            value = {"item_id": "minute:0001", "fingerprint": "a" * 64, "hearing": "Civil Review",
                     "reporting": "reported", "appearances": [{"person": "Synthetic Plaintiff", "role_id": "plaintiff",
                     "status": "present", "evidence": [{"file_page": 2, "text": "Plaintiff appeared."}]}],
                     "orders": "Motion denied.", "quality_flags": []}
            payload = {"artifact": "recordprep-minute-rows", "schema_version": 2, "rows": [value],
                       "rows_sha256": sa.sha256_json([value]), "attendance_policy": "explicit_complete_order",
                       "role_catalog": roles(), "profile_provenance": provenance("minutes")}
            path = minutes.checkpoint_path(root)
            path.parent.mkdir()
            path.write_text(json.dumps(payload))
            before = path.read_bytes()
            self.assertEqual(minutes.load_rows(root), [value])
            self.assertEqual(path.read_bytes(), before)
            self.assertNotIn("Parent", minutes.render_paragraph(value))
            self.assertIn("Synthetic Plaintiff appeared.", minutes.render_paragraph(value))
            self.assertIn("Appearances unclear.", minutes.render_paragraph(value | {"appearances": []}))
            with self.assertRaises(ValueError):
                minutes.run_stage(root, root / ".pi", lambda *args: self.fail("No model call"))
            with self.assertRaises(ValueError):
                minutes.publish_rows(root, [])
            self.assertEqual(path.read_bytes(), before)
            value["appearances"][0]["evidence"] = []
            payload["rows_sha256"] = sa.sha256_json([value])
            path.write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                minutes.load_rows(root)

    def test_legacy_publishers_cannot_downgrade_new_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(ValueError):
                sa.publish_digests(root, "reports", [], sa.ExtractionConfig("reports", "synthetic"), [row()])
            with self.assertRaises(ValueError):
                minutes.publish_rows(root, [{"appearances": []}])
            self.assertEqual(list(root.iterdir()), [])

    def test_legacy_participant_validator_parity_and_modern_dispatch(self):
        value = participant()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "artifacts").mkdir()
            path = root / "artifacts/participant_index.json"
            path.write_text(json.dumps(value))
            self.assertEqual(pi_bundle.validate_participant_index_output(root), [])
        value.update(schema_version=2)
        del value["role_catalog"], value["profile_provenance"]
        self.assertEqual(participant_index_issues(value), pi_bundle._legacy_participant_index_issues(value))
        value["hearings"][0]["participants"][0]["role_id"] = "mother"
        value["hearings"][0]["counsel"][0]["role_id"] = "mothers_counsel"
        self.assertEqual(participant_index_issues(value), pi_bundle._legacy_participant_index_issues(value))


if __name__ == "__main__":
    unittest.main()
