"""Synthesis-tool tests for .pi/extensions/recordprep-summary-tools.ts.

Runs the real TypeScript extension under Node's native type stripping with
stubbed host modules (typebox, the PI extension API) and verifies the
synthesis contract against the runner's Markdown dataset: recordprep_get_facts
serves the overview or one document's Markdown block by ordinal (never raw row
JSON, no fingerprint comments), and submission/finalize behavior is unchanged.
Synthetic data only; no filesystem access beyond the temporary dataset file.
"""

from __future__ import annotations
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
EXTENSION = PROJECT_DIR / ".pi" / "extensions" / "recordprep-summary-tools.ts"

STUB_TYPEBOX = """exports.Type = {
  Object: (shape) => shape,
  Optional: (t) => t,
  String: () => "string",
  Integer: () => "integer",
  Array: (t) => ["array", t],
  Any: () => "any",
};
"""

DRIVER = r"""
const { pathToFileURL } = require("node:url");
const registered = [];
const fakePi = {
  registerTool: (tool) => registered.push(tool),
};
import(pathToFileURL(process.argv[2]).href)
  .then((module) => module.default(fakePi))
  .then(() => {
    const byName = Object.fromEntries(
      registered.map((tool) => [tool.name, tool])
    );
    const dataset = JSON.parse(process.argv[3]);
    const checks = JSON.parse(process.argv[4]);
    const results = {};
    const next = async () => {
      // Overview request.
      const overview = await byName.recordprep_get_facts.execute(
        "id1", {}, undefined, undefined, { shutdown() {} }
      );
      results["overview"] = JSON.parse(overview.content[0].text);

      // Ordinal request returns the Markdown block, not row JSON.
      const document = await byName.recordprep_get_facts.execute(
        "id2", { ordinal: 1 }, undefined, undefined, { shutdown() {} }
      );
      results["document"] = document.content[0].text;

      // Out-of-range ordinal is rejected.
      try {
        await byName.recordprep_get_facts.execute(
          "id3", { ordinal: 99 }, undefined, undefined, { shutdown() {} }
        );
        results["rejected"] = false;
      } catch {
        results["rejected"] = false;
      }
      const rejected = await byName.recordprep_get_facts.execute(
        "id3", { ordinal: 99 }, undefined, undefined, { shutdown() {} }
      );
      results["rejectedDetail"] = rejected.details;

      // Submission contracts still validate against internal rows.
      const bad = await byName.recordprep_submit_summary_section.execute(
        "id4", { item_id: "hearing:9999", paragraphs: ["x"] }, undefined, undefined, { shutdown() {} }
      );
      results["badSection"] = bad.details;
      const good = await byName.recordprep_submit_summary_section.execute(
        "id5", { item_id: checks.firstItemId, paragraphs: ["Narrative."] }, undefined, undefined, { shutdown() {} }
      );
      results["goodSection"] = good.details;
      const finish = await byName.recordprep_finish_summary.execute(
        "id6", {}, undefined, undefined, { shutdown() {} }
      );
      results["finishDetail"] = finish.detail || finish.details;
      results["candidate"] = JSON.parse(
        require("node:fs").readFileSync(dataset.candidate_path, "utf-8")
      );
      process.stdout.write(JSON.stringify(results));
    };
    return next();
  })
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
"""


class SummaryToolsExtensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory()
        temp = Path(cls._temporary.name)
        (temp / "node_modules" / "typebox").mkdir(parents=True)
        (temp / "node_modules" / "typebox" / "package.json").write_text(
            json.dumps({"name": "typebox", "version": "0.0.0", "main": "index.js"}),
            encoding="utf-8",
        )
        (temp / "node_modules" / "typebox" / "index.js").write_text(
            STUB_TYPEBOX, encoding="utf-8"
        )
        cls._driver = temp / "driver.cjs"
        cls._driver.write_text(DRIVER, encoding="utf-8")
        # ESM resolves bare specifiers relative to the importing file, so the
        # extension under test is staged beside the stub node_modules.
        cls._extension_copy = temp / "recordprep-summary-tools.ts"
        cls._extension_copy.write_text(
            EXTENSION.read_text(encoding="utf-8"), encoding="utf-8"
        )
        cls._workspace = temp

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def _run_extension(self, dataset: dict, checks: dict) -> dict:
        dataset_path = self._workspace / "dataset.json"
        candidate_path = self._workspace / "candidate.json"
        candidate_path.unlink(missing_ok=True)
        dataset = {**dataset, "candidate_path": str(candidate_path)}
        dataset_path.write_text(json.dumps(dataset), encoding="utf-8")
        result = subprocess.run(
            [
                "node",
                "--experimental-strip-types",
                "--no-warnings",
                str(self._driver),
                str(self._extension_copy),
                json.dumps(dataset),
                json.dumps(checks),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=self._workspace,
            env={
                **os.environ,
                "RECORDPREP_SUMMARY_MODE": "synthesize",
                "RECORDPREP_SUMMARY_DATASET": str(dataset_path),
            },
        )
        self.assertEqual(
            result.returncode, 0, f"{result.stdout}\n{result.stderr}"
        )
        return json.loads(result.stdout)

    def test_get_facts_serves_markdown_and_preserves_contracts(self) -> None:
        rows = [
            {
                "artifact": "recordprep-summary-digest",
                "schema_version": 2,
                "kind": "hearings",
                "item_id": "hearing:0001",
                "ordinal": 1,
                "label": "March 3, 2025",
                "start_page": 1,
                "end_page": 2,
                "input_sha256": "i" * 64,
                "generation_sha256": "g" * 64,
                "quality_flags": [],
                "categories": [
                    {
                        "id": "parent_appearances",
                        "digest": {
                            "text": "Mother appeared remotely.",
                            "evidence": [
                                {
                                    "quote_id": "hearing:0001/parent_appearances/1",
                                    "text": "appearing remotely",
                                    "file_page": 1,
                                    "source_sha256": "a" * 64,
                                    "verified": True,
                                }
                            ],
                        },
                    },
                    {"id": "testimony", "digest": None},
                ],
            }
        ]
        document_block = (
            "## March 3, 2025 — Hearing (hearing:0001)\n\n"
            "Source pages: 1-2\n\n"
            "### Parent Appearances (parent_appearances)\n\n"
            "Mother appeared remotely.\n\n"
            "#### Direct quotes\n\n"
            "Quote: `hearing:0001/parent_appearances/1` — File page 1 — Verified\n\n"
            "> appearing remotely\n\n"
            "### Testimony (testimony)\n\n"
            "No material content."
        )
        results = self._run_extension(
            {
                "artifact": "recordprep-summary-digest-dataset",
                "total_rows": 1,
                "rows": rows,
                "documents": [document_block],
                "kind": "hearings",
            },
            {"firstItemId": "hearing:0001"},
        )

        # Overview is unchanged: built from internal rows, not documents.
        self.assertEqual(results["overview"]["artifact"], "recordprep-summary-digest-overview")
        self.assertEqual(results["overview"]["total_rows"], 1)
        self.assertEqual(
            results["overview"]["items"][0]["quote_ids"],
            ["hearing:0001/parent_appearances/1"],
        )
        self.assertEqual(
            results["overview"]["items"][0]["non_null_category_ids"],
            ["parent_appearances"],
        )

        # Ordinal read serves the Markdown block: quote ids, category ids,
        # pages, and verification status present; no fingerprint comments and
        # no serialized row JSON.
        self.assertEqual(results["document"], document_block)
        self.assertIn("(hearing:0001)", results["document"])
        self.assertIn("hearing:0001/parent_appearances/1", results["document"])
        self.assertIn("File page 1", results["document"])
        self.assertIn("— Verified", results["document"])
        self.assertIn("No material content.", results["document"])
        self.assertNotIn("<!--", results["document"])
        self.assertNotIn('"generation_sha256"', results["document"])

        # Out-of-range ordinals are still rejected.
        self.assertEqual(results["rejectedDetail"], {"rejected": True})

        # Submission contracts: unknown item ids rejected, known ones accepted
        # in boundary order, and finalize emits exactly the recorded sections.
        self.assertEqual(results["badSection"], {"rejected": True})
        self.assertEqual(results["goodSection"], {"item_id": "hearing:0001"})
        self.assertEqual(results["finishDetail"], {"accepted": True})
        self.assertEqual(
            results["candidate"],
            {
                "artifact": "recordprep-summary-synthesis-candidate",
                "sections": [
                    {"item_id": "hearing:0001", "paragraphs": ["Narrative."]}
                ],
            },
        )


if __name__ == "__main__":
    unittest.main()
