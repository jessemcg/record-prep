"""Strict, GTK-independent application recognition resources; no profile fallback."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .profile_contract import (CLASSIFICATION_FIRST_PAGE_TYPES, CLASSIFICATION_PAGE_TYPES,
                               _json, _object, _text)

RESOURCE = Path(__file__).parent / "resources/classification/recognition-v5.json"
CONTRACT_ID = "recordprep-recognition-v5"


@dataclass(frozen=True)
class RecognitionContract:
    identity: str
    page_types: tuple[tuple[str, tuple[tuple[str, str], ...]], ...]
    first_pages: tuple[tuple[str, str], ...]

    def descriptions(self, side: str) -> tuple[tuple[str, str], ...]:
        return dict(self.page_types)[side]

    def clues(self, task: str) -> str:
        return dict(self.first_pages)[task]


def load_recognition(path: Path | None = None) -> RecognitionContract:
    """Freeze canonical order and literal text. Read anew for each stage/inspection.

    Bounded strict JSON rejects duplicates, missing/unknown keys and invalid text.
    Missing/corrupt installed resources fail explicitly before any model work.
    """
    try:
        with (RESOURCE if path is None else path).open("rb") as stream:
            data = stream.read(256 * 1024 + 1)
        if len(data) > 256 * 1024:
            raise ValueError("oversized resource")
        value = _json(data, "application_recognition")
        _object(value, {"schema_version", "contract_id", "page_types", "first_pages"}, "application_recognition")
        if type(value["schema_version"]) is not int or value["schema_version"] != 1 or value["contract_id"] != CONTRACT_ID:
            raise ValueError("unsupported recognition contract")
        _object(value["page_types"], set(CLASSIFICATION_PAGE_TYPES), "page_types")
        pages = []
        for side, keys in CLASSIFICATION_PAGE_TYPES.items():
            descriptions = _object(value["page_types"][side], set(keys), side)
            pages.append((side, tuple((key, _text(descriptions[key], key)) for key in keys)))
        starts = _object(value["first_pages"], set(CLASSIFICATION_FIRST_PAGE_TYPES), "first_pages")
        return RecognitionContract(CONTRACT_ID, tuple(pages),
                                   tuple((key, _text(starts[key], key)) for key in CLASSIFICATION_FIRST_PAGE_TYPES))
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        raise ValueError("RecordPrep application classification resource is missing or invalid; reinstall or repair the application resources. No profile fallback is permitted.") from exc
