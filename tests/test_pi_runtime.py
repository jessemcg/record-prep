import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from recordprep.pi_runtime import (
    PiModel,
    available_pi_models,
    current_project_pi_model,
    discover_pi_agent_command,
    incompatible_pi_agent_flag,
    resolve_pi_agent_argv,
    save_project_pi_model,
)


class PiRuntimeTests(unittest.TestCase):
    def test_discovers_newest_pi_node_installation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            older = home / ".local/share/pi-node/node-v20/bin/pi"
            newer = home / ".local/share/pi-node/node-v22/bin/pi"
            for path in (older, newer):
                path.parent.mkdir(parents=True)
                path.write_text("#!/bin/sh\n", encoding="utf-8")
                path.chmod(0o755)
            os.utime(older, (1, 1))
            os.utime(newer, (2, 2))
            self.assertEqual(
                discover_pi_agent_command(home, path_env=""),
                str(newer),
            )

    def test_resolves_pi_and_rejects_owned_flags(self) -> None:
        with patch(
            "recordprep.pi_runtime.discover_pi_agent_command",
            return_value="/opt/pi/bin/pi",
        ):
            self.assertEqual(
                resolve_pi_agent_argv("pi --verbose"),
                ["/opt/pi/bin/pi", "--verbose"],
            )
        self.assertEqual(
            incompatible_pi_agent_flag(["pi", "--model", "other"]),
            "--model",
        )
        self.assertIsNone(incompatible_pi_agent_flag(["pi", "--verbose"]))

    def test_available_models_are_deduplicated_and_sorted(self) -> None:
        response = {
            "success": True,
            "data": {
                "models": [
                    {"provider": "zeta", "id": "two", "name": "Two"},
                    {"provider": "alpha", "id": "one", "name": "One"},
                    {"provider": "alpha", "id": "one", "name": "One replacement"},
                    {"provider": "", "id": "ignored"},
                ]
            },
        }
        with patch("recordprep.pi_runtime._pi_rpc_response", return_value=response):
            models = available_pi_models(["pi"])
        self.assertEqual(
            [(model.provider, model.model_id) for model in models],
            [("alpha", "one"), ("zeta", "two")],
        )
        self.assertEqual(models[0].name, "One replacement")

    def test_project_model_save_is_atomic_and_preserves_other_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            path.write_text(
                json.dumps(
                    {
                        "defaultProvider": "old",
                        "defaultModel": "old-model",
                        "enableSkillCommands": True,
                        "custom": {"keep": True},
                    }
                ),
                encoding="utf-8",
            )
            save_project_pi_model(PiModel("new", "model", "Model"), path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(current_project_pi_model(path), ("new", "model"))
            self.assertTrue(payload["enableSkillCommands"])
            self.assertEqual(payload["custom"], {"keep": True})
            self.assertEqual(list(path.parent.glob(".*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
