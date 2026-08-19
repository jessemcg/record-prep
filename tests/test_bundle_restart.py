import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import requests

from recordprep.ui.main_window import (
    GENERATED_CASE_BUNDLE_DIRS,
    GENERATED_CASE_BUNDLE_FILES,
    _bundle_inputs_changed,
    _generate_text_files_with_local_ocr,
    _reset_generated_case_bundle,
    _resolve_local_ocr_start_command,
    _start_server,
    _start_server_output_reader,
    _stop_server,
    _update_rt_ct_split_manifest,
    _write_manifest,
)


class BundleRestartTests(unittest.TestCase):
    def test_local_ocr_parallel_slots_do_not_enable_unified_kv(self) -> None:
        command = _resolve_local_ocr_start_command("./llama-server --port 8000", 4)

        self.assertIn("--parallel 4", command)
        self.assertNotIn("--kv-unified", command)

    def test_server_output_reader_prevents_a_full_pipe_deadlock(self) -> None:
        process = _start_server(
            "python3 -c 'for index in range(2000): print(index, \"x\" * 100)'"
        )
        try:
            recent_output = _start_server_output_reader(process)
            process.wait(timeout=5)

            self.assertEqual(process.returncode, 0)
            self.assertIn("1999 ", recent_output())
        finally:
            if process.poll() is None:
                _stop_server(process)
            elif process.stdout is not None:
                process.stdout.close()

    def test_server_output_reader_drains_output_without_newlines(self) -> None:
        process = _start_server(
            "python3 -c 'import sys; sys.stdout.write(\"x\" * 200000); "
            "sys.stdout.flush()'"
        )
        try:
            recent_output = _start_server_output_reader(process)
            process.wait(timeout=5)

            self.assertEqual(process.returncode, 0)
            self.assertTrue(recent_output().endswith("x" * 100))
        finally:
            if process.poll() is None:
                _stop_server(process)
            elif process.stdout is not None:
                process.stdout.close()

    def test_server_stop_terminates_the_launched_process_group(self) -> None:
        process = _start_server("sleep 30 & wait")
        try:
            time.sleep(0.1)
            self.assertIsNone(process.poll())

            _stop_server(process)

            self.assertIsNotNone(process.poll())
            with self.assertRaises(ProcessLookupError):
                os.killpg(process.pid, 0)
        finally:
            if process.poll() is None:
                _stop_server(process)

    def test_split_update_preserves_manifest_source_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base_dir = Path(temporary)
            root_dir = base_dir / "case_bundle"
            root_dir.mkdir()
            original_pdf = base_dir / "original.pdf"
            replacement_pdf = base_dir / "replacement.pdf"
            original_pdf.write_bytes(b"original")
            replacement_pdf.write_bytes(b"replacement")
            _write_manifest(root_dir, [original_pdf])

            self.assertFalse(_bundle_inputs_changed(root_dir, [original_pdf]))
            self.assertTrue(_bundle_inputs_changed(root_dir, [replacement_pdf]))
            self.assertTrue(
                _update_rt_ct_split_manifest(root_dir, 25, "split")
            )

            manifest = json.loads(
                (root_dir / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["input_pdfs"], ["../original.pdf"])
            self.assertEqual(manifest["rt_ct_split_page"], 25)

    def test_legacy_manifest_gets_one_clean_rebuild(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base_dir = Path(temporary)
            root_dir = base_dir / "case_bundle"
            root_dir.mkdir()
            source_pdf = base_dir / "source.pdf"
            source_pdf.write_bytes(b"source")
            (root_dir / "manifest.json").write_text(
                json.dumps({"input_pdfs": ["../source.pdf"]}),
                encoding="utf-8",
            )

            self.assertTrue(_bundle_inputs_changed(root_dir, [source_pdf]))
            _write_manifest(root_dir, [source_pdf])
            self.assertFalse(_bundle_inputs_changed(root_dir, [source_pdf]))

    def test_reset_removes_only_generated_bundle_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root_dir = Path(temporary) / "case_bundle"
            root_dir.mkdir()
            for name in GENERATED_CASE_BUNDLE_DIRS:
                generated_dir = root_dir / name
                generated_dir.mkdir()
                (generated_dir / "generated.txt").write_text(
                    "generated",
                    encoding="utf-8",
                )
            for name in GENERATED_CASE_BUNDLE_FILES:
                (root_dir / name).write_text("generated", encoding="utf-8")
            custom_file = root_dir / "keep-me.txt"
            custom_file.write_text("custom", encoding="utf-8")

            _reset_generated_case_bundle(root_dir)

            for name in GENERATED_CASE_BUNDLE_DIRS:
                self.assertFalse((root_dir / name).exists())
            for name in GENERATED_CASE_BUNDLE_FILES:
                self.assertFalse((root_dir / name).exists())
            self.assertEqual(custom_file.read_text(encoding="utf-8"), "custom")

    def test_local_ocr_restarts_sequentially_after_connection_abort(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            text_dir = root / "text_pages"
            image_dir = root / "image_pages"
            text_dir.mkdir()
            image_dir.mkdir()
            pdf_path = root / "source.pdf"
            pdf_path.write_bytes(b"pdf")
            first_process = mock.Mock(name="first_process")
            second_process = mock.Mock(name="second_process")

            def generate_images(_pdf_path: Path, target_dir: Path) -> None:
                (target_dir / "0001.png").write_bytes(b"image")

            with (
                mock.patch(
                    "recordprep.ui.main_window._start_server",
                    side_effect=[first_process, second_process],
                ) as start_server,
                mock.patch("recordprep.ui.main_window._stop_server") as stop_server,
                mock.patch("recordprep.ui.main_window._wait_for_endpoint_ready"),
                mock.patch("recordprep.ui.main_window._print_server_slot_report"),
                mock.patch(
                    "recordprep.ui.main_window._generate_image_page_files",
                    side_effect=generate_images,
                ),
                mock.patch(
                    "recordprep.ui.main_window._ocr_images",
                    side_effect=[requests.ConnectionError("closed"), None],
                ) as ocr_images,
            ):
                _generate_text_files_with_local_ocr(
                    pdf_path,
                    text_dir,
                    image_dir,
                    start_command="llama-server --model test.gguf",
                    workers=4,
                    slots=4,
                    sleep_seconds=0,
                )

            self.assertEqual(start_server.call_count, 2)
            self.assertIn("--parallel 4", start_server.call_args_list[0].args[0])
            self.assertIn("--parallel 1", start_server.call_args_list[1].args[0])
            self.assertEqual(ocr_images.call_args_list[0].kwargs["workers"], 4)
            self.assertEqual(ocr_images.call_args_list[1].kwargs["workers"], 1)
            self.assertEqual(
                stop_server.call_args_list,
                [mock.call(first_process), mock.call(second_process)],
            )

    def test_local_ocr_cleans_up_when_server_startup_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            text_dir = root / "text_pages"
            image_dir = root / "image_pages"
            text_dir.mkdir()
            image_dir.mkdir()
            pdf_path = root / "source.pdf"
            pdf_path.write_bytes(b"pdf")
            process = mock.Mock(name="server_process")
            process_changed = mock.Mock()

            with (
                mock.patch(
                    "recordprep.ui.main_window._start_server",
                    return_value=process,
                ),
                mock.patch(
                    "recordprep.ui.main_window._wait_for_endpoint_ready",
                    side_effect=RuntimeError("startup failed"),
                ),
                mock.patch(
                    "recordprep.ui.main_window._stop_server"
                ) as stop_server,
            ):
                with self.assertRaisesRegex(RuntimeError, "startup failed"):
                    _generate_text_files_with_local_ocr(
                        pdf_path,
                        text_dir,
                        image_dir,
                        server_process_changed=process_changed,
                        start_command="llama-server --model test.gguf",
                        sleep_seconds=0,
                    )

            stop_server.assert_called_once_with(process)
            self.assertEqual(
                process_changed.call_args_list,
                [mock.call(process), mock.call(None)],
            )


if __name__ == "__main__":
    unittest.main()
