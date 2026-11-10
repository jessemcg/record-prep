"""Pure task-specific vision instructions, shared by runtime and inspection."""
from __future__ import annotations

import json
from .profile_contract import CLASSIFICATION_PAGE_TYPES
from .prompt_document import PromptDocument, PromptSection
from .recognition_contract import RecognitionContract, load_recognition

INSTRUCTIONS = """Examine the attached page image. Use only visible evidence, preserve uncertainty, and do not invent information.
Return only the specified JSON object, without commentary or extra keys."""
BEST_FIT = "Compare all category descriptions and choose the single best-supported fit."
FIRST_TASKS = {
    "first_motion": "Review a page labeled CT_motion in a legal transcript image. Decide whether this is clearly the first page of a distinct motion paper, not a continuation. Check every page independently, including adjacent papers and separately titled oppositions, replies and supporting declarations. Detect starts even without an approved name. Answer yes if clearly the start; otherwise answer no.",
    "first_hearing": "Review a page labeled RT_body in a legal transcript image. Decide whether this is the first page of the hearing for the particular case that is called. Ignore page numbers. If the page shows that hearing starting, answer yes; otherwise answer no.",
    "first_minute": "Review a candidate labeled CT_minute_order in a legal transcript image. The label is a hypothesis, not proof. Decide whether this is clearly a fresh opening of an actual minute record, not a separate order or continuation. Answer yes only for a supported minute opening; otherwise answer no. A false underlying category needs nonminute correction, not merely demotion to a minute body.",
    "first_form": "Review a page labeled CT_form in a legal transcript image. Decide whether this is clearly the first page of the procedural filing, not a continuation. Answer yes if clearly the start; otherwise answer no.",
    "first_report": "Review a page labeled CT_report in a legal transcript image. Decide whether this is clearly the first page of a distinct report, not a continuation. Check each page independently: two reports can be directly adjacent. Detect starts even when the report has no approved output name. Answer yes if clearly the start; otherwise answer no.",
}
# Historical exact-match data only; never a runtime recognition fallback.
REPORT_FIRST_CLUES = """Look for a prominent report heading with a fresh opening layout, identifying fields, a report/hearing date, preparer or agency attribution, or introductory sections.
A first-page indicator can support a start. Repeated headings or report names in headers/footers alone do not establish a new report; continuing text or later sections without a fresh opening are continuation pages. Do not require an approved report name or decide whether this report should be summarized."""
DATE_TASKS = {
    "date_hearing": "Read the image of the first hearing page in a legal transcript. Extract the hearing date from the body text near the top of the page.",
    "date_minute": "Read the image of a candidate minute first page. Establish minute identity under the supplied current definition, then extract the date of the recorded proceeding/minute record from its identifying date field, including top-of-page hearing fields.",
}
DATE_RULES = """Ignore headers, footers, page numbers, and file stamps. Use a long-form U.S. date like March 5, 2019. Do not include the day of the week. If the date is missing or unclear, use an empty string. Return one JSON object with only the string key "date", for example {"date": "March 5, 2019"} or {"date": ""}."""

MINUTE_DATE_RULES = """Ignore unrelated filing/service stamps, print/template-revision dates, dates of referenced reports or petitions, and future settings. Return an empty string if this page does not establish a minute record or its relevant date is missing, conflicting or unreadable. Never borrow a neighboring document's date or infer one to make the candidate eligible. Use a long-form U.S. date like March 5, 2019, without the weekday. Return one JSON object with only the string key "date", for example {"date": "March 5, 2019"} or {"date": ""}."""


def classifier_document(kind: str, contract: RecognitionContract | None = None) -> PromptDocument:
    """Fixed task + frozen application contract, never profile task data."""
    contract = contract if contract is not None else load_recognition()
    if not isinstance(contract, RecognitionContract):
        raise ValueError("Expected a frozen application recognition contract")
    sections = [PromptSection("instructions", INSTRUCTIONS)]
    if kind in CLASSIFICATION_PAGE_TYPES:
        keys = CLASSIFICATION_PAGE_TYPES[kind]
        side = "reporter's transcript (RT)" if kind == "rt" else "clerk's transcript (CT)"
        sections.append(PromptSection("classification task", f"Classify one {side} page from an appellate record.\n" + BEST_FIT))
        sections.append(PromptSection("allowed labels and JSON", "Allowed page_type values: " + json.dumps(keys)
                       + ".\nExample response: " + json.dumps({"page_type": keys[0]})))
        sections.append(PromptSection("category descriptions heading", "Category Descriptions"))
        for key, description in contract.descriptions(kind):
            sections.append(PromptSection(key, key + "\n" + description))
    elif kind in FIRST_TASKS:
        sections.append(PromptSection("first-page task", FIRST_TASKS[kind]))
        sections.append(PromptSection("recognition clues", contract.clues(kind)))
        sections.append(PromptSection("JSON", 'Return {"first_page": "yes"} or {"first_page": "no"}.'))
    elif kind in DATE_TASKS:
        if kind == "date_minute":
            sections.append(PromptSection("minute identity", dict(contract.descriptions("ct"))["CT_minute_order"]))
        rules = MINUTE_DATE_RULES if kind == "date_minute" else DATE_RULES
        sections.append(PromptSection("date extraction", DATE_TASKS[kind] + "\n" + rules))
    else:
        raise ValueError("Unsupported classification task")
    return PromptDocument(tuple(sections))
