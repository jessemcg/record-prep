"""Ephemeral, literal reporter-transcript presentation. No GTK or research imports.

Offsets are Python/GTK Unicode character positions. Each emitted character owns
an original half-open range. Non-whitespace characters are retained verbatim;
inserted whitespace owns the intervening source layout. Nothing is persisted.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
import re

MAX_PAGE_BYTES = 256 * 1024
_MIN_UNMARKED_PAGE_CHARS = 600
_GUTTER_NUMBER_WORDS = frozenset(str(n) for n in range(1, 36)) | frozenset(f"{n:02}" for n in range(1, 10))
_GUTTER = re.compile(r"^(?P<pad>[ \t]*)(?P<num>\d{1,2})[ \t]*(?P<bar>[|│┃║])\s*")
_PLAIN = re.compile(r"^(?P<pad>[ \t]*)(?P<num>\d{1,2})(?:[ \t]{2,}|[ \t]*$)")
_BAR = re.compile(r"^[ \t]*[|│┃║][ \t]*")
_RULE = re.compile(r"^[ \t|│┃║─━═_+┼┤├┬┴┌┐└┘-]{8,}$")
_SPEAKER = (
    r"(?:(?:BY[ \t]+)?(?:(?:MR|MS|MRS|DR)(?:\.[ \t]*|[ \t]+)|"
    r"(?:ATTORNEY|DEPUTY)[ \t]+)[^\W\d_](?:[^\W\d_]|[ .’'\-]){0,64}:"
    r"|THE[ \t]+(?:COURT|WITNESS|CLERK|BAILIFF|REPORTER|INTERPRETER|JURY|"
    r"DEFENDANT|PETITIONER|RESPONDENT|MOTHER|FATHER|MINOR|CHILD):)")
_LABEL = re.compile(rf"^(?:{_SPEAKER}|[QA][.:](?=[ \t]|$))", re.I)
_INLINE_LABEL = re.compile(rf"(?<!\S)(?:{_SPEAKER}|[QA][.:](?=[ \t]|$))", re.I)
_QUOTED_LABEL = re.compile(r'''"[^"\n]*"|“[^”\n]*”|‘[^’\n]*’|(?<!\w)'[^'\n]*'(?!\w)''')
_INITIAL_BEFORE = re.compile(r"(?:^|\s)(?:[A-Z]\.|(?:MR|MS|MRS|DR)\.)\s*$", re.I)
_BARE_QA = re.compile(r"^[QA](?=\s)")
_HEADING = re.compile(r"^(?:(?:DIRECT|CROSS|REDIRECT|RECROSS|FURTHER)\s+EXAMINATION|"
                      r"EXAMINATION|BY\s+(?:MR|MS|MRS|DR)\.?\s+[^:]+:?|"
                      r"APPEARANCES:?|(?:DATE|TIME|DEPARTMENT):.*|DEPARTMENT\s+\d+.*|"
                      r"(?:BEFORE THE HONORABLE|CASE NO\.?|SUPERIOR COURT|COUNTY OF|"
                      r"IN THE (?:(?:SUPERIOR|DISTRICT|CIRCUIT) )?COURT|IN THE MATTER OF|"
                      r"STATE OF|HONORABLE|REPORTED BY|REPORTER)\b.*)$", re.I)
_EXAMINATION = re.compile(r"^(?:(?:(?:DIRECT|CROSS|REDIRECT|RECROSS|FURTHER)\s+)?EXAMINATION|"
                          r"BY[ \t]+(?:MR|MS|MRS|DR)\.?[ \t]+[^:\n]+:?)$", re.I)
_PAGE = re.compile(r"^(?:\d{1,6}|\d*(?:RT|CT)\s+\d+|PAGE\s+\d+.*|\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]\.?M\.?)?)$", re.I)
_DATE = re.compile(r"^(?:(?:MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY),?\s+)?"
                   r"(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)"
                   r"\s+\d{1,2},?\s+\d{4}$", re.I)
_LIST_ROW = re.compile(r"^(?:EXHIBIT|ITEM|SECTION)\s+(?:NO\.?\s*)?\d+\b", re.I)
_TABLE = re.compile(r"\S[ \t]{3,}\S.*[ \t]{3,}\S|\S\s*[|│║]\s*\S.*[|│║]")
_POSSIBLE_GUTTER = re.compile(r"(?m)^[ \t]*\d{1,2}(?:[ \t]*[|│┃║]|[ \t]{2,}(?=\S))")
# Start with the digit class so Python's regex engine can skip prose quickly.
# The left whitespace boundary is checked only at the sparse numeric matches.
_NUMBER_TOKEN = re.compile(r"(?P<num>[0-9]+)")
# Literal-first lookbehind lets the engine seek sparse '2' characters rather
# than test a whitespace lookbehind at every character of ordinary prose.
_TWENTIES_WORD = re.compile(r"2(?<=\s2)[0-9](?=\s|$)")
_NUMBER_ROW = re.compile(r"[ \t]*(?P<num>[1-9]|[12][0-9]|3[0-5])[ \t]*")
_TIMESTAMP = re.compile(r"^(?:\d{1,4}[-/]\d{1,2}[-/]\d{1,4})\s+"
                        r"\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AP]\.?M\.?)?$", re.I)
_FIELD = re.compile(r"^[A-Z][A-Z .'/&-]{1,40}:\s*")


@dataclass(frozen=True)
class OffsetMap:
    starts: tuple[int, ...]
    ends: tuple[int, ...]
    source_length: int

    def source_span(self, start: int, end: int) -> tuple[int, int]:
        """Display selection/anchor to original Unicode character range."""
        start = max(0, min(start, len(self.starts)))
        end = max(start, min(end, len(self.starts)))
        if end > start:
            return self.starts[start], self.ends[end - 1]
        anchor = self.starts[start] if start < len(self.starts) else self.source_length
        return anchor, anchor

    def display_span(self, start: int, end: int) -> tuple[int, int]:
        """Original span to visible span; removed gutters select no extra text."""
        if end <= start:
            pos = bisect_left(self.starts, start)
            return pos, pos
        left = bisect_right(self.ends, start)
        right = bisect_left(self.starts, end)
        return left, max(left, right)


@dataclass(frozen=True)
class ProjectionMap:
    """Piecewise identity map; search needs no per-character allocation."""
    display_starts: tuple[int, ...]
    source_starts: tuple[int, ...]
    source_length: int

    def source_span(self, start: int, end: int) -> tuple[int, int]:
        left = max(0, bisect_right(self.display_starts, start) - 1)
        right = max(0, bisect_right(self.display_starts, max(start, end - 1)) - 1)
        return (self.source_starts[left] + start - self.display_starts[left],
                self.source_starts[right] + end - self.display_starts[right])


@dataclass(frozen=True)
class Presentation:
    text: str
    mapping: OffsetMap
    styles: tuple[tuple[int, int], ...] = ()
    removed: tuple[tuple[int, int], ...] = ()
    diagnostic: str = "readable"


@dataclass(frozen=True)
class Layout:
    lines: tuple[tuple[int, int], ...]
    removed: tuple[tuple[int, int], ...]
    double_spaced: bool
    structured: bool
    # Ends of individual inline markers, before adjacent blank rows merge.
    wraps: tuple[int, ...] = ()


def within_limit(source: str) -> bool:
    return len(source) <= MAX_PAGE_BYTES and len(source.encode("utf-8")) <= MAX_PAGE_BYTES


def _line_spans(source: str) -> tuple[tuple[int, int], ...]:
    lines = []
    offset = 0
    for line in source.splitlines(keepends=True):
        end = offset + len(line.rstrip("\r\n"))
        lines.append((offset, end))
        offset += len(line)
    return tuple(lines)


def _number_tokens(source: str):
    for match in _NUMBER_TOKEN.finditer(source):
        start, end = match.span()
        if (end - start <= 2 and 1 <= int(match["num"]) <= 35
                and (start == 0 or source[start - 1].isspace())
                and (end == len(source) or source[end].isspace())):
            yield match


def _detached_number_rows(source: str, lines: tuple[tuple[int, int], ...]) -> list[tuple[int, int]]:
    """Confirm an alternating 1–28-style number/text column, not a short list."""
    if len(source) < _MIN_UNMARKED_PAGE_CHARS:
        return []
    occupied = [(a, b) for a, b in lines if source[a:b].strip()]
    pairs = []
    for index, (start, end) in enumerate(occupied[:-1]):
        match = _NUMBER_ROW.fullmatch(source[start:end])
        a, b = occupied[index + 1]
        if match and not _NUMBER_ROW.fullmatch(source[a:b]):
            pairs.append((int(match["num"]), start, a, b))
    if len(pairs) < 20:
        return []
    nums = [row[0] for row in pairs]
    if (nums[0] > 4 or nums[-1] < 24
            or any(not 1 <= b - a <= 3 for a, b in zip(nums, nums[1:]))
            or sum(b == a + 1 for a, b in zip(nums, nums[1:])) < (len(nums) - 1) * .8):
        return []
    payloads = [source[a:b].strip() for _, _, a, b in pairs]
    # Most rows must resemble wrapped physical lines, not complete numbered
    # propositions. Numbered lists with sentence-per-item structure stay intact.
    if (sum(30 <= len(text) <= 100 for text in payloads) < len(pairs) * .7
            or sum(text.endswith((".", "?", "!", ":", ";")) for text in payloads) > len(pairs) * .45
            or len(pairs) * 2 < len(occupied) * .85):
        return []
    return [(start, a + len(source[a:b]) - len(source[a:b].lstrip()))
            for _, start, a, b in pairs]


def _complete_short_column(source: str, tokens: list[tuple[int, int, int]]) -> bool:
    """Short/blank rows need a nearly complete, unambiguous column plus dialogue.

    Unlike the partial-column path, every candidate must be in order, so a
    repeated or out-of-order substantive quantity disqualifies this relaxation.
    Long physical-line intervals still have to corroborate the short ones.
    """
    if (len(tokens) < 24 or tokens[0][0] > 4 or tokens[-1][0] < 24
            or tokens[-1][1] - tokens[0][1] < len(source) * .65):
        return False
    steps = [b[0] - a[0] for a, b in zip(tokens, tokens[1:])]
    if (any(step not in (1, 2) for step in steps)
            or steps.count(1) < len(steps) * .9
            or any(b[1] - a[1] > 95 * (b[0] - a[0]) for a, b in zip(tokens, tokens[1:]))):
        return False
    long_rows = sum(35 <= b[1] - a[1] <= 85 for a, b in zip(tokens, tokens[1:]) if b[0] == a[0] + 1)
    if long_rows < max(8, len(steps) * .35):
        return False
    boundaries = 0
    blank_rows = 0
    for index, (_, _, end) in enumerate(tokens[:-1]):
        payload = source[end:tokens[index + 1][1]].strip()
        blank_rows += not payload
        boundaries += bool(_LABEL.match(payload) or payload.startswith("("))
    return boundaries >= 2 or (boundaries >= 1 and blank_rows >= 2)


def _flattened_number_column(source: str, lines: tuple[tuple[int, int], ...]) -> list[tuple[int, int]]:
    """Recover only a dense, regular, ascending latent physical-line column.

    At most 35 sequence states are retained. A substantive number encountered
    out of order (e.g. 12 months after line 15) cannot join the confirmed chain.
    No number is removed on the strength of its value alone.
    """
    if len(source) < _MIN_UNMARKED_PAGE_CHARS:
        return []
    tokens = []
    for line_start, line_end in lines:
        line = source[line_start:line_end]
        first = len(line) - len(line.lstrip())
        last = len(line.rstrip())
        for match in _number_tokens(line):
            if match.start() <= first or match.end() >= last:
                continue
            tokens.append((int(match["num"]), line_start + match.start(), line_start + match.end()))
    if _complete_short_column(source, tokens):
        chain = tokens
    else:
        states: dict[int, tuple[tuple[int, int, int], ...]] = {}
        for number, start, end in tokens:
            prior = [states[n] for n in range(max(1, number - 3), number)
                     if n in states and 18 <= (start - states[n][-1][1]) / (number - n) <= 95]
            chain = max(prior, key=len, default=()) + ((number, start, end),)
            if len(chain) > len(states.get(number, ())):
                states[number] = chain
        chain = max(states.values(), key=len, default=())
        if (len(chain) < 16 or chain[0][0] > 4 or chain[-1][0] < 24
                or chain[-1][1] - chain[0][1] < len(source) * .65):
            return []
        consecutive = [(b[1] - a[1]) for a, b in zip(chain, chain[1:]) if b[0] == a[0] + 1]
        if (len(consecutive) < (len(chain) - 1) * .75
                or sum(35 <= distance <= 85 for distance in consecutive) < len(consecutive) * .85):
            return []
    spans = []
    for _, start, end in chain:
        while end < len(source) and source[end] in " \t":
            end += 1
        spans.append((start, end))
    return spans


def analyze_layout(source: str, *, search_only: bool = False,
                   unmarked_only: bool = False) -> Layout:
    """Analyze one page; search may hint that three prefix rows were disproved."""
    lines = _line_spans(source)
    candidates = []
    for index, (start, end) in (() if unmarked_only else enumerate(lines)):
        line = source[start:end]
        match = _GUTTER.match(line) or _PLAIN.match(line)
        if match and 1 <= int(match["num"]) <= 35:
            # Numeric columns may be right-aligned; compare their right edge.
            candidates.append((index, match, match.end("num")))
    confirmed = []
    for bar in (True, False):
        rows = [(i, m, col) for i, m, col in candidates if ("bar" in m.re.groupindex) == bar]
        if len(rows) < (3 if bar else 10):
            continue
        columns = [col for _, _, col in rows]
        if max(columns) - min(columns) > (1 if bar else 0):
            continue
        if not bar and not (any(len(m["num"]) == 1 for _, m, _ in rows)
                            and any(len(m["num"]) == 2 for _, m, _ in rows)):
            # Without a rule marker, require the one-/two-digit transition to
            # prove right alignment; ordinary left-aligned numbered lists stay.
            continue
        nums = [int(m["num"]) for _, m, _ in rows]
        if any(b <= a for a, b in zip(nums, nums[1:])):
            continue
        if sum(b == a + 1 for a, b in zip(nums, nums[1:])) < (len(nums) - 1) * .65:
            continue
        # Bare numbers need a physical column on most nonempty lines. This
        # deliberately leaves short/ambiguous lists and missing columns alone.
        nonempty = sum(bool(source[s:e].strip()) for s, e in lines)
        if not bar and (len(rows) < nonempty * .7 or
                        sum(41 <= len(source[lines[i][0] + m.end():lines[i][1]]) <= 120
                            for i, m, _ in rows) < len(rows) * .6):
            continue
        confirmed.extend((lines[i][0], lines[i][0] + m.end()) for i, m, _ in rows)
        if bar:
            for start, end in lines:
                match = _BAR.match(source[start:end])
                if match and abs(match.end() - rows[0][1].end()) <= 4:
                    confirmed.append((start, start + match.end()))
    prefix_confirmed = bool(confirmed)
    if not prefix_confirmed and sum(bool(_LIST_ROW.match(source[a:b].strip())) for a, b in lines) >= 2:
        return Layout(lines, (), False, True)
    detached = [] if confirmed else _detached_number_rows(source, lines)
    confirmed.extend(detached)
    flattened = [] if confirmed else _flattened_number_column(source, lines)
    wraps = tuple(end for _, end in flattened)
    confirmed.extend(flattened)
    if confirmed:
        for start, end in lines:
            if _RULE.fullmatch(source[start:end]):
                confirmed.append((start, end))
    removed = _merge_spans(confirmed)
    if (search_only and not prefix_confirmed
            and not any(marker in source for marker in "|│┃║")
            and "   " not in source and "\t" not in source):
        # Unmarked removal cannot create a table separator/column. Removing an
        # interior token or a detached numeric row also cannot change the first
        # substantive word of a line. The raw list veto already ran above;
        # search needs neither projected line spans nor double-spacing analysis.
        return Layout(lines, removed, False, False, wraps)
    projected, _ = _remove_layout_spans(source, removed)
    clean_lines = [line.strip() for line in projected.splitlines()]
    occupied = [i for i, line in enumerate(clean_lines) if line]
    gaps = [b - a for a, b in zip(occupied, occupied[1:])]
    physical_lines = sum(len(clean_lines[i]) <= 120 for i in occupied)
    double = (not wraps and len(gaps) >= 3 and sum(g == 2 for g in gaps) >= len(gaps) * .85
              and physical_lines >= len(occupied) * .8)
    structured_rows = 0
    list_rows = 0
    for line in clean_lines:
        # Avoid the table pattern's full prose scan when neither column spacing
        # nor a separator exists. This matters especially for flattened pages.
        if "   " in line or "\t" in line or any(bar in line for bar in "|│┃║"):
            structured_rows += bool(_TABLE.search(line))
        list_rows += bool(_LIST_ROW.match(line))
        if structured_rows >= 2 or list_rows >= 2:
            break
    structured = structured_rows >= 2 or list_rows >= 2
    return Layout(tuple(lines), removed, double, structured, wraps)


def _merge_spans(spans: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    result = []
    for start, end in sorted(set(spans)):
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(end, result[-1][1]))
        else:
            result.append((start, end))
    return tuple(result)


def search_layout(source: str) -> Layout | None:
    """Bounded gutter decisions only; callers may reuse this within one scan."""
    if len(source) > MAX_PAGE_BYTES:
        return None
    bar = any(marker in source for marker in "|│┃║")
    horizontal = bar or "  " in source or "\t" in source
    candidates = _POSSIBLE_GUTTER.finditer(source) if horizontal else iter(())
    prefix_evidence = not any(next(candidates, None) is None for _ in range(3))
    if not prefix_evidence:
        # Detached/flattened columns need dense numeric evidence. A page label,
        # isolated quantity, date or ordinary short list is a cheap rejection.
        # Any qualifying ascending run reaching 24+ with steps <= 3 has at
        # least two values in the twenties. This literal-first test rejects
        # ordinary prose without splitting it or allocating character maps.
        twenties = _TWENTIES_WORD.finditer(source)
        if (len(source) < _MIN_UNMARKED_PAGE_CHARS
                or next(twenties, None) is None or next(twenties, None) is None
                or len(_GUTTER_NUMBER_WORDS.intersection(source.split())) < 16):
            return None
    if not within_limit(source):
        return None
    layout = analyze_layout(source, search_only=True, unmarked_only=not prefix_evidence)
    return layout if layout.removed and not layout.structured else None


def search_projection(source: str, *, mapped: bool = False,
                      layout: Layout | None = None) -> tuple[str, ProjectionMap | None]:
    """Gutter-only search, no casing/reflow and no map on the rejection pass."""
    layout = layout or search_layout(source)
    if layout is None or not layout.removed or layout.structured:
        return source, None
    return _remove_layout_spans(source, layout.removed, mapped=mapped)


def _remove_layout_spans(source: str, removed: tuple[tuple[int, int], ...], *,
                         mapped: bool = False) -> tuple[str, ProjectionMap | None]:
    pieces = []
    display_starts = []
    source_starts = []
    previous = 0
    size = 0
    for start, end in (*removed, (len(source), len(source))):
        if start > previous:
            pieces.append(source[previous:start])
            if mapped:
                display_starts.append(size)
                source_starts.append(previous)
            size += start - previous
        previous = end
    mapping = ProjectionMap(tuple(display_starts), tuple(source_starts), len(source)) if mapped and pieces else None
    return "".join(pieces), mapping


def original_presentation(source: str, diagnostic: str = "original") -> Presentation:
    return Presentation(source, OffsetMap(tuple(range(len(source))),
                        tuple(range(1, len(source) + 1)), len(source)), diagnostic=diagnostic)


def _speaker_starts(source: str, recovered: set[int]) -> set[int]:
    """Explicit turns, independent of gutter detection; never infer a speaker.

    Inline labels need a statement boundary (or a retained possible line number).
    Obvious quoted labels and honorific/initial sequences are not new turns.
    """
    matches = list(_INLINE_LABEL.finditer(source))
    paired_qa = ({m.group()[0].upper() for m in matches if len(m.group()) == 2} >= {"Q", "A"})
    quoted = tuple(m.span() for m in _QUOTED_LABEL.finditer(source))
    quote_index = 0
    starts = set()
    for match in matches:
        start = match.start()
        while quote_index < len(quoted) and quoted[quote_index][1] <= start:
            quote_index += 1
        if quote_index < len(quoted) and quoted[quote_index][0] <= start < quoted[quote_index][1]:
            continue
        previous = start - 1
        newline = False
        while previous >= 0 and source[previous].isspace():
            newline |= source[previous] in "\r\n"
            previous -= 1
        physical = previous < 0 or newline or start in recovered
        if not physical:
            qa = len(match.group()) == 2
            if qa and (not paired_qa or _INITIAL_BEFORE.search(source[max(0, start - 20):start])):
                continue
            number_start = previous
            while number_start >= 0 and source[number_start].isdigit():
                number_start -= 1
            possible_number = (previous - number_start in (1, 2)
                               and (number_start < 0 or source[number_start].isspace()))
            if source[previous] not in ".?!:)" and not possible_number:
                continue
        starts.add(start)
    return starts


def _reading_line_spans(source: str, mapping: ProjectionMap | None,
                        wraps: tuple[int, ...]) -> tuple[list[tuple[int, int]], set[int]]:
    """Restore proven physical starts for display, without changing search text.

    Adjacent blank numbered rows share a retained boundary. Keep duplicate cuts:
    the empty row between them is real paragraph-separation evidence.
    """
    cuts = []
    if mapping:
        for end in wraps:
            index = bisect_left(mapping.source_starts, end)
            cuts.append(mapping.display_starts[index] if index < len(mapping.display_starts) else len(source))
    recovered = set()
    for cut in cuts:
        while cut < len(source) and source[cut].isspace():
            cut += 1
        recovered.add(cut)
    turns = _speaker_starts(source, recovered)
    cuts.extend(turns.difference(cuts))
    cuts.sort()
    rows = []
    index = 0
    for start, end in _line_spans(source):
        while index < len(cuts) and cuts[index] < start:
            index += 1
        while index < len(cuts) and cuts[index] <= end:
            rows.append((start, cuts[index]))
            start = cuts[index]
            index += 1
        rows.append((start, end))
    return rows, turns


def render_readable(source: str) -> Presentation:
    if not within_limit(source):
        # Oversized fallback must not allocate a per-character map.
        return Presentation(source, OffsetMap((), (), len(source)), diagnostic="original:oversized")
    original = source
    layout = analyze_layout(source)
    if layout.structured:
        return original_presentation(source, "original:structured")
    removed = layout.removed
    source, projection_map = search_projection(source, mapped=True, layout=layout)
    offsets = None
    if projection_map:
        offsets = []
        boundaries = (*projection_map.display_starts, len(source))
        for index, start in enumerate(projection_map.source_starts):
            offsets.extend(range(start, start + boundaries[index + 1] - boundaries[index]))
    reading_rows, turns = _reading_line_spans(source, projection_map, layout.wraps)
    physical_starts = {a + len(source[a:b]) - len(source[a:b].lstrip()) for a, b in _line_spans(source)}
    rows = []
    for start, end in reading_rows:
        while start < end and source[start].isspace():
            start += 1
        while end > start and source[end - 1].isspace():
            end -= 1
        rows.append((start, end))
    # Bare A is also an ordinary article. Accept unpunctuated Q/A labels only
    # when both sides of the convention appear on this page.
    bare_qa = (any(source[a:b].startswith(("Q ", "Q.", "Q:")) for a, b in rows)
               and any(source[a:b].startswith(("A ", "A.", "A:")) for a, b in rows))
    paragraphs: list[list[tuple[int, int]]] = []
    blank = False
    parenthetical = 0
    previous_structural = False
    in_body = False
    for start, end in rows:
        text = source[start:end]
        if not text:
            blank = True
            continue
        speaker = (_LABEL.match(text) if start in turns else None) or (_BARE_QA.match(text) if bare_qa else None)
        field = not in_body and not speaker and bool(_FIELD.match(text))
        # Captions/fields are front matter, never inferred topic paragraphs in
        # speech. Saved physical rows may also contain standalone exam headings.
        heading = _HEADING.fullmatch(text) and (not in_body or _EXAMINATION.fullmatch(text))
        structural = start in physical_starts and bool(
            heading or _PAGE.fullmatch(text)
            or _DATE.fullmatch(text) or _TIMESTAMP.fullmatch(text) or field)
        boundary = bool(speaker or text.startswith("(") or structural)
        if not structural:
            in_body = True
        if not paragraphs or (not parenthetical and (boundary or previous_structural
                                or (blank and not layout.double_spaced))):
            paragraphs.append([])
        paragraphs[-1].append((start, end))
        parenthetical = max(0, parenthetical + text.count("(") - text.count(")"))
        previous_structural = structural
        blank = False
    output = []
    starts: list[int] = []
    ends: list[int] = []
    styles = []
    size = 0
    previous_end = 0
    for rows in paragraphs:
        first = source[rows[0][0]:rows[0][1]]
        label = (_LABEL.match(first) if rows[0][0] in turns else None) or (_BARE_QA.match(first) if bare_qa else None)
        if output:
            output.append("\n\n")
            starts.extend([previous_end] * 2)
            ends.extend([offsets[rows[0][0]] if offsets is not None else rows[0][0]] * 2)
            size += 2
        para_start = size
        # Structural formatting only: every retained character stays verbatim.
        joined = ""
        source_ranges = []
        for start, end in rows:
            if joined:
                separator = "" if joined.endswith("-") else " "
                joined += separator
                source_start = offsets[start] if offsets is not None else start
                source_ranges.extend([(previous_end, source_start)] * len(separator))
            joined += source[start:end]
            source_ranges.extend((offsets[i], offsets[i] + 1) if offsets is not None else (i, i + 1)
                                 for i in range(start, end))
            previous_end = offsets[end - 1] + 1 if offsets is not None else end
        starts.extend(a for a, _ in source_ranges)
        ends.extend(b for _, b in source_ranges)
        output.append(joined)
        size += len(joined)
        if label:
            styles.append((para_start, para_start + label.end()))
    text = "".join(output)
    mapping = OffsetMap(tuple(starts), tuple(ends), len(original))
    if (len(starts) != len(text) or len(ends) != len(text)
            or any(a > b for a, b in zip(starts, starts[1:]))
            or any(a > b for a, b in zip(ends, ends[1:]))):
        return original_presentation(original, "original:mapping")
    return Presentation(text, mapping, tuple(styles), removed)
