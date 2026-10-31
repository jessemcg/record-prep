"""Pure task-specific vision instructions, shared by runtime and inspection."""
from __future__ import annotations

import json
from .profile_contract import CLASSIFICATION_PAGE_TYPES
from .prompt_document import PromptDocument, PromptSection
from .structured_guidance import classification_task_resource

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
# Application-owned neutral fallbacks for schema 1, which has no task resource.
# Retired Common guidance is deliberately never a fallback source.
PAGE_DESCRIPTIONS = {
    "rt": {
        "RT_cover": "Case-identifying cover or title page. A repeated caption above dialogue does not make a dialogue page a cover.",
        "RT_index": "Index or table listing witnesses, subjects, exhibits or proceedings with page references, rather than spoken proceedings.",
        "RT_body": "Verbatim spoken proceedings with speaker labels or question-and-answer dialogue. A caption or heading may repeat above the dialogue.",
        "RT_certificate": "Reporter or clerk certification or attestation about transcript accuracy or preparation, usually with a signature, rather than dialogue.",
        "RT_other": "Other reporter-transcript material that best fits none of the cover, index, dialogue or certification descriptions.",
    },
    "ct": {
        "CT_cover": "Cover or section title identifying the clerk's transcript. A repeated case caption on a substantive document is not itself a cover.",
        "CT_index": "Index or table of contents listing filed documents with page references.",
        "CT_minute_order": "Court or clerk record of a hearing and judicial action, often with appearances and orders. Requested relief or an authored recommendation alone is not a judicial minute order.",
        "CT_report": "Authored narrative or evaluative report, including its continuation pages, with attribution, findings, assessments or recommendations. Proposed relief within a report is not an actual judicial order.",
        "CT_form": "Structured court form with labeled fields, boxes or standard sections; a form identifier or title can support recognition. No specialty-specific form list is required.",
        "CT_certificate": "Clerk's or other official certificate authenticating the transcript, filing or documents, rather than a narrative report or motion.",
        "CT_motion": "Party's application or motion seeking judicial action, possibly with supporting argument. Distinguish the request from a court's ruling.",
        "CT_notice": "Formal notice communicating a hearing, proceeding or other procedural event.",
        "CT_proof_of_service": "Declaration, certificate or return documenting service of identified papers, with method, recipient or service date.",
        "CT_other": "Other filed material, records, exhibits, correspondence or orders that best fit none of the listed structural descriptions.",
    },
}
FIRST_CLUES = {
    "first_hearing": "Look for the court calling the case and an opening exchange or appearances. Repeated captions and printed page numbers alone do not establish a new hearing.",
    "first_minute": "Look for a fresh minute-order heading, identifying hearing fields and the opening of the order. Repeated headers or continuing order items alone do not establish a start.",
    "first_form": "Look for the form title, identifying fields and beginning of its sections. Page 1 of X can support a start; a repeated heading on a later page is not enough.",
    "first_report": REPORT_FIRST_CLUES,
}
DATE_TASKS = {
    "date_hearing": "Read the image of the first hearing page in a legal transcript. Extract the hearing date from the body text near the top of the page.",
    "date_minute": "Read the image of the minute order first page in a legal transcript. Extract the minute order date from the body text.",
}
DATE_RULES = """Ignore headers, footers, page numbers, and file stamps. Use a long-form U.S. date like March 5, 2019. Do not include the day of the week. If the date is missing or unclear, use an empty string. Return one JSON object with only the string key "date", for example {"date": "March 5, 2019"} or {"date": ""}."""


def classifier_document(tasks: dict, kind: str) -> PromptDocument:
    sections = [PromptSection("instructions", INSTRUCTIONS)]
    tasks = classification_task_resource(tasks, kind)
    structured = "page_types" in tasks
    if kind in CLASSIFICATION_PAGE_TYPES:
        keys = CLASSIFICATION_PAGE_TYPES[kind]
        side = "reporter's transcript (RT)" if kind == "rt" else "clerk's transcript (CT)"
        sections.append(PromptSection("classification task", f"Classify one {side} page from an appellate record.\n" + BEST_FIT))
        sections.append(PromptSection("allowed labels and JSON", "Allowed page_type values: " + json.dumps(keys)
                       + ".\nExample response: " + json.dumps({"page_type": keys[0]})))
        sections.append(PromptSection("category descriptions heading", "Category Descriptions"))
        if structured or not tasks:
            descriptions = tasks["page_types"][kind] if structured else PAGE_DESCRIPTIONS[kind]
            for key in keys:
                sections.append(PromptSection(key, key + "\n" + descriptions[key], "profile" if structured else "fixed"))
        else:
            sections.append(PromptSection("legacy " + kind + " compatibility guidance", tasks.get(kind, ""), "profile"))
    elif kind in FIRST_TASKS:
        sections.append(PromptSection("first-page task", FIRST_TASKS[kind]))
        clues = tasks["first_pages"].get(kind, "") if structured else tasks.get(kind, "")
        fallback = not clues
        if fallback:
            # Schema 1 lacks task clues; later old profiles lack report starts.
            # Supply the neutral method without consulting retired Common prose.
            clues = FIRST_CLUES[kind]
        sections.append(PromptSection("recognition clues", clues, "fixed" if fallback else "profile"))
        sections.append(PromptSection("JSON", 'Return {"first_page": "yes"} or {"first_page": "no"}.'))
    elif kind in DATE_TASKS:
        sections.append(PromptSection("date extraction", DATE_TASKS[kind] + "\n" + DATE_RULES))
    else:
        raise ValueError("Unsupported classification task")
    return PromptDocument(tuple(sections))
