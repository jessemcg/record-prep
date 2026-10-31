"""Pure task-specific vision instructions, shared by runtime and inspection."""
from __future__ import annotations

import json
from .profile_contract import CLASSIFICATION_PAGE_TYPES
from .prompt_document import PromptDocument, PromptSection
from .structured_guidance import effective_resource

INSTRUCTIONS = """Examine the attached page image. Use only visible evidence, preserve uncertainty, and do not invent information.
Return only the specified JSON object, without commentary or extra keys."""
BEST_FIT = "Compare all category descriptions and choose the single best-supported fit."
FIRST_TASKS = {
    "first_hearing": "Review a page labeled RT_body in a legal transcript image. Decide whether this is the first page of the hearing for the particular case that is called. Ignore page numbers. If the page shows that hearing starting, answer yes; otherwise answer no.",
    "first_minute": "Review a page labeled CT_minute_order in a legal transcript image. Decide whether this is clearly the first page of the minute order, not a continuation. Answer yes if clearly the start; otherwise answer no.",
    "first_form": "Review a page labeled CT_form in a legal transcript image. Decide whether this is clearly the first page of the form, not a continuation. Answer yes if clearly the start; otherwise answer no.",
    "first_report": "Review a page labeled CT_report in a legal transcript image. Decide whether this is clearly the first page of a distinct report, not a continuation. Check each page independently: two reports can be directly adjacent. Detect starts even when the report has no approved output name. Answer yes if clearly the start; otherwise answer no.",
}
REPORT_FIRST_CLUES = """Look for a prominent report heading with a fresh opening layout, identifying fields, a report/hearing date, preparer or agency attribution, or introductory sections.
A first-page indicator can support a start. Repeated headings or report names in headers/footers alone do not establish a new report; continuing text or later sections without a fresh opening are continuation pages. Do not require an approved report name or decide whether this report should be summarized."""
DATE_TASKS = {
    "date_hearing": "Read the image of the first hearing page in a legal transcript. Extract the hearing date from the body text near the top of the page.",
    "date_minute": "Read the image of the minute order first page in a legal transcript. Extract the minute order date from the body text.",
}
DATE_RULES = """Ignore headers, footers, page numbers, and file stamps. Use a long-form U.S. date like March 5, 2019. Do not include the day of the week. If the date is missing or unclear, use an empty string. Return one JSON object with only the string key "date", for example {"date": "March 5, 2019"} or {"date": ""}."""


def classifier_document(tasks: dict, kind: str) -> PromptDocument:
    sections = [PromptSection("instructions", INSTRUCTIONS)]
    tasks = effective_resource(tasks, "classification_tasks")
    structured = "page_types" in tasks
    if kind in CLASSIFICATION_PAGE_TYPES:
        keys = CLASSIFICATION_PAGE_TYPES[kind]
        side = "reporter's transcript (RT)" if kind == "rt" else "clerk's transcript (CT)"
        sections.append(PromptSection("classification task", f"Classify one {side} page from an appellate record.\n" + BEST_FIT))
        sections.append(PromptSection("allowed labels and JSON", "Allowed page_type values: " + json.dumps(keys)
                       + ".\nExample response: " + json.dumps({"page_type": keys[0]})))
        sections.append(PromptSection("category descriptions heading", "Category Descriptions"))
        if structured:
            for key in keys:
                sections.append(PromptSection(key, key + "\n" + tasks["page_types"][kind].get(key, ""), "profile"))
        else:
            sections.append(PromptSection("legacy " + kind + " compatibility guidance", tasks.get(kind, ""), "profile"))
    elif kind in FIRST_TASKS:
        sections.append(PromptSection("first-page task", FIRST_TASKS[kind]))
        clues = tasks["first_pages"].get(kind, "") if structured else tasks.get(kind, "")
        if kind == "first_report" and not clues:
            # Older immutable profiles have no report-start field. Supply the
            # new application method without rewriting or splitting their prose.
            clues = REPORT_FIRST_CLUES
        sections.append(PromptSection("recognition clues", clues, "profile"))
        sections.append(PromptSection("JSON", 'Return {"first_page": "yes"} or {"first_page": "no"}.'))
    elif kind in DATE_TASKS:
        sections.append(PromptSection("date extraction", DATE_TASKS[kind] + "\n" + DATE_RULES))
    else:
        raise ValueError("Unsupported classification task")
    return PromptDocument(tuple(sections))
