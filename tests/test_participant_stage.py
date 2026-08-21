import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
from recordprep.pi_bundle import validate_participant_index_output  # noqa: E402
HELPER = (
    PROJECT_DIR
    / ".pi/skills/recordprep-build-participant-index/scripts/participant_index.py"
)
TEMPLATE_WARNING = "Participant review has not been completed."
WORKLIST_RELATIVE = Path("temp") / ".participant_worklist.json"


def _run_helper(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(HELPER), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def _transcript_entries(pages: range) -> list[dict]:
    entries = []
    for number in pages:
        entries.append(
            {
                "file_name": f"{number:04d}.txt",
                "file_page": number,
                "record_type": "RT",
                "page_type": "RT_other",
                "transcript_page_number": number,
                "transcript_page_label": str(number),
                "citation_series_id": "rt-1",
                "citation_prefix": "RT",
                "citation_label": f"RT {number}",
                "citation_key": f"RT:{number}",
                "status": "selected",
                "confidence": "high",
                "method": "sequence",
            }
        )
    return entries


def _build_record_fixture(
    temporary: str,
    *,
    hearings: int = 44,
    pages_per_hearing: int = 6,
) -> Path:
    """A record with N hearings, oath/examination markers, and RT index pages."""
    root = Path(temporary) / "case_bundle"
    (root / "text_pages").mkdir(parents=True)
    (root / "artifacts").mkdir()
    (root / "classification").mkdir()

    total_pages = hearings * pages_per_hearing
    boundaries = []
    for index in range(1, hearings + 1):
        start = (index - 1) * pages_per_hearing + 1
        end = start + pages_per_hearing - 1
        boundaries.append(
            {
                "id": f"hearing:{index:04d}",
                "date": f"Hearing {index}",
                "start_page": start,
                "end_page": end,
            }
        )
    (root / "artifacts/hearing_boundaries.json").write_text(
        json.dumps(boundaries), encoding="utf-8"
    )

    classification_rows = []
    for number in range(1, total_pages + 1):
        page_type = "RT_hearing"
        if number == total_pages + 1:
            continue
        classification_rows.append(
            {"file_page": number, "page_type": page_type, "file_name": f"{number:04d}.txt"}
        )
    # Index pages: one inside a hearing range, one outside the ranges, plus a CT one.
    classification_rows.extend(
        [
            {"file_page": 3, "page_type": "RT_index", "file_name": "0003.txt"},
            {"file_page": total_pages + 2, "page_type": "RT_index", "file_name": f"{total_pages + 2:04d}.txt"},
            {"file_page": total_pages + 3, "page_type": "RT_index", "file_name": f"{total_pages + 3:04d}.txt"},
        ]
    )
    (root / "classification/RT_basic_advanced_corrected_dates_names.jsonl").write_text(
        "\n".join(json.dumps(row) for row in classification_rows) + "\n",
        encoding="utf-8",
    )
    (root / "classification/CT_basic_advanced_corrected_dates_names.jsonl").write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                {"file_page": total_pages + 3, "page_type": "CT_index", "file_name": f"{total_pages + 3:04d}.txt"}
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    for number in range(1, total_pages + 1):
        text = [
            f"SUPERIOR COURT OF CALIFORNIA",
            f"Page {number}",
            "THE COURT: Good morning.",
        ]
        if number % pages_per_hearing == 1:
            text.append("MS. COUNSEL: Good morning, your honor. Counsel for the mother appears.")
        if number % pages_per_hearing == 2:
            text.append("THE COURT: Do you solemnly swear or affirm to tell the truth?")
            text.append("THE WITNESS: I do. OATH administered.")
        if number % pages_per_hearing == 3:
            text.append("DIRECT EXAMINATION")
            text.append("BY MS. COUNSEL:")
            text.append("Q: Where do you live?")
            text.append("A: In Los Angeles.")
        if number % pages_per_hearing == 4:
            text.append("CROSS-EXAMINATION")
            text.append("BY MR. COUNSEL:")
        if number % pages_per_hearing == 5:
            text.append("The minor's father was absent and failed to appear.")
        (root / "text_pages" / f"{number:04d}.txt").write_text(
            "\n".join(text), encoding="utf-8"
        )
    # An RT_index page outside hearing ranges.
    (root / "text_pages" / f"{total_pages + 1:04d}.txt").write_text(
        "WITNESS INDEX\n", encoding="utf-8"
    )
    (root / "text_pages" / f"{total_pages + 2:04d}.txt").write_text(
        "INDEX OF WITNESSES\n", encoding="utf-8"
    )

    entries = _transcript_entries(range(1, total_pages + 3))
    entries.append(
        {
            "file_name": f"{total_pages + 3:04d}.txt",
            "file_page": total_pages + 3,
            "record_type": "CT",
            "page_type": "CT_index",
            "transcript_page_number": 1,
            "transcript_page_label": "1",
            "citation_series_id": "ct-1",
            "citation_prefix": "CT",
            "citation_label": "CT 1",
            "citation_key": "CT:1",
            "status": "selected",
            "confidence": "high",
            "method": "sequence",
        }
    )
    (root / "artifacts/transcript_page_numbers.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "entries": entries,
                "citation_series": [
                    {"series_id": "rt-1", "citation_prefix": "RT"},
                    {"series_id": "ct-1", "citation_prefix": "CT"},
                ],
                "anomalies": [],
            }
        ),
        encoding="utf-8",
    )
    (root / "artifacts/report_boundaries.json").write_text("[]", encoding="utf-8")
    (root / "artifacts/minutes_boundaries.json").write_text("[]", encoding="utf-8")
    return root


def _review_hearing(
    hearing: dict,
    index: int,
    *,
    status: str = "verified",
) -> dict:
    """Fill a template hearing with valid reviewed content."""
    hearing = dict(hearing)
    start = int(hearing["start_page"])
    end = int(hearing["end_page"])
    hearing["warnings"] = [f"Hearing {index} reviewed synthetically."]
    hearing["counsel"] = [
        {
            "role_id": "mothers_counsel",
            "role_label": "Mother's counsel",
            "name": f"Attorney {index}",
            "aliases": [f"Ms. {index}"],
            "organization": "Clark & Le",
            "appearance_status": "present",
            "evidence": [
                {
                    "text_path": f"text_pages/{start:04d}.txt",
                    "file_page": start,
                    "citation_label": f"RT {start}",
                    "citation_key": f"RT:{start}",
                    "note": "Counsel appeared.",
                }
            ],
        }
    ]
    hearing["participants"] = [
        {
            "id": f"participant:hearing:{index:04d}:001",
            "role_id": "social_worker",
            "role_label": "Social worker",
            "name": f"Worker {index}",
            "aliases": [],
            "attendance_status": "present",
            "speaking_status": "spoke",
            "sworn_status": "unsworn",
            "evidence": [
                {
                    "text_path": f"text_pages/{start:04d}.txt",
                    "file_page": start,
                    "citation_label": f"RT {start}",
                    "citation_key": f"RT:{start}",
                    "note": "Spoke to the court.",
                }
            ],
        }
    ]
    if status in {"verified", "conflict"}:
        hearing["witness_status"] = status
        hearing["witness_evidence"] = []
        hearing["witnesses"] = [
            {
                "id": f"witness:{index:04d}:001",
                "name": f"Witness {index}",
                "description": "Sworn witness",
                "aliases": [],
                "evidence": [
                    {
                        "text_path": f"text_pages/{start + 1:04d}.txt",
                        "file_page": start + 1,
                        "citation_label": f"RT {start + 1}",
                        "citation_key": f"RT:{start + 1}",
                        "note": "Oath administered.",
                    }
                ],
                "examinations": [
                    {
                        "type": "direct",
                        "examiner_name": f"Attorney {index}",
                        "examiner_role_id": "mothers_counsel",
                        "start_printed_page": start + 2,
                        "end_printed_page": start + 3,
                        "start_file_page": start + 2,
                        "end_file_page": start + 3,
                        "start_citation_label": f"RT {start + 2}",
                        "end_citation_label": f"RT {start + 3}",
                        "evidence": [
                            {
                                "text_path": f"text_pages/{start + 2:04d}.txt",
                                "file_page": start + 2,
                                "citation_label": f"RT {start + 2}",
                                "citation_key": f"RT:{start + 2}",
                                "note": "DIRECT EXAMINATION.",
                            }
                        ],
                    }
                ],
            }
        ]
        if status == "conflict":
            hearing["warnings"] = [
                "Index and transcript disagree about this witness."
            ]
    elif status == "none":
        hearing["witness_status"] = "none"
        hearing["witness_evidence"] = [
            {
                "text_path": f"text_pages/{start:04d}.txt",
                "file_page": start,
                "citation_label": f"RT {start}",
                "citation_key": f"RT:{start}",
                "note": "Explicit no-witness index.",
            }
        ]
        hearing["witnesses"] = []
    else:
        hearing["witness_status"] = "unknown"
        hearing["witness_evidence"] = [
            {
                "text_path": f"text_pages/{start:04d}.txt",
                "file_page": start,
                "citation_label": f"RT {start}",
                "citation_key": f"RT:{start}",
                "note": "No reliable testimony evidence located.",
            }
        ]
        hearing["witnesses"] = []
        hearing["warnings"] = ["Testimony could not be established."]
    return hearing


class ParticipantStageHelperTests(unittest.TestCase):
    def test_skill_requires_bounded_incremental_work(self) -> None:
        skill = (
            PROJECT_DIR / ".pi/skills/recordprep-build-participant-index/SKILL.md"
        ).read_text(encoding="utf-8")
        for requirement in (
            "one hearing at a time",
            "Never concatenate the complete RT",
            "at most 12 page reads per hearing",
            "validate --partial",
            "up to 5 hearings",
            "Never stall while trying to eliminate uncertainty",
        ):
            self.assertIn(requirement, skill)

    def test_prepare_creates_44_hearing_template(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_record_fixture(temporary, hearings=44)
            result = _run_helper("prepare", str(root))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(
                (root / "artifacts/participant_index.json").read_text(encoding="utf-8")
            )
            self.assertEqual(payload["schema_version"], 2)
            self.assertEqual(len(payload["hearings"]), 44)
            self.assertEqual(payload["warnings"], [TEMPLATE_WARNING])
            self.assertTrue(
                all(h["warnings"] == [TEMPLATE_WARNING] for h in payload["hearings"])
            )

    def test_template_is_rejected_by_full_validation_but_ok_partial(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_record_fixture(temporary, hearings=44)
            _run_helper("prepare", str(root))
            full = _run_helper("validate", str(root))
            self.assertEqual(full.returncode, 1)
            self.assertIn("template warning remains", full.stderr)
            partial = _run_helper("validate", "--partial", str(root))
            self.assertEqual(partial.returncode, 0, partial.stdout + partial.stderr)

    def test_partial_validation_checks_reviewed_hearings_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_record_fixture(temporary, hearings=44)
            _run_helper("prepare", str(root))
            path = root / "artifacts/participant_index.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            hearings = payload["hearings"]
            # Review 10 hearings, leave 34 with the placeholder.
            hearings[:10] = [
                _review_hearing(h, index + 1) for index, h in enumerate(hearings[:10])
            ]
            path.write_text(json.dumps(payload), encoding="utf-8")

            partial = _run_helper("validate", "--partial", str(root))
            self.assertEqual(partial.returncode, 0, partial.stdout + partial.stderr)

            # A broken reviewed hearing must fail partial validation.
            hearings[3]["counsel"][0]["evidence"] = []
            path.write_text(json.dumps(payload), encoding="utf-8")
            partial = _run_helper("validate", "--partial", str(root))
            self.assertEqual(partial.returncode, 1)
            self.assertIn("counsel[1].evidence must not be empty", partial.stderr)

            # Full validation still rejects the leftover template hearings.
            full = _run_helper("validate", str(root))
            self.assertEqual(full.returncode, 1)
            self.assertIn("has not been reviewed", full.stderr)

    def test_worklist_is_temporary_scoped_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_record_fixture(temporary, hearings=44)
            result = _run_helper("worklist", str(root))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            worklist_path = root / WORKLIST_RELATIVE
            self.assertTrue(worklist_path.is_file())
            self.assertTrue(worklist_path.relative_to(root / "temp"))
            payload = json.loads(worklist_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["artifact"], "recordprep-participant-worklist")
            self.assertTrue(payload["temporary"])
            self.assertEqual(len(payload["hearings"]), 44)
            limits = payload["limits"]
            self.assertEqual(limits["pages_per_read"], 1)

            # Every hearing entry: bounded first/marker pages, no page text.
            for hearing in payload["hearings"]:
                start = int(hearing["start_page"])
                end = int(hearing["end_page"])
                self.assertLessEqual(len(hearing["first_pages"]), limits["first_pages_per_hearing"])
                self.assertLessEqual(len(hearing["marker_pages"]), limits["marker_pages_per_hearing"])
                self.assertEqual(
                    [p["file_page"] for p in hearing["first_pages"]],
                    list(range(start, min(start + 3, end + 1))),
                )
                for page in [*hearing["first_pages"], *hearing["marker_pages"], *hearing["index_pages"]]:
                    self.assertTrue(start <= page["file_page"] <= end)
                for page in hearing["marker_pages"]:
                    self.assertTrue(page["markers"])
                    self.assertTrue(any(
                        marker in {"oath", "examination", "counsel", "attendance", "absence"}
                        for marker in page["markers"]
                    ))

            # Index pages are scoped to the RT series: page 3 (in range) is in a
            # hearing, page total_pages+2 (RT, outside) is in the outside list,
            # and the CT index page never appears.
            inside = [p["file_page"] for h in payload["hearings"] for p in h["index_pages"]]
            outside = [p["file_page"] for p in payload["index_pages_outside_hearings"]]
            total_pages = 44 * 6
            self.assertIn(3, inside)
            self.assertNotIn(total_pages + 2, inside)
            self.assertIn(total_pages + 2, outside)
            self.assertNotIn(total_pages + 3, inside)
            self.assertNotIn(total_pages + 3, outside)

            # No string value may carry page text or a concatenation.
            def walk(value: object) -> None:
                if isinstance(value, dict):
                    for key, item in value.items():
                        self.assertNotIn(key, {"text", "content", "snippet", "page_text", "concatenated"})
                        if isinstance(item, str):
                            self.assertLessEqual(len(item), 240)
                        walk(item)
                elif isinstance(value, list):
                    for item in value:
                        walk(item)

            walk(payload)
            serialized = json.dumps(payload)
            self.assertLess(len(serialized), 100_000)

            # cleanup removes the temporary worklist.
            cleanup = _run_helper("cleanup", str(root))
            self.assertEqual(cleanup.returncode, 0, cleanup.stdout + cleanup.stderr)
            self.assertFalse(worklist_path.exists())

    def test_44_reviewed_hearings_pass_helper_and_recordprep_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_record_fixture(temporary, hearings=44)
            _run_helper("prepare", str(root))
            path = root / "artifacts/participant_index.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["hearings"] = [
                _review_hearing(h, index + 1, status=("verified" if index % 3 else "none"))
                for index, h in enumerate(payload["hearings"])
            ]
            payload["warnings"] = []
            path.write_text(json.dumps(payload), encoding="utf-8")

            helper = _run_helper("validate", str(root))
            self.assertEqual(helper.returncode, 0, helper.stdout + helper.stderr)

            self.assertEqual(validate_participant_index_output(root), [])
            payload = json.loads(path.read_text(encoding="utf-8"))
            statuses = {h["witness_status"] for h in payload["hearings"]}
            self.assertTrue(statuses <= {"verified", "none"})
            self.assertTrue(all(h["counsel"] and h["participants"] for h in payload["hearings"]))


if __name__ == "__main__":
    unittest.main()
