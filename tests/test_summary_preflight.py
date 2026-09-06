"""Tests for model-identity resolution and capacity accounting.

All fixtures are synthetic; no paid calls are made and no real case
material appears here.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from recordprep import pi_runtime
from recordprep import summary_preflight as sp

PROJECT_DIR = Path(__file__).resolve().parents[1]


def _capacity(
    *,
    provider: str = "fireworks",
    model_id: str = "accounts/fireworks/models/glm-5p3-flash",
    context_window: int | None = 1_000_000,
) -> sp.StageCapacity:
    identity = sp.ModelIdentity(
        provider=provider,
        model_id=model_id,
        thinking="low",
        provider_source="override",
        model_source="override",
        thinking_source="override",
    )
    return sp.StageCapacity(
        identity=identity,
        context_window=context_window,
        max_output_tokens=32_000,
        matched=context_window is not None,
        model_name="GLM" if context_window is not None else "",
    )


class ModelMatchingTests(unittest.TestCase):
    def test_provider_qualified_full_id_matches(self) -> None:
        models = [
            pi_runtime.PiModel(
                provider="fireworks",
                model_id="accounts/fireworks/models/glm-5p3-flash",
                name="GLM",
                context_window=1_000_000,
            )
        ]
        identity = sp.ModelIdentity(
            provider="fireworks",
            model_id="accounts/fireworks/models/glm-5p3-flash",
            thinking="low",
            provider_source="override",
            model_source="override",
            thinking_source="override",
        )
        self.assertIsNotNone(sp.match_model(identity, models))

    def test_basename_never_matches_full_id(self) -> None:
        """The retired basename comparison bug cannot resurrect here."""
        models = [
            pi_runtime.PiModel(
                provider="fireworks",
                model_id="accounts/fireworks/models/glm-5p3-flash",
                name="GLM",
                context_window=1_000_000,
            )
        ]
        identity = sp.ModelIdentity(
            provider="fireworks",
            model_id="glm-5p3-flash",
            thinking="low",
            provider_source="override",
            model_source="override",
            thinking_source="override",
        )
        self.assertIsNone(sp.match_model(identity, models))

    def test_same_basename_across_providers_never_matches_silently(self) -> None:
        models = [
            pi_runtime.PiModel(
                provider="other-provider",
                model_id="accounts/fireworks/models/glm-5p3-flash",
                name="GLM elsewhere",
                context_window=1_000_000,
            )
        ]
        identity = sp.ModelIdentity(
            provider="fireworks",
            model_id="accounts/fireworks/models/glm-5p3-flash",
            thinking="low",
            provider_source="override",
            model_source="override",
            thinking_source="override",
        )
        self.assertIsNone(sp.match_model(identity, models))

    def test_resolve_stage_capacity_with_given_models_spawns_nothing(self) -> None:
        models = [
            pi_runtime.PiModel(
                provider="fireworks",
                model_id="accounts/fireworks/models/glm-5p3-flash",
                name="GLM",
                context_window=262_144,
                max_output_tokens=8_000,
            )
        ]
        with tempfile.TemporaryDirectory() as temporary:
            settings_path = Path(temporary) / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "defaultProvider": "fireworks",
                        "defaultModel": "accounts/fireworks/models/glm-5p3-flash",
                        "defaultThinkingLevel": "low",
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(
                sp.pi_runtime, "available_pi_models"
            ) as discovery:
                capacity = sp.resolve_stage_capacity(
                    {"extract_provider": "", "extract_model": ""},
                    "extract",
                    settings_path,
                    models=models,
                )
            discovery.assert_not_called()
        self.assertTrue(capacity.known)
        self.assertEqual(capacity.headroom_tokens, int(262_144 * 0.8))

    def test_unknown_metadata_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            settings_path = Path(temporary) / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "defaultProvider": "fireworks",
                        "defaultModel": "accounts/fireworks/models/glm-5p3-flash",
                    }
                ),
                encoding="utf-8",
            )
            capacity = sp.resolve_stage_capacity(
                {},
                "extract",
                settings_path,
                models=[],
            )
        self.assertFalse(capacity.known)
        self.assertIn("not found", capacity.discovery_error)

    def test_resolve_stage_identity_prefers_overrides_and_labels_sources(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            settings_path = Path(temporary) / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "defaultProvider": "fireworks",
                        "defaultModel": "accounts/fireworks/models/project-model",
                        "defaultThinkingLevel": "high",
                    }
                ),
                encoding="utf-8",
            )
            identity = sp.resolve_stage_identity(
                {
                    "extract_provider": "other",
                    "extract_model": "",
                    "extract_thinking": "low",
                },
                "extract",
                settings_path,
            )
        self.assertEqual(identity.provider, "other")
        self.assertEqual(identity.model_id, "accounts/fireworks/models/project-model")
        self.assertEqual(identity.provider_source, "override")
        self.assertEqual(identity.model_source, "project-settings")
        self.assertEqual(identity.thinking_source, "override")


class CapacityDecisionTests(unittest.TestCase):
    def test_token_range_is_utf8_byte_aware(self) -> None:
        low, high = sp.estimate_token_range(120)
        self.assertEqual((low, high), (30, 40))
        # Non-ASCII text counts UTF-8 bytes, not characters.
        unicode_chars = 10
        low, high = sp.estimate_token_range("é" * unicode_chars)
        self.assertEqual((low, high), (20 // 4, 20 // 3))

    def test_oversized_individual_request_fails_before_paid_call(self) -> None:
        capacity = _capacity(context_window=1_000)
        with self.assertRaises(sp.PreflightError) as ctx:
            sp.check_individual_request(capacity, 500_000, label="hearing:0004")
        message = str(ctx.exception)
        self.assertIn("hearing:0004", message)
        self.assertIn("80%", message)
        self.assertIn("Settings", message)

    def test_individual_request_within_capacity_passes(self) -> None:
        capacity = _capacity(context_window=1_000_000)
        decision = sp.check_individual_request(
            capacity, 40_000, label="hearing:0004"
        )
        self.assertEqual(decision.level, "ok")

    def test_unknown_individual_metadata_is_reported_not_enforced(self) -> None:
        decision = sp.check_individual_request(None, 500_000, label="x")
        self.assertEqual(decision.level, "unknown")
        self.assertIn("unavailable", decision.message)

    def test_aggregate_history_warns_and_proceeds(self) -> None:
        capacity = _capacity(context_window=10_000)
        decision = sp.check_aggregate_history(capacity, 900_000, label="s")
        self.assertEqual(decision.level, "warn")
        self.assertIn("proceeds", decision.message)

    def test_aggregate_unknown_metadata_warns_unknown(self) -> None:
        decision = sp.check_aggregate_history(None, 900_000, label="s")
        self.assertEqual(decision.level, "unknown")

    def test_unknown_capacity_is_normalized(self) -> None:
        decision = sp.check_individual_request(None, 1, label="x")
        self.assertIsNone(decision.headroom_tokens)


class EstimateCompositionTests(unittest.TestCase):
    def test_extraction_estimate_counts_model_visible_components(self) -> None:
        static = {
            "system_prompt_chars": 100,
            "skill_chars": 50,
            "tool_schema_proxy_chars": 25,
            "envelope_overhead_chars": 10,
            "reasoning_allowance_chars": 5,
        }
        total = sp.extraction_request_chars(
            static, source_payload_chars=200, prompt_chars=40
        )
        # Output allowance is added exactly once.
        self.assertEqual(
            total,
            100 + 50 + 25 + 10 + 5 + 200 + 40
            + sp.EXTRACTION_OUTPUT_ALLOWANCE_CHARS,
        )

    def test_synthesis_estimate_counts_blocks_not_internal_json(self) -> None:
        static = dict.fromkeys(
            (
                "system_prompt_chars",
                "skill_chars",
                "tool_schema_proxy_chars",
                "envelope_overhead_chars",
                "reasoning_allowance_chars",
            ),
            10,
        )
        blocks = [100, 200]
        total = sp.synthesis_history_chars(
            static, overview_chars=30, document_block_chars=blocks
        )
        internal_rows_json = 4096  # would double-count the canonical store
        self.assertEqual(
            total,
            50  # static
            + 30  # overview
            + 300  # document blocks once
            + len(blocks)
            * (
                sp.SYNTHESIS_SECTION_ALLOWANCE_CHARS
                + sp.SYNTHESIS_TOOL_EXCHANGE_ALLOWANCE_CHARS
            ),
        )
        self.assertLess(total, internal_rows_json + total)  # sanity guard

    def test_stage_static_components_read_tracked_files(self) -> None:
        static = sp.stage_static_components(PROJECT_DIR / ".pi", "recordprep-extract-hearing")
        self.assertGreater(static["system_prompt_chars"], 0)
        self.assertGreater(static["skill_chars"], 0)
        self.assertGreater(static["tool_schema_proxy_chars"], 0)


class DiagnosticCliTests(unittest.TestCase):
    def test_cli_reports_counts_and_unknown_capacity_without_writes(
        self,
    ) -> None:
        from tests.test_summary_agent_pipeline import BundleBuilder

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "bundle"
            builder = BundleBuilder(root)
            builder.add_pages(1, 2, "h1")
            builder.add_pages(3, 4, "h2")
            builder.add_pages(5, 6, "r1")
            builder.finish(
                hearings=[(1, 2, "March 3, 2025"), (3, 4, "April 4, 2025")],
                reports=[(5, 6, "May 5, 2025", "Report")],
            )
            before = sorted(
                (path, path.stat().st_mtime_ns)
                for path in root.rglob("*")
                if path.is_file()
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "recordprep.summary_preflight",
                    "--case-bundle",
                    str(root),
                    "--kind",
                    "both",
                    "--skip-discovery",
                ],
                cwd=PROJECT_DIR,
                text=True,
                capture_output=True,
                timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["artifact"], sp.ARTIFACT)
            self.assertEqual(payload["kinds"]["hearings"]["documents"], 2)
            self.assertEqual(payload["kinds"]["reports"]["documents"], 1)
            self.assertGreater(
                payload["kinds"]["reports"]["largest_document_payload_chars"], 0
            )
            self.assertFalse(payload["capacities"]["hearings"]["extract"]["capacity_known"])
            self.assertEqual(
                payload["kinds"]["hearings"]["synthesis"]["level"], "unknown"
            )
            self.assertEqual(
                payload["kinds"]["hearings"]["synthesis"]["estimate_based_on"],
                "no digest on disk; estimate covers static components only",
            )
            after = sorted(
                (path, path.stat().st_mtime_ns)
                for path in root.rglob("*")
                if path.is_file()
            )
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
