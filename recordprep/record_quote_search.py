"""Ephemeral record-wide Focus-style phrase verification; no generated index.

Search pages independently. A hit establishes presence, not page attribution,
uniqueness, speaker identity or the truth of the digest's surrounding prose.
"""
from __future__ import annotations

from collections import OrderedDict
import hashlib
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Callable

from .focus_record_categories import Category, load_category_index
from .quote_search import build_pattern, preprocess_phrase, prepare_search_page

RECORD_SEARCH_CONTRACT = "focus-record-search-1"
MAX_CACHE_CHARS = 16 * 1024 * 1024


def _read(path: Path, limit: int) -> bytes:
    # Lazy import: the shared source reader's owner also uses summary publication.
    from .case_name_stage import _read as source_read
    return source_read(path, limit)


class RecordQuoteSearch:
    """One generation's read-only inventory and bounded lazy page cache.

    Stop callbacks run between pages. Source reads reject links/special files via
    the existing source-reader boundary. Only canonical numbered text pages are
    inspected, never summaries, images, model output or other bundle files.
    """
    def __init__(self, text_dir: Path, *, check_stop: Callable[[], None] | None = None):
        self.text_dir = Path(text_dir)
        self.check_stop = check_stop or (lambda: None)
        self.paths = {int(p.stem): p for p in sorted(self.text_dir.glob('*.txt'))
                      if re.fullmatch(r'\d{4}', p.stem)}
        artifacts = self.text_dir.parent / 'artifacts'
        self.layout = SimpleNamespace(
            transcript_page_numbers_path=artifacts / 'transcript_page_numbers.json',
            source_map_path=artifacts / 'source_map.json',
            hearing_boundaries_path=artifacts / 'hearing_boundaries.json',
            report_boundaries_path=artifacts / 'report_boundaries.json',
            motion_boundaries_path=artifacts / 'motion_boundaries.json',
            minutes_boundaries_path=artifacts / 'minutes_boundaries.json',
        )
        # Same strict eligibility as Focus: do not strip a report/table gutter
        # just because the current quote was extracted from a hearing.
        index = load_category_index(self.layout, self.paths, require_nonconflicting_body=True)
        self.reading_pages = frozenset(page for page, entry in index.items()
            if entry.category == Category.HEARING and entry.status == 'classified'
            and entry.provenance in {'transcript', 'source_map', 'boundary'})
        self._cache: OrderedDict[int, tuple[tuple[int, ...], str]] = OrderedDict()
        self._cache_chars = 0

    @staticmethod
    def _signature(path: Path) -> tuple[int, ...]:
        stat = path.lstat()
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns

    def _page(self, number: int) -> str:
        path = self.paths[number]
        signature = self._signature(path)
        old = self._cache.pop(number, None)
        if old is not None:
            self._cache_chars -= len(old[1])
            if old[0] == signature:
                self._cache[number] = old
                self._cache_chars += len(old[1])
                return old[1]
        raw = _read(path, 16 * 1024 * 1024).decode('utf-8')
        # Focus normalizes physical newlines on read, before layout detection.
        raw = raw.replace('\r\n', '\n').replace('\r', '\n')
        if self._signature(path) != signature:
            raise ValueError('Record quote-search source changed during verification.')
        text = prepare_search_page(raw, transcript=number in self.reading_pages)
        if len(text) <= MAX_CACHE_CHARS:
            while self._cache and self._cache_chars + len(text) > MAX_CACHE_CHARS:
                _, (_, evicted) = self._cache.popitem(last=False)
                self._cache_chars -= len(evicted)
            self._cache[number] = signature, text
            self._cache_chars += len(text)
        return text

    def matches(self, quote: str, reported_page: int) -> bool:
        phrase = preprocess_phrase(quote.strip())
        if not phrase.strip():
            return False
        regex = re.compile(build_pattern(phrase), re.IGNORECASE | re.DOTALL)
        pages = ([reported_page] if reported_page in self.paths else [])
        pages.extend(page for page in self.paths if page != reported_page)
        for number in pages:
            self.check_stop()
            if regex.search(self._page(number)) is not None:
                return True
        return False

    def fingerprint(self) -> str:
        """Bind freshness to the full searchable record, not just this document."""
        digest = hashlib.sha256()
        digest.update(RECORD_SEARCH_CONTRACT.encode())
        digest.update(repr(sorted(self.reading_pages)).encode())
        for number, path in self.paths.items():
            self.check_stop()
            raw = _read(path, 16 * 1024 * 1024)
            digest.update(f'\n{number}:'.encode())
            digest.update(hashlib.sha256(raw).digest())
        return digest.hexdigest()
