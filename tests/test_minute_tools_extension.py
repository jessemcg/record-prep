"""Exercise the real TypeScript minute tool implementation with a synthetic host."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_summary_tools_extension import STUB_TYPEBOX


class MinuteToolsTests(unittest.TestCase):
    def test_source_required_narrow_tools_and_candidate_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            extension = root / "minute-tools.ts"
            shutil.copy2(Path(__file__).resolve().parents[1] / ".pi/extensions/recordprep-minute-tools.ts", extension)
            module = root / "node_modules/typebox"
            module.mkdir(parents=True)
            (module / "package.json").write_text('{"main":"index.js"}')
            (module / "index.js").write_text(STUB_TYPEBOX)
            candidate = root / "candidate.json"
            spec = root / "spec.json"
            spec.write_text(json.dumps({"source": "FIRST PAGE: Mother present.", "item_id": "minute:0001", "candidate_path": str(candidate)}))
            driver = root / "driver.mjs"
            driver.write_text('''
import tools from "./minute-tools.ts";
const registered = {};
const handlers = {};
tools({ registerTool(tool) { registered[tool.name] = tool; }, on(name, handler) { handlers[name] = handler; } });
process.env.RECORDPREP_MINUTE_WORK_SPEC = process.argv[2];
const submit = registered.recordprep_submit_minute_summary;
const params = { hearing: "Review", reporting: "reported", parents: [{parent: "Mother", status: "present", first_page_evidence: "Mother present."}], orders: "Continued." };
let blocked = false, shutdown = 0;
try { await submit.execute("1", params, null, null, {shutdown() {shutdown++;}}); } catch { blocked = true; }
const source = await registered.recordprep_get_minute_source.execute();
const result = await submit.execute("2", params, null, null, {shutdown() {shutdown++;}});
console.log(JSON.stringify({ names: Object.keys(registered), blocked, source: source.content[0].text, shutdown, terminate: result.terminate }));
''')
            result = subprocess.run(["node", "--experimental-strip-types", str(driver), str(spec)], capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            actual = json.loads(result.stdout)
            self.assertEqual(actual["names"], ["recordprep_get_minute_source", "recordprep_submit_minute_summary"])
            self.assertTrue(actual["blocked"])
            self.assertEqual(actual["source"], "FIRST PAGE: Mother present.")
            self.assertEqual(actual["shutdown"], 1)
            self.assertTrue(actual["terminate"])
            payload = json.loads(candidate.read_text())
            self.assertEqual(payload["artifact"], "recordprep-minute-candidate")
            self.assertEqual(payload["item_id"], "minute:0001")


if __name__ == "__main__":
    unittest.main()
