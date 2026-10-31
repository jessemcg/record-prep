"""Summary launch-message assembly with explicit Pi skill expansion.

Inputs are frozen stage configs, not settings discovery. Runtime data may be
literal placeholders when inspecting; no generic formatting touches user prose.
"""
from __future__ import annotations
from .prompt_document import PromptDocument, PromptSection as S

# Re-export the established summary API and identity; request bytes are unchanged.
from .skill_commands import SKILL_DELIVERY_CONTRACT, skill_launch


def extraction_document(skill_name, item, config, candidate_path):
    sections = [S("launch", skill_launch(skill_name, "Run the loaded extraction skill now for the current document.")),
                S("document metadata", f"item_id: {item.item_id}\nordinal: {item.ordinal}\nlabel: {item.label}\npage range: {item.start_page}-{item.end_page}\ncandidate_path: {candidate_path}", "runtime"),
                S("category order", "category ids in order: " + ", ".join(d.identifier for d in config.definitions)),
                S("guidance heading", "\nEXTRACTION GUIDANCE — DIGEST CONTRACT"),
                S("digest contract and topics", config.guidance, "profile"),
                S("per-category heading", "\nPER-CATEGORY GUIDANCE")]
    sections.extend(S("topic " + d.identifier, f"- {d.identifier}: {d.guidance}", "profile") for d in config.definitions)
    if config.additional_guidance:
        sections.extend((S("additional heading", "\nADDITIONAL USER GUIDANCE — lower priority than the built-in contracts above:"),
                         S("additional guidance", config.additional_guidance, "profile")))
    sections.append(S("source instruction", "\nThe work specification file is available to your tools; read the complete document source, then submit once."))
    return PromptDocument(tuple(sections), "\n")


def synthesis_document(skill_name, total_rows, config, candidate_path):
    sections = [S("launch", skill_launch(skill_name, "Run the loaded synthesis skill now for the complete digest dataset.")),
                S("dataset metadata", f"total rows: {total_rows}\ncandidate_path: {candidate_path}", "runtime"),
                S("blank", ""), S("narrative contract and topics", str(config.get("guidance") or ""), "profile")]
    additional = str(config.get("additional_guidance") or "")
    if additional.strip():
        sections.extend((S("additional heading", "\nADDITIONAL USER GUIDANCE — lower priority than the built-in contracts above:"),
                         S("additional guidance", additional, "profile")))
    return PromptDocument(tuple(sections), "\n")


def minute_document(config):
    return PromptDocument((S("launch", skill_launch("recordprep-summarize-minutes", "Summarize the current minute order directly from its complete source pages.\nMINUTE-ORDER CONTRACT\n")),
                           S("minute contract and practice guidance", config["guidance"], "profile"),
                           S("additional heading", "\nADDITIONAL USER GUIDANCE (subordinate)\n"),
                           S("additional guidance", config["additional_guidance"], "profile"),
                           S("source instruction", "\nRead the source tool, then submit the structured summary.")), "")
