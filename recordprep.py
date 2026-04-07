#!/usr/bin/env python3

from __future__ import annotations

import base64
import sys
import datetime
import os
import importlib
import json
import random
import re
import shutil
import subprocess
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk, GObject  # type: ignore

import fitz
import pdftotext
from pypdf import PdfReader, PdfWriter
import requests
from bs4 import BeautifulSoup
from bs4.element import NavigableString
from pylatexenc.latex2text import LatexNodes2Text
from tabulate import tabulate

APPLICATION_ID = "com.mcglaw.RecordPrep"
APPLICATION_NAME = "Record Prep"
STARTUP_LOG_PATH = Path("/tmp/recordprep_startup.log")

GLib.set_application_name(APPLICATION_NAME)

LLM_MAX_RETRIES = 5
LLM_RETRY_BASE_SECONDS = 1.0
LLM_RETRY_MAX_SECONDS = 30.0
LLM_RETRYABLE_HTTP_CODES = {408, 409, 429, 500, 502, 503, 504}
LOCAL_OCR_SERVER_STARTUP_SECONDS = 1.0
LOCAL_VISION_SERVER_STARTUP_SECONDS = 2.0
LOCAL_SERVER_READY_TIMEOUT_SECONDS = 120.0
LOCAL_SERVER_READY_POLL_SECONDS = 1.0
VISION_CLASSIFICATION_STEP_IDS = {
    "classify_basic",
    "classify_advanced",
    "classify_dates",
    "classify_names",
}
MODEL_ID = "LightOnOCR-2-1B-Q8_0.gguf"
DEFAULT_SERVER_URL = "http://localhost:8000/v1/chat/completions"
START_SERVER_COMMAND = """\
cd $HOME/llama.cpp/build/bin
./llama-server \
-m $HOME/llama.cpp/models/LightOnOCR-2-1B-Q8_0.gguf \
--mmproj $HOME/llama.cpp/models/mmproj-LightOnOCR-2-1B-Q8_0.gguf \
-ngl 999 --port 8000 --flash-attn on
"""


class StopRequested(RuntimeError):
    pass


def _log_startup(message: str) -> None:
    try:
        timestamp = datetime.datetime.now().isoformat(sep=" ", timespec="seconds")
        with STARTUP_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"{timestamp} {message}\n")
    except OSError:
        pass

CONFIG_FILE = Path(__file__).with_name("config.json")
CONFIG_KEY_CLASSIFIER_API_URL = "classifier_api_url"
CONFIG_KEY_CLASSIFIER_MODEL_ID = "classifier_model_id"
CONFIG_KEY_CLASSIFIER_API_KEY = "classifier_api_key"
CONFIG_KEY_CLASSIFIER_PROMPT = "classifier_prompt"
CONFIG_KEY_CLASSIFIER_RT_PROMPT = "classifier_rt_prompt"
CONFIG_KEY_CLASSIFIER_CT_PROMPT = "classifier_ct_prompt"
CONFIG_KEY_CLASSIFIER_THINKING_ENABLED = "classifier_thinking_enabled"
CONFIG_KEY_CLASSIFIER_DISABLE_REASONING = "classifier_disable_reasoning"
CONFIG_KEY_CLASSIFIER_LOCAL_VISION_ENABLED = "classifier_local_vision_enabled"
CONFIG_KEY_CLASSIFIER_LOCAL_VISION_START_COMMAND = "classifier_local_vision_start_command"
CONFIG_KEY_CLASSIFY_DATES_HEARING_PROMPT = "classify_dates_hearing_prompt"
CONFIG_KEY_CLASSIFY_DATES_MINUTE_PROMPT = "classify_dates_minute_prompt"
CONFIG_KEY_CLASSIFY_NAMES_REPORT_PROMPT = "classify_names_report_prompt"
CONFIG_KEY_CLASSIFY_NAMES_FORM_PROMPT = "classify_names_form_prompt"
CONFIG_KEY_CASE_NAME_API_URL = "case_name_api_url"
CONFIG_KEY_CASE_NAME_MODEL_ID = "case_name_model_id"
CONFIG_KEY_CASE_NAME_API_KEY = "case_name_api_key"
CONFIG_KEY_CASE_NAME_DISABLE_REASONING = "case_name_disable_reasoning"
CONFIG_KEY_CASE_NAME_PROMPT = "case_name_prompt"
CONFIG_KEY_CASE_NAME = "case_name"
CONFIG_KEY_CASE_ROOT_DIR = "case_root_dir"
CONFIG_KEY_TEXT_SOURCE = "text_source"
CONFIG_KEY_LOCAL_OCR_SERVER_URL = "local_ocr_server_url"
CONFIG_KEY_LOCAL_OCR_MODEL_ID = "local_ocr_model_id"
CONFIG_KEY_LOCAL_OCR_START_COMMAND = "local_ocr_start_command"
CONFIG_KEY_ADVANCED_CLASSIFY_API_URL = "advanced_classify_api_url"
CONFIG_KEY_ADVANCED_CLASSIFY_MODEL_ID = "advanced_classify_model_id"
CONFIG_KEY_ADVANCED_CLASSIFY_API_KEY = "advanced_classify_api_key"
CONFIG_KEY_ADVANCED_CLASSIFY_HEARING_PROMPT = "advanced_classify_hearing_prompt"
CONFIG_KEY_ADVANCED_CLASSIFY_MINUTE_PROMPT = "advanced_classify_minute_prompt"
CONFIG_KEY_ADVANCED_CLASSIFY_FORM_PROMPT = "advanced_classify_form_prompt"

MAX_CASE_NAME_LEN = 120
MAX_CASE_NAME_DISPLAY_LEN = 80
CONFIG_KEY_CLASSIFY_FORMS_API_URL = "classify_form_names_api_url"
CONFIG_KEY_CLASSIFY_FORMS_MODEL_ID = "classify_form_names_model_id"
CONFIG_KEY_CLASSIFY_FORMS_API_KEY = "classify_form_names_api_key"
CONFIG_KEY_CLASSIFY_FORMS_PROMPT = "classify_form_names_prompt"
CONFIG_KEY_OPTIMIZE_HEARING_API_URL = "optimize_hearing_api_url"
CONFIG_KEY_OPTIMIZE_HEARING_MODEL_ID = "optimize_hearing_model_id"
CONFIG_KEY_OPTIMIZE_HEARING_API_KEY = "optimize_hearing_api_key"
CONFIG_KEY_OPTIMIZE_HEARING_DISABLE_REASONING = "optimize_hearing_disable_reasoning"
CONFIG_KEY_OPTIMIZE_REPORT_API_URL = "optimize_report_api_url"
CONFIG_KEY_OPTIMIZE_REPORT_MODEL_ID = "optimize_report_model_id"
CONFIG_KEY_OPTIMIZE_REPORT_API_KEY = "optimize_report_api_key"
CONFIG_KEY_OPTIMIZE_REPORT_DISABLE_REASONING = "optimize_report_disable_reasoning"
CONFIG_KEY_OPTIMIZE_ATTORNEY_API_URL = "optimize_attorney_api_url"
CONFIG_KEY_OPTIMIZE_ATTORNEY_MODEL_ID = "optimize_attorney_model_id"
CONFIG_KEY_OPTIMIZE_ATTORNEY_API_KEY = "optimize_attorney_api_key"
CONFIG_KEY_OPTIMIZE_ATTORNEY_DISABLE_REASONING = "optimize_attorney_disable_reasoning"
CONFIG_KEY_OPTIMIZE_CHUNK_SIZE = "optimize_chunk_size"
CONFIG_KEY_OPTIMIZE_MAX_TOKENS = "optimize_max_tokens"
CONFIG_KEY_OPTIMIZE_ATTORNEYS_PROMPT = "optimize_attorneys_prompt"
CONFIG_KEY_OPTIMIZE_HEARINGS_PROMPT = "optimize_hearings_prompt"
CONFIG_KEY_OPTIMIZE_REPORTS_PROMPT = "optimize_reports_prompt"
CONFIG_KEY_SUMMARIZE_API_URL = "summarize_api_url"
CONFIG_KEY_SUMMARIZE_MODEL_ID = "summarize_model_id"
CONFIG_KEY_SUMMARIZE_API_KEY = "summarize_api_key"
CONFIG_KEY_SUMMARIZE_DISABLE_REASONING = "summarize_disable_reasoning"
CONFIG_KEY_SUMMARIZE_HEARINGS_PROMPT = "summarize_hearings_prompt"
CONFIG_KEY_SUMMARIZE_REPORTS_PROMPT = "summarize_reports_prompt"
CONFIG_KEY_SUMMARIZE_MINUTES_PROMPT = "summarize_minutes_prompt"
CONFIG_KEY_SUMMARIZE_CHUNK_SIZE = "summarize_chunk_size"
CONFIG_KEY_OVERVIEW_API_URL = "overview_api_url"
CONFIG_KEY_OVERVIEW_MODEL_ID = "overview_model_id"
CONFIG_KEY_OVERVIEW_API_KEY = "overview_api_key"
CONFIG_KEY_OVERVIEW_DISABLE_REASONING = "overview_disable_reasoning"
CONFIG_KEY_OVERVIEW_PROMPT = "overview_prompt"
CONFIG_KEY_RAG_PROVIDER = "rag_provider"
CONFIG_KEY_RAG_VOYAGE_API_KEY = "rag_voyage_api_key"
CONFIG_KEY_RAG_VOYAGE_MODEL = "rag_voyage_model"
CONFIG_KEY_RAG_ISAACUS_API_KEY = "rag_isaacus_api_key"
CONFIG_KEY_RAG_ISAACUS_MODEL = "rag_isaacus_model"
CONFIG_KEY_SELECTED_PDFS = "selected_pdfs"
CONFIG_KEY_RT_CT_SPLIT_PAGE = "rt_ct_split_page"
CONFIG_KEY_RUN_UNTIL_STEP = "run_until_step"
TEXT_SOURCE_EMBEDDED = "embedded"
TEXT_SOURCE_LOCAL_OCR = "local_ocr"
DEFAULT_TEXT_SOURCE = TEXT_SOURCE_EMBEDDED
DEFAULT_LOCAL_VISION_START_COMMAND = ""
RAG_PROVIDER_VOYAGE = "voyage"
RAG_PROVIDER_ISAACUS = "isaacus"
DEFAULT_RAG_PROVIDER = RAG_PROVIDER_VOYAGE
DEFAULT_CLASSIFIER_PROMPT = (
    "You are labeling a single page of a legal transcript. "
    "Return JSON with keys: \"page_type\". "
    "page_type must be one of: hearing_page, minute_order_page, report_page, form_page, other. "
    "Use hearing_page for hearing transcript pages, minute_order_page for minute orders, "
    "report_page for reports, form_page for court/JV forms, and other for everything else. "
    "Examples:\n"
    "Hearing page example: \"APPEARANCES:\\nTHE COURT: ...\\nTHE WITNESS: ...\" "
    "-> {\"page_type\":\"hearing_page\"}\n"
    "Minute order page example: \"MINUTE ORDER\" \"Judicial Officer\" \"Case No.\" "
    "-> {\"page_type\":\"minute_order_page\"}\n"
    "Report page example: \"Psychological Evaluation\" \"Prepared by\" "
    "-> {\"page_type\":\"report_page\"}\n"
    "Form page example: \"Juvenile Court Petition\" \"Form JV-100\" "
    "-> {\"page_type\":\"form_page\"}\n"
    "Other example: \"Table of Contents\" -> {\"page_type\":\"other\"}"
)
DEFAULT_CLASSIFY_HEARING_DATES_PROMPT = (
    "You are extracting the hearing date from the text of the first hearing page "
    "in a legal transcript. "
    "The date is usually near the top and not in the footer. "
    "Return JSON with keys: date. "
    "date should be a long-form U.S. date if present. "
    "If unknown, use an empty string."
)
DEFAULT_CLASSIFY_MINUTE_DATES_PROMPT = (
    "You are extracting the minute order date from the text of the minute order first page "
    "in a legal transcript. "
    "Return JSON with keys: date. "
    "date should be a long-form U.S. date if present. "
    "If unknown, use an empty string."
)
DEFAULT_CLASSIFY_REPORT_NAMES_PROMPT = (
    "You are reviewing the text of the first page of a report in a legal transcript. "
    "Only return a report name if it matches the approved list provided. "
    "Return JSON with keys: name. "
    "name must be the matching report title from the list; otherwise use an empty string."
)
DEFAULT_ADVANCED_HEARING_PROMPT = (
    "You are reviewing a page labeled RT_body in a legal transcript. "
    "Determine if this is the first page of the hearing. "
    "Ignore page numbers. Look for the court calling the case name or docket number "
    "and parties announcing their appearances. "
    "Return JSON with keys: first_page. "
    "first_page must be yes or no."
)
DEFAULT_ADVANCED_MINUTE_PROMPT = (
    "You are reviewing a page labeled CT_minute_order in a legal transcript. "
    "Determine if this is the first page of the minute order (e.g., Page 1 of X). "
    "Return JSON with keys: first_page. "
    "first_page must be yes or no."
)
DEFAULT_ADVANCED_FORM_PROMPT = (
    "You are reviewing a page labeled CT_form in a legal transcript. "
    "Determine if this is the first page of the form (e.g., Page 1 of X). "
    "Return JSON with keys: first_page. "
    "first_page must be yes or no."
)
DEFAULT_CLASSIFY_FORM_NAMES_PROMPT = (
    "You are reviewing the text of the first page of a form in a legal transcript. "
    "Only return a form name if it matches the approved list provided. "
    "Return JSON with keys: name. "
    "name must be the matching form title from the list; otherwise use an empty string."
)
DEFAULT_CASE_NAME_PROMPT = (
    "You are inferring the case name from the first three pages of a legal transcript. "
    "Return only the case name as plain text. "
    "The case name should replace spaces with underscores, like In_re_Mark_T or "
    "Social_Services_v_Breanna_F. "
    "If unknown, use an empty string."
)
DEFAULT_OPTIMIZE_ATTORNEYS_PROMPT = (
    "You are building a case-level counsel role map for a juvenile court case. "
    "Return only valid JSON. Do not include markdown fences or any explanatory text. "
    "Return an object with keys: roles, unknown_speaker_labels, notes. "
    "roles must be an array of objects with keys: role, attorney_names, speaker_aliases, confidence. "
    "role must be one of: MOTHER'S COUNSEL, FATHER'S COUNSEL, ALLEGED FATHER'S COUNSEL, "
    "PRESUMED FATHER'S COUNSEL, PARENT'S COUNSEL, MINOR'S COUNSEL, COUNTY COUNSEL, "
    "TRIBE'S COUNSEL, OTHER COUNSEL. "
    "Normalize department or agency counsel to COUNTY COUNSEL. "
    "Normalize child or children's counsel to MINOR'S COUNSEL. "
    "attorney_names must be an array of full attorney names when known. "
    "speaker_aliases must be an array of exact speaker labels or close label variants from the record. "
    "confidence must be one of: high, medium, low. "
    "unknown_speaker_labels must be an array of speaker labels or names that appear but whose role is unclear. "
    "notes must be a short string and may be empty. "
    "If no role can be identified, return {\"roles\":[],\"unknown_speaker_labels\":[],\"notes\":\"\"}."
)
DEFAULT_OPTIMIZE_HEARINGS_PROMPT = (
    "TASK\n"
    "Reformat the hearing transcript into chunks for retrieval with speaker labels.\n\n"
    "CORE RULES\n"
    "1. Preserve every statement exactly as written.\n"
    "2. However, add speaker labels before each statement.\n"
    "3. For any attorney or counsel speaker, insert a counsel-role label instead of an attorney-name label whenever the role is clear from the reference counsel-role JSON.\n"
    "4. Use role labels such as 'MOTHER'S COUNSEL:', 'FATHER'S COUNSEL:', 'MINOR'S COUNSEL:', or 'COUNTY COUNSEL:' rather than labels such as 'MS. SMITH:' or 'MR. JONES:' when the speaker is counsel.\n"
    "5. If the transcript already uses an attorney-name label for counsel and the role is clear, replace that attorney-name label with the correct counsel-role label while preserving the spoken words exactly.\n"
    "6. Preserve non-counsel speaker labels such as 'THE COURT:' exactly as written.\n"
    "7. If a counsel speaker's role is unclear, preserve the original speaker label rather than guessing.\n"
    "8. If a statement lacks a speaker label, add the shortest accurate label you can from the transcript and reference JSON.\n"
    "9. Treat any counsel-role reference section as context only. Never quote it, summarize it, or use it to rewrite the transcript wording.\n"
    "10. Keep the original order of events.\n"
    "11. Do not summarize, omit, generalize, or add commentary.\n\n"
    "CLEANUP RULES\n"
    "• Remove repeated headers and footers.\n"
    "• Normalize spacing and sentence case.\n"
    "• Ignore all tables, including ASCII tables.\n\n"
    "OUTPUT FORMAT\n"
    "• Organize the statements with speaker labels into paragraphs of about five sentences each.\n"
    "• Each paragraph must appear on exactly one physical line of output.\n"
    "• Replace every line break inside a paragraph with a space.\n"
    "• Use line breaks only to separate paragraphs.\n"
    "• Separate paragraphs with one blank line."
)
DEFAULT_OPTIMIZE_REPORTS_PROMPT = (
    "TASK\n"
    "Reformat the report into chunks for retrieval.\n\n"
    "CORE RULES\n"
    "1. Preserve every statement exactly as written.\n"
    "2. Keep the original order of events.\n"
    "3. Do not summarize, omit, generalize, or add commentary.\n\n"
    "CLEANUP RULES\n"
    "• Remove repeated headers and footers.\n"
    "• Normalize spacing and sentence case.\n"
    "• Ignore all tables, including ASCII tables.\n\n"
    "OUTPUT FORMAT\n"
    "• Organize the statements into paragraphs of about five sentences each.\n"
    "• Each paragraph must appear on exactly one physical line of output.\n"
    "• Replace every line break inside a paragraph with a space.\n"
    "• Use line breaks only to separate paragraphs.\n"
    "• Separate paragraphs with one blank line."
)
DEFAULT_OPTIMIZE_CHUNK_SIZE = 10000
DEFAULT_OPTIMIZE_MAX_TOKENS = 8192
DEFAULT_SUMMARIZE_HEARINGS_PROMPT = (
    "Summarize the following court hearing in one very concise paragraph using plain "
    "and simple English. Include short direct quotes (3-6 words) from the hearing to "
    "highlight legally significant statements. Each quote must be in quotation marks "
    "and must be verbatim. Do not use ellipses. Do not add commentary or markdown. "
    "Do not begin with prefatory language. Do not include the hearing date in the summary. "
    "Here is the hearing:"
)
DEFAULT_SUMMARIZE_REPORTS_PROMPT = (
    "Summarize the following reports in one very concise paragraph using plain "
    "and simple English. Include short direct quotes (5-10 words) from the reports to "
    "highlight legally significant statements. Each quote must be in quotation marks "
    "and must be verbatim. Do not use ellipses. Do not add commentary or markdown. "
    "Do not begin with prefatory language. Here are the reports:"
)
DEFAULT_SUMMARIZE_MINUTES_PROMPT = (
    "I will provide you with the pages of a minute order. Based on this information, "
    "state the name of the hearing, whether the hearing was reported, whether one or "
    "both parents were present, and what the juvenile court ordered. The description "
    "of what the juvenile court ordered must be brief and concise. Only state that a "
    "parent is present if the minute order indicates that the parent is present on the "
    "first page of the minute order. If only a parent's attorney is listed, assume that "
    "the parent is not present. Do not insert any line breaks. Here are three examples "
    "of the proper format:\n\nDetention Hearing. Reported. No parent appeared. The "
    "juvenile court ordered the children temporarily removed from the parents.\n\n"
    "Receipt of Report Hearing. Not Reported. No parent appeared. The juvenile court "
    "received the section 361.66 report into evidence.\n\nPermanent Plan Review "
    "Hearing. Reported. Only mother appeared. The juvenile court received the social "
    "worker reports into evidence and heard testimony from mother. The juvenile court "
    "terminated parental rights.\n\nOkay, here is the minute order:"
)
DEFAULT_SUMMARIZE_CHUNK_SIZE = 15
DEFAULT_OVERVIEW_PROMPT = (
    "I will provide you with hearing summaries, report summaries, and minute order "
    "summaries from a legal case. Produce output using exactly these three markdown "
    "headings and no others. Use normal markdown heading syntax with the `## ` prefix "
    "(for example, `## Parties`).\n\n"
    "## Parties\n"
    "Write one concise paragraph identifying the parties and specifying which attorney "
    "represented each party. Identify each attorney by name rather than only by law "
    "firm.\n\n"
    "## Factual History\n"
    "Write a chronological list from earliest to latest of the most significant "
    "factual events (what happened out of court). Each list item must start with a "
    "date in long-form U.S. style (Month D, YYYY, for example January 5, 2024) and "
    "then one concise sentence describing the event. Include no more than 20 events. "
    "If there are more than 20 significant events, include only the most significant "
    "20.\n\n"
    "## Procedural History\n"
    "Write a chronological list from earliest to latest of the most significant "
    "procedural events (what happened in court). Each list item must start with a "
    "date in long-form U.S. style (Month D, YYYY, for example January 5, 2024) and "
    "then one concise sentence describing the event. Include no more than 20 events. "
    "If there are more than 20 significant events, include only the most significant "
    "20.\n\n"
    "Do not add any other headings, preface text, or commentary. Okay, here are the "
    "summaries:"
)
PREVIOUS_DEFAULT_OVERVIEW_PROMPT = (
    "I will provide you with hearing summaries, report summaries, and minute order "
    "summaries from a legal case. Produce output using exactly these two markdown "
    "headings and no others.\n\n"
    "## Parties\n"
    "Write one concise paragraph identifying the parties and specifying which attorney "
    "represented each party. Identify each attorney by name rather than only by law "
    "firm.\n\n"
    "## Case Chronology\n"
    "Write a chronological list from earliest to latest. Each list item must start "
    "with a date and then one concise sentence describing a significant event. Events "
    "may be factual or procedural. Include no more than 20 events total. If there are "
    "more than 20 significant events, include only the most significant 20.\n\n"
    "Do not add any other headings, preface text, or commentary. Okay, here are the "
    "summaries:"
)
LEGACY_DEFAULT_OVERVIEW_PROMPT = (
    "I will provide you with summaries from a legal case. Please provide concise "
    "details about the case in the form of three paragraphs. In the first paragraph, "
    "identify the parties and specify which attorney represented them. Identify each "
    "attorney by name rather than just their law firm. In the second paragraph, "
    "provide a procedural history of the case. In the third paragraph, provide a "
    "factual history of the case. Do not add any other commentary. Okay, here are the "
    "summaries:"
)
DEFAULT_RAG_VOYAGE_MODEL = "voyage-law-2"
DEFAULT_RAG_ISAACUS_MODEL = "kanon-2-embedder"
COUNSEL_ROLE_ORDER = (
    "MOTHER'S COUNSEL",
    "FATHER'S COUNSEL",
    "ALLEGED FATHER'S COUNSEL",
    "PRESUMED FATHER'S COUNSEL",
    "PARENT'S COUNSEL",
    "MINOR'S COUNSEL",
    "COUNTY COUNSEL",
    "TRIBE'S COUNSEL",
    "OTHER COUNSEL",
)
COUNSEL_ROLE_ALIASES = {
    "mothers counsel": "MOTHER'S COUNSEL",
    "mother counsel": "MOTHER'S COUNSEL",
    "mothers attorney": "MOTHER'S COUNSEL",
    "father counsel": "FATHER'S COUNSEL",
    "fathers counsel": "FATHER'S COUNSEL",
    "father attorney": "FATHER'S COUNSEL",
    "alleged father counsel": "ALLEGED FATHER'S COUNSEL",
    "alleged fathers counsel": "ALLEGED FATHER'S COUNSEL",
    "presumed father counsel": "PRESUMED FATHER'S COUNSEL",
    "presumed fathers counsel": "PRESUMED FATHER'S COUNSEL",
    "parents counsel": "PARENT'S COUNSEL",
    "parent counsel": "PARENT'S COUNSEL",
    "minor counsel": "MINOR'S COUNSEL",
    "minors counsel": "MINOR'S COUNSEL",
    "child counsel": "MINOR'S COUNSEL",
    "childrens counsel": "MINOR'S COUNSEL",
    "children counsel": "MINOR'S COUNSEL",
    "county counsel": "COUNTY COUNSEL",
    "department counsel": "COUNTY COUNSEL",
    "agency counsel": "COUNTY COUNSEL",
    "tribe counsel": "TRIBE'S COUNSEL",
    "tribes counsel": "TRIBE'S COUNSEL",
    "other counsel": "OTHER COUNSEL",
}
COUNSEL_ROLE_EXTRACTION_CHUNK_SIZE = 10000
DEFAULT_DISABLE_REASONING = False
ISAACUS_MAX_EMBED_BATCH = 128


def _model_looks_kimi(model_id: str) -> bool:
    normalized = (model_id or "").strip().lower()
    return "kimi" in normalized or "moonshot" in normalized


def _model_looks_deepseek(model_id: str) -> bool:
    normalized = (model_id or "").strip().lower()
    return "deepseek" in normalized


def _extract_embedding_vectors(response: Any) -> list[list[float]]:
    embeddings = getattr(response, "embeddings", None)
    if embeddings is None and isinstance(response, dict):
        embeddings = response.get("embeddings")
    if not isinstance(embeddings, list):
        raise ValueError("Invalid embeddings response format.")
    vectors: list[list[float]] = []
    for item in embeddings:
        vector = getattr(item, "embedding", None)
        if vector is None and isinstance(item, dict):
            vector = item.get("embedding")
        if not isinstance(vector, list):
            raise ValueError("Missing embedding vector in response.")
        vectors.append(vector)
    return vectors


class IsaacusEmbeddings:
    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        cleaned_texts: list[str] = []
        for text in texts:
            if text is None:
                cleaned_texts.append("")
            elif isinstance(text, str):
                cleaned_texts.append(text)
            else:
                cleaned_texts.append(str(text))
        vectors: list[list[float]] = []
        for start in range(0, len(cleaned_texts), ISAACUS_MAX_EMBED_BATCH):
            batch = cleaned_texts[start : start + ISAACUS_MAX_EMBED_BATCH]
            response = self._client.embeddings.create(
                model=self._model,
                texts=batch,
                task="retrieval/document",
            )
            batch_vectors = _extract_embedding_vectors(response)
            if len(batch_vectors) != len(batch):
                raise ValueError(
                    "Isaacus returned a mismatched number of embedding vectors."
                )
            vectors.extend(batch_vectors)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        response = self._client.embeddings.create(
            model=self._model,
            texts=[text if isinstance(text, str) else str(text)],
            task="retrieval/query",
        )
        vectors = _extract_embedding_vectors(response)
        if not vectors:
            raise ValueError("Isaacus returned no embedding vectors.")
        return vectors[0]


def _unique_in_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _extract_prompt_keys(prompt: str) -> list[str]:
    if not prompt:
        return []
    lower_prompt = prompt.lower()
    markers = ("names of the keys are", "keys are", "keys:")
    for marker in markers:
        index = lower_prompt.find(marker)
        if index == -1:
            continue
        segment = prompt[index + len(marker) :]
        segment = segment.splitlines()[0]
        if "." in segment:
            segment = segment.split(".", 1)[0]
        tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", segment)
        if tokens:
            return _unique_in_order(tokens)
    json_key_tokens = re.findall(r"['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*:", prompt)
    if json_key_tokens:
        return _unique_in_order(json_key_tokens)
    backtick_tokens = re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)`", prompt)
    if backtick_tokens:
        return _unique_in_order(backtick_tokens)
    return []


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", key.lower())


def _extract_page_number(filename: str) -> int | None:
    match = re.search(r"(\d+)", Path(filename).stem)
    if match:
        return int(match.group(1))
    return None


def _normalize_rt_ct_split_page(value: int | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _normalize_rt_ct_split_mode(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"rt_only", "ct_only", "split"}:
        return normalized
    return "split"


def _read_rt_ct_split_page(root_dir: Path) -> int | None:
    manifest = _read_manifest(root_dir)
    value = manifest.get("rt_ct_split_page")
    return _normalize_rt_ct_split_page(value)


def _read_rt_ct_split_mode(root_dir: Path) -> str:
    manifest = _read_manifest(root_dir)
    return _normalize_rt_ct_split_mode(manifest.get("rt_ct_split_mode"))


def _read_rt_ct_split_page_config() -> int | None:
    config = _read_config()
    return _normalize_rt_ct_split_page(config.get(CONFIG_KEY_RT_CT_SPLIT_PAGE))


def _write_rt_ct_split_page_config(value: int | None) -> None:
    config = _read_config()
    config[CONFIG_KEY_RT_CT_SPLIT_PAGE] = value
    _write_config(config)


def _count_text_pages(text_dir: Path) -> int:
    if not text_dir.exists():
        return 0
    try:
        return len(list(text_dir.glob("*.txt")))
    except OSError:
        return 0


def _resolve_rt_ct_split(root_dir: Path, text_dir: Path) -> tuple[int, int, bool, bool, str]:
    split_mode = _read_rt_ct_split_mode(root_dir)
    total_pages = _count_text_pages(text_dir)
    if split_mode == "rt_only":
        return max(1, total_pages), total_pages, True, False, split_mode
    if split_mode == "ct_only":
        return 0, total_pages, False, True, split_mode
    split_page = _read_rt_ct_split_page(root_dir)
    if split_page is None:
        raise ValueError("Set the RT end page number before running classification.")
    need_rt = split_page >= 1
    need_ct = total_pages > 0 and split_page < total_pages
    return split_page, total_pages, need_rt, need_ct, split_mode


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in {"true", "yes", "y", "1", "relevant", "keep"}


def _load_classify_date_targets(classify_path: Path) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    if not classify_path.exists():
        return targets
    entries: list[tuple[str, str, int]] = []
    with classify_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            file_name = str(payload.get("file_name", "") or "").strip()
            page_type = str(payload.get("page_type", "") or "").strip().lower()
            if not file_name or not page_type:
                continue
            page_number = _extract_page_number(file_name)
            if page_number is None:
                continue
            entries.append((file_name, page_type, page_number))
    for file_name, page_type, page_number in entries:
        if page_type in {
            "hearing_first_page",
            "rt_body_first_page",
            "minute_order_first_page",
            "minute_order_page_first_page",
            "ct_minute_order_first_page",
        }:
            targets.append((file_name, page_type))
    return targets


def _load_classify_report_targets(classify_path: Path) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    if not classify_path.exists():
        return targets
    entries: list[tuple[str, str, int]] = []
    with classify_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            file_name = str(payload.get("file_name", "") or "").strip()
            page_type = str(payload.get("page_type", "") or "").strip().lower()
            if not file_name or not page_type:
                continue
            page_number = _extract_page_number(file_name)
            if page_number is None:
                continue
            entries.append((file_name, page_type, page_number))
    prev_type: str | None = None
    prev_number: int | None = None
    for file_name, page_type, page_number in entries:
        if page_type in {"report", "report_page"}:
            if prev_type not in {"report", "report_page"} or prev_number is None or page_number != prev_number + 1:
                targets.append((file_name, page_type))
            prev_type = page_type
            prev_number = page_number
        else:
            prev_type = None
            prev_number = None
    return targets


def _load_classify_form_targets(classify_path: Path) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    if not classify_path.exists():
        return targets
    with classify_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            file_name = str(payload.get("file_name", "") or "").strip()
            page_type = str(payload.get("page_type", "") or "").strip().lower()
            if not file_name or page_type not in {
                "form_first_page",
                "form_page_first_page",
                "ct_form_first_page",
            }:
                continue
            targets.append((file_name, page_type))
    return targets


def _load_relevant_form_targets(path: Path) -> list[str]:
    entries = _load_jsonl_entries(path)
    targets: list[str] = []
    for entry in entries:
        file_name = _extract_entry_value(entry, "file_name", "filename")
        if file_name:
            targets.append(file_name)
    return targets


def _load_relevant_report_targets(path: Path) -> list[str]:
    entries = _load_jsonl_entries(path)
    targets: list[str] = []
    for entry in entries:
        file_name = _extract_entry_value(entry, "file_name", "filename")
        if file_name:
            targets.append(file_name)
    return targets


def _load_jsonl_entries(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not path.exists():
        return entries
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                entries.append(payload)
    return entries


def _write_jsonl_entries(path: Path, entries: list[dict[str, Any]]) -> None:
    lines = [json.dumps(entry, ensure_ascii=False) for entry in entries if isinstance(entry, dict)]
    payload = "\n".join(lines)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


def _load_combined_jsonl_entries(paths: list[Path]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in paths:
        entries.extend(_load_jsonl_entries(path))
    if not entries:
        return entries
    entries.sort(
        key=lambda entry: _natural_sort_key(_extract_entry_value(entry, "file_name", "filename"))
    )
    return entries


def _load_jsonl_file_names(path: Path) -> set[str]:
    entries = _load_jsonl_entries(path)
    file_names: set[str] = set()
    for entry in entries:
        file_name = _extract_entry_value(entry, "file_name", "filename")
        if file_name:
            file_names.add(file_name)
    return file_names


def _last_jsonl_file_name(path: Path) -> str:
    last_file_name = ""
    if not path.exists():
        return last_file_name
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            file_name = _extract_entry_value(payload, "file_name", "filename")
            if file_name:
                last_file_name = file_name
    return last_file_name


def _dedupe_jsonl_by_file_name(path: Path) -> int:
    entries = _load_jsonl_entries(path)
    if not entries:
        return 0
    by_file: dict[str, dict[str, Any]] = {}
    valid_count = 0
    for entry in entries:
        file_name = _extract_entry_value(entry, "file_name", "filename")
        if not file_name:
            continue
        valid_count += 1
        by_file[file_name] = entry
    deduped_entries = list(by_file.values())
    deduped_entries.sort(
        key=lambda entry: _natural_sort_key(
            _extract_entry_value(entry, "file_name", "filename")
        )
    )
    removed_count = len(entries) - len(deduped_entries)
    if removed_count <= 0 and len(deduped_entries) == len(entries):
        return 0
    with path.open("w", encoding="utf-8") as handle:
        for entry in deduped_entries:
            handle.write(json.dumps(entry))
            handle.write("\n")
    return removed_count if removed_count > 0 else max(len(entries) - valid_count, 0)


def _load_json_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]
    return []


def _extract_entry_value(entry: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if key in entry:
            value = entry.get(key)
            return str(value).strip() if value is not None else ""
    normalized = {_normalize_key(key): key for key in entry}
    for key in keys:
        normalized_key = _normalize_key(key)
        source_key = normalized.get(normalized_key)
        if source_key is not None:
            value = entry.get(source_key)
            return str(value).strip() if value is not None else ""
    return ""


def _extract_page_type_from_jsonish(text: str) -> str:
    if not text:
        return ""
    match = re.search(
        r'["\']?page[_\-\s]?type["\']?\s*:\s*["\']?([A-Za-z0-9_\-]+)["\']?',
        text,
        re.IGNORECASE,
    )
    if not match:
        return ""
    return match.group(1).strip()


def _page_label_from_filename(filename: str) -> str:
    return Path(filename).stem if filename else ""


def _page_number_from_label(label: str) -> int | None:
    if not label:
        return None
    return _extract_page_number(label)


def _format_toc_line(label: str, page: str) -> str:
    if label and page:
        return f"\t{label} {page}"
    if label:
        return f"\t{label}"
    if page:
        return f"\t{page}"
    return "\t"


def _sanitize_case_name_tokens(tokens: list[str]) -> str:
    cleaned: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if lowered in {"v", "vs"}:
            cleaned.append("v")
        elif lowered == "re":
            cleaned.append("re")
        elif lowered == "in":
            cleaned.append("In")
        else:
            cleaned.append(token)
    return "_".join(cleaned)


def _sanitize_case_name_value(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        return ""
    cleaned = re.sub(r"\s+", "_", trimmed)
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.strip("_")


def _limit_case_name_words(value: str, max_words: int = 8) -> str:
    sanitized = _sanitize_case_name_value(value)
    if not sanitized:
        return ""
    parts = [part for part in sanitized.split("_") if part]
    if len(parts) <= max_words:
        return sanitized
    return "_".join(parts[:max_words])


def _looks_like_case_name(value: str) -> bool:
    sanitized = _sanitize_case_name_value(value)
    if not sanitized:
        return False
    lowered = sanitized.lower().replace("_", " ")
    if "we are given" in lowered or "we're given" in lowered:
        return False
    if "first" in lowered and ("page" in lowered or "pages" in lowered):
        return False
    if "given" in lowered and "pages" in lowered:
        return False
    if "transcript" in lowered or "ocr" in lowered:
        return False
    tokens = re.findall(r"[a-zA-Z]+", lowered)
    return bool(tokens)


def _image_path_for_filename(filename: str, image_dir: Path) -> Path:
    if not filename:
        raise FileNotFoundError("Missing filename for image lookup.")
    image_path = image_dir / f"{Path(filename).stem}.png"
    if not image_path.exists():
        raise FileNotFoundError(f"Missing image file {image_path.name} for classification.")
    return image_path


def _normalize_case_name(value: str) -> str:
    sanitized = _sanitize_case_name_value(value)
    if not sanitized:
        return ""
    if len(sanitized) > MAX_CASE_NAME_LEN:
        sanitized = sanitized[:MAX_CASE_NAME_LEN].rstrip("_")
    return sanitized


def _display_case_name(value: str) -> str:
    sanitized = _normalize_case_name(value)
    if not sanitized:
        return ""
    display = sanitized.replace("_", " ")
    if len(display) > MAX_CASE_NAME_DISPLAY_LEN:
        display = f"{display[:MAX_CASE_NAME_DISPLAY_LEN - 3]}..."
    return display


def _load_case_name_from_file(root_dir: Path) -> str:
    case_name_path = root_dir / "case_name.txt"
    if not case_name_path.exists():
        return ""
    try:
        value = case_name_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    return _sanitize_case_name_value(value)


def _summary_output_paths(root_dir: Path) -> tuple[Path, Path]:
    summaries_dir = root_dir / "summaries"
    case_name = _load_case_name_from_file(root_dir)
    if not case_name:
        case_name, _ = load_case_context()
        case_name = _sanitize_case_name_value(case_name)
    if case_name:
        return (
            summaries_dir / f"hearings_sum_{case_name}.txt",
            summaries_dir / f"reports_sum_{case_name}.txt",
        )
    return (
        summaries_dir / "summarized_hearings.txt",
        summaries_dir / "summarized_reports.txt",
    )


def _minutes_summary_output_path(root_dir: Path) -> Path:
    summaries_dir = root_dir / "summaries"
    case_name = _load_case_name_from_file(root_dir)
    if not case_name:
        case_name, _ = load_case_context()
        case_name = _sanitize_case_name_value(case_name)
    if case_name:
        return summaries_dir / f"minutes_sum_{case_name}.txt"
    return summaries_dir / "summarized_minutes.txt"


def _strip_nonstandard_characters(text: str) -> str:
    cleaned_chars: list[str] = []
    for ch in text:
        if ch in {"\n", "\t"}:
            cleaned_chars.append(ch)
        elif unicodedata.category(ch) != "Cc":
            cleaned_chars.append(ch)
    return "".join(cleaned_chars)


@dataclass
class RetrievalSection:
    section_type: str
    content: str
    metadata: dict[str, Any]


@dataclass
class ChunkedSectionFiles:
    section_type: str
    label: str
    directory: Path
    chunk_paths: list[Path]
    metadata: dict[str, Any]


def _canonical_retrieval_metadata_key(label: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
    aliases = {
        "type": "type",
        "hearing_date": "hearing_date",
        "report_name": "report_name",
    }
    return aliases.get(normalized, normalized)


def _parse_retrieval_chunk(paragraph: str) -> tuple[dict[str, Any], str]:
    stripped = paragraph.strip()
    if not stripped:
        return {}, ""

    legacy_body, legacy_date = _strip_hearing_date_prefix(stripped)
    if legacy_date:
        return {
            "type": "hearing",
            "hearing_date": _format_long_us_date(legacy_date) or _normalize_hearing_date(legacy_date),
        }, legacy_body
    if re.match(r"^Reporting:\s*", stripped, re.IGNORECASE):
        return {"type": "report"}, re.sub(r"^Reporting:\s*", "", stripped, flags=re.IGNORECASE)

    metadata: dict[str, Any] = {}
    content_lines: list[str] = []
    content_started = False
    for line in stripped.splitlines():
        raw_line = line.strip()
        if not raw_line:
            continue
        if content_started:
            content_lines.append(raw_line)
            continue
        if raw_line.lower().startswith("content:"):
            content_started = True
            remainder = raw_line.split(":", 1)[1].strip()
            if remainder:
                content_lines.append(remainder)
            continue
        if ":" in raw_line:
            label, value = raw_line.split(":", 1)
            metadata[_canonical_retrieval_metadata_key(label)] = value.strip()
            continue
        content_lines.append(raw_line)
        content_started = True

    section_type = str(metadata.get("type", "")).strip().lower()
    if section_type:
        metadata["type"] = section_type
    hearing_date = str(metadata.get("hearing_date", "")).strip()
    if hearing_date:
        metadata["hearing_date"] = _format_long_us_date(hearing_date) or _normalize_hearing_date(
            hearing_date
        )
    return metadata, "\n".join(content_lines).strip()


def _clean_retrieval_chunk_content(metadata: dict[str, Any], content: str) -> str:
    cleaned = content.strip()
    chunk_type = str(metadata.get("type", "")).strip().lower()
    if chunk_type == "hearing":
        cleaned = re.sub(
            r"^\s*Hearing date:\s*[^.\n]{1,100}\.?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()
    elif chunk_type == "report":
        cleaned = re.sub(r"^\s*Reporting:\s*", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def _render_retrieval_chunk(metadata: dict[str, Any], content: str) -> str:
    return _clean_retrieval_chunk_content(metadata, content)


def _read_boundary_entry_text(entry: dict[str, Any], text_dir: Path) -> str:
    start_label = _extract_entry_value(entry, "start_page", "start", "starte_page").strip()
    end_label = _extract_entry_value(entry, "end_page", "end", "endpage").strip()
    start_page = _page_number_from_label(start_label)
    end_page = _page_number_from_label(end_label)
    if start_page is None or end_page is None:
        raise ValueError("Boundary entry missing start/end page.")
    if end_page < start_page:
        raise ValueError("Boundary entry has end page before start page.")

    page_texts: list[str] = []
    for page in range(start_page, end_page + 1):
        page_path = text_dir / f"{page:04d}.txt"
        if not page_path.exists():
            raise FileNotFoundError(f"Missing text file {page_path.name}.")
        page_texts.append(page_path.read_text(encoding="utf-8", errors="ignore").rstrip("\n"))
    return "\n".join(page_texts).strip()


def _build_hearing_sections(
    hearing_entries: list[dict[str, Any]],
    text_dir: Path,
    minute_entries: list[dict[str, Any]] | None = None,
) -> list[RetrievalSection]:
    minute_page_by_date: dict[str, str] = {}
    if minute_entries:
        for entry in minute_entries:
            date_value = _extract_entry_value(entry, "date").strip()
            if not date_value:
                continue
            date_key = _hearing_date_key(date_value)
            page_str = _extract_start_page_for_date_links(entry)
            if date_key and page_str:
                minute_page_by_date.setdefault(date_key, page_str)

    sections: list[RetrievalSection] = []
    for entry in hearing_entries:
        date_value = _extract_entry_value(entry, "date").strip()
        content = _read_boundary_entry_text(entry, text_dir)
        if not content:
            continue
        normalized_date = _format_long_us_date(date_value) or _normalize_hearing_date(date_value)
        metadata: dict[str, Any] = {
            "type": "hearing",
            "source": "hearing_transcript",
            "hearing_date": normalized_date,
        }
        date_key = _hearing_date_key(date_value)
        linked_minute_page = minute_page_by_date.get(date_key, "")
        metadata["has_matching_minute_order"] = bool(linked_minute_page)
        sections.append(RetrievalSection(section_type="hearing", content=content, metadata=metadata))
    return sections


def _build_report_sections(
    report_entries: list[dict[str, Any]],
    text_dir: Path,
) -> list[RetrievalSection]:
    sections: list[RetrievalSection] = []
    for entry in report_entries:
        report_name = _extract_entry_value(entry, "report_name", "report", "name").strip()
        content = _read_boundary_entry_text(entry, text_dir)
        if not content:
            continue
        metadata: dict[str, Any] = {
            "type": "report",
            "source": "report",
            "report_name": report_name or "Unknown",
        }
        sections.append(RetrievalSection(section_type="report", content=content, metadata=metadata))
    return sections


def _split_tagged_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_label: str | None = None
    current_lines: list[str] = []
    for line in text.splitlines():
        match = re.match(r"\s*<<<\s*(.*?)\s*>>>\s*$", line)
        if match:
            if current_label is not None:
                sections.append((current_label, "\n".join(current_lines).strip()))
            current_label = match.group(1).strip() or "Unknown"
            current_lines = []
        else:
            current_lines.append(line)
    if current_label is not None:
        sections.append((current_label, "\n".join(current_lines).strip()))
    return sections


def _split_into_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    parts = re.split(r"(?<=[.!?])\s+", normalized)
    return [part.strip() for part in parts if part.strip()]


def _chunk_sentences(sentences: list[str], max_chars: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _chunk_lines_preserving_structure(lines: list[str], max_chars: int) -> list[str]:
    chunks: list[str] = []
    current_lines: list[str] = []
    current_length = 0
    for line in lines:
        line_length = len(line)
        separator_length = 1 if current_lines else 0
        candidate_length = current_length + separator_length + line_length
        if current_lines and candidate_length > max_chars:
            chunks.append("\n".join(current_lines).strip())
            current_lines = [line]
            current_length = line_length
        else:
            current_lines.append(line)
            current_length = candidate_length
    if current_lines:
        chunks.append("\n".join(current_lines).strip())
    return [chunk for chunk in chunks if chunk]


def _chunk_text_preserving_structure(text: str, max_chars: int) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []

    blocks = [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]
    chunks: list[str] = []
    current_blocks: list[str] = []
    current_length = 0

    def _flush_current() -> None:
        nonlocal current_blocks, current_length
        if current_blocks:
            chunks.append("\n\n".join(current_blocks).strip())
            current_blocks = []
            current_length = 0

    def _append_block(block: str) -> None:
        nonlocal current_length
        separator_length = 2 if current_blocks else 0
        current_blocks.append(block)
        current_length += separator_length + len(block)

    for block in blocks:
        block_length = len(block)
        candidate_length = current_length + (2 if current_blocks else 0) + block_length
        if block_length <= max_chars:
            if current_blocks and candidate_length > max_chars:
                _flush_current()
            _append_block(block)
            continue

        _flush_current()
        lines = [line.rstrip() for line in block.split("\n")]
        line_chunks = _chunk_lines_preserving_structure(lines, max_chars)
        for line_chunk in line_chunks:
            if len(line_chunk) <= max_chars:
                chunks.append(line_chunk)
                continue
            sentences = _split_into_sentences(line_chunk)
            if sentences:
                chunks.extend(_chunk_sentences(sentences, max_chars))
            else:
                chunks.append(line_chunk[:max_chars].strip())

    _flush_current()
    return [chunk for chunk in chunks if chunk.strip()]


def _collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).rstrip() + "\n"


def _split_paragraphs(text: str) -> list[str]:
    chunks = re.split(r"\n\s*\n", text.strip())
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _flatten_paragraph_lines(text: str) -> str:
    paragraphs = _split_paragraphs(text)
    flattened: list[str] = []
    for paragraph in paragraphs:
        # Preserve paragraph breaks, but collapse all internal line breaks and spacing.
        single_line = re.sub(r"\s*\n\s*", " ", paragraph)
        single_line = re.sub(r"[ \t]{2,}", " ", single_line).strip()
        if single_line:
            flattened.append(single_line)
    return "\n\n".join(flattened)


def _chunk_paragraphs(paragraphs: list[str], max_count: int) -> list[str]:
    grouped: list[str] = []
    for index in range(0, len(paragraphs), max_count):
        grouped.append("\n\n".join(paragraphs[index : index + max_count]))
    return grouped


def _expand_section_chunk_paragraphs(chunks: list[Any]) -> list[str]:
    paragraphs: list[str] = []
    for chunk in chunks:
        raw_chunk = str(chunk or "").strip()
        if not raw_chunk:
            continue
        paragraphs.extend(_split_paragraphs(raw_chunk))
    return [paragraph.strip() for paragraph in paragraphs if paragraph.strip()]


def _strip_hearing_date_prefix(text: str) -> tuple[str, str | None]:
    match = re.match(r"^\s*Hearing date:\s*([^.\n]+)\.\s*(.*)$", text, re.DOTALL)
    if match:
        return match.group(2).strip(), match.group(1).strip()
    return text.strip(), None


def _remove_hearing_date_mentions(text: str) -> str:
    return re.sub(
        r"Hearing date:\s*[^.\n]{3,80}\.?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()


def _normalize_hearing_date(value: str) -> str:
    cleaned = re.sub(
        r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+",
        "",
        value.strip(),
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def _format_long_us_date(value: str) -> str:
    cleaned = _normalize_hearing_date(value)
    if not cleaned:
        return ""
    for fmt in (
        "%B %d, %Y",
        "%b %d, %Y",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%Y-%m-%d",
    ):
        try:
            parsed = datetime.datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
        return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"
    return cleaned


def _hearing_date_key(value: str) -> str:
    return _format_long_us_date(value).lower()


def _extract_start_page_for_date_links(entry: dict[str, Any]) -> str | None:
    start_label = _extract_entry_value(entry, "start_page", "start", "starte_page").strip()
    if not start_label:
        return None
    start_page = _page_number_from_label(start_label)
    if start_page is None:
        return None
    return f"{start_page:04d}"


def _has_page_markdown_links(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return bool(re.search(r"\]\(page:\d{4}\)", text))


def _remove_standalone_date_lines(text: str) -> str:
    if not text:
        return text
    date_patterns = (
        r"^[A-Za-z]+\s+\d{1,2},\s*\d{4}$",
        r"^[A-Za-z]+\s+\d{1,2}\s+\d{4}$",
        r"^\d{1,2}/\d{1,2}/\d{2,4}$",
        r"^Hearing date:\s*.+$",
    )
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
        if any(re.match(pattern, stripped, re.IGNORECASE) for pattern in date_patterns):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def _infer_case_name_from_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    patterns = [
        re.compile(r"\bIn\s+re\b", re.IGNORECASE),
        re.compile(r"\bIn\s+the\s+Matter\s+of\b", re.IGNORECASE),
    ]
    for line in lines:
        if any(pattern.search(line) for pattern in patterns):
            tokens = re.findall(r"[A-Za-z0-9]+", line)
            if tokens:
                return _sanitize_case_name_tokens(tokens)
    for line in lines:
        if re.search(r"\b(vs\.?|v\.)\b", line, re.IGNORECASE):
            tokens = re.findall(r"[A-Za-z0-9]+", line)
            if tokens:
                return _sanitize_case_name_tokens(tokens)
    for line in lines:
        tokens = [token for token in re.findall(r"[A-Za-z0-9]+", line) if token.isalpha()]
        if len(tokens) >= 2:
            return _sanitize_case_name_tokens(tokens[:8])
    return ""


def _compile_raw_sections_text(sections: list[RetrievalSection]) -> str:
    rendered_sections: list[str] = []
    for section in sections:
        content = str(section.content or "").strip()
        if not content:
            continue
        if section.section_type == "hearing":
            label = str(section.metadata.get("hearing_date", "")).strip() or "Unknown"
        elif section.section_type == "report":
            label = str(section.metadata.get("report_name", "")).strip() or "Unknown"
        else:
            label = str(section.metadata.get("type", "")).strip() or "Unknown"
        rendered_sections.append(f"<<<{label}>>>")
        rendered_sections.append(content.rstrip("\n"))
        rendered_sections.append("")
    return "\n".join(rendered_sections).rstrip() + "\n"


def _artifact_label_component(value: str, fallback: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", value.strip()).strip("_")
    normalized = re.sub(r"_+", "_", normalized)
    return normalized or fallback


def _strip_ascii_and_html_tables(text: str) -> str:
    if not text:
        return ""

    cleaned = text
    if "<table" in cleaned.lower():
        cleaned = _convert_html_tables(cleaned)

    border_chars = set("│┃║╎╏┆┇┊┋─━═┄┅┈┉┌┐└┘├┤┬┴┼╭╮╰╯+")
    cleaned_lines: list[str] = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
        non_space = [ch for ch in stripped if not ch.isspace()]
        if non_space and all(ch in border_chars for ch in non_space):
            continue

        # Remove leading box-drawn table columns such as "│  21 │ text".
        stripped = re.sub(r"^\s*[│┃║]\s*\d+\s*[│┃║]\s*", "", stripped)
        stripped = re.sub(r"^\s*\d+\s*[│┃║]\s*", "", stripped)

        # Remove pleading-paper style left margin numbers such as "21  text".
        stripped = re.sub(r"^\s*\d{1,3}\s{2,}", "", stripped)
        stripped = re.sub(r"^\s*\d{1,2}\s+(?=[A-Za-z(\"'])", "", stripped)

        # Trim stray vertical border characters left at the start/end of the line.
        stripped = re.sub(r"^\s*[│┃║]\s*", "", stripped)
        stripped = re.sub(r"\s*[│┃║]\s*$", "", stripped)
        stripped = re.sub(r"\s*[│┃║]\s*", "    ", stripped)
        stripped = re.sub(r" {5,}", "    ", stripped).strip()

        if not stripped:
            cleaned_lines.append("")
            continue
        cleaned_lines.append(stripped)
    return "\n".join(cleaned_lines)


def _chunk_text_for_artifacts(text: str, max_chars: int) -> list[str]:
    if max_chars <= 0:
        return []
    if not text:
        return []

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    boundary_pattern = re.compile(r"\.[ \t]*\n(?:\s*\n)?")

    while start < len(normalized):
        target = start + max_chars
        if target >= len(normalized):
            final_chunk = normalized[start:].strip()
            if final_chunk:
                chunks.append(final_chunk)
            break

        match = boundary_pattern.search(normalized, pos=target)
        if match:
            end = match.end()
        else:
            newline_index = normalized.find("\n", target)
            end = newline_index + 1 if newline_index != -1 else len(normalized)

        if end <= start:
            end = min(start + max_chars, len(normalized))

        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end
        while start < len(normalized) and normalized[start].isspace():
            start += 1

    return chunks


def _prepare_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _normalize_confidence(value: Any) -> str:
    confidence = str(value or "").strip().lower()
    return confidence if confidence in {"high", "medium", "low"} else "low"


def _coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _counsel_role_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _normalize_counsel_role(value: str) -> str:
    stripped = str(value or "").strip()
    if not stripped:
        return ""
    for canonical in COUNSEL_ROLE_ORDER:
        if stripped.upper() == canonical:
            return canonical
    return COUNSEL_ROLE_ALIASES.get(_counsel_role_key(stripped), "")


def _speaker_label_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _extract_attorney_like_speaker_labels(text: str) -> list[str]:
    cleaned = _strip_ascii_and_html_tables(text)
    labels: list[str] = []
    seen: set[str] = set()
    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r"^([A-Za-z][A-Za-z0-9 .,'()/&-]{1,80}):(?:\s|$)", stripped)
        if not match:
            continue
        label = re.sub(r"\s+", " ", match.group(1)).strip()
        upper_label = label.upper()
        if not (
            re.search(r"\b(MR|MS|MRS|MISS|COUNSEL|ATTORNEY|ESQ)\b", upper_label)
            or _normalize_counsel_role(label)
        ):
            continue
        if upper_label in seen:
            continue
        seen.add(upper_label)
        labels.append(label)
    return labels


def _build_transcript_counsel_role_evidence(transcript: str) -> str:
    cleaned = _strip_ascii_and_html_tables(transcript).strip()
    if not cleaned:
        return ""
    lines = ["HEARING TRANSCRIPT", cleaned]
    speaker_labels = _extract_attorney_like_speaker_labels(cleaned)
    if speaker_labels:
        lines.extend(["", "ATTORNEY-LIKE SPEAKER LABELS", *speaker_labels])
    return "\n".join(lines).strip()


def _read_boundary_entry_excerpt_text(
    entry: dict[str, Any],
    text_dir: Path,
    max_pages: int,
) -> str:
    start_label = _extract_entry_value(entry, "start_page", "start", "starte_page").strip()
    end_label = _extract_entry_value(entry, "end_page", "end", "endpage").strip()
    start_page = _page_number_from_label(start_label)
    end_page = _page_number_from_label(end_label)
    if start_page is None or end_page is None:
        raise ValueError("Boundary entry missing start/end page.")
    if end_page < start_page:
        raise ValueError("Boundary entry has end page before start page.")
    excerpt_end_page = min(end_page, start_page + max(0, max_pages - 1))
    page_texts: list[str] = []
    for page in range(start_page, excerpt_end_page + 1):
        page_path = text_dir / f"{page:04d}.txt"
        if not page_path.exists():
            raise FileNotFoundError(f"Missing text file {page_path.name}.")
        page_texts.append(page_path.read_text(encoding="utf-8", errors="ignore").rstrip("\n"))
    return "\n".join(page_texts).strip()


def _build_case_counsel_role_evidence(
    hearing_entries: list[dict[str, Any]],
    text_dir: Path,
) -> str:
    if not hearing_entries:
        return ""
    lines: list[str] = ["CASE COUNSEL ROLE EVIDENCE", "", "FIRST TWO PAGES OF EACH HEARING"]
    all_speaker_labels: list[str] = []
    seen_speaker_labels: set[str] = set()
    included_excerpt = False
    for index, entry in enumerate(hearing_entries, start=1):
        date_value = _extract_entry_value(entry, "date").strip() or f"Hearing {index}"
        excerpt = _read_boundary_entry_excerpt_text(entry, text_dir, 2)
        if excerpt:
            lines.extend(["", f"HEARING: {date_value}", excerpt])
            included_excerpt = True
        for label in _extract_attorney_like_speaker_labels(excerpt):
            label_key = label.upper()
            if label_key in seen_speaker_labels:
                continue
            seen_speaker_labels.add(label_key)
            all_speaker_labels.append(label)

    if all_speaker_labels:
        lines.extend(["", "UNIQUE ATTORNEY-LIKE SPEAKER LABELS", *all_speaker_labels])

    return "\n".join(lines).strip() if included_excerpt or all_speaker_labels else ""


def _build_optimize_hearing_payload(counsel_roles: str, transcript: str) -> str:
    cleaned_counsel_roles = counsel_roles.strip() or '{"roles":[],"unknown_speaker_labels":[],"notes":"Unknown."}'
    cleaned_transcript = transcript.strip()
    return (
        "REFERENCE COUNSEL ROLE JSON\n"
        "Use this only to determine whether counsel is speaking for mother, father, minor, county, tribe, or another party. "
        "Do not quote or rewrite the transcript from this section.\n"
        f"{cleaned_counsel_roles}\n\n"
        "TRANSCRIPT\n"
        "Only this section may appear in the output. Preserve spoken text exactly as written.\n"
        f"{cleaned_transcript}"
    )


def _build_attorney_request_settings(
    optimize_settings: dict[str, Any],
) -> dict[str, Any]:
    return {
        "api_url": str(
            optimize_settings.get("attorney_api_url")
            or optimize_settings.get("api_url")
            or ""
        ).strip(),
        "model_id": str(
            optimize_settings.get("attorney_model_id")
            or optimize_settings.get("model_id")
            or ""
        ).strip(),
        "api_key": str(
            optimize_settings.get("attorney_api_key")
            or optimize_settings.get("api_key")
            or ""
        ).strip(),
        "disable_reasoning": bool(
            optimize_settings.get(
                "attorney_disable_reasoning",
                optimize_settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING),
            )
        ),
        "prompt": str(
            optimize_settings.get("attorneys_prompt")
            or optimize_settings.get("prompt")
            or DEFAULT_OPTIMIZE_ATTORNEYS_PROMPT
        ).strip(),
        "max_tokens": str(
            optimize_settings.get("max_tokens") or DEFAULT_OPTIMIZE_MAX_TOKENS
        ).strip(),
    }


def _build_optimize_hearing_request_settings(
    optimize_settings: dict[str, Any],
) -> dict[str, Any]:
    return {
        "api_url": str(
            optimize_settings.get("hearing_api_url")
            or optimize_settings.get("api_url")
            or ""
        ).strip(),
        "model_id": str(
            optimize_settings.get("hearing_model_id")
            or optimize_settings.get("model_id")
            or ""
        ).strip(),
        "api_key": str(
            optimize_settings.get("hearing_api_key")
            or optimize_settings.get("api_key")
            or ""
        ).strip(),
        "disable_reasoning": bool(
            optimize_settings.get(
                "hearing_disable_reasoning",
                optimize_settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING),
            )
        ),
        "prompt": str(
            optimize_settings.get("hearings_prompt")
            or optimize_settings.get("prompt")
            or DEFAULT_OPTIMIZE_HEARINGS_PROMPT
        ).strip(),
        "max_tokens": str(
            optimize_settings.get("max_tokens") or DEFAULT_OPTIMIZE_MAX_TOKENS
        ).strip(),
    }


def _build_optimize_report_request_settings(
    optimize_settings: dict[str, Any],
) -> dict[str, Any]:
    return {
        "api_url": str(
            optimize_settings.get("report_api_url")
            or optimize_settings.get("api_url")
            or ""
        ).strip(),
        "model_id": str(
            optimize_settings.get("report_model_id")
            or optimize_settings.get("model_id")
            or ""
        ).strip(),
        "api_key": str(
            optimize_settings.get("report_api_key")
            or optimize_settings.get("api_key")
            or ""
        ).strip(),
        "disable_reasoning": bool(
            optimize_settings.get(
                "report_disable_reasoning",
                optimize_settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING),
            )
        ),
        "prompt": str(
            optimize_settings.get("reports_prompt")
            or optimize_settings.get("prompt")
            or DEFAULT_OPTIMIZE_REPORTS_PROMPT
        ).strip(),
        "max_tokens": str(
            optimize_settings.get("max_tokens") or DEFAULT_OPTIMIZE_MAX_TOKENS
        ).strip(),
    }


def _normalize_counsel_role_json_payload(payload: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "roles": [],
        "unknown_speaker_labels": [],
        "notes": "",
    }
    if not isinstance(payload, dict):
        raise ValueError("Counsel role extraction must return a JSON object.")

    role_items = payload.get("roles")
    if role_items is None and isinstance(payload.get("attorneys"), list):
        role_items = payload.get("attorneys")
    if isinstance(role_items, list):
        merged_roles: dict[str, dict[str, Any]] = {}
        confidence_rank = {"low": 0, "medium": 1, "high": 2}
        for item in role_items:
            if not isinstance(item, dict):
                continue
            role = _normalize_counsel_role(item.get("role", "") or item.get("represents", ""))
            if not role:
                continue
            merged_entry = merged_roles.setdefault(
                role,
                {
                    "role": role,
                    "attorney_names": [],
                    "speaker_aliases": [],
                    "confidence": "low",
                },
            )
            attorney_names = _coerce_string_list(item.get("attorney_names"))
            if not attorney_names:
                legacy_name = str(item.get("name", "") or "").strip()
                if legacy_name:
                    attorney_names = [legacy_name]
            speaker_aliases = _coerce_string_list(item.get("speaker_aliases"))
            if not speaker_aliases:
                legacy_alias = str(item.get("speaker_label", "") or "").strip()
                if legacy_alias:
                    speaker_aliases = [legacy_alias]
            for name in attorney_names:
                if name not in merged_entry["attorney_names"]:
                    merged_entry["attorney_names"].append(name)
            for alias in speaker_aliases:
                if alias not in merged_entry["speaker_aliases"]:
                    merged_entry["speaker_aliases"].append(alias)
            confidence = _normalize_confidence(item.get("confidence"))
            if confidence_rank[confidence] > confidence_rank[merged_entry["confidence"]]:
                merged_entry["confidence"] = confidence
        result["roles"] = [
            merged_roles[role]
            for role in COUNSEL_ROLE_ORDER
            if role in merged_roles
            and (
                merged_roles[role]["attorney_names"]
                or merged_roles[role]["speaker_aliases"]
            )
        ]

    unknown_value = payload.get("unknown_speaker_labels")
    if unknown_value is None:
        unknown_value = payload.get("unknown_speakers", [])
    if isinstance(unknown_value, list):
        result["unknown_speaker_labels"] = [
            str(item).strip() for item in unknown_value if str(item).strip()
        ]

    result["notes"] = str(payload.get("notes", "") or "").strip()
    return result


def _merge_counsel_role_payloads(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    merged_roles: dict[str, dict[str, Any]] = {}
    name_roles: dict[str, set[str]] = {}
    alias_roles: dict[str, set[str]] = {}
    name_forms: dict[str, set[str]] = {}
    alias_forms: dict[str, set[str]] = {}
    unknown_labels: set[str] = set()
    notes: list[str] = []
    confidence_rank = {"low": 0, "medium": 1, "high": 2}

    for payload in payloads:
        normalized = _normalize_counsel_role_json_payload(payload)
        for label in normalized["unknown_speaker_labels"]:
            unknown_labels.add(label)
        note = str(normalized.get("notes", "") or "").strip()
        if note and note not in notes:
            notes.append(note)
        for role_item in normalized["roles"]:
            role = str(role_item.get("role", "")).strip()
            if not role:
                continue
            merged_entry = merged_roles.setdefault(
                role,
                {
                    "role": role,
                    "attorney_names": [],
                    "speaker_aliases": [],
                    "confidence": "low",
                },
            )
            for name in role_item.get("attorney_names", []):
                cleaned_name = str(name).strip()
                if not cleaned_name:
                    continue
                name_key = cleaned_name.casefold()
                name_roles.setdefault(name_key, set()).add(role)
                name_forms.setdefault(name_key, set()).add(cleaned_name)
                if cleaned_name not in merged_entry["attorney_names"]:
                    merged_entry["attorney_names"].append(cleaned_name)
            for alias in role_item.get("speaker_aliases", []):
                cleaned_alias = str(alias).strip()
                if not cleaned_alias:
                    continue
                alias_key = cleaned_alias.casefold()
                alias_roles.setdefault(alias_key, set()).add(role)
                alias_forms.setdefault(alias_key, set()).add(cleaned_alias)
                if cleaned_alias not in merged_entry["speaker_aliases"]:
                    merged_entry["speaker_aliases"].append(cleaned_alias)
            confidence = _normalize_confidence(role_item.get("confidence"))
            if confidence_rank[confidence] > confidence_rank[merged_entry["confidence"]]:
                merged_entry["confidence"] = confidence

    for name_key, roles in name_roles.items():
        if len(roles) <= 1:
            continue
        for role in roles:
            merged_entry = merged_roles.get(role)
            if merged_entry:
                merged_entry["attorney_names"] = [
                    item for item in merged_entry["attorney_names"] if item.casefold() != name_key
                ]
        unknown_labels.update(name_forms.get(name_key, set()))

    for alias_key, roles in alias_roles.items():
        if len(roles) <= 1:
            continue
        for role in roles:
            merged_entry = merged_roles.get(role)
            if merged_entry:
                merged_entry["speaker_aliases"] = [
                    item
                    for item in merged_entry["speaker_aliases"]
                    if item.casefold() != alias_key
                ]
        unknown_labels.update(alias_forms.get(alias_key, set()))

    result = {
        "roles": [
            merged_roles[role]
            for role in COUNSEL_ROLE_ORDER
            if role in merged_roles
            and (
                merged_roles[role]["attorney_names"]
                or merged_roles[role]["speaker_aliases"]
            )
        ],
        "unknown_speaker_labels": sorted(unknown_labels, key=str.casefold),
        "notes": " ".join(notes).strip(),
    }
    return _normalize_counsel_role_json_payload(result)


def _render_counsel_role_json(counsel_roles: dict[str, Any]) -> str:
    normalized = _normalize_counsel_role_json_payload(counsel_roles)
    return json.dumps(normalized, indent=2, ensure_ascii=True)


def _build_counsel_role_speaker_label_map(
    counsel_roles: dict[str, Any],
) -> dict[str, str]:
    normalized = _normalize_counsel_role_json_payload(counsel_roles)
    labels_by_key: dict[str, set[str]] = {}

    for role_item in normalized["roles"]:
        role = str(role_item.get("role", "")).strip()
        if not role:
            continue
        label_values = [role]
        label_values.extend(_coerce_string_list(role_item.get("speaker_aliases")))
        label_values.extend(_coerce_string_list(role_item.get("attorney_names")))
        for label in label_values:
            cleaned_label = str(label or "").strip().rstrip(":")
            if not cleaned_label:
                continue
            key = _speaker_label_key(cleaned_label)
            if not key:
                continue
            labels_by_key.setdefault(key, set()).add(role)

    return {
        key: next(iter(roles))
        for key, roles in labels_by_key.items()
        if len(roles) == 1
    }


def _normalize_hearing_speaker_labels(
    content: str,
    counsel_roles: dict[str, Any],
) -> str:
    label_map = _build_counsel_role_speaker_label_map(counsel_roles)
    if not label_map:
        return content

    pattern = re.compile(
        r"(^|\s)([A-Za-z][A-Za-z0-9 .,'()/&-]{1,80}?):(?=\s|$)",
        re.MULTILINE,
    )

    def _replace(match: re.Match[str]) -> str:
        prefix = match.group(1)
        label = re.sub(r"\s+", " ", match.group(2)).strip()
        normalized_role = label_map.get(_speaker_label_key(label))
        if not normalized_role:
            return match.group(0)
        return f"{prefix}{normalized_role}:"

    return pattern.sub(_replace, content)


def _write_chunked_section_files(
    base_dir: Path,
    sections: list[RetrievalSection],
    label_key: str,
    chunk_size: int,
) -> list[ChunkedSectionFiles]:
    written_sections: list[ChunkedSectionFiles] = []
    for section_index, section in enumerate(sections, start=1):
        content = _strip_ascii_and_html_tables(str(section.content or ""))
        if not content.strip():
            continue
        label = str(section.metadata.get(label_key, "")).strip() or f"{section.section_type.title()} {section_index}"
        section_dir = base_dir / (
            f"{section_index:04d}_{_artifact_label_component(label, section.section_type)}"
        )
        section_dir.mkdir(parents=True, exist_ok=True)
        (section_dir / "label.txt").write_text(label + "\n", encoding="utf-8")

        chunk_paths: list[Path] = []
        for chunk_index, chunk in enumerate(_chunk_text_for_artifacts(content, chunk_size), start=1):
            chunk_path = section_dir / f"{chunk_index:04d}.txt"
            chunk_path.write_text(chunk, encoding="utf-8")
            chunk_paths.append(chunk_path)

        written_sections.append(
            ChunkedSectionFiles(
                section_type=section.section_type,
                label=label,
                directory=section_dir,
                chunk_paths=chunk_paths,
                metadata=dict(section.metadata),
            )
        )
    return written_sections


def _create_preoptimized_chunks(
    root_dir: Path,
    hearing_sections: list[RetrievalSection],
    report_sections: list[RetrievalSection],
    chunk_size: int,
    counsel_role_evidence: str,
    counsel_roles: dict[str, Any],
) -> tuple[list[ChunkedSectionFiles], list[ChunkedSectionFiles]]:
    artifacts_dir = root_dir / "artifacts"
    preoptimized_dir = artifacts_dir / "preoptimized"
    hearings_dir = preoptimized_dir / "hearings"
    reports_dir = preoptimized_dir / "reports"
    _prepare_directory(preoptimized_dir)
    (preoptimized_dir / "counsel_role_evidence.txt").write_text(
        counsel_role_evidence.strip(),
        encoding="utf-8",
    )
    (preoptimized_dir / "counsel_roles.json").write_text(
        _render_counsel_role_json(counsel_roles),
        encoding="utf-8",
    )
    hearings_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    hearing_files = _write_chunked_section_files(
        hearings_dir,
        hearing_sections,
        "hearing_date",
        chunk_size,
    )
    report_files = _write_chunked_section_files(
        reports_dir,
        report_sections,
        "report_name",
        chunk_size,
    )
    return hearing_files, report_files


def _create_optimized_output_dirs(root_dir: Path) -> tuple[Path, Path]:
    artifacts_dir = root_dir / "artifacts"
    optimized_dir = artifacts_dir / "optimized"
    hearings_dir = optimized_dir / "hearings"
    reports_dir = optimized_dir / "reports"
    _prepare_directory(optimized_dir)
    hearings_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    return hearings_dir, reports_dir


def _load_chunked_section_files(
    base_dir: Path,
    section_type: str,
    label_key: str,
) -> list[ChunkedSectionFiles]:
    loaded_sections: list[ChunkedSectionFiles] = []
    if not base_dir.exists():
        return loaded_sections
    for section_dir in sorted((path for path in base_dir.iterdir() if path.is_dir()), key=_natural_sort_key):
        label_path = section_dir / "label.txt"
        if label_path.exists():
            label = label_path.read_text(encoding="utf-8", errors="ignore").strip()
        else:
            label = section_dir.name
        chunk_paths = sorted(section_dir.glob("[0-9][0-9][0-9][0-9].txt"), key=_natural_sort_key)
        loaded_sections.append(
            ChunkedSectionFiles(
                section_type=section_type,
                label=label,
                directory=section_dir,
                chunk_paths=chunk_paths,
                metadata={"type": section_type, label_key: label},
            )
        )
    return loaded_sections


def _load_labeled_chunk_directories(
    base_dir: Path,
    section_type: str,
    label_key: str,
) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    if not base_dir.exists():
        return sections
    for section_dir in sorted((path for path in base_dir.iterdir() if path.is_dir()), key=_natural_sort_key):
        label_path = section_dir / "label.txt"
        if label_path.exists():
            label = label_path.read_text(encoding="utf-8", errors="ignore").strip()
        else:
            label = section_dir.name
        chunks: list[str] = []
        for chunk_path in sorted(section_dir.glob("[0-9][0-9][0-9][0-9].txt"), key=_natural_sort_key):
            content = chunk_path.read_text(encoding="utf-8", errors="ignore").strip()
            if content:
                chunks.append(content)
        metadata: dict[str, Any] = {"type": section_type}
        metadata[label_key] = label
        sections.append(
            {
                "label": label,
                "metadata": metadata,
                "chunks": chunks,
            }
        )
    return sections


def _load_classify_basic_entries(classify_path: Path) -> list[tuple[str, str, int]]:
    entries: list[tuple[str, str, int]] = []
    if not classify_path.exists():
        return entries
    with classify_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            file_name = str(payload.get("file_name", "") or "").strip()
            page_type = str(payload.get("page_type", "") or "").strip().lower()
            if not file_name or not page_type:
                continue
            page_number = _extract_page_number(file_name)
            if page_number is None:
                continue
            entries.append((file_name, page_type, page_number))
    return entries


def _natural_sort_key(path: Path | str) -> list[object]:
    if isinstance(path, Path):
        name = path.name
    else:
        name = str(path).strip()
        if not name:
            return []
        name = Path(name).name
    parts = re.split(r"(\d+)", name)
    key: list[object] = []
    for part in parts:
        if part.isdigit():
            key.append(int(part))
        else:
            key.append(part.lower())
    return key


def _merge_pdfs(paths: list[Path], output_path: Path) -> Path:
    writer = PdfWriter()
    for path in paths:
        reader = PdfReader(str(path))
        for page in reader.pages:
            writer.add_page(page)
    with output_path.open("wb") as handle:
        writer.write(handle)
    return output_path


def _ensure_case_bundle_dirs(base_dir: Path) -> tuple[Path, Path, Path]:
    root = base_dir / "case_bundle"
    text_dir = root / "text_pages"
    image_pages_dir = root / "image_pages"
    text_dir.mkdir(parents=True, exist_ok=True)
    image_pages_dir.mkdir(parents=True, exist_ok=True)
    return root, text_dir, image_pages_dir


def _retry_after_seconds(error: urllib.error.HTTPError) -> float | None:
    if not error.headers:
        return None
    retry_after = error.headers.get("Retry-After")
    if not retry_after:
        return None
    try:
        return float(retry_after)
    except ValueError:
        return None


def _retry_delay_seconds(attempt: int, retry_after: float | None) -> float:
    if retry_after is not None:
        return max(0.0, retry_after)
    base = min(LLM_RETRY_MAX_SECONDS, LLM_RETRY_BASE_SECONDS * (2 ** (attempt - 1)))
    jitter = random.uniform(0.0, base * 0.2)
    return base + jitter


def _post_json_with_retries(
    req: urllib.request.Request,
    timeout: int,
    error_label: str,
) -> dict[str, Any]:
    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
            if isinstance(payload, dict):
                return payload
            raise RuntimeError(f"{error_label}: response was not JSON")
        except urllib.error.HTTPError as exc:
            retry_after = _retry_after_seconds(exc)
            if exc.code in LLM_RETRYABLE_HTTP_CODES and attempt < LLM_MAX_RETRIES:
                time.sleep(_retry_delay_seconds(attempt, retry_after))
                continue
            error_body = ""
            try:
                error_body = exc.read().decode("utf-8", errors="ignore")
            except Exception:
                error_body = ""
            detail = error_body.strip() or exc.reason or "request failed"
            raise RuntimeError(f"{error_label}: HTTP {exc.code} {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt < LLM_MAX_RETRIES:
                time.sleep(_retry_delay_seconds(attempt, None))
                continue
            raise RuntimeError(f"{error_label}: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"{error_label}: {exc}") from exc
    raise RuntimeError(f"{error_label}: exhausted retries")


def _endpoint_responding(url: str, timeout: float = 1.0) -> bool:
    target = str(url or "").strip()
    if not target:
        return False
    req = urllib.request.Request(target, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except urllib.error.HTTPError as exc:
        return exc.code in {400, 401, 403, 404, 405}
    except Exception:
        return False


def _wait_for_endpoint_ready(
    url: str,
    *,
    timeout_seconds: float = LOCAL_SERVER_READY_TIMEOUT_SECONDS,
    poll_seconds: float = LOCAL_SERVER_READY_POLL_SECONDS,
    process: subprocess.Popen[str] | None = None,
    stop_check: Callable[[], None] | None = None,
) -> None:
    deadline = time.monotonic() + max(0.1, timeout_seconds)
    while time.monotonic() < deadline:
        if stop_check:
            stop_check()
        if _endpoint_responding(url, timeout=1.0):
            return
        if process is not None and process.poll() is not None:
            detail = "process exited before startup completed."
            output = ""
            if process.stdout is not None:
                try:
                    output = process.stdout.read()
                except Exception:
                    output = ""
            output = output.strip()
            if output:
                detail = output.splitlines()[-1]
            raise RuntimeError(f"Local OCR server exited during startup: {detail}")
        time.sleep(max(0.1, poll_seconds))
    raise RuntimeError(f"Local OCR server did not become ready within {timeout_seconds:.0f} seconds.")


def _manifest_path(root_dir: Path) -> Path:
    return root_dir / "manifest.json"


def _read_manifest(root_dir: Path) -> dict[str, Any]:
    manifest_path = _manifest_path(root_dir)
    if not manifest_path.exists():
        return {}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_manifest(
    root_dir: Path,
    selected_pdfs: list[Path],
    pipeline_info: dict[str, Any] | None = None,
    rt_ct_split_page: int | None = None,
    rt_ct_split_mode: str | None = None,
) -> None:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    manifest_path = _manifest_path(root_dir)
    existing = _read_manifest(root_dir)
    created_at = now
    if isinstance(existing, dict):
        existing_created = existing.get("created_at")
        if isinstance(existing_created, str) and existing_created.strip():
            created_at = existing_created

    text_dir = root_dir / "text_pages"
    image_pages_dir = root_dir / "image_pages"
    classification_dir = root_dir / "classification"
    artifacts_dir = root_dir / "artifacts"
    summaries_dir = root_dir / "summaries"
    rag_dir = root_dir / "rag"
    temp_dir = root_dir / "temp"
    summarized_hearings_path, summarized_reports_path = _summary_output_paths(root_dir)
    summarized_minutes_path = _minutes_summary_output_path(root_dir)

    def _root_path(value: Path) -> str:
        return str(value)

    def _relpath(value: Path) -> str:
        if not value.is_absolute():
            return value.as_posix()
        try:
            return value.relative_to(root_dir).as_posix()
        except ValueError:
            return os.path.relpath(str(value), str(root_dir))

    pipeline: dict[str, Any] = {}
    if isinstance(existing.get("pipeline"), dict):
        pipeline.update(existing["pipeline"])
    if pipeline_info:
        for key, value in pipeline_info.items():
            if value is None:
                pipeline.pop(key, None)
            else:
                pipeline[key] = value
        if "last_completed_step" in pipeline_info and "last_completed_at" not in pipeline_info:
            pipeline["last_completed_at"] = now
        if "last_failed_step" in pipeline_info and "last_failed_at" not in pipeline_info:
            pipeline["last_failed_at"] = now

    existing_split = _normalize_rt_ct_split_page(existing.get("rt_ct_split_page"))
    existing_mode = _normalize_rt_ct_split_mode(existing.get("rt_ct_split_mode"))
    split_page_value = (
        existing_split if rt_ct_split_page is None else _normalize_rt_ct_split_page(rt_ct_split_page)
    )
    split_mode_value = (
        existing_mode if rt_ct_split_mode is None else _normalize_rt_ct_split_mode(rt_ct_split_mode)
    )

    payload: dict[str, Any] = {
        "schema_version": 1,
        "created_at": created_at,
        "updated_at": now,
        "root_dir": _root_path(root_dir),
        "rt_ct_split_page": split_page_value,
        "rt_ct_split_mode": split_mode_value,
        "input_pdfs": [_relpath(path) for path in selected_pdfs],
        "dirs": {
            "text_pages": _relpath(text_dir),
            "image_pages": _relpath(image_pages_dir),
            "classification": _relpath(classification_dir),
            "artifacts": _relpath(artifacts_dir),
            "preoptimized": _relpath(artifacts_dir / "preoptimized"),
            "optimized_dir": _relpath(artifacts_dir / "optimized"),
            "summaries": _relpath(summaries_dir),
            "rag": _relpath(rag_dir),
            "temp": _relpath(temp_dir),
        },
        "files": {
            "merged_pdf": _relpath(temp_dir / "merged.pdf"),
            "toc": _relpath(artifacts_dir / "toc.txt"),
            "hearing_boundaries": _relpath(artifacts_dir / "hearing_boundaries.json"),
            "report_boundaries": _relpath(artifacts_dir / "report_boundaries.json"),
            "minutes_boundaries": _relpath(artifacts_dir / "minutes_boundaries.json"),
            "raw_hearings": _relpath(artifacts_dir / "raw_hearings.txt"),
            "raw_reports": _relpath(artifacts_dir / "raw_reports.txt"),
            "optimized_hearings": _relpath(artifacts_dir / "optimized_hearings.txt"),
            "optimized_reports": _relpath(artifacts_dir / "optimized_reports.txt"),
            "summarized_hearings": _relpath(summarized_hearings_path),
            "summarized_reports": _relpath(summarized_reports_path),
            "summarized_minutes": _relpath(summarized_minutes_path),
            "case_overview": _relpath(rag_dir / "case_overview.txt"),
        },
        "classification": {
            "rt_basic": _relpath(classification_dir / "RT_basic.jsonl"),
            "ct_basic": _relpath(classification_dir / "CT_basic.jsonl"),
            "rt_basic": _relpath(classification_dir / "RT_basic.jsonl"),
            "ct_basic": _relpath(classification_dir / "CT_basic.jsonl"),
            "rt_basic_advanced": _relpath(
                classification_dir / "RT_basic_advanced.jsonl"
            ),
            "ct_basic_advanced": _relpath(
                classification_dir / "CT_basic_advanced.jsonl"
            ),
            "rt_basic_advanced_corrected": _relpath(
                classification_dir / "RT_basic_advanced_corrected.jsonl"
            ),
            "ct_basic_advanced_corrected": _relpath(
                classification_dir / "CT_basic_advanced_corrected.jsonl"
            ),
            "rt_basic_advanced_corrected_dates": _relpath(
                classification_dir / "RT_basic_advanced_corrected_dates.jsonl"
            ),
            "ct_basic_advanced_corrected_dates": _relpath(
                classification_dir / "CT_basic_advanced_corrected_dates.jsonl"
            ),
            "rt_basic_advanced_corrected_dates_names": _relpath(
                classification_dir / "RT_basic_advanced_corrected_dates_names.jsonl"
            ),
            "ct_basic_advanced_corrected_dates_names": _relpath(
                classification_dir / "CT_basic_advanced_corrected_dates_names.jsonl"
            ),
            "hearings_pages": _relpath(classification_dir / "hearings_pages.jsonl"),
            "minute_order_pages": _relpath(classification_dir / "minute_order_pages.jsonl"),
            "report_pages": _relpath(classification_dir / "report_pages.jsonl"),
            "form_pages": _relpath(classification_dir / "form_pages.jsonl"),
            "dates": _relpath(classification_dir / "dates.jsonl"),
            "report_names": _relpath(classification_dir / "report_names.jsonl"),
            "relevant_forms": _relpath(classification_dir / "relevant_forms.jsonl"),
            "relevant_reports": _relpath(classification_dir / "relevant_reports.jsonl"),
            "form_names": _relpath(classification_dir / "form_names.jsonl"),
        },
        "rag": {
            "vector_database": _relpath(rag_dir / "vector_database"),
        },
        "pipeline": pipeline,
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        raw = CONFIG_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _write_config(config: dict[str, Any]) -> None:
    serializable: dict[str, Any] = {}
    for key, value in config.items():
        if not isinstance(key, str):
            continue
        serializable[key] = value
    try:
        CONFIG_FILE.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    except OSError:
        pass


def _read_config_bool(config: dict[str, Any], key: str, default: bool) -> bool:
    value = config.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def load_run_until_step_setting() -> str | None:
    config = _read_config()
    value = config.get(CONFIG_KEY_RUN_UNTIL_STEP)
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def save_run_until_step_setting(step_id: str | None) -> None:
    config = _read_config()
    normalized = str(step_id or "").strip()
    config[CONFIG_KEY_RUN_UNTIL_STEP] = normalized or None
    _write_config(config)


def load_classifier_settings() -> dict[str, Any]:
    config = _read_config()
    api_url = str(config.get(CONFIG_KEY_CLASSIFIER_API_URL, "") or "").strip()
    model_id = str(config.get(CONFIG_KEY_CLASSIFIER_MODEL_ID, "") or "").strip()
    api_key = str(config.get(CONFIG_KEY_CLASSIFIER_API_KEY, "") or "").strip()
    if CONFIG_KEY_CLASSIFIER_DISABLE_REASONING in config:
        disable_reasoning = _read_config_bool(
            config,
            CONFIG_KEY_CLASSIFIER_DISABLE_REASONING,
            DEFAULT_DISABLE_REASONING,
        )
    else:
        disable_reasoning = not _read_config_bool(
            config,
            CONFIG_KEY_CLASSIFIER_THINKING_ENABLED,
            True,
        )
    local_vision_enabled = _read_config_bool(config, CONFIG_KEY_CLASSIFIER_LOCAL_VISION_ENABLED, False)
    local_vision_start_command = str(
        config.get(
            CONFIG_KEY_CLASSIFIER_LOCAL_VISION_START_COMMAND,
            DEFAULT_LOCAL_VISION_START_COMMAND,
        )
        or ""
    ).strip()
    prompt = str(config.get(CONFIG_KEY_CLASSIFIER_PROMPT, DEFAULT_CLASSIFIER_PROMPT) or "").strip()
    rt_prompt = str(
        config.get(CONFIG_KEY_CLASSIFIER_RT_PROMPT, prompt or DEFAULT_CLASSIFIER_PROMPT) or ""
    ).strip()
    ct_prompt = str(
        config.get(CONFIG_KEY_CLASSIFIER_CT_PROMPT, prompt or DEFAULT_CLASSIFIER_PROMPT) or ""
    ).strip()
    return {
        "api_url": api_url,
        "model_id": model_id,
        "api_key": api_key,
        "prompt": prompt or DEFAULT_CLASSIFIER_PROMPT,
        "rt_prompt": rt_prompt or DEFAULT_CLASSIFIER_PROMPT,
        "ct_prompt": ct_prompt or DEFAULT_CLASSIFIER_PROMPT,
        "disable_reasoning": disable_reasoning,
        "local_vision_enabled": local_vision_enabled,
        "local_vision_start_command": local_vision_start_command,
    }


def save_classifier_settings(
    api_url: str,
    model_id: str,
    api_key: str,
    rt_prompt: str,
    ct_prompt: str,
    disable_reasoning: bool,
    local_vision_enabled: bool,
    local_vision_start_command: str,
) -> None:
    config = _read_config()
    config[CONFIG_KEY_CLASSIFIER_API_URL] = api_url
    config[CONFIG_KEY_CLASSIFIER_MODEL_ID] = model_id
    config[CONFIG_KEY_CLASSIFIER_API_KEY] = api_key
    normalized_rt = rt_prompt or DEFAULT_CLASSIFIER_PROMPT
    normalized_ct = ct_prompt or DEFAULT_CLASSIFIER_PROMPT
    config[CONFIG_KEY_CLASSIFIER_PROMPT] = normalized_rt
    config[CONFIG_KEY_CLASSIFIER_RT_PROMPT] = normalized_rt
    config[CONFIG_KEY_CLASSIFIER_CT_PROMPT] = normalized_ct
    config[CONFIG_KEY_CLASSIFIER_DISABLE_REASONING] = bool(disable_reasoning)
    config[CONFIG_KEY_CLASSIFIER_LOCAL_VISION_ENABLED] = bool(local_vision_enabled)
    config[CONFIG_KEY_CLASSIFIER_LOCAL_VISION_START_COMMAND] = local_vision_start_command.strip()
    _write_config(config)


def load_advanced_classify_settings() -> dict[str, Any]:
    config = _read_config()
    shared = load_classifier_settings()
    api_url = shared["api_url"] or str(config.get(CONFIG_KEY_ADVANCED_CLASSIFY_API_URL, "") or "").strip()
    model_id = shared["model_id"] or str(
        config.get(CONFIG_KEY_ADVANCED_CLASSIFY_MODEL_ID, "") or ""
    ).strip()
    api_key = shared["api_key"] or str(config.get(CONFIG_KEY_ADVANCED_CLASSIFY_API_KEY, "") or "").strip()
    hearing_prompt = str(
        config.get(CONFIG_KEY_ADVANCED_CLASSIFY_HEARING_PROMPT, DEFAULT_ADVANCED_HEARING_PROMPT)
        or ""
    ).strip()
    minute_prompt = str(
        config.get(CONFIG_KEY_ADVANCED_CLASSIFY_MINUTE_PROMPT, DEFAULT_ADVANCED_MINUTE_PROMPT)
        or ""
    ).strip()
    form_prompt = str(
        config.get(CONFIG_KEY_ADVANCED_CLASSIFY_FORM_PROMPT, DEFAULT_ADVANCED_FORM_PROMPT) or ""
    ).strip()
    return {
        "api_url": api_url,
        "model_id": model_id,
        "api_key": api_key,
        "hearing_prompt": hearing_prompt or DEFAULT_ADVANCED_HEARING_PROMPT,
        "minute_prompt": minute_prompt or DEFAULT_ADVANCED_MINUTE_PROMPT,
        "form_prompt": form_prompt or DEFAULT_ADVANCED_FORM_PROMPT,
        "disable_reasoning": bool(shared.get("disable_reasoning", DEFAULT_DISABLE_REASONING)),
        "local_vision_enabled": bool(shared.get("local_vision_enabled", False)),
        "local_vision_start_command": str(
            shared.get("local_vision_start_command", DEFAULT_LOCAL_VISION_START_COMMAND) or ""
        ).strip(),
    }


def save_advanced_classify_settings(
    hearing_prompt: str,
    minute_prompt: str,
    form_prompt: str,
) -> None:
    config = _read_config()
    config[CONFIG_KEY_ADVANCED_CLASSIFY_HEARING_PROMPT] = (
        hearing_prompt or DEFAULT_ADVANCED_HEARING_PROMPT
    )
    config[CONFIG_KEY_ADVANCED_CLASSIFY_MINUTE_PROMPT] = (
        minute_prompt or DEFAULT_ADVANCED_MINUTE_PROMPT
    )
    config[CONFIG_KEY_ADVANCED_CLASSIFY_FORM_PROMPT] = (
        form_prompt or DEFAULT_ADVANCED_FORM_PROMPT
    )
    _write_config(config)

def load_classify_dates_settings() -> dict[str, Any]:
    config = _read_config()
    shared = load_classifier_settings()
    api_url = shared["api_url"]
    model_id = shared["model_id"]
    api_key = shared["api_key"]
    hearing_prompt = str(
        config.get(CONFIG_KEY_CLASSIFY_DATES_HEARING_PROMPT, DEFAULT_CLASSIFY_HEARING_DATES_PROMPT)
        or ""
    ).strip()
    minute_prompt = str(
        config.get(CONFIG_KEY_CLASSIFY_DATES_MINUTE_PROMPT, DEFAULT_CLASSIFY_MINUTE_DATES_PROMPT)
        or ""
    ).strip()
    return {
        "api_url": api_url,
        "model_id": model_id,
        "api_key": api_key,
        "hearing_prompt": hearing_prompt or DEFAULT_CLASSIFY_HEARING_DATES_PROMPT,
        "minute_prompt": minute_prompt or DEFAULT_CLASSIFY_MINUTE_DATES_PROMPT,
        "disable_reasoning": bool(shared.get("disable_reasoning", DEFAULT_DISABLE_REASONING)),
        "local_vision_enabled": bool(shared.get("local_vision_enabled", False)),
        "local_vision_start_command": str(
            shared.get("local_vision_start_command", DEFAULT_LOCAL_VISION_START_COMMAND) or ""
        ).strip(),
    }


def save_classify_dates_settings(
    hearing_prompt: str,
    minute_prompt: str,
) -> None:
    config = _read_config()
    config[CONFIG_KEY_CLASSIFY_DATES_HEARING_PROMPT] = (
        hearing_prompt or DEFAULT_CLASSIFY_HEARING_DATES_PROMPT
    )
    config[CONFIG_KEY_CLASSIFY_DATES_MINUTE_PROMPT] = (
        minute_prompt or DEFAULT_CLASSIFY_MINUTE_DATES_PROMPT
    )
    _write_config(config)


def load_classify_names_settings() -> dict[str, Any]:
    config = _read_config()
    shared = load_classifier_settings()
    api_url = shared["api_url"]
    model_id = shared["model_id"]
    api_key = shared["api_key"]
    report_prompt = str(
        config.get(CONFIG_KEY_CLASSIFY_NAMES_REPORT_PROMPT, DEFAULT_CLASSIFY_REPORT_NAMES_PROMPT)
        or ""
    ).strip()
    form_prompt = str(
        config.get(CONFIG_KEY_CLASSIFY_NAMES_FORM_PROMPT, DEFAULT_CLASSIFY_FORM_NAMES_PROMPT) or ""
    ).strip()
    return {
        "api_url": api_url,
        "model_id": model_id,
        "api_key": api_key,
        "report_prompt": report_prompt or DEFAULT_CLASSIFY_REPORT_NAMES_PROMPT,
        "form_prompt": form_prompt or DEFAULT_CLASSIFY_FORM_NAMES_PROMPT,
        "disable_reasoning": bool(shared.get("disable_reasoning", DEFAULT_DISABLE_REASONING)),
        "local_vision_enabled": bool(shared.get("local_vision_enabled", False)),
        "local_vision_start_command": str(
            shared.get("local_vision_start_command", DEFAULT_LOCAL_VISION_START_COMMAND) or ""
        ).strip(),
    }


def save_classify_names_settings(
    report_prompt: str,
    form_prompt: str,
) -> None:
    config = _read_config()
    config[CONFIG_KEY_CLASSIFY_NAMES_REPORT_PROMPT] = (
        report_prompt or DEFAULT_CLASSIFY_REPORT_NAMES_PROMPT
    )
    config[CONFIG_KEY_CLASSIFY_NAMES_FORM_PROMPT] = form_prompt or DEFAULT_CLASSIFY_FORM_NAMES_PROMPT
    _write_config(config)


def load_case_name_settings() -> dict[str, Any]:
    config = _read_config()
    api_url = str(config.get(CONFIG_KEY_CASE_NAME_API_URL, "") or "").strip()
    model_id = str(config.get(CONFIG_KEY_CASE_NAME_MODEL_ID, "") or "").strip()
    api_key = str(config.get(CONFIG_KEY_CASE_NAME_API_KEY, "") or "").strip()
    disable_reasoning = _read_config_bool(
        config,
        CONFIG_KEY_CASE_NAME_DISABLE_REASONING,
        DEFAULT_DISABLE_REASONING,
    )
    prompt = str(config.get(CONFIG_KEY_CASE_NAME_PROMPT, DEFAULT_CASE_NAME_PROMPT) or "").strip()
    return {
        "api_url": api_url,
        "model_id": model_id,
        "api_key": api_key,
        "disable_reasoning": disable_reasoning,
        "prompt": prompt or DEFAULT_CASE_NAME_PROMPT,
    }


def save_case_name_settings(
    api_url: str,
    model_id: str,
    api_key: str,
    disable_reasoning: bool,
    prompt: str,
) -> None:
    config = _read_config()
    config[CONFIG_KEY_CASE_NAME_API_URL] = api_url
    config[CONFIG_KEY_CASE_NAME_MODEL_ID] = model_id
    config[CONFIG_KEY_CASE_NAME_API_KEY] = api_key
    config[CONFIG_KEY_CASE_NAME_DISABLE_REASONING] = bool(disable_reasoning)
    config[CONFIG_KEY_CASE_NAME_PROMPT] = prompt or DEFAULT_CASE_NAME_PROMPT
    _write_config(config)


def load_case_context() -> tuple[str, Path | None]:
    config = _read_config()
    case_name = str(config.get(CONFIG_KEY_CASE_NAME, "") or "").strip()
    normalized = _normalize_case_name(case_name)
    if normalized != case_name:
        config[CONFIG_KEY_CASE_NAME] = normalized
        _write_config(config)
        case_name = normalized
    root_value = str(config.get(CONFIG_KEY_CASE_ROOT_DIR, "") or "").strip()
    root_dir = Path(root_value) if root_value else None
    if root_dir is not None and not root_dir.exists():
        root_dir = None
    return case_name, root_dir


def save_case_context(case_name: str, root_dir: Path) -> None:
    config = _read_config()
    config[CONFIG_KEY_CASE_NAME] = _normalize_case_name(case_name)
    config[CONFIG_KEY_CASE_ROOT_DIR] = str(root_dir)
    _write_config(config)


def load_selected_pdfs() -> list[Path]:
    config = _read_config()
    raw = config.get(CONFIG_KEY_SELECTED_PDFS)
    if isinstance(raw, list):
        paths = [Path(item) for item in raw if isinstance(item, str) and item.strip()]
        return [path for path in paths if path.exists()]
    return []


def save_selected_pdfs(paths: list[Path]) -> None:
    config = _read_config()
    config[CONFIG_KEY_SELECTED_PDFS] = [str(path) for path in paths]
    _write_config(config)


def load_text_source_setting() -> str:
    config = _read_config()
    raw = str(config.get(CONFIG_KEY_TEXT_SOURCE, "") or "").strip()
    if raw in {TEXT_SOURCE_EMBEDDED, TEXT_SOURCE_LOCAL_OCR}:
        return raw
    return DEFAULT_TEXT_SOURCE


def save_text_source_setting(value: str) -> None:
    config = _read_config()
    if value not in {TEXT_SOURCE_EMBEDDED, TEXT_SOURCE_LOCAL_OCR}:
        value = DEFAULT_TEXT_SOURCE
    config[CONFIG_KEY_TEXT_SOURCE] = value
    _write_config(config)

def load_local_ocr_settings() -> dict[str, str]:
    config = _read_config()
    server_url = str(
        config.get(CONFIG_KEY_LOCAL_OCR_SERVER_URL, DEFAULT_SERVER_URL) or ""
    ).strip()
    model_id = str(config.get(CONFIG_KEY_LOCAL_OCR_MODEL_ID, MODEL_ID) or "").strip()
    start_command = str(
        config.get(CONFIG_KEY_LOCAL_OCR_START_COMMAND, START_SERVER_COMMAND) or ""
    ).strip()
    return {
        "server_url": server_url or DEFAULT_SERVER_URL,
        "model_id": model_id or MODEL_ID,
        "start_command": start_command or START_SERVER_COMMAND,
    }


def save_local_ocr_settings(server_url: str, model_id: str, start_command: str) -> None:
    config = _read_config()
    config[CONFIG_KEY_LOCAL_OCR_SERVER_URL] = server_url or DEFAULT_SERVER_URL
    config[CONFIG_KEY_LOCAL_OCR_MODEL_ID] = model_id or MODEL_ID
    config[CONFIG_KEY_LOCAL_OCR_START_COMMAND] = start_command or START_SERVER_COMMAND
    _write_config(config)

def _generate_text_files(pdf_path: Path, text_dir: Path) -> None:
    with pdf_path.open("rb") as handle:
        pdf = pdftotext.PDF(handle, physical=True)
    for index, page_text in enumerate(pdf, start=1):
        target = text_dir / f"{index:04d}.txt"
        target.write_text(page_text, encoding="utf-8")


def _generate_image_page_files(pdf_path: Path, image_pages_dir: Path) -> None:
    doc = fitz.open(str(pdf_path))
    try:
        target_dpi = 200
        max_dimension_px = 1540
        base_zoom = target_dpi / 72.0
        for index in range(len(doc)):
            page = doc.load_page(index)
            page_rect = page.rect
            width_px = page_rect.width * target_dpi / 72.0
            height_px = page_rect.height * target_dpi / 72.0
            max_dim = max(width_px, height_px)
            scale = min(1.0, max_dimension_px / max_dim) if max_dim else 1.0
            matrix = fitz.Matrix(base_zoom * scale, base_zoom * scale)
            pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY)
            pix.save(str(image_pages_dir / f"{index + 1:04d}.png"))
    finally:
        doc.close()


def _extract_table_rows(table) -> tuple[list[str], list[list[str]]]:
    headers: list[str] = []
    rows: list[list[str]] = []

    thead = table.find("thead")
    if thead:
        header_cells = thead.find_all("th")
        headers = [cell.get_text(" ", strip=True) for cell in header_cells]

    tbody = table.find("tbody")
    tr_elements = (tbody or table).find_all("tr")
    for row_index, tr in enumerate(tr_elements):
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue
        cell_text = [cell.get_text(" ", strip=True) for cell in cells]
        if not headers and row_index == 0 and tr.find_all("th"):
            headers = cell_text
            continue
        rows.append(cell_text)

    return headers, rows


def _convert_html_tables(content: str) -> str:
    soup = BeautifulSoup(content, "html.parser")
    tables = soup.find_all("table")
    for table in tables:
        headers, rows = _extract_table_rows(table)
        if not rows and not headers:
            table.replace_with(NavigableString(""))
            continue
        table_text = tabulate(rows, headers=headers or (), tablefmt="rounded_grid")
        table.replace_with(NavigableString(f"\n{table_text}\n"))

    return soup.get_text(separator="\n\n", strip=True)


def _normalize_optimized_text(content: str) -> str:
    normalized = content
    if "<table" in normalized.lower():
        normalized = _convert_html_tables(normalized)
    return _flatten_paragraph_lines(normalized).strip()


def _strip_markdown(content: str) -> str:
    content = re.sub(r"(?m)^[ \t]*!\[[^]]*]\([^)\s]+\)[ \t]*\n?", "", content)
    return content


def _start_server(command: str) -> subprocess.Popen[str]:
    command = command.strip()
    if not command:
        raise RuntimeError("Start server command is empty.")
    return subprocess.Popen(
        ["bash", "-lc", command],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def _stop_server(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _ocr_image(image_path: Path, server_url: str, model_id: str) -> str:
    with image_path.open("rb") as handle:
        image_base64 = base64.b64encode(handle.read()).decode()
    response = requests.post(
        server_url,
        json={
            "model": model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                        }
                    ],
                }
            ],
            "max_tokens": 1024,
            "temperature": 0.2,
            "top_k": 0,
            "top_p": 0.9,
        },
        timeout=300,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def _generate_text_files_with_local_ocr(
    pdf_path: Path,
    text_dir: Path,
    image_pages_dir: Path,
    stop_check: Callable[[], None] | None = None,
    server_url: str = DEFAULT_SERVER_URL,
    start_command: str = START_SERVER_COMMAND,
    model_id: str = MODEL_ID,
    sleep_seconds: float = LOCAL_OCR_SERVER_STARTUP_SECONDS,
) -> None:
    server_process: subprocess.Popen[str] | None = None
    try:
        server_process = _start_server(start_command)
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
        _wait_for_endpoint_ready(
            server_url,
            process=server_process,
            stop_check=stop_check,
        )

        if stop_check:
            stop_check()
        _generate_image_page_files(pdf_path, image_pages_dir)
        image_paths = sorted(image_pages_dir.glob("*.png"))
        if not image_paths:
            raise RuntimeError("No images generated for OCR.")

        for image_path in image_paths:
            if stop_check:
                stop_check()
            text = _ocr_image(image_path, server_url, model_id)
            target = text_dir / f"{image_path.stem}.txt"
            target.write_text(text, encoding="utf-8")

    finally:
        if server_process is not None:
            _stop_server(server_process)

@dataclass
class ClassifySettingsWidgets:
    api_url_row: Adw.EntryRow
    model_row: Adw.EntryRow
    api_key_row: Adw.EntryRow
    prompt_buffer: Gtk.TextBuffer
    ct_prompt_buffer: Gtk.TextBuffer | None = None
    disable_reasoning_switch: Gtk.Switch | None = None
    local_server_switch: Gtk.Switch | None = None
    local_start_command_buffer: Gtk.TextBuffer | None = None
    disable_reasoning_row: Adw.SwitchRow | None = None


@dataclass
class ClassifyDatesSettingsWidgets:
    hearing_prompt_buffer: Gtk.TextBuffer
    minute_prompt_buffer: Gtk.TextBuffer


@dataclass
class ClassifyNamesSettingsWidgets:
    report_prompt_buffer: Gtk.TextBuffer
    form_prompt_buffer: Gtk.TextBuffer


@dataclass
class LocalOcrSettingsWidgets:
    server_url_row: Adw.EntryRow
    model_row: Adw.EntryRow
    start_command_buffer: Gtk.TextBuffer


@dataclass
class AdvancedClassificationSettingsWidgets:
    hearing_prompt_buffer: Gtk.TextBuffer
    minute_prompt_buffer: Gtk.TextBuffer
    form_prompt_buffer: Gtk.TextBuffer


@dataclass
class OptimizeSettingsWidgets:
    hearing_api_url_row: Adw.EntryRow
    hearing_model_row: Adw.EntryRow
    hearing_api_key_row: Adw.EntryRow
    hearing_disable_reasoning_row: Adw.SwitchRow
    report_api_url_row: Adw.EntryRow
    report_model_row: Adw.EntryRow
    report_api_key_row: Adw.EntryRow
    report_disable_reasoning_row: Adw.SwitchRow
    attorney_api_url_row: Adw.EntryRow
    attorney_model_row: Adw.EntryRow
    attorney_api_key_row: Adw.EntryRow
    attorney_disable_reasoning_row: Adw.SwitchRow
    chunk_size_row: Adw.EntryRow
    max_tokens_row: Adw.EntryRow
    attorneys_prompt_buffer: Gtk.TextBuffer
    hearings_prompt_buffer: Gtk.TextBuffer
    reports_prompt_buffer: Gtk.TextBuffer


@dataclass
class SummarizeSettingsWidgets:
    api_url_row: Adw.EntryRow
    model_row: Adw.EntryRow
    api_key_row: Adw.EntryRow
    disable_reasoning_row: Adw.SwitchRow
    chunk_size_row: Adw.EntryRow
    hearings_prompt_buffer: Gtk.TextBuffer
    reports_prompt_buffer: Gtk.TextBuffer
    minutes_prompt_buffer: Gtk.TextBuffer


@dataclass
class OverviewSettingsWidgets:
    api_url_row: Adw.EntryRow
    model_row: Adw.EntryRow
    api_key_row: Adw.EntryRow
    disable_reasoning_row: Adw.SwitchRow
    prompt_buffer: Gtk.TextBuffer


@dataclass
class RagSettingsWidgets:
    provider_row: Adw.ComboRow
    provider_values: list[str]
    voyage_model_row: Adw.EntryRow
    voyage_key_row: Adw.EntryRow
    isaacus_model_row: Adw.EntryRow
    isaacus_key_row: Adw.EntryRow


def load_optimize_settings() -> dict[str, Any]:
    config = _read_config()
    hearing_api_url = str(
        config.get(CONFIG_KEY_OPTIMIZE_HEARING_API_URL, "") or ""
    ).strip()
    hearing_model_id = str(
        config.get(CONFIG_KEY_OPTIMIZE_HEARING_MODEL_ID, "") or ""
    ).strip()
    hearing_api_key = str(
        config.get(CONFIG_KEY_OPTIMIZE_HEARING_API_KEY, "") or ""
    ).strip()
    hearing_disable_reasoning = _read_config_bool(
        config,
        CONFIG_KEY_OPTIMIZE_HEARING_DISABLE_REASONING,
        DEFAULT_DISABLE_REASONING,
    )
    report_api_url = str(
        config.get(CONFIG_KEY_OPTIMIZE_REPORT_API_URL, "") or ""
    ).strip()
    report_model_id = str(
        config.get(CONFIG_KEY_OPTIMIZE_REPORT_MODEL_ID, "") or ""
    ).strip()
    report_api_key = str(
        config.get(CONFIG_KEY_OPTIMIZE_REPORT_API_KEY, "") or ""
    ).strip()
    report_disable_reasoning = _read_config_bool(
        config,
        CONFIG_KEY_OPTIMIZE_REPORT_DISABLE_REASONING,
        DEFAULT_DISABLE_REASONING,
    )
    attorney_api_url = str(
        config.get(CONFIG_KEY_OPTIMIZE_ATTORNEY_API_URL, "") or ""
    ).strip()
    attorney_model_id = str(
        config.get(CONFIG_KEY_OPTIMIZE_ATTORNEY_MODEL_ID, "") or ""
    ).strip()
    attorney_api_key = str(
        config.get(CONFIG_KEY_OPTIMIZE_ATTORNEY_API_KEY, "") or ""
    ).strip()
    attorney_disable_reasoning = _read_config_bool(
        config,
        CONFIG_KEY_OPTIMIZE_ATTORNEY_DISABLE_REASONING,
        DEFAULT_DISABLE_REASONING,
    )
    chunk_size_raw = str(config.get(CONFIG_KEY_OPTIMIZE_CHUNK_SIZE, "") or "").strip()
    chunk_size = DEFAULT_OPTIMIZE_CHUNK_SIZE
    if chunk_size_raw:
        try:
            chunk_size = max(1, int(chunk_size_raw))
        except ValueError:
            chunk_size = DEFAULT_OPTIMIZE_CHUNK_SIZE
    max_tokens_raw = str(config.get(CONFIG_KEY_OPTIMIZE_MAX_TOKENS, "") or "").strip()
    max_tokens = DEFAULT_OPTIMIZE_MAX_TOKENS
    if max_tokens_raw:
        try:
            max_tokens = max(1, int(max_tokens_raw))
        except ValueError:
            max_tokens = DEFAULT_OPTIMIZE_MAX_TOKENS
    attorneys_prompt = str(
        config.get(CONFIG_KEY_OPTIMIZE_ATTORNEYS_PROMPT, DEFAULT_OPTIMIZE_ATTORNEYS_PROMPT) or ""
    ).strip()
    hearings_prompt = str(
        config.get(CONFIG_KEY_OPTIMIZE_HEARINGS_PROMPT, DEFAULT_OPTIMIZE_HEARINGS_PROMPT) or ""
    ).strip()
    reports_prompt = str(
        config.get(CONFIG_KEY_OPTIMIZE_REPORTS_PROMPT, DEFAULT_OPTIMIZE_REPORTS_PROMPT) or ""
    ).strip()
    return {
        "hearing_api_url": hearing_api_url,
        "hearing_model_id": hearing_model_id,
        "hearing_api_key": hearing_api_key,
        "hearing_disable_reasoning": hearing_disable_reasoning,
        "report_api_url": report_api_url,
        "report_model_id": report_model_id,
        "report_api_key": report_api_key,
        "report_disable_reasoning": report_disable_reasoning,
        "attorney_api_url": attorney_api_url,
        "attorney_model_id": attorney_model_id,
        "attorney_api_key": attorney_api_key,
        "attorney_disable_reasoning": attorney_disable_reasoning,
        "chunk_size": str(chunk_size),
        "max_tokens": str(max_tokens),
        "attorneys_prompt": attorneys_prompt or DEFAULT_OPTIMIZE_ATTORNEYS_PROMPT,
        "hearings_prompt": hearings_prompt or DEFAULT_OPTIMIZE_HEARINGS_PROMPT,
        "reports_prompt": reports_prompt or DEFAULT_OPTIMIZE_REPORTS_PROMPT,
    }


def save_optimize_settings(
    hearing_api_url: str,
    hearing_model_id: str,
    hearing_api_key: str,
    hearing_disable_reasoning: bool,
    report_api_url: str,
    report_model_id: str,
    report_api_key: str,
    report_disable_reasoning: bool,
    attorney_api_url: str,
    attorney_model_id: str,
    attorney_api_key: str,
    attorney_disable_reasoning: bool,
    chunk_size: str,
    max_tokens: str,
    attorneys_prompt: str,
    hearings_prompt: str,
    reports_prompt: str,
) -> None:
    config = _read_config()
    config[CONFIG_KEY_OPTIMIZE_HEARING_API_URL] = hearing_api_url
    config[CONFIG_KEY_OPTIMIZE_HEARING_MODEL_ID] = hearing_model_id
    config[CONFIG_KEY_OPTIMIZE_HEARING_API_KEY] = hearing_api_key
    config[CONFIG_KEY_OPTIMIZE_HEARING_DISABLE_REASONING] = bool(
        hearing_disable_reasoning
    )
    config[CONFIG_KEY_OPTIMIZE_REPORT_API_URL] = report_api_url
    config[CONFIG_KEY_OPTIMIZE_REPORT_MODEL_ID] = report_model_id
    config[CONFIG_KEY_OPTIMIZE_REPORT_API_KEY] = report_api_key
    config[CONFIG_KEY_OPTIMIZE_REPORT_DISABLE_REASONING] = bool(
        report_disable_reasoning
    )
    config[CONFIG_KEY_OPTIMIZE_ATTORNEY_API_URL] = attorney_api_url
    config[CONFIG_KEY_OPTIMIZE_ATTORNEY_MODEL_ID] = attorney_model_id
    config[CONFIG_KEY_OPTIMIZE_ATTORNEY_API_KEY] = attorney_api_key
    config[CONFIG_KEY_OPTIMIZE_ATTORNEY_DISABLE_REASONING] = bool(
        attorney_disable_reasoning
    )
    config[CONFIG_KEY_OPTIMIZE_CHUNK_SIZE] = chunk_size
    config[CONFIG_KEY_OPTIMIZE_MAX_TOKENS] = max_tokens
    config[CONFIG_KEY_OPTIMIZE_ATTORNEYS_PROMPT] = attorneys_prompt or DEFAULT_OPTIMIZE_ATTORNEYS_PROMPT
    config[CONFIG_KEY_OPTIMIZE_HEARINGS_PROMPT] = hearings_prompt or DEFAULT_OPTIMIZE_HEARINGS_PROMPT
    config[CONFIG_KEY_OPTIMIZE_REPORTS_PROMPT] = reports_prompt or DEFAULT_OPTIMIZE_REPORTS_PROMPT
    _write_config(config)


def load_summarize_settings() -> dict[str, Any]:
    config = _read_config()
    api_url = str(config.get(CONFIG_KEY_SUMMARIZE_API_URL, "") or "").strip()
    model_id = str(config.get(CONFIG_KEY_SUMMARIZE_MODEL_ID, "") or "").strip()
    api_key = str(config.get(CONFIG_KEY_SUMMARIZE_API_KEY, "") or "").strip()
    disable_reasoning = _read_config_bool(
        config,
        CONFIG_KEY_SUMMARIZE_DISABLE_REASONING,
        DEFAULT_DISABLE_REASONING,
    )
    chunk_size_raw = str(config.get(CONFIG_KEY_SUMMARIZE_CHUNK_SIZE, "") or "").strip()
    chunk_size = DEFAULT_SUMMARIZE_CHUNK_SIZE
    if chunk_size_raw:
        try:
            chunk_size = max(1, int(chunk_size_raw))
        except ValueError:
            chunk_size = DEFAULT_SUMMARIZE_CHUNK_SIZE
    hearings_prompt = str(
        config.get(CONFIG_KEY_SUMMARIZE_HEARINGS_PROMPT, DEFAULT_SUMMARIZE_HEARINGS_PROMPT) or ""
    ).strip()
    reports_prompt = str(
        config.get(CONFIG_KEY_SUMMARIZE_REPORTS_PROMPT, DEFAULT_SUMMARIZE_REPORTS_PROMPT) or ""
    ).strip()
    minutes_prompt = str(
        config.get(CONFIG_KEY_SUMMARIZE_MINUTES_PROMPT, DEFAULT_SUMMARIZE_MINUTES_PROMPT) or ""
    ).strip()
    return {
        "api_url": api_url,
        "model_id": model_id,
        "api_key": api_key,
        "disable_reasoning": disable_reasoning,
        "chunk_size": str(chunk_size),
        "hearings_prompt": hearings_prompt or DEFAULT_SUMMARIZE_HEARINGS_PROMPT,
        "reports_prompt": reports_prompt or DEFAULT_SUMMARIZE_REPORTS_PROMPT,
        "minutes_prompt": minutes_prompt or DEFAULT_SUMMARIZE_MINUTES_PROMPT,
    }


def save_summarize_settings(
    api_url: str,
    model_id: str,
    api_key: str,
    disable_reasoning: bool,
    chunk_size: str,
    hearings_prompt: str,
    reports_prompt: str,
    minutes_prompt: str,
) -> None:
    config = _read_config()
    config[CONFIG_KEY_SUMMARIZE_API_URL] = api_url
    config[CONFIG_KEY_SUMMARIZE_MODEL_ID] = model_id
    config[CONFIG_KEY_SUMMARIZE_API_KEY] = api_key
    config[CONFIG_KEY_SUMMARIZE_DISABLE_REASONING] = bool(disable_reasoning)
    config[CONFIG_KEY_SUMMARIZE_CHUNK_SIZE] = chunk_size
    config[CONFIG_KEY_SUMMARIZE_HEARINGS_PROMPT] = (
        hearings_prompt or DEFAULT_SUMMARIZE_HEARINGS_PROMPT
    )
    config[CONFIG_KEY_SUMMARIZE_REPORTS_PROMPT] = (
        reports_prompt or DEFAULT_SUMMARIZE_REPORTS_PROMPT
    )
    config[CONFIG_KEY_SUMMARIZE_MINUTES_PROMPT] = (
        minutes_prompt or DEFAULT_SUMMARIZE_MINUTES_PROMPT
    )
    _write_config(config)


def load_overview_settings() -> dict[str, Any]:
    config = _read_config()
    api_url = str(config.get(CONFIG_KEY_OVERVIEW_API_URL, "") or "").strip()
    model_id = str(config.get(CONFIG_KEY_OVERVIEW_MODEL_ID, "") or "").strip()
    api_key = str(config.get(CONFIG_KEY_OVERVIEW_API_KEY, "") or "").strip()
    disable_reasoning = _read_config_bool(
        config,
        CONFIG_KEY_OVERVIEW_DISABLE_REASONING,
        DEFAULT_DISABLE_REASONING,
    )
    prompt = str(config.get(CONFIG_KEY_OVERVIEW_PROMPT, DEFAULT_OVERVIEW_PROMPT) or "").strip()
    if prompt in {LEGACY_DEFAULT_OVERVIEW_PROMPT, PREVIOUS_DEFAULT_OVERVIEW_PROMPT}:
        prompt = DEFAULT_OVERVIEW_PROMPT
    return {
        "api_url": api_url,
        "model_id": model_id,
        "api_key": api_key,
        "disable_reasoning": disable_reasoning,
        "prompt": prompt or DEFAULT_OVERVIEW_PROMPT,
    }


def save_overview_settings(
    api_url: str,
    model_id: str,
    api_key: str,
    disable_reasoning: bool,
    prompt: str,
) -> None:
    config = _read_config()
    config[CONFIG_KEY_OVERVIEW_API_URL] = api_url
    config[CONFIG_KEY_OVERVIEW_MODEL_ID] = model_id
    config[CONFIG_KEY_OVERVIEW_API_KEY] = api_key
    config[CONFIG_KEY_OVERVIEW_DISABLE_REASONING] = bool(disable_reasoning)
    config[CONFIG_KEY_OVERVIEW_PROMPT] = prompt or DEFAULT_OVERVIEW_PROMPT
    _write_config(config)


def load_rag_settings() -> dict[str, str]:
    config = _read_config()
    provider = str(config.get(CONFIG_KEY_RAG_PROVIDER, DEFAULT_RAG_PROVIDER) or "").strip().lower()
    if provider not in {RAG_PROVIDER_VOYAGE, RAG_PROVIDER_ISAACUS}:
        provider = DEFAULT_RAG_PROVIDER
    voyage_key = str(config.get(CONFIG_KEY_RAG_VOYAGE_API_KEY, "") or "").strip()
    voyage_model = str(
        config.get(CONFIG_KEY_RAG_VOYAGE_MODEL, DEFAULT_RAG_VOYAGE_MODEL) or ""
    ).strip()
    isaacus_key = str(config.get(CONFIG_KEY_RAG_ISAACUS_API_KEY, "") or "").strip()
    isaacus_model = str(
        config.get(CONFIG_KEY_RAG_ISAACUS_MODEL, DEFAULT_RAG_ISAACUS_MODEL) or ""
    ).strip()
    return {
        "provider": provider,
        "voyage_api_key": voyage_key,
        "voyage_model": voyage_model or DEFAULT_RAG_VOYAGE_MODEL,
        "isaacus_api_key": isaacus_key,
        "isaacus_model": isaacus_model or DEFAULT_RAG_ISAACUS_MODEL,
    }


def save_rag_settings(
    provider: str,
    voyage_api_key: str,
    voyage_model: str,
    isaacus_api_key: str,
    isaacus_model: str,
) -> None:
    config = _read_config()
    normalized_provider = provider.strip().lower()
    if normalized_provider not in {RAG_PROVIDER_VOYAGE, RAG_PROVIDER_ISAACUS}:
        normalized_provider = DEFAULT_RAG_PROVIDER
    config[CONFIG_KEY_RAG_PROVIDER] = normalized_provider
    config[CONFIG_KEY_RAG_VOYAGE_API_KEY] = voyage_api_key
    config[CONFIG_KEY_RAG_VOYAGE_MODEL] = voyage_model or DEFAULT_RAG_VOYAGE_MODEL
    config[CONFIG_KEY_RAG_ISAACUS_API_KEY] = isaacus_api_key
    config[CONFIG_KEY_RAG_ISAACUS_MODEL] = isaacus_model or DEFAULT_RAG_ISAACUS_MODEL
    _write_config(config)


class SettingsWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, on_saved: Callable[[], None] | None = None) -> None:
        super().__init__(application=app, title="Settings")
        self.set_default_size(900, 720)
        self.set_resizable(True)
        self._on_saved = on_saved
        self._prompt_editors: dict[str, ClassifySettingsWidgets] = {}
        self._classify_dates_widgets: ClassifyDatesSettingsWidgets | None = None
        self._classify_names_widgets: ClassifyNamesSettingsWidgets | None = None
        self._advanced_classify_widgets: AdvancedClassificationSettingsWidgets | None = None
        self._local_ocr_widgets: LocalOcrSettingsWidgets | None = None
        self._prompt_row_keys: dict[Gtk.ListBoxRow, str] = {}
        self._text_source_row: Adw.ComboRow | None = None
        self._text_source_values: list[str] = []
        self._build_ui()

    def trigger_save(self) -> None:
        self._save_settings()

    def _build_password_row(self, title: str) -> Adw.EntryRow:
        password_row_cls = getattr(Adw, "PasswordEntryRow", None)
        if password_row_cls:
            row = password_row_cls(title=title)
            if hasattr(row, "set_show_peek_icon"):
                row.set_show_peek_icon(True)
        else:
            row = Adw.EntryRow(title=title)
            if hasattr(row, "set_input_purpose"):
                row.set_input_purpose(Gtk.InputPurpose.PASSWORD)
            if hasattr(row, "set_visibility"):
                try:
                    row.set_visibility(False)
                except Exception:
                    pass
        if hasattr(row, "set_hexpand"):
            row.set_hexpand(True)
        return row

    def _build_ui(self) -> None:
        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.add_css_class("flat")
        header.set_title_widget(Gtk.Label(label="Settings", xalign=0))
        view.add_top_bar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(18)
        box.set_margin_bottom(12)
        box.set_margin_start(18)
        box.set_margin_end(18)

        split = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        split.set_hexpand(True)
        split.set_vexpand(True)
        split.set_shrink_start_child(False)
        split.set_shrink_end_child(False)
        split.set_resize_start_child(False)
        split.set_resize_end_child(True)

        prompt_list = Gtk.ListBox()
        prompt_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        prompt_list.add_css_class("navigation-sidebar")
        prompt_list.connect("row-selected", self._on_prompt_row_selected)
        self._prompt_list = prompt_list

        prompt_list_scroller = Gtk.ScrolledWindow()
        prompt_list_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        prompt_list_scroller.set_min_content_width(220)
        prompt_list_scroller.set_child(prompt_list)

        prompt_stack = Gtk.Stack()
        prompt_stack.set_hexpand(True)
        prompt_stack.set_vexpand(True)
        prompt_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self._prompt_stack = prompt_stack

        text_source_row = Gtk.ListBoxRow()
        text_source_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        text_source_box.set_margin_top(8)
        text_source_box.set_margin_bottom(8)
        text_source_box.set_margin_start(12)
        text_source_box.set_margin_end(12)
        text_source_label = Gtk.Label(label="Create files", xalign=0)
        text_source_box.append(text_source_label)
        text_source_row.set_child(text_source_box)
        prompt_list.append(text_source_row)
        self._prompt_row_keys[text_source_row] = "text-source"
        text_source_page = self._build_text_source_page()
        prompt_stack.add_named(text_source_page, "text-source")

        local_ocr_row = Gtk.ListBoxRow()
        local_ocr_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        local_ocr_box.set_margin_top(8)
        local_ocr_box.set_margin_bottom(8)
        local_ocr_box.set_margin_start(12)
        local_ocr_box.set_margin_end(12)
        local_ocr_label = Gtk.Label(label="Local OCR", xalign=0)
        local_ocr_box.append(local_ocr_label)
        local_ocr_row.set_child(local_ocr_box)
        prompt_list.append(local_ocr_row)
        self._prompt_row_keys[local_ocr_row] = "local-ocr"
        local_ocr_page = self._build_local_ocr_page(load_local_ocr_settings())
        prompt_stack.add_named(local_ocr_page, "local-ocr")

        prompt_definitions = [
            ("case-name", "Infer Case Name", load_case_name_settings(), DEFAULT_CASE_NAME_PROMPT),
        ]
        first_row: Gtk.ListBoxRow | None = None
        for key, title, settings, default_prompt in prompt_definitions:
            row = Gtk.ListBoxRow()
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            row_box.set_margin_top(8)
            row_box.set_margin_bottom(8)
            row_box.set_margin_start(12)
            row_box.set_margin_end(12)
            label = Gtk.Label(label=title, xalign=0)
            row_box.append(label)
            row.set_child(row_box)
            prompt_list.append(row)
            self._prompt_row_keys[row] = key
            if first_row is None:
                first_row = row

            page = self._build_prompt_page(key, title, settings, default_prompt)
            prompt_stack.add_named(page, key)

        classify_row = Gtk.ListBoxRow()
        classify_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        classify_box.set_margin_top(8)
        classify_box.set_margin_bottom(8)
        classify_box.set_margin_start(12)
        classify_box.set_margin_end(12)
        classify_label = Gtk.Label(label="Classification basic", xalign=0)
        classify_box.append(classify_label)
        classify_row.set_child(classify_box)
        prompt_list.append(classify_row)
        self._prompt_row_keys[classify_row] = "classify-basic"
        classify_page = self._build_prompt_page(
            "classify-basic",
            "Classification basic",
            load_classifier_settings(),
            DEFAULT_CLASSIFIER_PROMPT,
        )
        prompt_stack.add_named(classify_page, "classify-basic")

        classify_advanced_row = Gtk.ListBoxRow()
        classify_advanced_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        classify_advanced_box.set_margin_top(8)
        classify_advanced_box.set_margin_bottom(8)
        classify_advanced_box.set_margin_start(12)
        classify_advanced_box.set_margin_end(12)
        classify_advanced_label = Gtk.Label(label="Classification advanced", xalign=0)
        classify_advanced_box.append(classify_advanced_label)
        classify_advanced_row.set_child(classify_advanced_box)
        prompt_list.append(classify_advanced_row)
        self._prompt_row_keys[classify_advanced_row] = "classify-advanced"
        classify_advanced_page = self._build_advanced_classify_prompt_page()
        prompt_stack.add_named(classify_advanced_page, "classify-advanced")

        classify_dates_row = Gtk.ListBoxRow()
        classify_dates_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        classify_dates_box.set_margin_top(8)
        classify_dates_box.set_margin_bottom(8)
        classify_dates_box.set_margin_start(12)
        classify_dates_box.set_margin_end(12)
        classify_dates_label = Gtk.Label(label="Classification dates", xalign=0)
        classify_dates_box.append(classify_dates_label)
        classify_dates_row.set_child(classify_dates_box)
        prompt_list.append(classify_dates_row)
        self._prompt_row_keys[classify_dates_row] = "classify-dates"
        classify_dates_page = self._build_classify_dates_prompt_page()
        prompt_stack.add_named(classify_dates_page, "classify-dates")

        classify_names_row = Gtk.ListBoxRow()
        classify_names_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        classify_names_box.set_margin_top(8)
        classify_names_box.set_margin_bottom(8)
        classify_names_box.set_margin_start(12)
        classify_names_box.set_margin_end(12)
        classify_names_label = Gtk.Label(label="Classification names", xalign=0)
        classify_names_box.append(classify_names_label)
        classify_names_row.set_child(classify_names_box)
        prompt_list.append(classify_names_row)
        self._prompt_row_keys[classify_names_row] = "classify-names"
        classify_names_page = self._build_classify_names_prompt_page()
        prompt_stack.add_named(classify_names_page, "classify-names")

        optimize_row = Gtk.ListBoxRow()
        optimize_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        optimize_box.set_margin_top(8)
        optimize_box.set_margin_bottom(8)
        optimize_box.set_margin_start(12)
        optimize_box.set_margin_end(12)
        optimize_label = Gtk.Label(label="Optimize", xalign=0)
        optimize_box.append(optimize_label)
        optimize_row.set_child(optimize_box)
        prompt_list.append(optimize_row)
        self._prompt_row_keys[optimize_row] = "optimize"
        optimize_page = self._build_optimize_prompt_page(load_optimize_settings())
        prompt_stack.add_named(optimize_page, "optimize")

        summarize_row = Gtk.ListBoxRow()
        summarize_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        summarize_box.set_margin_top(8)
        summarize_box.set_margin_bottom(8)
        summarize_box.set_margin_start(12)
        summarize_box.set_margin_end(12)
        summarize_label = Gtk.Label(label="Summarize", xalign=0)
        summarize_box.append(summarize_label)
        summarize_row.set_child(summarize_box)
        prompt_list.append(summarize_row)
        self._prompt_row_keys[summarize_row] = "summarize"
        summarize_page = self._build_summarize_prompt_page(load_summarize_settings())
        prompt_stack.add_named(summarize_page, "summarize")

        overview_row = Gtk.ListBoxRow()
        overview_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        overview_box.set_margin_top(8)
        overview_box.set_margin_bottom(8)
        overview_box.set_margin_start(12)
        overview_box.set_margin_end(12)
        overview_label = Gtk.Label(label="Case Overview", xalign=0)
        overview_box.append(overview_label)
        overview_row.set_child(overview_box)
        prompt_list.append(overview_row)
        self._prompt_row_keys[overview_row] = "overview"
        overview_page = self._build_overview_prompt_page(load_overview_settings())
        prompt_stack.add_named(overview_page, "overview")

        rag_row = Gtk.ListBoxRow()
        rag_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        rag_box.set_margin_top(8)
        rag_box.set_margin_bottom(8)
        rag_box.set_margin_start(12)
        rag_box.set_margin_end(12)
        rag_label = Gtk.Label(label="RAG", xalign=0)
        rag_box.append(rag_label)
        rag_row.set_child(rag_box)
        prompt_list.append(rag_row)
        self._prompt_row_keys[rag_row] = "rag"
        rag_page = self._build_rag_prompt_page(load_rag_settings())
        prompt_stack.add_named(rag_page, "rag")

        if first_row is not None:
            prompt_list.select_row(first_row)
            prompt_stack.set_visible_child_name(self._prompt_row_keys[first_row])

        split.set_start_child(prompt_list_scroller)
        split.set_end_child(prompt_stack)
        box.append(split)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_child(box)
        content.append(scrolled)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        buttons.set_margin_top(6)
        buttons.set_margin_bottom(12)
        buttons.set_margin_start(12)
        buttons.set_margin_end(12)
        buttons.set_halign(Gtk.Align.END)
        save_btn = Gtk.Button(label="Save Settings")
        save_btn.add_css_class("suggested-action")
        save_btn.add_css_class("flat")
        save_btn.set_action_name("app.save-settings")
        buttons.append(save_btn)
        content.append(buttons)

        view.set_content(content)
        self.set_content(view)

    def _build_text_source_page(self) -> Gtk.Widget:
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page_box.set_margin_top(12)
        page_box.set_margin_bottom(12)
        page_box.set_margin_start(12)
        page_box.set_margin_end(12)
        page_box.set_vexpand(True)

        title_label = Gtk.Label(label="Create files", xalign=0)
        title_label.add_css_class("title-3")
        page_box.append(title_label)

        info_label = Gtk.Label(
            label="Choose how text files are generated during Create files.",
            xalign=0,
        )
        info_label.add_css_class("dim-label")
        page_box.append(info_label)

        group = Adw.PreferencesGroup(title="Text extraction")
        group.add_css_class("list-stack")
        page_box.append(group)

        options = [
            ("Use embedded text", TEXT_SOURCE_EMBEDDED),
            ("OCR with local model", TEXT_SOURCE_LOCAL_OCR),
        ]
        labels = [label for label, _value in options]
        values = [value for _label, value in options]
        model = Gtk.StringList.new(labels)
        row = Adw.ComboRow(title="Text source")
        row.set_model(model)
        current = load_text_source_setting()
        try:
            row.set_selected(values.index(current))
        except ValueError:
            row.set_selected(0)
        group.add(row)

        self._text_source_row = row
        self._text_source_values = values

        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.set_hexpand(True)
        page.set_vexpand(True)
        page.set_child(page_box)
        return page

    def _build_prompt_editor(self, text: str) -> tuple[Gtk.ScrolledWindow, Gtk.TextBuffer]:
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_hexpand(True)
        scroller.set_vexpand(False)
        scroller.set_has_frame(False)

        buffer = Gtk.TextBuffer()
        buffer.set_text(text)
        prompt_view = Gtk.TextView.new_with_buffer(buffer)
        prompt_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        prompt_view.set_monospace(True)
        prompt_view.set_vexpand(False)
        prompt_view.set_hexpand(True)
        prompt_view.set_top_margin(12)
        prompt_view.set_bottom_margin(12)
        prompt_view.set_left_margin(12)
        prompt_view.set_right_margin(12)
        scroller.set_child(prompt_view)
        return scroller, buffer

    def _set_prompt_editor_height(
        self,
        scroller: Gtk.ScrolledWindow,
        min_height: int = 220,
    ) -> None:
        scroller.set_min_content_height(min_height)
        scroller.set_size_request(-1, min_height)

    def _build_local_ocr_page(self, settings: dict[str, str]) -> Gtk.Widget:
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page_box.set_margin_top(12)
        page_box.set_margin_bottom(12)
        page_box.set_margin_start(12)
        page_box.set_margin_end(12)
        page_box.set_vexpand(True)

        title_label = Gtk.Label(label="Local OCR", xalign=0)
        title_label.add_css_class("title-3")
        page_box.append(title_label)

        info_label = Gtk.Label(
            label="Configure the local OCR server and model used for Create files.",
            xalign=0,
        )
        info_label.add_css_class("dim-label")
        page_box.append(info_label)

        server_group = Adw.PreferencesGroup(title="Server")
        server_group.add_css_class("list-stack")
        server_group.set_hexpand(True)
        page_box.append(server_group)

        server_url_row = Adw.EntryRow(title="Server URL")
        server_url_row.set_text(settings.get("server_url", DEFAULT_SERVER_URL))
        server_group.add(server_url_row)

        model_row = Adw.EntryRow(title="Model ID")
        model_row.set_text(settings.get("model_id", MODEL_ID))
        server_group.add(model_row)

        command_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        command_section.set_hexpand(True)
        command_section.set_vexpand(True)

        command_label = Gtk.Label(label="Start server command", xalign=0)
        command_label.add_css_class("dim-label")
        command_section.append(command_label)
        command_scroller, command_buffer = self._build_prompt_editor(
            settings.get("start_command", START_SERVER_COMMAND)
        )
        self._set_prompt_editor_height(command_scroller, 180)
        command_section.append(command_scroller)
        page_box.append(command_section)

        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.set_hexpand(True)
        page.set_vexpand(True)
        page.set_child(page_box)

        self._local_ocr_widgets = LocalOcrSettingsWidgets(
            server_url_row=server_url_row,
            model_row=model_row,
            start_command_buffer=command_buffer,
        )
        return page

    def _build_prompt_page(
        self,
        key: str,
        title: str,
        settings: dict[str, Any],
        default_prompt: str,
    ) -> Gtk.Widget:
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page_box.set_margin_top(12)
        page_box.set_margin_bottom(12)
        page_box.set_margin_start(12)
        page_box.set_margin_end(12)
        page_box.set_vexpand(True)

        title_label = Gtk.Label(label=title, xalign=0)
        title_label.add_css_class("title-3")
        page_box.append(title_label)

        is_classify_basic = key == "classify-basic"
        is_case_name = key == "case-name"

        if is_classify_basic:
            info_label = Gtk.Label(
                label="Requires a vision-capable model. Choose a vision model ID.",
                xalign=0,
            )
            info_label.add_css_class("dim-label")
            page_box.append(info_label)

        credentials_group = Adw.PreferencesGroup(title="Credentials")
        credentials_group.add_css_class("list-stack")
        credentials_group.set_hexpand(True)
        page_box.append(credentials_group)

        api_url_row = Adw.EntryRow(title="API URL")
        api_url_row.set_text(settings.get("api_url", ""))
        credentials_group.add(api_url_row)

        model_title = "Vision Model ID" if is_classify_basic else "Model ID (optional)"
        model_row = Adw.EntryRow(title=model_title)
        model_row.set_text(settings.get("model_id", ""))
        credentials_group.add(model_row)

        api_key_row = self._build_password_row("API Key")
        api_key_row.set_text(settings.get("api_key", ""))
        credentials_group.add(api_key_row)
        disable_reasoning_switch: Gtk.Switch | None = None
        local_server_switch: Gtk.Switch | None = None
        local_start_command_buffer: Gtk.TextBuffer | None = None
        disable_reasoning_row: Adw.SwitchRow | None = None
        if is_classify_basic:
            disable_reasoning_row = Adw.ActionRow(
                title="Disable reasoning",
                subtitle="Leave off to use the model's default behavior.",
            )
            disable_reasoning_switch = Gtk.Switch()
            disable_reasoning_switch.set_valign(Gtk.Align.CENTER)
            disable_reasoning_switch.set_active(
                bool(settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING))
            )
            disable_reasoning_row.add_suffix(disable_reasoning_switch)
            disable_reasoning_row.set_activatable_widget(disable_reasoning_switch)
            credentials_group.add(disable_reasoning_row)

            local_server_row = Adw.ActionRow(
                title="Use local llama.cpp vision server",
                subtitle="Start local server automatically and stop it after classification tasks.",
            )
            local_server_switch = Gtk.Switch()
            local_server_switch.set_valign(Gtk.Align.CENTER)
            local_server_switch.set_active(bool(settings.get("local_vision_enabled", False)))
            local_server_row.add_suffix(local_server_switch)
            local_server_row.set_activatable_widget(local_server_switch)
            credentials_group.add(local_server_row)
        elif is_case_name:
            disable_reasoning_row = Adw.SwitchRow(
                title="Disable reasoning",
                subtitle="Leave off to use the model's default behavior.",
            )
            disable_reasoning_row.set_active(
                bool(settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING))
            )
            credentials_group.add(disable_reasoning_row)

        if is_classify_basic:
            command_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            command_section.set_hexpand(True)
            command_section.set_vexpand(True)

            command_label = Gtk.Label(label="Local server start command", xalign=0)
            command_label.add_css_class("dim-label")
            command_section.append(command_label)
            command_scroller, local_start_command_buffer = self._build_prompt_editor(
                settings.get("local_vision_start_command", DEFAULT_LOCAL_VISION_START_COMMAND)
            )
            self._set_prompt_editor_height(command_scroller, 160)
            command_section.append(command_scroller)
            page_box.append(command_section)

        buffer: Gtk.TextBuffer
        ct_buffer: Gtk.TextBuffer | None = None
        prompt_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        prompt_section.set_hexpand(True)
        prompt_section.set_vexpand(True)
        if is_classify_basic:
            rt_label = Gtk.Label(label="Reporter transcript prompt", xalign=0)
            rt_label.add_css_class("dim-label")
            prompt_section.append(rt_label)
            prompt_scroller, buffer = self._build_prompt_editor(
                settings.get("rt_prompt") or default_prompt
            )
            self._set_prompt_editor_height(prompt_scroller, 280)
            prompt_section.append(prompt_scroller)

            ct_label = Gtk.Label(label="Clerk transcript prompt", xalign=0)
            ct_label.add_css_class("dim-label")
            prompt_section.append(ct_label)
            ct_scroller, ct_buffer = self._build_prompt_editor(
                settings.get("ct_prompt") or default_prompt
            )
            self._set_prompt_editor_height(ct_scroller, 280)
            prompt_section.append(ct_scroller)
        else:
            prompt_label = Gtk.Label(label="Prompt", xalign=0)
            prompt_label.add_css_class("dim-label")
            prompt_section.append(prompt_label)
            prompt_scroller, buffer = self._build_prompt_editor(
                settings.get("prompt") or default_prompt
            )
            self._set_prompt_editor_height(prompt_scroller, 320)
            prompt_section.append(prompt_scroller)
        page_box.append(prompt_section)

        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.set_hexpand(True)
        page.set_vexpand(True)
        page.set_child(page_box)

        self._prompt_editors[key] = ClassifySettingsWidgets(
            api_url_row=api_url_row,
            model_row=model_row,
            api_key_row=api_key_row,
            prompt_buffer=buffer,
            ct_prompt_buffer=ct_buffer,
            disable_reasoning_switch=disable_reasoning_switch,
            local_server_switch=local_server_switch,
            local_start_command_buffer=local_start_command_buffer,
            disable_reasoning_row=disable_reasoning_row,
        )
        return page

    def _build_advanced_classify_prompt_page(self) -> Gtk.Widget:
        settings = load_advanced_classify_settings()

        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page_box.set_margin_top(12)
        page_box.set_margin_bottom(12)
        page_box.set_margin_start(12)
        page_box.set_margin_end(12)
        page_box.set_vexpand(True)

        title_label = Gtk.Label(label="Classification advanced", xalign=0)
        title_label.add_css_class("title-3")
        page_box.append(title_label)

        info_label = Gtk.Label(
            label="Uses Classification basic vision model credentials.",
            xalign=0,
        )
        info_label.add_css_class("dim-label")
        page_box.append(info_label)

        prompt_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        prompt_section.set_hexpand(True)
        prompt_section.set_vexpand(True)

        hearing_label = Gtk.Label(label="Hearing First Page Prompt", xalign=0)
        hearing_label.add_css_class("dim-label")
        prompt_section.append(hearing_label)
        hearing_scroller, hearing_buffer = self._build_prompt_editor(
            settings.get("hearing_prompt") or DEFAULT_ADVANCED_HEARING_PROMPT
        )
        self._set_prompt_editor_height(hearing_scroller, 240)
        prompt_section.append(hearing_scroller)

        minute_label = Gtk.Label(label="Minute Order First Page Prompt", xalign=0)
        minute_label.add_css_class("dim-label")
        prompt_section.append(minute_label)
        minute_scroller, minute_buffer = self._build_prompt_editor(
            settings.get("minute_prompt") or DEFAULT_ADVANCED_MINUTE_PROMPT
        )
        self._set_prompt_editor_height(minute_scroller, 240)
        prompt_section.append(minute_scroller)

        forms_label = Gtk.Label(label="Form First Page Prompt", xalign=0)
        forms_label.add_css_class("dim-label")
        prompt_section.append(forms_label)
        forms_scroller, forms_buffer = self._build_prompt_editor(
            settings.get("form_prompt") or DEFAULT_ADVANCED_FORM_PROMPT
        )
        self._set_prompt_editor_height(forms_scroller, 240)
        prompt_section.append(forms_scroller)

        page_box.append(prompt_section)

        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.set_hexpand(True)
        page.set_vexpand(True)
        page.set_child(page_box)

        self._advanced_classify_widgets = AdvancedClassificationSettingsWidgets(
            hearing_prompt_buffer=hearing_buffer,
            minute_prompt_buffer=minute_buffer,
            form_prompt_buffer=forms_buffer,
        )
        return page

    def _build_classify_dates_prompt_page(self) -> Gtk.Widget:
        settings = load_classify_dates_settings()

        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page_box.set_margin_top(12)
        page_box.set_margin_bottom(12)
        page_box.set_margin_start(12)
        page_box.set_margin_end(12)
        page_box.set_vexpand(True)

        title_label = Gtk.Label(label="Classification dates", xalign=0)
        title_label.add_css_class("title-3")
        page_box.append(title_label)

        info_label = Gtk.Label(
            label="Uses Classification basic vision model credentials.",
            xalign=0,
        )
        info_label.add_css_class("dim-label")
        page_box.append(info_label)

        prompt_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        prompt_section.set_hexpand(True)
        prompt_section.set_vexpand(True)

        hearing_label = Gtk.Label(label="Hearing Date Prompt", xalign=0)
        hearing_label.add_css_class("dim-label")
        prompt_section.append(hearing_label)
        hearing_scroller, hearing_buffer = self._build_prompt_editor(
            settings.get("hearing_prompt") or DEFAULT_CLASSIFY_HEARING_DATES_PROMPT
        )
        self._set_prompt_editor_height(hearing_scroller, 240)
        prompt_section.append(hearing_scroller)

        minute_label = Gtk.Label(label="Minute Order Date Prompt", xalign=0)
        minute_label.add_css_class("dim-label")
        prompt_section.append(minute_label)
        minute_scroller, minute_buffer = self._build_prompt_editor(
            settings.get("minute_prompt") or DEFAULT_CLASSIFY_MINUTE_DATES_PROMPT
        )
        self._set_prompt_editor_height(minute_scroller, 240)
        prompt_section.append(minute_scroller)

        page_box.append(prompt_section)

        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.set_hexpand(True)
        page.set_vexpand(True)
        page.set_child(page_box)

        self._classify_dates_widgets = ClassifyDatesSettingsWidgets(
            hearing_prompt_buffer=hearing_buffer,
            minute_prompt_buffer=minute_buffer,
        )
        return page

    def _build_classify_names_prompt_page(self) -> Gtk.Widget:
        settings = load_classify_names_settings()

        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page_box.set_margin_top(12)
        page_box.set_margin_bottom(12)
        page_box.set_margin_start(12)
        page_box.set_margin_end(12)
        page_box.set_vexpand(True)

        title_label = Gtk.Label(label="Classification names", xalign=0)
        title_label.add_css_class("title-3")
        page_box.append(title_label)

        info_label = Gtk.Label(
            label="Uses Classification basic vision model credentials.",
            xalign=0,
        )
        info_label.add_css_class("dim-label")
        page_box.append(info_label)

        prompt_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        prompt_section.set_hexpand(True)
        prompt_section.set_vexpand(True)

        reports_label = Gtk.Label(label="Report Name Prompt", xalign=0)
        reports_label.add_css_class("dim-label")
        prompt_section.append(reports_label)
        reports_scroller, reports_buffer = self._build_prompt_editor(
            settings.get("report_prompt") or DEFAULT_CLASSIFY_REPORT_NAMES_PROMPT
        )
        self._set_prompt_editor_height(reports_scroller, 240)
        prompt_section.append(reports_scroller)

        forms_label = Gtk.Label(label="Form Name Prompt", xalign=0)
        forms_label.add_css_class("dim-label")
        prompt_section.append(forms_label)
        forms_scroller, forms_buffer = self._build_prompt_editor(
            settings.get("form_prompt") or DEFAULT_CLASSIFY_FORM_NAMES_PROMPT
        )
        self._set_prompt_editor_height(forms_scroller, 240)
        prompt_section.append(forms_scroller)

        page_box.append(prompt_section)

        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.set_hexpand(True)
        page.set_vexpand(True)
        page.set_child(page_box)

        self._classify_names_widgets = ClassifyNamesSettingsWidgets(
            report_prompt_buffer=reports_buffer,
            form_prompt_buffer=forms_buffer,
        )
        return page

    def _build_optimize_prompt_page(self, settings: dict[str, Any]) -> Gtk.Widget:
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page_box.set_margin_top(12)
        page_box.set_margin_bottom(12)
        page_box.set_margin_start(12)
        page_box.set_margin_end(12)
        page_box.set_vexpand(True)

        title_label = Gtk.Label(label="Optimize", xalign=0)
        title_label.add_css_class("title-3")
        page_box.append(title_label)

        hearing_credentials_group = Adw.PreferencesGroup(
            title="Hearing Optimization Credentials",
        )
        hearing_credentials_group.add_css_class("list-stack")
        hearing_credentials_group.set_hexpand(True)
        page_box.append(hearing_credentials_group)

        hearing_api_url_row = Adw.EntryRow(title="Hearing API URL")
        hearing_api_url_row.set_text(settings.get("hearing_api_url", ""))
        hearing_credentials_group.add(hearing_api_url_row)

        hearing_model_row = Adw.EntryRow(title="Hearing Model ID")
        hearing_model_row.set_text(settings.get("hearing_model_id", ""))
        hearing_credentials_group.add(hearing_model_row)

        hearing_api_key_row = self._build_password_row("Hearing API Key")
        hearing_api_key_row.set_text(settings.get("hearing_api_key", ""))
        hearing_credentials_group.add(hearing_api_key_row)

        hearing_disable_reasoning_row = Adw.SwitchRow(
            title="Disable hearing reasoning",
            subtitle="Used only for hearing optimization requests.",
        )
        hearing_disable_reasoning_row.set_active(
            bool(
                settings.get(
                    "hearing_disable_reasoning",
                    DEFAULT_DISABLE_REASONING,
                )
            )
        )
        hearing_credentials_group.add(hearing_disable_reasoning_row)

        report_credentials_group = Adw.PreferencesGroup(
            title="Report Optimization Credentials",
        )
        report_credentials_group.add_css_class("list-stack")
        report_credentials_group.set_hexpand(True)
        page_box.append(report_credentials_group)

        report_api_url_row = Adw.EntryRow(title="Report API URL")
        report_api_url_row.set_text(settings.get("report_api_url", ""))
        report_credentials_group.add(report_api_url_row)

        report_model_row = Adw.EntryRow(title="Report Model ID")
        report_model_row.set_text(settings.get("report_model_id", ""))
        report_credentials_group.add(report_model_row)

        report_api_key_row = self._build_password_row("Report API Key")
        report_api_key_row.set_text(settings.get("report_api_key", ""))
        report_credentials_group.add(report_api_key_row)

        report_disable_reasoning_row = Adw.SwitchRow(
            title="Disable report reasoning",
            subtitle="Used only for report optimization requests.",
        )
        report_disable_reasoning_row.set_active(
            bool(
                settings.get(
                    "report_disable_reasoning",
                    DEFAULT_DISABLE_REASONING,
                )
            )
        )
        report_credentials_group.add(report_disable_reasoning_row)

        attorney_credentials_group = Adw.PreferencesGroup(
            title="Counsel Role Extraction Credentials",
        )
        attorney_credentials_group.add_css_class("list-stack")
        attorney_credentials_group.set_hexpand(True)
        page_box.append(attorney_credentials_group)

        attorney_api_url_row = Adw.EntryRow(title="Counsel Role API URL")
        attorney_api_url_row.set_text(settings.get("attorney_api_url", ""))
        attorney_credentials_group.add(attorney_api_url_row)

        attorney_model_row = Adw.EntryRow(title="Counsel Role Model ID")
        attorney_model_row.set_text(settings.get("attorney_model_id", ""))
        attorney_credentials_group.add(attorney_model_row)

        attorney_api_key_row = self._build_password_row("Counsel Role API Key")
        attorney_api_key_row.set_text(settings.get("attorney_api_key", ""))
        attorney_credentials_group.add(attorney_api_key_row)

        attorney_disable_reasoning_row = Adw.SwitchRow(
            title="Disable counsel role reasoning",
            subtitle="Used only for counsel role extraction requests.",
        )
        attorney_disable_reasoning_row.set_active(
            bool(
                settings.get(
                    "attorney_disable_reasoning",
                    DEFAULT_DISABLE_REASONING,
                )
            )
        )
        attorney_credentials_group.add(attorney_disable_reasoning_row)

        chunk_size_row = Adw.EntryRow(title="Chunk Size (characters)")
        chunk_size_row.set_text(
            settings.get("chunk_size", str(DEFAULT_OPTIMIZE_CHUNK_SIZE))
        )
        hearing_credentials_group.add(chunk_size_row)

        max_tokens_row = Adw.EntryRow(title="Max Output Tokens")
        max_tokens_row.set_text(
            settings.get("max_tokens", str(DEFAULT_OPTIMIZE_MAX_TOKENS))
        )
        hearing_credentials_group.add(max_tokens_row)

        prompt_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        prompt_section.set_hexpand(True)
        prompt_section.set_vexpand(True)

        attorneys_label = Gtk.Label(label="Counsel Role Extraction Prompt", xalign=0)
        attorneys_label.add_css_class("dim-label")
        prompt_section.append(attorneys_label)
        attorneys_scroller, attorneys_buffer = self._build_prompt_editor(
            settings.get("attorneys_prompt") or DEFAULT_OPTIMIZE_ATTORNEYS_PROMPT
        )
        self._set_prompt_editor_height(attorneys_scroller, 220)
        prompt_section.append(attorneys_scroller)

        hearings_label = Gtk.Label(label="Optimize Hearings Prompt", xalign=0)
        hearings_label.add_css_class("dim-label")
        prompt_section.append(hearings_label)
        hearings_scroller, hearings_buffer = self._build_prompt_editor(
            settings.get("hearings_prompt") or DEFAULT_OPTIMIZE_HEARINGS_PROMPT
        )
        self._set_prompt_editor_height(hearings_scroller, 260)
        prompt_section.append(hearings_scroller)

        reports_label = Gtk.Label(label="Optimize Reports Prompt", xalign=0)
        reports_label.add_css_class("dim-label")
        prompt_section.append(reports_label)
        reports_scroller, reports_buffer = self._build_prompt_editor(
            settings.get("reports_prompt") or DEFAULT_OPTIMIZE_REPORTS_PROMPT
        )
        self._set_prompt_editor_height(reports_scroller, 260)
        prompt_section.append(reports_scroller)

        page_box.append(prompt_section)

        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.set_hexpand(True)
        page.set_vexpand(True)
        page.set_child(page_box)

        self._optimize_widgets = OptimizeSettingsWidgets(
            hearing_api_url_row=hearing_api_url_row,
            hearing_model_row=hearing_model_row,
            hearing_api_key_row=hearing_api_key_row,
            hearing_disable_reasoning_row=hearing_disable_reasoning_row,
            report_api_url_row=report_api_url_row,
            report_model_row=report_model_row,
            report_api_key_row=report_api_key_row,
            report_disable_reasoning_row=report_disable_reasoning_row,
            attorney_api_url_row=attorney_api_url_row,
            attorney_model_row=attorney_model_row,
            attorney_api_key_row=attorney_api_key_row,
            attorney_disable_reasoning_row=attorney_disable_reasoning_row,
            chunk_size_row=chunk_size_row,
            max_tokens_row=max_tokens_row,
            attorneys_prompt_buffer=attorneys_buffer,
            hearings_prompt_buffer=hearings_buffer,
            reports_prompt_buffer=reports_buffer,
        )
        return page

    def _build_summarize_prompt_page(self, settings: dict[str, Any]) -> Gtk.Widget:
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page_box.set_margin_top(12)
        page_box.set_margin_bottom(12)
        page_box.set_margin_start(12)
        page_box.set_margin_end(12)
        page_box.set_vexpand(True)

        title_label = Gtk.Label(label="Summarize", xalign=0)
        title_label.add_css_class("title-3")
        page_box.append(title_label)

        credentials_group = Adw.PreferencesGroup(title="Credentials")
        credentials_group.add_css_class("list-stack")
        credentials_group.set_hexpand(True)
        page_box.append(credentials_group)

        api_url_row = Adw.EntryRow(title="API URL")
        api_url_row.set_text(settings.get("api_url", ""))
        credentials_group.add(api_url_row)

        model_row = Adw.EntryRow(title="Model ID")
        model_row.set_text(settings.get("model_id", ""))
        credentials_group.add(model_row)

        api_key_row = self._build_password_row("API Key")
        api_key_row.set_text(settings.get("api_key", ""))
        credentials_group.add(api_key_row)

        disable_reasoning_row = Adw.SwitchRow(
            title="Disable reasoning",
            subtitle="Leave off to use the model's default behavior.",
        )
        disable_reasoning_row.set_active(
            bool(settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING))
        )
        credentials_group.add(disable_reasoning_row)

        chunk_size_row = Adw.EntryRow(title="Chunk Size (paragraphs)")
        chunk_size_row.set_text(settings.get("chunk_size", str(DEFAULT_SUMMARIZE_CHUNK_SIZE)))
        credentials_group.add(chunk_size_row)

        prompt_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        prompt_section.set_hexpand(True)
        prompt_section.set_vexpand(True)

        hearings_label = Gtk.Label(label="Summarize Hearings Prompt", xalign=0)
        hearings_label.add_css_class("dim-label")
        prompt_section.append(hearings_label)
        hearings_scroller, hearings_buffer = self._build_prompt_editor(
            settings.get("hearings_prompt") or DEFAULT_SUMMARIZE_HEARINGS_PROMPT
        )
        self._set_prompt_editor_height(hearings_scroller, 240)
        prompt_section.append(hearings_scroller)

        reports_label = Gtk.Label(label="Summarize Reports Prompt", xalign=0)
        reports_label.add_css_class("dim-label")
        prompt_section.append(reports_label)
        reports_scroller, reports_buffer = self._build_prompt_editor(
            settings.get("reports_prompt") or DEFAULT_SUMMARIZE_REPORTS_PROMPT
        )
        self._set_prompt_editor_height(reports_scroller, 240)
        prompt_section.append(reports_scroller)

        minutes_label = Gtk.Label(label="Summarize Minute Orders Prompt", xalign=0)
        minutes_label.add_css_class("dim-label")
        prompt_section.append(minutes_label)
        minutes_scroller, minutes_buffer = self._build_prompt_editor(
            settings.get("minutes_prompt") or DEFAULT_SUMMARIZE_MINUTES_PROMPT
        )
        self._set_prompt_editor_height(minutes_scroller, 240)
        prompt_section.append(minutes_scroller)

        page_box.append(prompt_section)

        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.set_hexpand(True)
        page.set_vexpand(True)
        page.set_child(page_box)

        self._summarize_widgets = SummarizeSettingsWidgets(
            api_url_row=api_url_row,
            model_row=model_row,
            api_key_row=api_key_row,
            disable_reasoning_row=disable_reasoning_row,
            chunk_size_row=chunk_size_row,
            hearings_prompt_buffer=hearings_buffer,
            reports_prompt_buffer=reports_buffer,
            minutes_prompt_buffer=minutes_buffer,
        )
        return page

    def _build_overview_prompt_page(self, settings: dict[str, Any]) -> Gtk.Widget:
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page_box.set_margin_top(12)
        page_box.set_margin_bottom(12)
        page_box.set_margin_start(12)
        page_box.set_margin_end(12)
        page_box.set_vexpand(True)

        title_label = Gtk.Label(label="Case Overview", xalign=0)
        title_label.add_css_class("title-3")
        page_box.append(title_label)

        credentials_group = Adw.PreferencesGroup(title="Credentials")
        credentials_group.add_css_class("list-stack")
        credentials_group.set_hexpand(True)
        page_box.append(credentials_group)

        api_url_row = Adw.EntryRow(title="API URL")
        api_url_row.set_text(settings.get("api_url", ""))
        credentials_group.add(api_url_row)

        model_row = Adw.EntryRow(title="Model ID")
        model_row.set_text(settings.get("model_id", ""))
        credentials_group.add(model_row)

        api_key_row = self._build_password_row("API Key")
        api_key_row.set_text(settings.get("api_key", ""))
        credentials_group.add(api_key_row)

        disable_reasoning_row = Adw.SwitchRow(
            title="Disable reasoning",
            subtitle="Leave off to use the model's default behavior.",
        )
        disable_reasoning_row.set_active(
            bool(settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING))
        )
        credentials_group.add(disable_reasoning_row)

        prompt_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        prompt_section.set_hexpand(True)
        prompt_section.set_vexpand(True)
        prompt_label = Gtk.Label(label="Prompt", xalign=0)
        prompt_label.add_css_class("dim-label")
        prompt_section.append(prompt_label)
        prompt_scroller, buffer = self._build_prompt_editor(
            settings.get("prompt") or DEFAULT_OVERVIEW_PROMPT
        )
        self._set_prompt_editor_height(prompt_scroller, 320)
        prompt_section.append(prompt_scroller)
        page_box.append(prompt_section)

        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.set_hexpand(True)
        page.set_vexpand(True)
        page.set_child(page_box)

        self._overview_widgets = OverviewSettingsWidgets(
            api_url_row=api_url_row,
            model_row=model_row,
            api_key_row=api_key_row,
            disable_reasoning_row=disable_reasoning_row,
            prompt_buffer=buffer,
        )
        return page

    def _build_rag_prompt_page(self, settings: dict[str, str]) -> Gtk.Widget:
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page_box.set_margin_top(12)
        page_box.set_margin_bottom(12)
        page_box.set_margin_start(12)
        page_box.set_margin_end(12)
        page_box.set_vexpand(True)

        title_label = Gtk.Label(label="RAG", xalign=0)
        title_label.add_css_class("title-3")
        page_box.append(title_label)

        provider_group = Adw.PreferencesGroup(title="Embedding Provider")
        provider_group.add_css_class("list-stack")
        provider_group.set_hexpand(True)
        page_box.append(provider_group)

        provider_values = [RAG_PROVIDER_VOYAGE, RAG_PROVIDER_ISAACUS]
        provider_labels = ["VoyageAI", "Isaacus"]
        provider_row = Adw.ComboRow(title="Provider")
        provider_row.set_model(Gtk.StringList.new(provider_labels))
        provider = (settings.get("provider") or DEFAULT_RAG_PROVIDER).strip().lower()
        if provider in provider_values:
            provider_row.set_selected(provider_values.index(provider))
        else:
            provider_row.set_selected(0)
        provider_group.add(provider_row)

        voyage_group = Adw.PreferencesGroup(title="Voyage RAG")
        voyage_group.add_css_class("list-stack")
        voyage_group.set_hexpand(True)
        page_box.append(voyage_group)

        voyage_model_row = Adw.EntryRow(title="Voyage Model")
        voyage_model_row.set_text(settings.get("voyage_model", DEFAULT_RAG_VOYAGE_MODEL))
        voyage_group.add(voyage_model_row)

        voyage_key_row = self._build_password_row("Voyage API Key")
        voyage_key_row.set_text(settings.get("voyage_api_key", ""))
        voyage_group.add(voyage_key_row)

        isaacus_group = Adw.PreferencesGroup(title="Isaacus RAG")
        isaacus_group.add_css_class("list-stack")
        isaacus_group.set_hexpand(True)
        page_box.append(isaacus_group)

        isaacus_model_row = Adw.EntryRow(title="Isaacus Model")
        isaacus_model_row.set_text(settings.get("isaacus_model", DEFAULT_RAG_ISAACUS_MODEL))
        isaacus_group.add(isaacus_model_row)

        isaacus_key_row = self._build_password_row("Isaacus API Key")
        isaacus_key_row.set_text(settings.get("isaacus_api_key", ""))
        isaacus_group.add(isaacus_key_row)

        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.set_hexpand(True)
        page.set_vexpand(True)
        page.set_child(page_box)

        self._rag_widgets = RagSettingsWidgets(
            provider_row=provider_row,
            provider_values=provider_values,
            voyage_model_row=voyage_model_row,
            voyage_key_row=voyage_key_row,
            isaacus_model_row=isaacus_model_row,
            isaacus_key_row=isaacus_key_row,
        )
        return page

    def _prompt_text(self, buffer: Gtk.TextBuffer) -> str:
        start, end = buffer.get_bounds()
        return buffer.get_text(start, end, True)

    def _on_prompt_row_selected(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if not row:
            return
        key = self._prompt_row_keys.get(row)
        if key:
            self._prompt_stack.set_visible_child_name(key)

    def _save_settings(self) -> None:
        case_widgets = self._prompt_editors.get("case-name")
        classify_basic_widgets = self._prompt_editors.get("classify-basic")
        advanced_classify_widgets = self._advanced_classify_widgets
        classify_dates_widgets = self._classify_dates_widgets
        classify_names_widgets = self._classify_names_widgets
        local_ocr_widgets = self._local_ocr_widgets
        optimize_widgets = getattr(self, "_optimize_widgets", None)
        summarize_widgets = getattr(self, "_summarize_widgets", None)
        overview_widgets = getattr(self, "_overview_widgets", None)
        rag_widgets = getattr(self, "_rag_widgets", None)
        if self._text_source_row:
            selected = self._text_source_row.get_selected()
            value = DEFAULT_TEXT_SOURCE
            if 0 <= selected < len(self._text_source_values):
                value = self._text_source_values[selected]
            save_text_source_setting(value)
        if case_widgets:
            save_case_name_settings(
                case_widgets.api_url_row.get_text().strip(),
                case_widgets.model_row.get_text().strip(),
                case_widgets.api_key_row.get_text().strip(),
                (
                    bool(case_widgets.disable_reasoning_row.get_active())
                    if case_widgets.disable_reasoning_row
                    else DEFAULT_DISABLE_REASONING
                ),
                self._prompt_text(case_widgets.prompt_buffer).strip(),
            )
        if classify_basic_widgets:
            rt_prompt = self._prompt_text(classify_basic_widgets.prompt_buffer).strip()
            ct_prompt = (
                self._prompt_text(classify_basic_widgets.ct_prompt_buffer).strip()
                if classify_basic_widgets.ct_prompt_buffer
                else rt_prompt
            )
            save_classifier_settings(
                classify_basic_widgets.api_url_row.get_text().strip(),
                classify_basic_widgets.model_row.get_text().strip(),
                classify_basic_widgets.api_key_row.get_text().strip(),
                rt_prompt,
                ct_prompt,
                (
                    bool(classify_basic_widgets.disable_reasoning_switch.get_active())
                    if classify_basic_widgets.disable_reasoning_switch
                    else DEFAULT_DISABLE_REASONING
                ),
                (
                    bool(classify_basic_widgets.local_server_switch.get_active())
                    if classify_basic_widgets.local_server_switch
                    else False
                ),
                (
                    self._prompt_text(classify_basic_widgets.local_start_command_buffer).strip()
                    if classify_basic_widgets.local_start_command_buffer
                    else DEFAULT_LOCAL_VISION_START_COMMAND
                ),
            )
        if advanced_classify_widgets:
            save_advanced_classify_settings(
                self._prompt_text(advanced_classify_widgets.hearing_prompt_buffer).strip(),
                self._prompt_text(advanced_classify_widgets.minute_prompt_buffer).strip(),
                self._prompt_text(advanced_classify_widgets.form_prompt_buffer).strip(),
            )
        if classify_dates_widgets:
            save_classify_dates_settings(
                self._prompt_text(classify_dates_widgets.hearing_prompt_buffer).strip(),
                self._prompt_text(classify_dates_widgets.minute_prompt_buffer).strip(),
            )
        if classify_names_widgets:
            save_classify_names_settings(
                self._prompt_text(classify_names_widgets.report_prompt_buffer).strip(),
                self._prompt_text(classify_names_widgets.form_prompt_buffer).strip(),
            )
        if local_ocr_widgets:
            save_local_ocr_settings(
                local_ocr_widgets.server_url_row.get_text().strip(),
                local_ocr_widgets.model_row.get_text().strip(),
                self._prompt_text(local_ocr_widgets.start_command_buffer).strip(),
            )
        if optimize_widgets:
            save_optimize_settings(
                optimize_widgets.hearing_api_url_row.get_text().strip(),
                optimize_widgets.hearing_model_row.get_text().strip(),
                optimize_widgets.hearing_api_key_row.get_text().strip(),
                bool(optimize_widgets.hearing_disable_reasoning_row.get_active()),
                optimize_widgets.report_api_url_row.get_text().strip(),
                optimize_widgets.report_model_row.get_text().strip(),
                optimize_widgets.report_api_key_row.get_text().strip(),
                bool(optimize_widgets.report_disable_reasoning_row.get_active()),
                optimize_widgets.attorney_api_url_row.get_text().strip(),
                optimize_widgets.attorney_model_row.get_text().strip(),
                optimize_widgets.attorney_api_key_row.get_text().strip(),
                bool(optimize_widgets.attorney_disable_reasoning_row.get_active()),
                optimize_widgets.chunk_size_row.get_text().strip(),
                optimize_widgets.max_tokens_row.get_text().strip(),
                self._prompt_text(optimize_widgets.attorneys_prompt_buffer).strip(),
                self._prompt_text(optimize_widgets.hearings_prompt_buffer).strip(),
                self._prompt_text(optimize_widgets.reports_prompt_buffer).strip(),
            )
        if summarize_widgets:
            save_summarize_settings(
                summarize_widgets.api_url_row.get_text().strip(),
                summarize_widgets.model_row.get_text().strip(),
                summarize_widgets.api_key_row.get_text().strip(),
                bool(summarize_widgets.disable_reasoning_row.get_active()),
                summarize_widgets.chunk_size_row.get_text().strip(),
                self._prompt_text(summarize_widgets.hearings_prompt_buffer).strip(),
                self._prompt_text(summarize_widgets.reports_prompt_buffer).strip(),
                self._prompt_text(summarize_widgets.minutes_prompt_buffer).strip(),
            )
        if overview_widgets:
            save_overview_settings(
                overview_widgets.api_url_row.get_text().strip(),
                overview_widgets.model_row.get_text().strip(),
                overview_widgets.api_key_row.get_text().strip(),
                bool(overview_widgets.disable_reasoning_row.get_active()),
                self._prompt_text(overview_widgets.prompt_buffer).strip(),
            )
        if rag_widgets:
            selected = rag_widgets.provider_row.get_selected()
            provider = DEFAULT_RAG_PROVIDER
            if 0 <= selected < len(rag_widgets.provider_values):
                provider = rag_widgets.provider_values[selected]
            save_rag_settings(
                provider,
                rag_widgets.voyage_key_row.get_text().strip(),
                rag_widgets.voyage_model_row.get_text().strip(),
                rag_widgets.isaacus_key_row.get_text().strip(),
                rag_widgets.isaacus_model_row.get_text().strip(),
            )
        if self._on_saved:
            self._on_saved()
        self.close()


class TocEditorWindow(Adw.ApplicationWindow):
    def __init__(
        self,
        app: Adw.Application,
        toc_path: Path,
        on_saved: Callable[[Path], None] | None = None,
    ) -> None:
        super().__init__(application=app, title="Edit TOC")
        self.set_default_size(800, 600)
        self.set_resizable(True)
        self._toc_path = toc_path
        self._on_saved = on_saved
        self._build_ui()

    def _build_ui(self) -> None:
        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.add_css_class("flat")
        header.set_title_widget(Gtk.Label(label="Edit TOC", xalign=0))
        save_button = Gtk.Button(label="Save")
        save_button.add_css_class("flat")
        save_button.connect("clicked", self._on_save_clicked)
        header.pack_end(save_button)
        view.add_top_bar(header)

        scroller = Gtk.ScrolledWindow()
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        text_view = Gtk.TextView()
        text_view.set_wrap_mode(Gtk.WrapMode.NONE)
        text_view.set_monospace(True)
        text_view.set_vexpand(True)
        text_view.set_hexpand(True)
        buffer = text_view.get_buffer()
        initial_text = ""
        if self._toc_path.exists():
            initial_text = self._toc_path.read_text(encoding="utf-8", errors="ignore")
        buffer.set_text(initial_text)
        scroller.set_child(text_view)
        view.set_content(scroller)
        self.set_content(view)

        self._text_view = text_view

    def _on_save_clicked(self, _button: Gtk.Button) -> None:
        buffer = self._text_view.get_buffer()
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        content = buffer.get_text(start, end, True)
        self._toc_path.write_text(content.rstrip() + "\n", encoding="utf-8")
        if self._on_saved:
            self._on_saved(self._toc_path)


class TestClassificationWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, parent: "RecordPrepWindow") -> None:
        super().__init__(application=app, title="Test Classification")
        self.set_default_size(720, 560)
        self.set_resizable(True)
        self._parent = parent
        self._selected_image_path: Path | None = None
        self._mode_values: list[str] = []
        self._running = False
        self._paned_position_set = False
        self._build_ui()

    def _build_ui(self) -> None:
        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.add_css_class("flat")
        header.set_title_widget(Gtk.Label(label="Test Classification", xalign=0))
        view.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(18)
        content.set_margin_bottom(12)
        content.set_margin_start(18)
        content.set_margin_end(18)

        group = Adw.PreferencesGroup(title="Test settings")
        group.add_css_class("list-stack")
        content.append(group)

        options = [
            ("Basic (RT prompt)", "basic_rt"),
            ("Basic (CT prompt)", "basic_ct"),
            ("Advanced (Hearing prompt)", "advanced_hearing"),
            ("Advanced (Minute prompt)", "advanced_minute"),
            ("Advanced (Form prompt)", "advanced_form"),
            ("Dates (Hearing prompt)", "dates_hearing"),
            ("Dates (Minute prompt)", "dates_minute"),
            ("Names (Report prompt)", "names_report"),
            ("Names (Form prompt)", "names_form"),
        ]
        labels = [label for label, _value in options]
        self._mode_values = [value for _label, value in options]
        model = Gtk.StringList.new(labels)
        mode_row = Adw.ComboRow(title="Classification step")
        mode_row.set_model(model)
        mode_row.set_selected(0)
        group.add(mode_row)
        self._mode_row = mode_row

        image_row = Adw.ActionRow(title="Image file")
        image_row.set_subtitle("Choose a PNG image to classify.")
        choose_button = Gtk.Button(label="Choose image")
        choose_button.add_css_class("flat")
        choose_button.connect("clicked", self._on_choose_image_clicked)
        image_row.add_suffix(choose_button)
        group.add(image_row)
        self._image_row = image_row

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_hexpand(True)
        paned.set_vexpand(True)
        paned.set_shrink_start_child(False)
        paned.set_shrink_end_child(False)
        paned.set_resize_start_child(True)
        paned.set_resize_end_child(True)
        self._paned = paned

        preview_frame = Gtk.Frame()
        preview_frame.set_margin_top(6)
        preview_frame.set_margin_bottom(6)
        preview_frame.set_margin_end(6)
        preview_frame.set_hexpand(True)
        preview_frame.set_vexpand(True)
        preview_picture = Gtk.Picture()
        preview_picture.set_can_shrink(True)
        preview_picture.set_hexpand(True)
        preview_picture.set_vexpand(True)
        preview_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        preview_frame.set_child(preview_picture)
        self._preview_picture = preview_picture

        output_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        output_box.set_hexpand(True)
        output_box.set_vexpand(True)

        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._run_button = Gtk.Button(label="Run test")
        self._run_button.add_css_class("suggested-action")
        self._run_button.add_css_class("flat")
        self._run_button.connect("clicked", self._on_run_clicked)
        action_box.append(self._run_button)

        self._status_spinner = Gtk.Spinner()
        self._status_label = Gtk.Label(label="Idle", xalign=0)
        action_box.append(self._status_spinner)
        action_box.append(self._status_label)
        output_box.append(action_box)

        output_scroller = Gtk.ScrolledWindow()
        output_scroller.set_hexpand(True)
        output_scroller.set_vexpand(True)
        output_scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        output_view = Gtk.TextView()
        output_view.set_monospace(True)
        output_view.set_wrap_mode(Gtk.WrapMode.NONE)
        output_view.set_editable(False)
        output_view.set_cursor_visible(False)
        output_view.set_vexpand(True)
        output_view.set_hexpand(True)
        output_scroller.set_child(output_view)
        output_box.append(output_scroller)
        self._output_buffer = output_view.get_buffer()

        paned.set_start_child(preview_frame)
        paned.set_end_child(output_box)
        content.append(paned)

        view.set_content(content)
        self.set_content(view)
        GLib.idle_add(self._set_initial_paned_position)

    def _set_status(self, message: str, running: bool) -> None:
        self._status_label.set_text(message)
        if running:
            self._status_spinner.start()
        else:
            self._status_spinner.stop()

    def _on_choose_image_clicked(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileDialog(title="Choose PNG image")
        file_filter = Gtk.FileFilter()
        file_filter.add_mime_type("image/png")
        file_filter.set_name("PNG images")
        dialog.set_default_filter(file_filter)
        root_dir = self._parent._resolve_case_root()
        if root_dir is not None:
            image_dir = root_dir / "image_pages"
            if image_dir.exists():
                dialog.set_initial_folder(Gio.File.new_for_path(str(image_dir)))
        dialog.open(self, None, self._on_image_chosen)

    def _on_image_chosen(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            gfile = dialog.open_finish(result)
        except GLib.Error:
            return
        if not isinstance(gfile, Gio.File):
            return
        path = gfile.get_path()
        if not path:
            return
        self._selected_image_path = Path(path)
        self._image_row.set_subtitle(self._selected_image_path.name)
        self._preview_picture.set_filename(str(self._selected_image_path))

    def _set_initial_paned_position(self) -> bool:
        if self._paned_position_set:
            return False
        width = self._paned.get_width()
        if width <= 0:
            return True
        self._paned.set_position(width // 2)
        self._paned_position_set = True
        return False

    def _on_run_clicked(self, _button: Gtk.Button) -> None:
        if self._running:
            return
        if not self._selected_image_path or not self._selected_image_path.exists():
            self._set_status("Choose an image first.", False)
            return
        selected = self._mode_row.get_selected()
        if not (0 <= selected < len(self._mode_values)):
            self._set_status("Choose a classification step.", False)
            return
        mode_id = self._mode_values[selected]
        self._running = True
        self._run_button.set_sensitive(False)
        self._set_status("Running...", True)

        def _on_done(output: str, error: str | None) -> None:
            if error:
                self._set_status(f"Failed: {error}", False)
                output = error
            else:
                self._set_status("Done", False)
            self._output_buffer.set_text(output)
            self._run_button.set_sensitive(True)
            self._running = False

        self._parent.run_test_classification(mode_id, self._selected_image_path, _on_done)


class TestOptimizeSummarizeWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, parent: "RecordPrepWindow") -> None:
        super().__init__(application=app, title="Test Optimize and Summarize")
        self.set_default_size(960, 640)
        self.set_resizable(True)
        self._parent = parent
        self._mode_values: list[str] = []
        self._running = False
        self._paned_position_set = False
        self._build_ui()

    def _build_ui(self) -> None:
        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.add_css_class("flat")
        header.set_title_widget(Gtk.Label(label="Test Optimize and Summarize", xalign=0))
        view.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(18)
        content.set_margin_bottom(12)
        content.set_margin_start(18)
        content.set_margin_end(18)

        settings_group = Adw.PreferencesGroup(title="Test settings")
        settings_group.add_css_class("list-stack")
        content.append(settings_group)

        options = [
            ("Optimize (Counsel roles prompt)", "optimize_attorneys"),
            ("Optimize (Hearings prompt)", "optimize_hearings"),
            ("Optimize (Reports prompt)", "optimize_reports"),
            ("Summarize (Hearings prompt)", "summarize_hearings"),
            ("Summarize (Reports prompt)", "summarize_reports"),
            ("Summarize (Minutes prompt)", "summarize_minutes"),
        ]
        labels = [label for label, _value in options]
        self._mode_values = [value for _label, value in options]
        mode_model = Gtk.StringList.new(labels)
        mode_row = Adw.ComboRow(title="Test mode")
        mode_row.set_model(mode_model)
        mode_row.set_selected(0)
        mode_row.connect("notify::selected", self._on_mode_changed)
        settings_group.add(mode_row)
        self._mode_row = mode_row

        details_row = Adw.ActionRow(title="Prompt and input")
        settings_group.add(details_row)
        self._details_row = details_row

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_hexpand(True)
        paned.set_vexpand(True)
        paned.set_shrink_start_child(False)
        paned.set_shrink_end_child(False)
        paned.set_resize_start_child(True)
        paned.set_resize_end_child(True)
        self._paned = paned

        input_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        input_box.set_hexpand(True)
        input_box.set_vexpand(True)
        input_box.set_margin_top(6)
        input_box.set_margin_end(6)
        input_box.append(Gtk.Label(label="Raw input", xalign=0))
        input_scroller = Gtk.ScrolledWindow()
        input_scroller.set_hexpand(True)
        input_scroller.set_vexpand(True)
        input_scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        input_view = Gtk.TextView()
        input_view.set_monospace(True)
        input_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        input_view.set_vexpand(True)
        input_view.set_hexpand(True)
        input_view.set_top_margin(10)
        input_view.set_bottom_margin(10)
        input_view.set_left_margin(10)
        input_view.set_right_margin(10)
        input_scroller.set_child(input_view)
        input_box.append(input_scroller)
        self._input_buffer = input_view.get_buffer()

        output_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        output_box.set_hexpand(True)
        output_box.set_vexpand(True)
        output_box.set_margin_top(6)
        output_box.append(Gtk.Label(label="Output", xalign=0))

        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._run_button = Gtk.Button(label="Run test")
        self._run_button.add_css_class("suggested-action")
        self._run_button.add_css_class("flat")
        self._run_button.connect("clicked", self._on_run_clicked)
        action_box.append(self._run_button)

        self._status_spinner = Gtk.Spinner()
        self._status_label = Gtk.Label(label="Idle", xalign=0)
        action_box.append(self._status_spinner)
        action_box.append(self._status_label)
        output_box.append(action_box)

        output_scroller = Gtk.ScrolledWindow()
        output_scroller.set_hexpand(True)
        output_scroller.set_vexpand(True)
        output_scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        output_view = Gtk.TextView()
        output_view.set_monospace(True)
        output_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        output_view.set_editable(False)
        output_view.set_cursor_visible(False)
        output_view.set_vexpand(True)
        output_view.set_hexpand(True)
        output_view.set_top_margin(10)
        output_view.set_bottom_margin(10)
        output_view.set_left_margin(10)
        output_view.set_right_margin(10)
        output_scroller.set_child(output_view)
        output_box.append(output_scroller)
        self._output_buffer = output_view.get_buffer()

        paned.set_start_child(input_box)
        paned.set_end_child(output_box)
        content.append(paned)

        view.set_content(content)
        self.set_content(view)
        self._apply_mode_settings(self._mode_values[0])
        GLib.idle_add(self._set_initial_paned_position)

    def _buffer_text(self, buffer: Gtk.TextBuffer) -> str:
        start, end = buffer.get_bounds()
        return buffer.get_text(start, end, True)

    def _set_status(self, message: str, running: bool) -> None:
        self._status_label.set_text(message)
        if running:
            self._status_spinner.start()
        else:
            self._status_spinner.stop()

    def _set_initial_paned_position(self) -> bool:
        if self._paned_position_set:
            return False
        width = self._paned.get_width()
        if width <= 0:
            return True
        self._paned.set_position(width // 2)
        self._paned_position_set = True
        return False

    def _mode_details(self, mode_id: str) -> str:
        if mode_id == "optimize_attorneys":
            return "Uses the saved counsel role extraction prompt and counsel role credentials. Paste hearing transcript text."
        if mode_id == "optimize_hearings":
            return (
                "Uses the saved hearing optimize prompt and the selected case's "
                "`artifacts/preoptimized/counsel_roles.json`. If the first line starts with "
                "'Hearing date:', that date is used; otherwise 'TEST DATE' is used."
            )
        if mode_id == "optimize_reports":
            return "Uses the saved Optimize reports prompt. Paste raw report text."
        if mode_id == "summarize_hearings":
            return "Uses the saved Summarize hearings prompt. Paste optimized hearing text."
        if mode_id == "summarize_reports":
            return "Uses the saved Summarize reports prompt. Paste optimized report text."
        if mode_id == "summarize_minutes":
            return "Uses the saved Summarize minutes prompt. Paste minute order text."
        return "Uses the saved prompt for the selected mode."

    def _apply_mode_settings(self, mode_id: str) -> None:
        self._details_row.set_subtitle(self._mode_details(mode_id))

    def _on_mode_changed(self, _row: Adw.ComboRow, _pspec: GObject.ParamSpec) -> None:
        selected = self._mode_row.get_selected()
        if 0 <= selected < len(self._mode_values):
            self._apply_mode_settings(self._mode_values[selected])

    def _on_run_clicked(self, _button: Gtk.Button) -> None:
        if self._running:
            return
        selected = self._mode_row.get_selected()
        if not (0 <= selected < len(self._mode_values)):
            self._set_status("Choose a test mode.", False)
            return
        raw_text = self._buffer_text(self._input_buffer).strip()
        if not raw_text:
            self._set_status("Enter raw text first.", False)
            return
        mode_id = self._mode_values[selected]
        self._running = True
        self._run_button.set_sensitive(False)
        self._set_status("Running...", True)

        def _on_done(output: str, error: str | None) -> None:
            if error:
                self._set_status(f"Failed: {error}", False)
                output = error
            else:
                self._set_status("Done", False)
            self._output_buffer.set_text(output)
            self._run_button.set_sensitive(True)
            self._running = False

        self._parent.run_test_optimize_summarize(mode_id, raw_text, {}, _on_done)


class RecordPrepWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title=APPLICATION_NAME)
        self.set_default_size(900, 600)

        self.selected_pdfs: list[Path] = []
        self._settings_window: SettingsWindow | None = None
        self._toc_editor_window: TocEditorWindow | None = None
        self._pipeline_running = False
        self._stop_event = threading.Event()
        self._step_status_labels: dict[Adw.ActionRow, Gtk.Label] = {}
        self._rt_ct_split_spin: Gtk.SpinButton | None = None
        self._rt_ct_split_label: Gtk.Label | None = None
        self._rt_ct_split_dropdown: Gtk.DropDown | None = None
        self._rt_ct_split_entry: Gtk.Entry | None = None
        self._rt_ct_split_pending: int | None = None
        self._rt_ct_split_mode_pending: str | None = None
        self._rt_ct_split_updating = False
        self._test_classification_window: TestClassificationWindow | None = None
        self._test_optimize_summarize_window: TestOptimizeSummarizeWindow | None = None
        self._log_buffer: Gtk.TextBuffer | None = None
        self._log_view: Gtk.TextView | None = None
        self.run_indicator_spinner: Gtk.Spinner | None = None
        self._run_until_dropdown: Gtk.DropDown | None = None
        self._run_until_values: list[str | None] = [None]
        self._run_completion_message: str | None = None
        self._local_vision_server_process: subprocess.Popen[str] | None = None
        self._local_vision_server_owned = False

        header_bar = Adw.HeaderBar()

        self.case_bundle_button = Gtk.Button.new_from_icon_name("folder-open-symbolic")
        self.case_bundle_button.set_tooltip_text("Choose case bundle")
        self.case_bundle_button.add_css_class("flat")
        self.case_bundle_button.connect("clicked", self.on_choose_case_bundle)
        header_bar.pack_start(self.case_bundle_button)

        self.file_button = Gtk.Button.new_from_icon_name("list-add-symbolic")
        self.file_button.set_tooltip_text("Choose PDF(s)")
        self.file_button.add_css_class("flat")
        self.file_button.connect("clicked", self.on_choose_pdf)
        header_bar.pack_start(self.file_button)

        self.menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic")
        header_bar.pack_end(self.menu_button)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header_bar)
        self.set_content(toolbar_view)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(24)
        content.set_margin_bottom(24)
        content.set_margin_start(24)
        content.set_margin_end(24)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(content)
        scroller.set_vexpand(True)
        toolbar_view.set_content(scroller)

        log_frame = Gtk.Frame(label="Log")
        log_frame.set_hexpand(True)
        log_frame.set_margin_top(6)
        log_scroller = Gtk.ScrolledWindow()
        log_scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        log_scroller.set_min_content_height(140)
        log_scroller.set_vexpand(False)
        log_view = Gtk.TextView()
        log_view.set_editable(False)
        log_view.set_cursor_visible(False)
        log_view.set_monospace(True)
        log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        log_view.set_left_margin(10)
        log_view.set_right_margin(10)
        log_view.set_top_margin(8)
        log_view.set_bottom_margin(8)
        log_scroller.set_child(log_view)
        log_frame.set_child(log_scroller)
        self._log_view = log_view
        self._log_buffer = log_view.get_buffer()

        transcript_section = self._build_transcript_split_section()
        content.append(transcript_section)

        self.selected_label = Gtk.Label(label="Selected: None", xalign=0)
        self.selected_label.add_css_class("dim-label")
        content.append(self.selected_label)

        content.append(log_frame)

        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.run_all_button = Gtk.Button(label="Run all steps")
        self.run_all_button.set_halign(Gtk.Align.START)
        self.run_all_button.connect("clicked", self.on_run_all_clicked)
        action_box.append(self.run_all_button)

        self.resume_button = Gtk.Button(label="Resume")
        self.resume_button.set_halign(Gtk.Align.START)
        self.resume_button.connect("clicked", self.on_resume_clicked)
        action_box.append(self.resume_button)

        self.stop_button = Gtk.Button(label="Stop")
        self.stop_button.set_halign(Gtk.Align.START)
        self.stop_button.set_sensitive(False)
        self.stop_button.connect("clicked", self.on_stop_clicked)
        action_box.append(self.stop_button)

        run_until_label = Gtk.Label(label="Run until", xalign=0)
        action_box.append(run_until_label)
        self._run_until_dropdown = Gtk.DropDown.new_from_strings(["End of pipeline"])
        self._run_until_dropdown.set_tooltip_text(
            "Stop automatically after the selected step when running all steps."
        )
        self._run_until_dropdown.connect("notify::selected", self._on_run_until_changed)
        action_box.append(self._run_until_dropdown)

        self.run_indicator_spinner = Gtk.Spinner()
        self.run_indicator_spinner.set_tooltip_text("Pipeline running")
        action_box.append(self.run_indicator_spinner)

        content.append(action_box)

        self.step_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.step_list.add_css_class("boxed-list")
        content.append(self.step_list)

        self.step_one_row = Adw.ActionRow(
            title="Create files",
            subtitle="Generate per-page text and image files for the selected PDFs.",
        )
        self.step_one_row.set_activatable(False)
        self._attach_step_controls(
            "create_files",
            self.step_one_row,
            lambda _btn: self.on_step_one_clicked(self.step_one_row),
        )
        self._attach_step_status(self.step_one_row)
        self.step_list.append(self.step_one_row)

        self.step_strip_nonstandard_row = Adw.ActionRow(
            title="Process text files",
            subtitle="Clean non-printing characters, normalize tables, and convert LaTeX.",
        )
        self.step_strip_nonstandard_row.set_activatable(False)
        self._attach_step_controls(
            "strip_characters",
            self.step_strip_nonstandard_row,
            lambda _btn: self.on_step_strip_nonstandard_clicked(self.step_strip_nonstandard_row),
        )
        self._attach_step_status(self.step_strip_nonstandard_row)
        self.step_list.append(self.step_strip_nonstandard_row)

        self.step_infer_case_row = Adw.ActionRow(
            title="Infer case",
            subtitle="Use the first pages to infer the case name and save it.",
        )
        self.step_infer_case_row.set_activatable(False)
        self._attach_step_controls(
            "infer_case",
            self.step_infer_case_row,
            lambda _btn: self.on_step_infer_case_clicked(self.step_infer_case_row),
        )
        self._attach_step_status(self.step_infer_case_row)
        self.step_list.append(self.step_infer_case_row)

        self.step_two_row = Adw.ActionRow(
            title="Classification basic",
            subtitle="Create basic classifications for RT and CT pages.",
        )
        self.step_two_row.set_activatable(False)
        self._attach_step_controls(
            "classify_basic",
            self.step_two_row,
            lambda _btn: self.on_step_two_clicked(self.step_two_row),
        )
        self._attach_step_status(self.step_two_row)
        self.step_list.append(self.step_two_row)

        self.step_advanced_row = Adw.ActionRow(
            title="Classification advanced",
            subtitle="Refine hearing, minute order, and form page types.",
        )
        self.step_advanced_row.set_activatable(False)
        self._attach_step_controls(
            "classify_advanced",
            self.step_advanced_row,
            lambda _btn: self.on_step_advanced_clicked(self.step_advanced_row),
        )
        self._attach_step_status(self.step_advanced_row)
        self.step_list.append(self.step_advanced_row)

        self.step_correct_advanced_row = Adw.ActionRow(
            title="Correct classification advanced",
            subtitle="Convert consecutive RT first-page markers to RT body pages.",
        )
        self.step_correct_advanced_row.set_activatable(False)
        self._attach_step_controls(
            "correct_classify_advanced",
            self.step_correct_advanced_row,
            lambda _btn: self.on_step_correct_advanced_clicked(
                self.step_correct_advanced_row
            ),
        )
        self._attach_step_status(self.step_correct_advanced_row)
        self.step_list.append(self.step_correct_advanced_row)

        self.step_dates_row = Adw.ActionRow(
            title="Classification dates",
            subtitle="Add hearing and minute order dates to first pages.",
        )
        self.step_dates_row.set_activatable(False)
        self._attach_step_controls(
            "classify_dates",
            self.step_dates_row,
            lambda _btn: self.on_step_dates_clicked(self.step_dates_row),
        )
        self._attach_step_status(self.step_dates_row)
        self.step_list.append(self.step_dates_row)

        self.step_names_row = Adw.ActionRow(
            title="Classification names",
            subtitle="Add report and form names to first pages.",
        )
        self.step_names_row.set_activatable(False)
        self._attach_step_controls(
            "classify_names",
            self.step_names_row,
            lambda _btn: self.on_step_names_clicked(self.step_names_row),
        )
        self._attach_step_status(self.step_names_row)
        self.step_list.append(self.step_names_row)

        self.step_six_row = Adw.ActionRow(
            title="Build TOC",
            subtitle="Compile a table of contents for forms, reports, orders, and hearings.",
        )
        self.step_six_row.set_activatable(False)
        self._attach_step_controls(
            "build_toc",
            self.step_six_row,
            lambda _btn: self.on_step_six_clicked(self.step_six_row),
        )
        self._attach_step_status(self.step_six_row)
        self.step_list.append(self.step_six_row)

        self.step_correct_toc_row = Adw.ActionRow(
            title="Correct TOC",
            subtitle="Remove duplicate minute order dates in the TOC.",
        )
        self.step_correct_toc_row.set_activatable(False)
        self._attach_step_controls(
            "correct_toc",
            self.step_correct_toc_row,
            lambda _btn: self.on_step_correct_toc_clicked(self.step_correct_toc_row),
        )
        self._attach_step_status(self.step_correct_toc_row)
        self.step_list.append(self.step_correct_toc_row)

        self.step_seven_row = Adw.ActionRow(
            title="Find boundaries",
            subtitle="Determine page ranges for hearings, named reports, and dated minute orders.",
        )
        self.step_seven_row.set_activatable(False)
        self._attach_step_controls(
            "find_boundaries",
            self.step_seven_row,
            lambda _btn: self.on_step_seven_clicked(self.step_seven_row),
        )
        self._attach_step_status(self.step_seven_row)
        self.step_list.append(self.step_seven_row)

        self.step_correct_boundaries_row = Adw.ActionRow(
            title="Correct boundaries",
            subtitle="Remove hearing boundaries without dates and single-page report boundaries unless they are last-minute.",
        )
        self.step_correct_boundaries_row.set_activatable(False)
        self._attach_step_controls(
            "correct_boundaries",
            self.step_correct_boundaries_row,
            lambda _btn: self.on_step_correct_boundaries_clicked(
                self.step_correct_boundaries_row
            ),
        )
        self._attach_step_status(self.step_correct_boundaries_row)
        self.step_list.append(self.step_correct_boundaries_row)

        self.step_eight_row = Adw.ActionRow(
            title="Create raw",
            subtitle="Create raw hearing and report text files.",
        )
        self.step_eight_row.set_activatable(False)
        self._attach_step_controls(
            "create_raw",
            self.step_eight_row,
            lambda _btn: self.on_step_eight_clicked(self.step_eight_row),
        )
        self._attach_step_status(self.step_eight_row)
        self.step_list.append(self.step_eight_row)

        self.step_preoptimized_row = Adw.ActionRow(
            title="Create pre-optimized",
            subtitle="Create exact pre-optimization chunk files for hearings and reports.",
        )
        self.step_preoptimized_row.set_activatable(False)
        self._attach_step_controls(
            "create_preoptimized",
            self.step_preoptimized_row,
            lambda _btn: self.on_step_preoptimized_clicked(self.step_preoptimized_row),
        )
        self._attach_step_status(self.step_preoptimized_row)
        self.step_list.append(self.step_preoptimized_row)

        self.step_nine_row = Adw.ActionRow(
            title="Create optimized",
            subtitle="Run optimization using the saved pre-optimization chunk files.",
        )
        self.step_nine_row.set_activatable(False)
        self._attach_step_controls(
            "create_optimized",
            self.step_nine_row,
            lambda _btn: self.on_step_nine_clicked(self.step_nine_row),
        )
        self._attach_step_status(self.step_nine_row)
        self.step_list.append(self.step_nine_row)

        self.step_ten_row = Adw.ActionRow(
            title="Create summaries",
            subtitle="Summarize hearings, reports, and minute orders into concise paragraphs.",
        )
        self.step_ten_row.set_activatable(False)
        self._attach_step_controls(
            "create_summaries",
            self.step_ten_row,
            lambda _btn: self.on_step_ten_clicked(self.step_ten_row),
        )
        self._attach_step_status(self.step_ten_row)
        self.step_list.append(self.step_ten_row)

        self.step_add_hearing_date_links_row = Adw.ActionRow(
            title="Add date links to hearing sum",
            subtitle="Add Markdown page links for RT and minute-order first pages.",
        )
        self.step_add_hearing_date_links_row.set_activatable(False)
        self._attach_step_controls(
            "add_hearing_date_links",
            self.step_add_hearing_date_links_row,
            lambda _btn: self.on_step_add_hearing_date_links_clicked(
                self.step_add_hearing_date_links_row
            ),
        )
        self._attach_step_status(self.step_add_hearing_date_links_row)
        self.step_list.append(self.step_add_hearing_date_links_row)

        self.step_eleven_row = Adw.ActionRow(
            title="Case overview",
            subtitle="Create parties plus factual/procedural dated histories for RAG context.",
        )
        self.step_eleven_row.set_activatable(False)
        self._attach_step_controls(
            "case_overview",
            self.step_eleven_row,
            lambda _btn: self.on_step_eleven_clicked(self.step_eleven_row),
        )
        self._attach_step_status(self.step_eleven_row)
        self.step_list.append(self.step_eleven_row)

        self.step_twelve_row = Adw.ActionRow(
            title="Create RAG index",
            subtitle="Build a VoyageAI or Isaacus Chroma vector store from optimized text.",
        )
        self.step_twelve_row.set_activatable(False)
        self._attach_step_controls(
            "create_rag_index",
            self.step_twelve_row,
            lambda _btn: self.on_step_twelve_clicked(self.step_twelve_row),
        )
        self._attach_step_status(self.step_twelve_row)
        self.step_list.append(self.step_twelve_row)

        self._setup_menu(app)
        self._populate_run_until_dropdown()
        self._load_selected_pdfs()
        self._load_case_context()
        self._load_rt_ct_split()
        self._set_status(APPLICATION_NAME, False)
        self._refresh_step_statuses_from_artifacts()

    def _setup_menu(self, app: Adw.Application) -> None:
        menu = Gio.Menu()
        menu.append("Edit TOC", "app.edit-toc")
        menu.append("Test Classification...", "app.test-classification")
        menu.append("Test Optimize/Summarize...", "app.test-optimize-summarize")
        menu.append("Settings", "app.settings")
        self.menu_button.set_menu_model(menu)

        edit_toc_action = app.lookup_action("edit-toc")
        if edit_toc_action is None:
            edit_toc_action = Gio.SimpleAction.new("edit-toc", None)
            edit_toc_action.connect("activate", self.on_edit_toc_clicked)
            app.add_action(edit_toc_action)
        edit_toc_action.set_enabled(False)
        self._edit_toc_action = edit_toc_action

        action = Gio.SimpleAction.new("settings", None)
        action.connect("activate", self.on_settings)
        app.add_action(action)

        if app.lookup_action("save-settings") is None:
            save_action = Gio.SimpleAction.new("save-settings", None)
            save_action.connect("activate", self._on_action_save_settings)
            app.add_action(save_action)

        if app.lookup_action("test-classification") is None:
            test_action = Gio.SimpleAction.new("test-classification", None)
            test_action.connect("activate", self.on_test_classification)
            app.add_action(test_action)

        if app.lookup_action("test-optimize-summarize") is None:
            optimize_summarize_action = Gio.SimpleAction.new(
                "test-optimize-summarize", None
            )
            optimize_summarize_action.connect(
                "activate", self.on_test_optimize_summarize
            )
            app.add_action(optimize_summarize_action)

    def on_settings(self, _action: Gio.SimpleAction, _param: object) -> None:
        if self._settings_window:
            self._settings_window.present()
            return
        settings = SettingsWindow(self.get_application(), on_saved=self._on_settings_saved)
        settings.connect("close-request", self._on_settings_close_request)
        self._settings_window = settings
        settings.present()

    def _on_settings_saved(self) -> None:
        self.show_toast("Settings saved.")

    def _on_settings_close_request(self, _window: SettingsWindow) -> bool:
        self._settings_window = None
        return False

    def on_test_classification(self, _action: Gio.SimpleAction, _param: object) -> None:
        if self._test_classification_window:
            self._test_classification_window.present()
            return
        test_window = TestClassificationWindow(self.get_application(), parent=self)
        test_window.connect("close-request", self._on_test_classification_close_request)
        self._test_classification_window = test_window
        test_window.present()

    def _on_test_classification_close_request(
        self, _window: TestClassificationWindow
    ) -> bool:
        self._test_classification_window = None
        return False

    def on_test_optimize_summarize(
        self, _action: Gio.SimpleAction, _param: object
    ) -> None:
        if self._test_optimize_summarize_window:
            self._test_optimize_summarize_window.present()
            return
        test_window = TestOptimizeSummarizeWindow(self.get_application(), parent=self)
        test_window.connect(
            "close-request", self._on_test_optimize_summarize_close_request
        )
        self._test_optimize_summarize_window = test_window
        test_window.present()

    def _on_test_optimize_summarize_close_request(
        self, _window: TestOptimizeSummarizeWindow
    ) -> bool:
        self._test_optimize_summarize_window = None
        return False

    def _build_test_classification_settings(self, mode_id: str) -> dict[str, Any]:
        if mode_id == "basic_rt":
            shared = load_classifier_settings()
            return {
                "api_url": shared["api_url"],
                "model_id": shared["model_id"],
                "api_key": shared["api_key"],
                "prompt": shared.get("rt_prompt") or shared.get("prompt"),
                "disable_reasoning": bool(shared.get("disable_reasoning", DEFAULT_DISABLE_REASONING)),
                "local_vision_enabled": bool(shared.get("local_vision_enabled", False)),
                "local_vision_start_command": str(
                    shared.get("local_vision_start_command", DEFAULT_LOCAL_VISION_START_COMMAND)
                    or ""
                ).strip(),
            }
        if mode_id == "basic_ct":
            shared = load_classifier_settings()
            return {
                "api_url": shared["api_url"],
                "model_id": shared["model_id"],
                "api_key": shared["api_key"],
                "prompt": shared.get("ct_prompt") or shared.get("prompt"),
                "disable_reasoning": bool(shared.get("disable_reasoning", DEFAULT_DISABLE_REASONING)),
                "local_vision_enabled": bool(shared.get("local_vision_enabled", False)),
                "local_vision_start_command": str(
                    shared.get("local_vision_start_command", DEFAULT_LOCAL_VISION_START_COMMAND)
                    or ""
                ).strip(),
            }
        if mode_id == "advanced_hearing":
            settings = load_advanced_classify_settings()
            return {
                "api_url": settings["api_url"],
                "model_id": settings["model_id"],
                "api_key": settings["api_key"],
                "prompt": settings["hearing_prompt"],
                "disable_reasoning": bool(settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)),
                "local_vision_enabled": bool(settings.get("local_vision_enabled", False)),
                "local_vision_start_command": str(
                    settings.get("local_vision_start_command", DEFAULT_LOCAL_VISION_START_COMMAND)
                    or ""
                ).strip(),
            }
        if mode_id == "advanced_minute":
            settings = load_advanced_classify_settings()
            return {
                "api_url": settings["api_url"],
                "model_id": settings["model_id"],
                "api_key": settings["api_key"],
                "prompt": settings["minute_prompt"],
                "disable_reasoning": bool(settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)),
                "local_vision_enabled": bool(settings.get("local_vision_enabled", False)),
                "local_vision_start_command": str(
                    settings.get("local_vision_start_command", DEFAULT_LOCAL_VISION_START_COMMAND)
                    or ""
                ).strip(),
            }
        if mode_id == "advanced_form":
            settings = load_advanced_classify_settings()
            return {
                "api_url": settings["api_url"],
                "model_id": settings["model_id"],
                "api_key": settings["api_key"],
                "prompt": settings["form_prompt"],
                "disable_reasoning": bool(settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)),
                "local_vision_enabled": bool(settings.get("local_vision_enabled", False)),
                "local_vision_start_command": str(
                    settings.get("local_vision_start_command", DEFAULT_LOCAL_VISION_START_COMMAND)
                    or ""
                ).strip(),
            }
        if mode_id == "dates_hearing":
            settings = load_classify_dates_settings()
            return {
                "api_url": settings["api_url"],
                "model_id": settings["model_id"],
                "api_key": settings["api_key"],
                "prompt": settings["hearing_prompt"],
                "disable_reasoning": bool(settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)),
                "local_vision_enabled": bool(settings.get("local_vision_enabled", False)),
                "local_vision_start_command": str(
                    settings.get("local_vision_start_command", DEFAULT_LOCAL_VISION_START_COMMAND)
                    or ""
                ).strip(),
            }
        if mode_id == "dates_minute":
            settings = load_classify_dates_settings()
            return {
                "api_url": settings["api_url"],
                "model_id": settings["model_id"],
                "api_key": settings["api_key"],
                "prompt": settings["minute_prompt"],
                "disable_reasoning": bool(settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)),
                "local_vision_enabled": bool(settings.get("local_vision_enabled", False)),
                "local_vision_start_command": str(
                    settings.get("local_vision_start_command", DEFAULT_LOCAL_VISION_START_COMMAND)
                    or ""
                ).strip(),
            }
        if mode_id == "names_report":
            settings = load_classify_names_settings()
            return {
                "api_url": settings["api_url"],
                "model_id": settings["model_id"],
                "api_key": settings["api_key"],
                "prompt": settings["report_prompt"],
                "disable_reasoning": bool(settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)),
                "local_vision_enabled": bool(settings.get("local_vision_enabled", False)),
                "local_vision_start_command": str(
                    settings.get("local_vision_start_command", DEFAULT_LOCAL_VISION_START_COMMAND)
                    or ""
                ).strip(),
            }
        if mode_id == "names_form":
            settings = load_classify_names_settings()
            return {
                "api_url": settings["api_url"],
                "model_id": settings["model_id"],
                "api_key": settings["api_key"],
                "prompt": settings["form_prompt"],
                "disable_reasoning": bool(settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)),
                "local_vision_enabled": bool(settings.get("local_vision_enabled", False)),
                "local_vision_start_command": str(
                    settings.get("local_vision_start_command", DEFAULT_LOCAL_VISION_START_COMMAND)
                    or ""
                ).strip(),
            }
        raise ValueError(f"Unknown classification mode: {mode_id}")

    def _build_test_optimize_summarize_settings(self, mode_id: str) -> dict[str, Any]:
        if mode_id.startswith("optimize_"):
            settings = load_optimize_settings()
            request_settings = _build_optimize_report_request_settings(settings)
            if mode_id == "optimize_attorneys":
                request_settings = _build_attorney_request_settings(settings)
            elif mode_id == "optimize_hearings":
                request_settings = _build_optimize_hearing_request_settings(settings)
            elif mode_id == "optimize_reports":
                request_settings = _build_optimize_report_request_settings(settings)
            else:
                raise ValueError(f"Unknown optimize test mode: {mode_id}")
            return request_settings
        if mode_id.startswith("summarize_"):
            settings = load_summarize_settings()
            prompt = settings["reports_prompt"]
            if mode_id == "summarize_hearings":
                prompt = settings["hearings_prompt"]
            elif mode_id == "summarize_reports":
                prompt = settings["reports_prompt"]
            elif mode_id == "summarize_minutes":
                prompt = settings["minutes_prompt"]
            else:
                raise ValueError(f"Unknown summarize test mode: {mode_id}")
            return {
                "api_url": settings["api_url"],
                "model_id": settings["model_id"],
                "api_key": settings["api_key"],
                "disable_reasoning": bool(
                    settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)
                ),
                "prompt": prompt,
            }
        raise ValueError(f"Unknown optimize/summarize mode: {mode_id}")

    def run_test_classification(
        self,
        mode_id: str,
        image_path: Path,
        on_done: Callable[[str, str | None], None],
    ) -> None:
        def _worker() -> None:
            local_server_started = False
            try:
                settings = self._build_test_classification_settings(mode_id)
                self._validate_vision_settings(settings)
                if not settings.get("prompt"):
                    raise ValueError("Prompt is empty in Settings.")
                if bool(settings.get("local_vision_enabled", False)):
                    local_server_started = self._ensure_local_vision_server_running()
                result = self._classify_image(settings, image_path.name, image_path)
                output = json.dumps(result, indent=2)
                GLib.idle_add(on_done, output, None)
            except StopRequested:
                GLib.idle_add(on_done, "", "Stopped.")
            except Exception as exc:
                GLib.idle_add(on_done, "", str(exc))
            finally:
                if local_server_started:
                    self._stop_local_vision_server()

        threading.Thread(target=_worker, daemon=True).start()

    def _parse_optimize_hearing_test_input(self, raw_text: str) -> tuple[str, str]:
        cleaned = raw_text.strip()
        if not cleaned:
            return "TEST DATE", ""
        lines = cleaned.splitlines()
        first_line = lines[0].strip() if lines else ""
        if first_line.lower().startswith("hearing date:"):
            date_value = first_line.split(":", 1)[1].strip() or "TEST DATE"
            transcript = "\n".join(lines[1:]).strip()
            return date_value, transcript or cleaned
        return "TEST DATE", cleaned

    def _summarize_hearing_test_text(
        self,
        settings: dict[str, Any],
        raw_text: str,
    ) -> str:
        chunk_size = DEFAULT_SUMMARIZE_CHUNK_SIZE
        chunk_size_raw = settings.get("chunk_size", "")
        if chunk_size_raw:
            try:
                chunk_size = max(1, int(chunk_size_raw))
            except ValueError:
                chunk_size = DEFAULT_SUMMARIZE_CHUNK_SIZE

        hearing_paragraphs = _split_paragraphs(raw_text)
        hearing_groups: list[tuple[str, list[str]]] = []
        current_date: str | None = None
        for paragraph in hearing_paragraphs:
            metadata, cleaned = _parse_retrieval_chunk(paragraph)
            date_value = str(metadata.get("hearing_date", "")).strip()
            if date_value:
                date_value = _normalize_hearing_date(date_value)
                if current_date != date_value:
                    hearing_groups.append((date_value, []))
                    current_date = date_value
            if not hearing_groups:
                hearing_groups.append(("HEARING", []))
            hearing_groups[-1][1].append(
                _remove_standalone_date_lines(_remove_hearing_date_mentions(cleaned))
            )

        output_lines: list[str] = []
        first_section = True
        for date_value, paragraphs in hearing_groups:
            self._raise_if_stop_requested()
            if not first_section:
                output_lines.append("")
            output_lines.append(date_value or "HEARING")
            output_lines.append("")
            first_section = False
            for chunk in _chunk_paragraphs(paragraphs, chunk_size):
                self._raise_if_stop_requested()
                response = self._request_plain_text(
                    {
                        "api_url": settings["api_url"],
                        "model_id": settings["model_id"],
                        "api_key": settings["api_key"],
                        "disable_reasoning": bool(
                            settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)
                        ),
                        "prompt": settings["hearings_prompt"],
                    },
                    chunk,
                )
                cleaned_response = response.strip() if response else ""
                if cleaned_response:
                    cleaned_response = _remove_hearing_date_mentions(cleaned_response)
                    output_lines.append(
                        _remove_standalone_date_lines(cleaned_response)
                    )
                    output_lines.append("")
        return _collapse_blank_lines("\n".join(output_lines)).strip()

    def _summarize_report_test_text(
        self,
        settings: dict[str, Any],
        raw_text: str,
    ) -> str:
        chunk_size = DEFAULT_SUMMARIZE_CHUNK_SIZE
        chunk_size_raw = settings.get("chunk_size", "")
        if chunk_size_raw:
            try:
                chunk_size = max(1, int(chunk_size_raw))
            except ValueError:
                chunk_size = DEFAULT_SUMMARIZE_CHUNK_SIZE

        report_paragraphs = _split_paragraphs(raw_text)
        cleaned_reports: list[str] = []
        for paragraph in report_paragraphs:
            _metadata, cleaned = _parse_retrieval_chunk(paragraph)
            if cleaned:
                cleaned_reports.append(cleaned)
        report_paragraphs = cleaned_reports
        output_lines: list[str] = []
        for chunk in _chunk_paragraphs(report_paragraphs, chunk_size):
            self._raise_if_stop_requested()
            response = self._request_plain_text(
                {
                    "api_url": settings["api_url"],
                    "model_id": settings["model_id"],
                    "api_key": settings["api_key"],
                    "disable_reasoning": bool(
                        settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)
                    ),
                    "prompt": settings["reports_prompt"],
                },
                chunk,
            )
            cleaned_response = response.strip() if response else ""
            if cleaned_response:
                output_lines.append(cleaned_response)
                output_lines.append("")
        return _collapse_blank_lines("\n".join(output_lines)).strip()

    def _optimize_hearing_test_text(
        self,
        settings: dict[str, Any],
        date_value: str,
        transcript: str,
    ) -> str:
        transcript = transcript.strip()
        if not transcript:
            return ""
        root_dir = self._resolve_case_root()
        if root_dir is None:
            raise ValueError(
                "Choose a saved case or select PDFs first so the hearing test can load "
                "`artifacts/preoptimized/counsel_roles.json`."
            )
        counsel_roles_path = root_dir / "artifacts" / "preoptimized" / "counsel_roles.json"
        if not counsel_roles_path.exists():
            raise FileNotFoundError(
                "Run Create pre-optimized first so the hearing test can use "
                "`artifacts/preoptimized/counsel_roles.json`."
            )
        try:
            counsel_roles = _normalize_counsel_role_json_payload(
                json.loads(
                    counsel_roles_path.read_text(
                        encoding="utf-8",
                        errors="ignore",
                    )
                )
            )
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid counsel_roles.json: {exc}") from exc
        hearing_metadata = {
            "type": "hearing",
            "hearing_date": _format_long_us_date(date_value)
            or _normalize_hearing_date(date_value),
        }
        section_paragraphs: list[str] = []
        self._raise_if_stop_requested()
        payload = _build_optimize_hearing_payload(
            _render_counsel_role_json(counsel_roles),
            transcript,
        )
        response = self._request_plain_text(settings, payload)
        if response:
            normalized_response = _normalize_hearing_speaker_labels(
                _normalize_optimized_text(response),
                counsel_roles,
            )
            section_paragraphs.extend(_split_paragraphs(normalized_response))
        if not section_paragraphs:
            return ""
        rendered: list[str] = []
        total_paragraphs = len(section_paragraphs)
        for chunk_index, paragraph in enumerate(section_paragraphs, start=1):
            paragraph_metadata = dict(hearing_metadata)
            paragraph_metadata["chunk_index"] = chunk_index
            paragraph_metadata["chunk_total"] = total_paragraphs
            rendered.append(_render_retrieval_chunk(paragraph_metadata, paragraph))
        return "\n\n".join(rendered)

    def _optimize_report_test_text(
        self,
        settings: dict[str, Any],
        raw_text: str,
    ) -> str:
        raw_text = raw_text.strip()
        if not raw_text:
            return ""
        report_metadata = {
            "type": "report",
            "report_name": "TEST REPORT",
        }
        section_paragraphs: list[str] = []
        self._raise_if_stop_requested()
        response = self._optimize_report_chunk(
            settings,
            raw_text,
        )
        if response:
            section_paragraphs.extend(_split_paragraphs(_normalize_optimized_text(response)))
        if not section_paragraphs:
            return ""
        rendered: list[str] = []
        total_paragraphs = len(section_paragraphs)
        for chunk_index, paragraph in enumerate(section_paragraphs, start=1):
            paragraph_metadata = dict(report_metadata)
            paragraph_metadata["chunk_index"] = chunk_index
            paragraph_metadata["chunk_total"] = total_paragraphs
            rendered.append(_render_retrieval_chunk(paragraph_metadata, paragraph))
        return "\n\n".join(rendered)

    def run_test_optimize_summarize(
        self,
        mode_id: str,
        raw_text: str,
        overrides: dict[str, Any],
        on_done: Callable[[str, str | None], None],
    ) -> None:
        def _worker() -> None:
            try:
                settings = self._build_test_optimize_summarize_settings(mode_id)
                for key in ("api_url", "model_id", "api_key", "prompt"):
                    override_value = overrides.get(key)
                    if isinstance(override_value, str) and override_value.strip():
                        settings[key] = override_value.strip()
                if "disable_reasoning" in overrides:
                    settings["disable_reasoning"] = bool(overrides["disable_reasoning"])
                if not settings["api_url"] or not settings["model_id"] or not settings["api_key"]:
                    raise ValueError("Enter API URL, model ID, and API key.")
                if not settings.get("prompt"):
                    raise ValueError("Prompt is empty in Settings.")

                output = ""
                if mode_id == "optimize_attorneys":
                    optimize_settings = load_optimize_settings()
                    counsel_roles = self._extract_counsel_roles(
                        optimize_settings,
                        _build_transcript_counsel_role_evidence(raw_text),
                    )
                    output = _render_counsel_role_json(counsel_roles)
                elif mode_id == "optimize_hearings":
                    date_value, transcript = self._parse_optimize_hearing_test_input(raw_text)
                    if not transcript:
                        raise ValueError("Enter transcript text for optimize hearing testing.")
                    output = self._optimize_hearing_test_text(
                        settings,
                        date_value,
                        transcript,
                    )
                elif mode_id == "optimize_reports":
                    output = self._optimize_report_test_text(settings, raw_text)
                elif mode_id == "summarize_hearings":
                    summarize_settings = load_summarize_settings()
                    summarize_settings.update(overrides)
                    output = self._summarize_hearing_test_text(
                        summarize_settings,
                        raw_text,
                    )
                elif mode_id == "summarize_reports":
                    summarize_settings = load_summarize_settings()
                    summarize_settings.update(overrides)
                    output = self._summarize_report_test_text(
                        summarize_settings,
                        raw_text,
                    )
                elif mode_id == "summarize_minutes":
                    output = self._request_plain_text(settings, raw_text)
                else:
                    raise ValueError(f"Unknown optimize/summarize mode: {mode_id}")
                GLib.idle_add(on_done, output.strip(), None)
            except StopRequested:
                GLib.idle_add(on_done, "", "Stopped.")
            except Exception as exc:
                GLib.idle_add(on_done, "", str(exc))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_action_save_settings(self, _action: Gio.SimpleAction, _param: object) -> None:
        if not self._settings_window:
            self.show_toast("Settings window is not open.")
            return
        self._settings_window.trigger_save()

    def on_edit_toc_clicked(self, *_args: object) -> None:
        toc_path = self._toc_path()
        if not toc_path or not toc_path.exists():
            self.show_toast("Run Build TOC to generate artifacts/toc.txt first.")
            self._update_toc_button()
            return
        if self._toc_editor_window:
            self._toc_editor_window.present()
            return
        editor = TocEditorWindow(
            self.get_application(),
            toc_path,
            on_saved=self._on_toc_editor_saved,
        )
        editor.connect("close-request", self._on_toc_editor_close_request)
        self._toc_editor_window = editor
        editor.present()

    def _on_toc_editor_saved(self, _path: Path) -> None:
        self.show_toast("TOC saved.")

    def _on_toc_editor_close_request(self, _window: TocEditorWindow) -> bool:
        self._toc_editor_window = None
        return False

    def _infer_log_level(self, message: str) -> str:
        text = message.lower()
        error_markers = (
            " failed",
            "error",
            "unable to",
            "missing ",
            "no ",
            "invalid",
            "exception",
            "fix the errors",
        )
        warn_markers = (
            "stop requested",
            "pipeline stopped",
            "choose ",
            "set the ",
            "configure ",
            "unknown ",
            "not open",
            "must be",
            "before ",
        )
        if any(marker in text for marker in error_markers):
            return "ERROR"
        if any(marker in text for marker in warn_markers):
            return "WARN"
        return "INFO"

    def _append_log_message(self, message: str, level: str = "INFO") -> bool:
        if self._log_buffer is None:
            return False
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        text = " ".join(str(message).split()).strip()
        if not text:
            return False
        level_normalized = str(level or "").upper()
        if level_normalized not in {"INFO", "WARN", "ERROR"}:
            level_normalized = self._infer_log_level(text)
        end_iter = self._log_buffer.get_end_iter()
        self._log_buffer.insert(end_iter, f"[{timestamp}] [{level_normalized}] {text}\n")
        if self._log_view is not None:
            end_iter = self._log_buffer.get_end_iter()
            self._log_view.scroll_to_iter(end_iter, 0.0, False, 0.0, 1.0)
        return False

    def show_toast(self, message: str, level: str | None = None) -> None:
        resolved_level = level or self._infer_log_level(str(message))
        GLib.idle_add(self._append_log_message, str(message), resolved_level)
        # Keep stderr logging so errors are still visible when launching from terminal.
        print(f"[{resolved_level}] {message}", file=sys.stderr)

    def _toc_path(self) -> Path | None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            return None
        return root_dir / "artifacts" / "toc.txt"

    def _update_toc_button(self) -> None:
        toc_path = self._toc_path()
        enabled = bool(toc_path and toc_path.exists())
        if hasattr(self, "_edit_toc_action") and self._edit_toc_action:
            self._edit_toc_action.set_enabled(enabled)

    def _set_status(self, message: str, active: bool) -> None:
        if active:
            if self.run_indicator_spinner is not None:
                self.run_indicator_spinner.start()
        else:
            if self.run_indicator_spinner is not None:
                self.run_indicator_spinner.stop()

    def _attach_step_status(self, row: Adw.ActionRow) -> None:
        status_label = Gtk.Label(label="Pending", xalign=1)
        status_label.add_css_class("dim-label")
        row.add_suffix(status_label)
        self._step_status_labels[row] = status_label

    def _attach_step_controls(
        self,
        step_id: str,
        row: Adw.ActionRow,
        run_one: Callable[[Gtk.Button], None],
    ) -> None:
        control_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        run_one_button = Gtk.Button(icon_name="media-playback-start-symbolic")
        run_one_button.add_css_class("flat")
        run_one_button.set_tooltip_text("Run this step")
        run_one_button.connect("clicked", run_one)
        control_box.append(run_one_button)

        run_from_button = Gtk.Button(icon_name="media-skip-forward-symbolic")
        run_from_button.add_css_class("flat")
        run_from_button.set_tooltip_text("Run this and all remaining steps")
        run_from_button.connect(
            "clicked", lambda _btn, step=step_id: self.on_run_from_step_clicked(step)
        )
        control_box.append(run_from_button)
        row.add_suffix(control_box)

    def _set_step_status(self, row: Adw.ActionRow, status: str) -> None:
        label = self._step_status_labels.get(row)
        if label is not None:
            label.set_text(status)

    def _reset_step_statuses(self) -> None:
        for row in self._step_status_labels:
            self._set_step_status(row, "Pending")

    def _refresh_step_statuses_from_artifacts(self) -> None:
        if self._pipeline_running:
            return
        root_dir = self._resolve_case_root()
        if root_dir is None:
            return

        def _set_done(row: Adw.ActionRow, done: bool) -> None:
            self._set_step_status(row, "Done" if done else "Pending")

        for step_id, row, _handler in self._pipeline_steps():
            _set_done(row, self._step_artifact_complete(step_id, root_dir))

    def _expected_classification_file_names(
        self,
        root_dir: Path,
    ) -> tuple[set[str], set[str], bool, bool]:
        text_dir = root_dir / "text_pages"
        text_files = sorted(text_dir.glob("*.txt"), key=_natural_sort_key)
        if not text_files:
            return set(), set(), False, False
        try:
            split_page, _total_pages, need_rt, need_ct, split_mode = _resolve_rt_ct_split(
                root_dir,
                text_dir,
            )
        except Exception:
            return set(), set(), False, False
        rt_expected: set[str] = set()
        ct_expected: set[str] = set()
        for index, text_path in enumerate(text_files, start=1):
            if split_mode == "rt_only":
                is_rt = True
            elif split_mode == "ct_only":
                is_rt = False
            else:
                is_rt = index <= split_page
            if is_rt and need_rt:
                rt_expected.add(text_path.name)
            elif not is_rt and need_ct:
                ct_expected.add(text_path.name)
        return rt_expected, ct_expected, need_rt, need_ct

    def _jsonl_complete_for_expected(
        self,
        path: Path,
        expected_names: set[str],
        needed: bool,
    ) -> bool:
        if not needed:
            return True
        if not expected_names or not path.exists():
            return False
        return expected_names <= _load_jsonl_file_names(path)

    def _classification_output_complete(
        self,
        root_dir: Path,
        rt_path: Path,
        ct_path: Path,
        rt_expected: set[str] | None = None,
        ct_expected: set[str] | None = None,
    ) -> bool:
        _rt_base, _ct_base, need_rt, need_ct = self._expected_classification_file_names(
            root_dir
        )
        if not need_rt and not need_ct:
            return False
        if rt_expected is None:
            rt_expected = _rt_base
        if ct_expected is None:
            ct_expected = _ct_base
        return self._jsonl_complete_for_expected(
            rt_path,
            rt_expected,
            need_rt,
        ) and self._jsonl_complete_for_expected(ct_path, ct_expected, need_ct)

    def _step_artifact_complete(self, step_id: str, root_dir: Path) -> bool:
        def _dir_has_files(path: Path, pattern: str) -> bool:
            try:
                return path.exists() and any(path.glob(pattern))
            except OSError:
                return False

        text_dir = root_dir / "text_pages"
        image_dir = root_dir / "image_pages"
        classification_dir = root_dir / "classification"
        artifacts_dir = root_dir / "artifacts"
        rag_dir = root_dir / "rag"
        summaries_path, reports_path = _summary_output_paths(root_dir)
        minutes_path = _minutes_summary_output_path(root_dir)

        if step_id == "create_files":
            return _dir_has_files(text_dir, "*.txt") and _dir_has_files(image_dir, "*.png")
        if step_id == "strip_characters":
            return _dir_has_files(text_dir, "*.txt")
        if step_id == "infer_case":
            return (root_dir / "case_name.txt").exists()
        if step_id == "classify_basic":
            return self._classification_output_complete(
                root_dir,
                classification_dir / "RT_basic.jsonl",
                classification_dir / "CT_basic.jsonl",
            )
        if step_id == "classify_advanced":
            return self._classification_output_complete(
                root_dir,
                classification_dir / "RT_basic_advanced.jsonl",
                classification_dir / "CT_basic_advanced.jsonl",
                _load_jsonl_file_names(classification_dir / "RT_basic.jsonl"),
                _load_jsonl_file_names(classification_dir / "CT_basic.jsonl"),
            )
        if step_id == "correct_classify_advanced":
            return self._classification_output_complete(
                root_dir,
                classification_dir / "RT_basic_advanced_corrected.jsonl",
                classification_dir / "CT_basic_advanced_corrected.jsonl",
                _load_jsonl_file_names(classification_dir / "RT_basic_advanced.jsonl"),
                _load_jsonl_file_names(classification_dir / "CT_basic_advanced.jsonl"),
            )
        if step_id == "classify_dates":
            return self._classification_output_complete(
                root_dir,
                classification_dir / "RT_basic_advanced_corrected_dates.jsonl",
                classification_dir / "CT_basic_advanced_corrected_dates.jsonl",
                _load_jsonl_file_names(
                    classification_dir / "RT_basic_advanced_corrected.jsonl"
                ),
                _load_jsonl_file_names(
                    classification_dir / "CT_basic_advanced_corrected.jsonl"
                ),
            )
        if step_id == "classify_names":
            return self._classification_output_complete(
                root_dir,
                classification_dir / "RT_basic_advanced_corrected_dates_names.jsonl",
                classification_dir / "CT_basic_advanced_corrected_dates_names.jsonl",
                _load_jsonl_file_names(
                    classification_dir / "RT_basic_advanced_corrected_dates.jsonl"
                ),
                _load_jsonl_file_names(
                    classification_dir / "CT_basic_advanced_corrected_dates.jsonl"
                ),
            )
        if step_id == "build_toc":
            return (artifacts_dir / "toc.txt").exists()
        if step_id == "correct_toc":
            return (artifacts_dir / "toc.txt").exists()
        if step_id == "find_boundaries":
            return (
                (artifacts_dir / "hearing_boundaries.json").exists()
                and (artifacts_dir / "report_boundaries.json").exists()
                and (artifacts_dir / "minutes_boundaries.json").exists()
            )
        if step_id == "correct_boundaries":
            return (
                (artifacts_dir / "hearing_boundaries.json").exists()
                and (artifacts_dir / "report_boundaries.json").exists()
            )
        if step_id == "create_raw":
            return (
                (artifacts_dir / "raw_hearings.txt").exists()
                and (artifacts_dir / "raw_reports.txt").exists()
            )
        if step_id == "create_preoptimized":
            return (
                (artifacts_dir / "preoptimized" / "hearings").exists()
                and (artifacts_dir / "preoptimized" / "reports").exists()
            )
        if step_id == "create_optimized":
            return (
                (artifacts_dir / "optimized_hearings.txt").exists()
                and (artifacts_dir / "optimized_reports.txt").exists()
            )
        if step_id == "create_summaries":
            return summaries_path.exists() and reports_path.exists() and minutes_path.exists()
        if step_id == "add_hearing_date_links":
            return _has_page_markdown_links(summaries_path)
        if step_id == "case_overview":
            return (rag_dir / "case_overview.txt").exists()
        if step_id == "create_rag_index":
            return (
                rag_dir.exists()
                and (rag_dir / "vector_database").exists()
                and _dir_has_files(rag_dir / "vector_database", "*")
            )
        return False

    def _finish_step(self, row: Adw.ActionRow, success: bool | str | None) -> None:
        if isinstance(success, str):
            self._set_step_status(row, success)
            return
        self._set_step_status(row, "Done" if success else "Pending")

    def _start_step(self, row: Adw.ActionRow) -> None:
        title = row.get_title() or "Working"
        self._set_step_status(row, "Pending")
        self._set_status(f"Working: {title}", True)
        self.show_toast(f"Working on {title}.", "INFO")

    def _stop_status(self) -> None:
        self._set_status(APPLICATION_NAME, False)

    def _stop_status_if_idle(self) -> None:
        if not self._pipeline_running:
            self._stop_status()

    def _stop_button_if_idle(self) -> None:
        if not self._pipeline_running:
            self.stop_button.set_sensitive(False)

    def _build_transcript_split_section(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        dropdown = Gtk.DropDown.new_from_strings(
            [
                "RT/CT Split",
                "Reporter's transcript only",
                "Clerk's transcript only",
            ]
        )
        dropdown.set_halign(Gtk.Align.START)
        dropdown.connect("notify::selected", self._on_rt_ct_split_mode_changed)
        controls.append(dropdown)

        label = Gtk.Label(label="RT ends at page", xalign=0)
        controls.append(label)

        entry = Gtk.Entry()
        entry.set_width_chars(4)
        entry.set_max_length(5)
        entry.set_input_purpose(Gtk.InputPurpose.NUMBER)
        entry.connect("activate", self._on_rt_ct_split_commit)
        entry.connect("notify::has-focus", self._on_rt_ct_split_focus_notify)
        controls.append(entry)

        self._rt_ct_split_dropdown = dropdown
        self._rt_ct_split_spin = None
        self._rt_ct_split_entry = entry
        self._rt_ct_split_label = None

        box.append(controls)
        return box

    def _set_rt_ct_split_ui(
        self, split_page: int | None, total_pages: int | None, split_mode: str
    ) -> None:
        entry = self._rt_ct_split_entry
        dropdown = self._rt_ct_split_dropdown
        if entry is None or dropdown is None:
            return
        self._rt_ct_split_updating = True
        if not entry.has_focus():
            entry.set_text(str(split_page or ""))
        dropdown.set_selected(
            0 if split_mode == "split" else (1 if split_mode == "rt_only" else 2)
        )
        self._rt_ct_split_updating = False
        entry.set_sensitive(split_mode == "split")
        if split_mode == "split":
            entry.remove_css_class("dim-label")
        else:
            entry.add_css_class("dim-label")

    def _load_rt_ct_split(self) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None or not root_dir.exists():
            pending_mode = self._rt_ct_split_mode_pending or "split"
            split_page = self._rt_ct_split_pending
            if split_page is None:
                split_page = _read_rt_ct_split_page_config()
            self._set_rt_ct_split_ui(split_page, None, pending_mode)
            return
        split_page = _read_rt_ct_split_page(root_dir)
        split_mode = _read_rt_ct_split_mode(root_dir)
        if split_page is None and self._rt_ct_split_pending:
            split_page = self._rt_ct_split_pending
            try:
                _write_manifest(
                    root_dir,
                    self.selected_pdfs,
                    rt_ct_split_page=split_page,
                    rt_ct_split_mode=split_mode,
                )
            except Exception:
                pass
            self._rt_ct_split_pending = None
        if self._rt_ct_split_mode_pending:
            split_mode = self._rt_ct_split_mode_pending
            try:
                _write_manifest(
                    root_dir,
                    self.selected_pdfs,
                    rt_ct_split_page=split_page,
                    rt_ct_split_mode=split_mode,
                )
            except Exception:
                pass
            self._rt_ct_split_mode_pending = None
        total_pages = _count_text_pages(root_dir / "text_pages")
        self._set_rt_ct_split_ui(split_page, total_pages, split_mode)

    def _on_rt_ct_split_mode_changed(
        self, dropdown: Gtk.DropDown, _pspec: GObject.ParamSpec
    ) -> None:
        if self._rt_ct_split_updating:
            return
        if self._pipeline_running:
            self.show_toast("Stop the pipeline before changing the RT/CT split.")
            root_dir = self._resolve_case_root()
            current_mode = (
                _read_rt_ct_split_mode(root_dir) if root_dir and root_dir.exists() else "split"
            )
            current_page = _read_rt_ct_split_page(root_dir) if root_dir and root_dir.exists() else None
            total_pages = (
                _count_text_pages(root_dir / "text_pages")
                if root_dir and root_dir.exists()
                else None
            )
            self._set_rt_ct_split_ui(current_page, total_pages, current_mode)
            return
        mode = "split"
        selected = dropdown.get_selected()
        if selected == 1:
            mode = "rt_only"
        elif selected == 2:
            mode = "ct_only"
        root_dir = self._resolve_case_root()
        if root_dir is None or not root_dir.exists():
            self._rt_ct_split_mode_pending = mode
            self._set_rt_ct_split_ui(self._rt_ct_split_pending, None, mode)
            return
        try:
            _write_manifest(
                root_dir,
                self.selected_pdfs,
                rt_ct_split_page=_read_rt_ct_split_page(root_dir),
                rt_ct_split_mode=mode,
            )
        except Exception as exc:
            self.show_toast(f"Unable to save RT/CT split: {exc}")
        total_pages = _count_text_pages(root_dir / "text_pages")
        self._set_rt_ct_split_ui(_read_rt_ct_split_page(root_dir), total_pages, mode)
        self._refresh_step_statuses_from_artifacts()

    def _commit_rt_ct_split_entry(self, entry: Gtk.Entry, allow_ui_update: bool) -> None:
        if self._rt_ct_split_updating:
            return
        raw = entry.get_text().strip()
        split_page = int(raw) if raw.isdigit() else None
        self._rt_ct_split_pending = split_page
        if self._pipeline_running:
            return
        root_dir = self._resolve_case_root()
        if root_dir is None or not root_dir.exists():
            self._rt_ct_split_pending = split_page
            _write_rt_ct_split_page_config(split_page)
            pending_mode = self._rt_ct_split_mode_pending or "split"
            if allow_ui_update and not entry.has_focus():
                self._set_rt_ct_split_ui(split_page, None, pending_mode)
            return
        try:
            _write_manifest(
                root_dir,
                self.selected_pdfs,
                rt_ct_split_page=split_page,
                rt_ct_split_mode=_read_rt_ct_split_mode(root_dir),
            )
            _write_rt_ct_split_page_config(split_page)
        except Exception as exc:
            self.show_toast(f"Unable to save RT/CT split: {exc}")
        self._refresh_step_statuses_from_artifacts()
        if allow_ui_update and not entry.has_focus():
            self._set_rt_ct_split_ui(
                _read_rt_ct_split_page(root_dir),
                _count_text_pages(root_dir / "text_pages"),
                _read_rt_ct_split_mode(root_dir),
            )

    def _on_rt_ct_split_commit(self, entry: Gtk.Entry) -> None:
        self._commit_rt_ct_split_entry(entry, allow_ui_update=False)

    def _on_rt_ct_split_focus_notify(
        self, entry: Gtk.Entry, _pspec: GObject.ParamSpec
    ) -> None:
        has_focus = (
            entry.has_focus() if hasattr(entry, "has_focus") else entry.get_property("has-focus")
        )
        if not has_focus:
            self._commit_rt_ct_split_entry(entry, allow_ui_update=True)

    def _raise_if_stop_requested(self) -> None:
        if self._stop_event.is_set():
            raise StopRequested()

    def _validate_vision_settings(self, settings: dict[str, Any]) -> None:
        api_url = str(settings.get("api_url", "") or "").strip()
        model_id = str(settings.get("model_id", "") or "").strip()
        if not api_url or not model_id:
            raise ValueError("Configure vision API URL and model ID in Settings.")
        local_vision_enabled = bool(settings.get("local_vision_enabled", False))
        api_key = str(settings.get("api_key", "") or "").strip()
        if not local_vision_enabled and not api_key:
            raise ValueError(
                "Configure vision API key in Settings, or enable local llama.cpp vision server."
            )
        if local_vision_enabled:
            start_command = str(settings.get("local_vision_start_command", "") or "").strip()
            if not start_command:
                raise ValueError(
                    "Configure local vision start command in Classification basic settings."
                )

    def _ensure_local_vision_server_running(self) -> bool:
        settings = load_classifier_settings()
        if not bool(settings.get("local_vision_enabled", False)):
            return False
        self._validate_vision_settings(settings)

        process = self._local_vision_server_process
        if process is not None and process.poll() is None and self._local_vision_server_owned:
            return True
        if process is not None and process.poll() is not None:
            self._local_vision_server_process = None
            self._local_vision_server_owned = False

        api_url = str(settings.get("api_url", "") or "").strip()
        if _endpoint_responding(api_url, timeout=1.0):
            return False

        start_command = str(settings.get("local_vision_start_command", "") or "").strip()
        process = _start_server(start_command)
        self._local_vision_server_process = process
        self._local_vision_server_owned = True
        if LOCAL_VISION_SERVER_STARTUP_SECONDS > 0:
            time.sleep(LOCAL_VISION_SERVER_STARTUP_SECONDS)
        try:
            _wait_for_endpoint_ready(
                api_url,
                process=process,
                stop_check=self._raise_if_stop_requested,
            )
        except Exception:
            self._local_vision_server_process = None
            self._local_vision_server_owned = False
            raise
        return True

    def _stop_local_vision_server(self) -> None:
        process = self._local_vision_server_process
        owned = self._local_vision_server_owned
        self._local_vision_server_process = None
        self._local_vision_server_owned = False
        if process is None or not owned:
            return
        _stop_server(process)

    def on_stop_clicked(self, _button: Gtk.Button) -> None:
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        self.stop_button.set_sensitive(False)
        self.show_toast("Stop requested.")

    def _safe_update_manifest(
        self,
        root_dir: Path,
        pipeline_info: dict[str, Any] | None = None,
        rt_ct_split_page: int | None = None,
        rt_ct_split_mode: str | None = None,
    ) -> None:
        try:
            if pipeline_info:
                pipeline_info = {
                    key: value
                    for key, value in pipeline_info.items()
                    if key
                    not in {
                        "last_completed_step",
                        "last_failed_step",
                        "last_completed_at",
                        "last_failed_at",
                    }
                }
                if not pipeline_info:
                    pipeline_info = None
            _write_manifest(
                root_dir,
                self.selected_pdfs,
                pipeline_info=pipeline_info,
                rt_ct_split_page=rt_ct_split_page,
                rt_ct_split_mode=rt_ct_split_mode,
            )
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Manifest update failed: {exc}")

    def on_choose_pdf(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileDialog(title="Choose PDF files")
        file_filter = Gtk.FileFilter()
        file_filter.add_mime_type("application/pdf")
        file_filter.set_name("PDF files")
        dialog.set_default_filter(file_filter)
        dialog.open_multiple(self, None, self._on_files_chosen)

    def on_choose_case_bundle(self, _button: Gtk.Button) -> None:
        if self._pipeline_running:
            self.show_toast("Stop the pipeline before choosing a case bundle.")
            return
        dialog = Gtk.FileDialog(title="Choose case bundle folder")
        base_dir = self._resolve_case_base()
        if base_dir is not None:
            dialog.set_initial_folder(Gio.File.new_for_path(str(base_dir)))
        dialog.select_folder(self, None, self._on_case_bundle_chosen)

    def _on_case_bundle_chosen(
        self, dialog: Gtk.FileDialog, result: Gio.AsyncResult
    ) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        if not isinstance(folder, Gio.File):
            return
        selected_path = folder.get_path()
        if not selected_path:
            return
        selected = Path(selected_path)
        root_dir: Path | None = None
        base_dir: Path | None = None
        if selected.name == "case_bundle":
            root_dir = selected
            base_dir = selected.parent
        elif (selected / "case_bundle").is_dir():
            base_dir = selected
            root_dir = selected / "case_bundle"
        if root_dir is None or base_dir is None or not root_dir.exists():
            self.show_toast("Choose a case_bundle folder or its parent directory.")
            return
        case_name = _load_case_name_from_file(root_dir)
        if not case_name:
            case_name = _sanitize_case_name_value(base_dir.name)
        save_case_context(case_name, base_dir)
        self.selected_pdfs = []
        save_selected_pdfs([])
        display_name = _display_case_name(case_name) or "case bundle"
        self.selected_label.set_text(f"Selected: {display_name}")
        self.show_toast(f"Selected: {display_name}")
        self._reset_step_statuses()
        self._load_rt_ct_split()
        self._update_toc_button()
        self._refresh_step_statuses_from_artifacts()

    def _on_files_chosen(
        self, dialog: Gtk.FileDialog, result: Gio.AsyncResult
    ) -> None:
        try:
            files = dialog.open_multiple_finish(result)
        except GLib.Error:
            return
        paths: list[Path] = []
        for index in range(files.get_n_items()):
            gfile = files.get_item(index)
            if not isinstance(gfile, Gio.File):
                continue
            path = gfile.get_path()
            if path:
                paths.append(Path(path))
        if not paths:
            self.show_toast("No PDFs selected.")
            return
        self.selected_pdfs = sorted(paths, key=_natural_sort_key)
        save_selected_pdfs(self.selected_pdfs)
        label = (
            self.selected_pdfs[0].name
            if len(self.selected_pdfs) == 1
            else f"{len(self.selected_pdfs)} PDFs selected"
        )
        self._reset_step_statuses()
        self.selected_label.set_text(f"Selected: {label}")
        self.show_toast(f"Selected: {label}")
        self._load_rt_ct_split()
        self._update_toc_button()
        self._refresh_step_statuses_from_artifacts()

    def _load_selected_pdfs(self) -> None:
        self.selected_pdfs = load_selected_pdfs()
        if not self.selected_pdfs:
            return
        label = (
            self.selected_pdfs[0].name
            if len(self.selected_pdfs) == 1
            else f"{len(self.selected_pdfs)} PDFs selected"
        )
        self._reset_step_statuses()
        self.selected_label.set_text(f"Selected: {label}")
        self._load_rt_ct_split()
        self._update_toc_button()
        self._refresh_step_statuses_from_artifacts()

    def _load_case_context(self) -> None:
        case_name, _root_dir = load_case_context()
        if case_name:
            display_name = _display_case_name(case_name) or case_name
            self.selected_label.set_text(f"Selected: {display_name}")
        self._load_rt_ct_split()
        self._update_toc_button()
        self._refresh_step_statuses_from_artifacts()

    def _pipeline_steps(self) -> list[tuple[str, Adw.ActionRow, Callable[[], bool]]]:
        return [
            ("create_files", self.step_one_row, self._run_step_one),
            ("strip_characters", self.step_strip_nonstandard_row, self._run_step_strip_nonstandard),
            ("infer_case", self.step_infer_case_row, self._run_step_infer_case),
            ("classify_basic", self.step_two_row, self._run_step_two),
            ("classify_advanced", self.step_advanced_row, self._run_step_advanced),
            (
                "correct_classify_advanced",
                self.step_correct_advanced_row,
                self._run_step_correct_advanced,
            ),
            ("classify_dates", self.step_dates_row, self._run_step_dates),
            ("classify_names", self.step_names_row, self._run_step_names),
            ("build_toc", self.step_six_row, self._run_step_six),
            ("correct_toc", self.step_correct_toc_row, self._run_step_correct_toc),
            ("find_boundaries", self.step_seven_row, self._run_step_seven),
            (
                "correct_boundaries",
                self.step_correct_boundaries_row,
                self._run_step_correct_boundaries,
            ),
            ("create_raw", self.step_eight_row, self._run_step_eight),
            ("create_preoptimized", self.step_preoptimized_row, self._run_step_preoptimized),
            ("create_optimized", self.step_nine_row, self._run_step_nine),
            ("create_summaries", self.step_ten_row, self._run_step_ten),
            (
                "add_hearing_date_links",
                self.step_add_hearing_date_links_row,
                self._run_step_add_hearing_date_links,
            ),
            ("case_overview", self.step_eleven_row, self._run_step_eleven),
            ("create_rag_index", self.step_twelve_row, self._run_step_twelve),
        ]

    def _pipeline_step_options(self) -> list[tuple[str, str]]:
        options: list[tuple[str, str]] = []
        for step_id, row, _handler in self._pipeline_steps():
            label = (row.get_title() or step_id).strip() or step_id
            options.append((step_id, label))
        return options

    def _populate_run_until_dropdown(self) -> None:
        dropdown = self._run_until_dropdown
        if dropdown is None:
            return
        options = self._pipeline_step_options()
        labels = ["End of pipeline", *[label for _step_id, label in options]]
        dropdown.set_model(Gtk.StringList.new(labels))
        self._run_until_values = [None, *[step_id for step_id, _label in options]]
        saved_value = load_run_until_step_setting()
        selected_index = 0
        if saved_value in self._run_until_values:
            selected_index = self._run_until_values.index(saved_value)
        dropdown.set_selected(selected_index)

    def _selected_run_until_step(self) -> str | None:
        dropdown = self._run_until_dropdown
        if dropdown is None:
            return None
        selected = dropdown.get_selected()
        if 0 <= selected < len(self._run_until_values):
            return self._run_until_values[selected]
        return None

    def _run_until_label(self, step_id: str | None) -> str:
        if not step_id:
            return "End of pipeline"
        for candidate_id, label in self._pipeline_step_options():
            if candidate_id == step_id:
                return label
        return step_id

    def _on_run_until_changed(
        self, dropdown: Gtk.DropDown, _pspec: GObject.ParamSpec
    ) -> None:
        selected = dropdown.get_selected()
        step_id: str | None = None
        if 0 <= selected < len(self._run_until_values):
            step_id = self._run_until_values[selected]
        save_run_until_step_setting(step_id)

    def _resolve_case_root(self) -> Path | None:
        if self.selected_pdfs:
            parents = {path.parent for path in self.selected_pdfs}
            if len(parents) != 1:
                return None
            base_dir = parents.pop()
            return base_dir / "case_bundle"
        _case_name, base_dir = load_case_context()
        if base_dir is None:
            return None
        return base_dir / "case_bundle"

    def _resolve_case_base(self) -> Path | None:
        if self.selected_pdfs:
            parents = {path.parent for path in self.selected_pdfs}
            if len(parents) != 1:
                return None
            return parents.pop()
        _case_name, base_dir = load_case_context()
        return base_dir

    def _resume_start_index(self, root_dir: Path, end_step_id: str | None) -> int | None:
        steps = self._pipeline_steps()
        end_index = len(steps) - 1
        if end_step_id:
            step_ids = [step_id for step_id, _row, _handler in steps]
            if end_step_id not in step_ids:
                raise ValueError("Unknown end step.")
            end_index = step_ids.index(end_step_id)
        for index, (step_id, _row, _handler) in enumerate(steps[: end_index + 1]):
            if not self._step_artifact_complete(step_id, root_dir):
                return index
        return None

    def on_run_all_clicked(self, _button: Gtk.Button) -> None:
        if not self.selected_pdfs:
            self.show_toast("Choose PDF files first.")
            return
        if self._pipeline_running:
            self.show_toast("Pipeline already running.")
            return
        end_step_id = self._selected_run_until_step()
        self._stop_event.clear()
        self._run_completion_message = None
        self._pipeline_running = True
        self.run_all_button.set_sensitive(False)
        self.resume_button.set_sensitive(False)
        self.stop_button.set_sensitive(True)
        if self._run_until_dropdown:
            self._run_until_dropdown.set_sensitive(False)
        threading.Thread(
            target=self._run_all_steps,
            args=(end_step_id,),
            daemon=True,
        ).start()

    def on_resume_clicked(self, _button: Gtk.Button) -> None:
        if self._pipeline_running:
            self.show_toast("Pipeline already running.")
            return
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        end_step_id = self._selected_run_until_step()
        try:
            start_index = self._resume_start_index(root_dir, end_step_id)
        except ValueError as exc:
            self.show_toast(str(exc))
            return
        if start_index is None:
            label = self._run_until_label(end_step_id)
            self.show_toast(f"Already complete through {label}.")
            return
        steps = self._pipeline_steps()
        start_step_id, start_row, _handler = steps[start_index]
        if start_step_id == "create_files" and not self.selected_pdfs:
            self.show_toast("Choose PDF files first to resume Create files.")
            return
        label = start_row.get_title() or start_step_id
        self.show_toast(f"Resuming at {label}.", "INFO")
        self._stop_event.clear()
        self._run_completion_message = None
        self._pipeline_running = True
        self.run_all_button.set_sensitive(False)
        self.resume_button.set_sensitive(False)
        self.stop_button.set_sensitive(True)
        if self._run_until_dropdown:
            self._run_until_dropdown.set_sensitive(False)
        threading.Thread(
            target=self._run_steps_from_index,
            args=(start_index, root_dir, end_step_id),
            daemon=True,
        ).start()

    def on_run_from_step_clicked(self, step_id: str) -> None:
        if self._pipeline_running:
            self.show_toast("Pipeline already running.")
            return
        steps = self._pipeline_steps()
        step_ids = [step for step, _row, _handler in steps]
        if step_id not in step_ids:
            self.show_toast("Unknown step.")
            return
        if step_id == "create_files":
            if not self.selected_pdfs:
                self.show_toast("Choose PDF files first.")
                return
        else:
            root_dir = self._resolve_case_root()
            if root_dir is None:
                if self.selected_pdfs:
                    self.show_toast("Selected PDFs must be in the same folder.")
                else:
                    self.show_toast("Choose PDF files or select a saved case first.")
                return
        start_index = step_ids.index(step_id)
        root_dir = self._resolve_case_root()
        self._stop_event.clear()
        self._run_completion_message = None
        self._pipeline_running = True
        self.run_all_button.set_sensitive(False)
        self.resume_button.set_sensitive(False)
        self.stop_button.set_sensitive(True)
        if self._run_until_dropdown:
            self._run_until_dropdown.set_sensitive(False)
        threading.Thread(
            target=self._run_steps_from_index,
            args=(start_index, root_dir),
            daemon=True,
        ).start()

    def _launch_single_step(
        self,
        row: Adw.ActionRow,
        handler: Callable[[], bool],
        step_id: str | None = None,
    ) -> None:
        if self._pipeline_running:
            self.show_toast("Pipeline already running.")
            return
        self._stop_event.clear()
        self._run_completion_message = None
        self._pipeline_running = True
        self.run_all_button.set_sensitive(False)
        self.resume_button.set_sensitive(False)
        self.stop_button.set_sensitive(True)
        if self._run_until_dropdown:
            self._run_until_dropdown.set_sensitive(False)
        row.set_sensitive(False)
        self._start_step(row)
        threading.Thread(
            target=self._run_single_step_thread,
            args=(handler, row, step_id),
            daemon=True,
        ).start()

    def _run_single_step_thread(
        self,
        handler: Callable[[], bool],
        row: Adw.ActionRow,
        step_id: str | None,
    ) -> None:
        local_server_started = False
        try:
            if step_id in VISION_CLASSIFICATION_STEP_IDS:
                local_server_started = self._ensure_local_vision_server_running()
            handler()
        except Exception as exc:
            title = row.get_title() or "Step"
            GLib.idle_add(self.show_toast, f"{title} failed: {exc}")
            GLib.idle_add(row.set_sensitive, True)
            GLib.idle_add(self._finish_step, row, False)
        finally:
            if local_server_started:
                self._stop_local_vision_server()
            GLib.idle_add(self._finish_single_step)

    def _finish_single_step(self) -> None:
        self._pipeline_running = False
        self.run_all_button.set_sensitive(True)
        self.resume_button.set_sensitive(True)
        self.stop_button.set_sensitive(False)
        if self._run_until_dropdown:
            self._run_until_dropdown.set_sensitive(True)
        self._stop_status()
        self._update_toc_button()
        self._refresh_step_statuses_from_artifacts()

    def on_step_one_clicked(self, _row: Adw.ActionRow) -> None:
        if not self.selected_pdfs:
            self.show_toast("Choose PDF files first.")
            return
        self._launch_single_step(self.step_one_row, self._run_step_one)

    def on_step_strip_nonstandard_clicked(self, _row: Adw.ActionRow) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(self.step_strip_nonstandard_row, self._run_step_strip_nonstandard)

    def on_step_infer_case_clicked(self, _row: Adw.ActionRow) -> None:
        base_dir = self._resolve_case_base()
        if base_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(self.step_infer_case_row, self._run_step_infer_case)

    def _run_step_one(self) -> bool:
        success: bool | None = False
        try:
            self._raise_if_stop_requested()
            parents = {path.parent for path in self.selected_pdfs}
            if len(parents) != 1:
                raise ValueError("Selected PDFs must be in the same folder.")
            base_dir = parents.pop()
            root_dir, text_dir, image_pages_dir = _ensure_case_bundle_dirs(base_dir)
            if len(self.selected_pdfs) > 1:
                temp_dir = root_dir / "temp"
                temp_dir.mkdir(parents=True, exist_ok=True)
                merged_path = temp_dir / "merged.pdf"
                pdf_path = _merge_pdfs(self.selected_pdfs, merged_path)
            else:
                pdf_path = self.selected_pdfs[0]
            self._raise_if_stop_requested()
            text_source = load_text_source_setting()
            if text_source == TEXT_SOURCE_LOCAL_OCR:
                ocr_settings = load_local_ocr_settings()
                _generate_text_files_with_local_ocr(
                    pdf_path,
                    text_dir,
                    image_pages_dir,
                    stop_check=self._raise_if_stop_requested,
                    server_url=ocr_settings["server_url"],
                    start_command=ocr_settings["start_command"],
                    model_id=ocr_settings["model_id"],
                )
            else:
                _generate_text_files(pdf_path, text_dir)
                self._raise_if_stop_requested()
                _generate_image_page_files(pdf_path, image_pages_dir)
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Create files failed: {exc}")
        else:
            success = True
            pending_split = self._rt_ct_split_pending
            pending_mode = self._rt_ct_split_mode_pending
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "create_files",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
                rt_ct_split_page=pending_split,
                rt_ct_split_mode=pending_mode,
            )
            if pending_split is not None:
                self._rt_ct_split_pending = None
            if pending_mode is not None:
                self._rt_ct_split_mode_pending = None
            GLib.idle_add(self._load_rt_ct_split)
            GLib.idle_add(self.show_toast, "Create files complete.")
        finally:
            GLib.idle_add(self.step_one_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_one_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True

    def _run_step_strip_nonstandard(self) -> bool:
        success: bool | None = False
        try:
            self._raise_if_stop_requested()
            root_dir = self._resolve_case_root()
            if root_dir is None:
                if self.selected_pdfs:
                    raise ValueError("Selected PDFs must be in the same folder.")
                raise ValueError("Choose PDF files or select a saved case first.")
            text_dir = root_dir / "text_pages"
            if not text_dir.exists():
                raise FileNotFoundError("Run Create files to generate text files first.")
            text_files = sorted(text_dir.glob("*.txt"), key=_natural_sort_key)
            if not text_files:
                raise FileNotFoundError("No text files found to process.")
            split_mode = _read_rt_ct_split_mode(root_dir)
            split_page = _read_rt_ct_split_page(root_dir)
            if split_page is None:
                split_page = _read_rt_ct_split_page_config()
            for text_path in text_files:
                self._raise_if_stop_requested()
                content = text_path.read_text(encoding="utf-8", errors="ignore")
                cleaned = _strip_nonstandard_characters(content)
                converted = _convert_html_tables(cleaned)
                plain_text = LatexNodes2Text().latex_to_text(converted)
                processed = _strip_markdown(plain_text)
                page_number = _extract_page_number(text_path.name)
                is_rt_page = False
                if split_mode == "rt_only":
                    is_rt_page = True
                elif split_mode == "split" and split_page is not None and page_number is not None:
                    is_rt_page = page_number <= split_page
                if is_rt_page:
                    processed = _strip_ascii_and_html_tables(processed)
                if processed != content:
                    text_path.write_text(processed, encoding="utf-8")
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Process text files failed: {exc}")
        else:
            success = True
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "strip_characters",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            GLib.idle_add(self.show_toast, "Process text files complete.")
        finally:
            GLib.idle_add(self.step_strip_nonstandard_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_strip_nonstandard_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True

    def _run_step_infer_case(self) -> bool:
        success: bool | None = False
        try:
            self._raise_if_stop_requested()
            base_dir = self._resolve_case_base()
            if base_dir is None:
                if self.selected_pdfs:
                    raise ValueError("Selected PDFs must be in the same folder.")
                raise ValueError("Choose PDF files or select a saved case first.")
            root_dir = base_dir / "case_bundle"
            text_dir = root_dir / "text_pages"
            if not text_dir.exists():
                raise FileNotFoundError("Run Create files to generate text files first.")
            settings = load_case_name_settings()
            if not settings["api_url"] or not settings["model_id"] or not settings["api_key"]:
                raise ValueError("Configure case name API URL, model ID, and API key in Settings.")
            text_files = sorted(text_dir.glob("*.txt"), key=_natural_sort_key)[:3]
            if not text_files:
                raise FileNotFoundError("No text files found to infer case name.")
            combined = "\n".join(
                path.read_text(encoding="utf-8", errors="ignore") for path in text_files
            )
            response_text = self._request_plain_text(settings, combined)
            case_name = _limit_case_name_words(response_text)
            if not _looks_like_case_name(case_name):
                case_name = _limit_case_name_words(_infer_case_name_from_text(response_text))
            if not _looks_like_case_name(case_name):
                case_name = _limit_case_name_words(_infer_case_name_from_text(combined))
            if not _looks_like_case_name(case_name):
                raise ValueError("Unable to infer case name from first three pages.")
            (root_dir / "case_name.txt").write_text(case_name, encoding="utf-8")
            save_case_context(case_name, base_dir)
            display_name = case_name.replace("_", " ") if case_name else case_name
            GLib.idle_add(self.selected_label.set_text, f"Selected: {display_name}")
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Infer case name failed: {exc}")
        else:
            success = True
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "infer_case",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            GLib.idle_add(self.show_toast, "Infer case name complete.")
        finally:
            GLib.idle_add(self.step_infer_case_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_infer_case_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True

    def on_step_two_clicked(self, _row: Adw.ActionRow) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(self.step_two_row, self._run_step_two, "classify_basic")

    def on_step_advanced_clicked(self, _row: Adw.ActionRow) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(self.step_advanced_row, self._run_step_advanced, "classify_advanced")

    def on_step_dates_clicked(self, _row: Adw.ActionRow) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(self.step_dates_row, self._run_step_dates, "classify_dates")

    def on_step_correct_advanced_clicked(self, _row: Adw.ActionRow) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(
            self.step_correct_advanced_row, self._run_step_correct_advanced
        )

    def on_step_names_clicked(self, _row: Adw.ActionRow) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(self.step_names_row, self._run_step_names, "classify_names")

    def on_step_six_clicked(self, _row: Adw.ActionRow) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(self.step_six_row, self._run_step_six)

    def on_step_correct_toc_clicked(self, _row: Adw.ActionRow) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(self.step_correct_toc_row, self._run_step_correct_toc)

    def on_step_seven_clicked(self, _row: Adw.ActionRow) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(self.step_seven_row, self._run_step_seven)

    def on_step_correct_boundaries_clicked(self, _row: Adw.ActionRow) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(
            self.step_correct_boundaries_row, self._run_step_correct_boundaries
        )

    def on_step_eight_clicked(self, _row: Adw.ActionRow) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(self.step_eight_row, self._run_step_eight)

    def on_step_preoptimized_clicked(self, _row: Adw.ActionRow) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(self.step_preoptimized_row, self._run_step_preoptimized)

    def on_step_nine_clicked(self, _row: Adw.ActionRow) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(self.step_nine_row, self._run_step_nine)

    def on_step_ten_clicked(self, _row: Adw.ActionRow) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(self.step_ten_row, self._run_step_ten)

    def on_step_add_hearing_date_links_clicked(self, _row: Adw.ActionRow) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(
            self.step_add_hearing_date_links_row,
            self._run_step_add_hearing_date_links,
        )

    def on_step_eleven_clicked(self, _row: Adw.ActionRow) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(self.step_eleven_row, self._run_step_eleven)

    def on_step_twelve_clicked(self, _row: Adw.ActionRow) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(self.step_twelve_row, self._run_step_twelve)

    def _run_all_steps(self, end_step_id: str | None = None) -> None:
        root_dir = self._resolve_case_root()
        self._run_steps_from_index(0, root_dir, end_step_id=end_step_id)

    def _run_steps_from_index(
        self,
        start_index: int,
        root_dir: Path | None,
        end_step_id: str | None = None,
    ) -> None:
        steps = self._pipeline_steps()
        if start_index < 0 or start_index >= len(steps):
            raise ValueError("Unknown start step.")
        end_index = len(steps) - 1
        if end_step_id:
            step_ids = [step_id for step_id, _row, _handler in steps]
            if end_step_id not in step_ids:
                raise ValueError("Unknown end step.")
            end_index = step_ids.index(end_step_id)
            if end_index < start_index:
                raise ValueError("End step must not come before the start step.")
        steps_to_run = steps[start_index : end_index + 1]
        classification_offsets = [
            offset
            for offset, (step_id, _row, _handler) in enumerate(steps_to_run)
            if step_id in VISION_CLASSIFICATION_STEP_IDS
        ]
        manage_local_vision = (
            bool(load_classifier_settings().get("local_vision_enabled", False))
            and bool(classification_offsets)
        )
        first_classify_offset = classification_offsets[0] if classification_offsets else -1
        last_classify_offset = classification_offsets[-1] if classification_offsets else -1
        local_server_started = False
        success = True
        try:
            for offset, (step_id, row, handler) in enumerate(steps_to_run):
                self._raise_if_stop_requested()
                if manage_local_vision and offset == first_classify_offset:
                    local_server_started = self._ensure_local_vision_server_running()
                GLib.idle_add(self._start_step, row)
                if not handler():
                    success = False
                    break
                if manage_local_vision and local_server_started and offset == last_classify_offset:
                    self._stop_local_vision_server()
                    local_server_started = False
            if success and end_step_id and end_index < len(steps) - 1:
                label = self._run_until_label(end_step_id)
                self._run_completion_message = f"Pipeline complete through {label}."
            else:
                self._run_completion_message = None
        except StopRequested:
            success = False
        except Exception as exc:
            success = False
            self._run_completion_message = None
            GLib.idle_add(self.show_toast, f"Pipeline failed: {exc}")
        finally:
            if local_server_started:
                self._stop_local_vision_server()
            GLib.idle_add(self._finish_run_all, success)

    def _finish_run_all(self, success: bool) -> None:
        stop_requested = self._stop_event.is_set()
        self._stop_event.clear()
        self._pipeline_running = False
        self.run_all_button.set_sensitive(True)
        self.resume_button.set_sensitive(True)
        self.stop_button.set_sensitive(False)
        if self._run_until_dropdown:
            self._run_until_dropdown.set_sensitive(True)
        self._stop_status()
        self._update_toc_button()
        self._refresh_step_statuses_from_artifacts()
        completion_message = self._run_completion_message
        self._run_completion_message = None
        if stop_requested:
            self.show_toast("Pipeline stopped.")
        elif completion_message:
            self.show_toast(completion_message)
        elif success:
            self.show_toast("Pipeline complete.")
        else:
            self.show_toast("Pipeline stopped. Fix the errors and try again.")

    def _run_step_two(self) -> bool:
        success: bool | None = False
        try:
            self._raise_if_stop_requested()
            root_dir = self._resolve_case_root()
            if root_dir is None:
                if self.selected_pdfs:
                    raise ValueError("Selected PDFs must be in the same folder.")
                raise ValueError("Choose PDF files or select a saved case first.")
            text_dir = root_dir / "text_pages"
            image_dir = root_dir / "image_pages"
            if not text_dir.exists():
                raise FileNotFoundError("Run Create files to generate text files first.")
            if not image_dir.exists():
                raise FileNotFoundError("Run Create files to generate image files first.")
            shared_settings = load_classifier_settings()
            self._validate_vision_settings(shared_settings)
            classification_dir = root_dir / "classification"
            classification_dir.mkdir(parents=True, exist_ok=True)
            rt_basic_path = classification_dir / "RT_basic.jsonl"
            ct_basic_path = classification_dir / "CT_basic.jsonl"
            text_files = sorted(text_dir.glob("*.txt"), key=_natural_sort_key)
            if not text_files:
                raise FileNotFoundError("No text files found to classify.")
            split_page, _total_pages, need_rt, need_ct, split_mode = _resolve_rt_ct_split(
                root_dir, text_dir
            )
            if need_rt:
                rt_basic_path.touch(exist_ok=True)
            if need_ct:
                ct_basic_path.touch(exist_ok=True)
            if need_rt:
                removed_rt = _dedupe_jsonl_by_file_name(rt_basic_path)
                if removed_rt > 0:
                    GLib.idle_add(
                        self.show_toast,
                        f"Classification basic RT: removed {removed_rt} duplicate/invalid rows.",
                    )
            if need_ct:
                removed_ct = _dedupe_jsonl_by_file_name(ct_basic_path)
                if removed_ct > 0:
                    GLib.idle_add(
                        self.show_toast,
                        f"Classification basic CT: removed {removed_ct} duplicate/invalid rows.",
                    )
            done_rt = _load_jsonl_file_names(rt_basic_path) if need_rt else set()
            done_ct = _load_jsonl_file_names(ct_basic_path) if need_ct else set()
            rt_last_done = _last_jsonl_file_name(rt_basic_path) if need_rt else ""
            ct_last_done = _last_jsonl_file_name(ct_basic_path) if need_ct else ""
            if rt_last_done:
                GLib.idle_add(
                    self.show_toast,
                    f"Classification basic RT resume: continuing after {rt_last_done}.",
                )
            if ct_last_done:
                GLib.idle_add(
                    self.show_toast,
                    f"Classification basic CT resume: continuing after {ct_last_done}.",
                )
            basic_rt_settings = {
                "api_url": shared_settings["api_url"],
                "model_id": shared_settings["model_id"],
                "api_key": shared_settings["api_key"],
                "prompt": shared_settings.get("rt_prompt") or shared_settings.get("prompt"),
                "disable_reasoning": bool(
                    shared_settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)
                ),
            }
            basic_ct_settings = {
                "api_url": shared_settings["api_url"],
                "model_id": shared_settings["model_id"],
                "api_key": shared_settings["api_key"],
                "prompt": shared_settings.get("ct_prompt") or shared_settings.get("prompt"),
                "disable_reasoning": bool(
                    shared_settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)
                ),
            }
            for index, text_path in enumerate(text_files, start=1):
                self._raise_if_stop_requested()
                if split_mode == "rt_only":
                    is_rt = True
                elif split_mode == "ct_only":
                    is_rt = False
                else:
                    is_rt = index <= split_page
                if is_rt:
                    if not need_rt or text_path.name in done_rt:
                        continue
                else:
                    if not need_ct or text_path.name in done_ct:
                        continue
                image_path = _image_path_for_filename(text_path.name, image_dir)
                entry: dict[str, str] = {}
                page_type = ""
                max_attempts = 3
                for attempt in range(1, max_attempts + 1):
                    self._raise_if_stop_requested()
                    entry = self._classify_image(
                        basic_rt_settings if is_rt else basic_ct_settings,
                        text_path.name,
                        image_path,
                    )
                    page_type = _extract_entry_value(entry, "page_type", "pagetype").strip()
                    if page_type:
                        break
                if not page_type:
                    raise RuntimeError(
                        f"Classification basic returned blank page_type for {text_path.name} "
                        f"after {max_attempts} attempts."
                    )
                target_path = rt_basic_path if is_rt else ct_basic_path
                with target_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(entry))
                    handle.write("\n")
                if is_rt:
                    done_rt.add(text_path.name)
                else:
                    done_ct.add(text_path.name)
            if need_ct and ct_basic_path.exists():
                self._raise_if_stop_requested()
                ct_entries = _load_jsonl_entries(ct_basic_path)
                if ct_entries:
                    ct_entries.sort(
                        key=lambda entry: _natural_sort_key(
                            _extract_entry_value(entry, "file_name", "filename")
                        )
                    )
                    changed = False
                    for idx in range(1, len(ct_entries) - 1):
                        current = ct_entries[idx]
                        prev_entry = ct_entries[idx - 1]
                        next_entry = ct_entries[idx + 1]
                        current_type = _extract_entry_value(
                            current, "page_type", "pagetype"
                        ).strip().lower()
                        prev_type = _extract_entry_value(
                            prev_entry, "page_type", "pagetype"
                        ).strip().lower()
                        next_type = _extract_entry_value(
                            next_entry, "page_type", "pagetype"
                        ).strip().lower()
                        if current_type != "ct_report" and prev_type == "ct_report" and next_type == "ct_report":
                            normalized = {_normalize_key(key): key for key in current}
                            target_key = normalized.get("pagetype", "page_type")
                            current[target_key] = "CT_report"
                            changed = True
                    if changed:
                        with ct_basic_path.open("w", encoding="utf-8") as handle:
                            for entry in ct_entries:
                                handle.write(json.dumps(entry))
                                handle.write("\n")
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Classification basic failed: {exc}")
        else:
            success = True
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "classify_basic",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            GLib.idle_add(self.show_toast, "Classification basic complete.")
        finally:
            GLib.idle_add(self.step_two_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_two_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True

    def _run_step_advanced(self) -> bool:
        success: bool | None = False
        try:
            self._raise_if_stop_requested()
            root_dir = self._resolve_case_root()
            if root_dir is None:
                if self.selected_pdfs:
                    raise ValueError("Selected PDFs must be in the same folder.")
                raise ValueError("Choose PDF files or select a saved case first.")
            text_dir = root_dir / "text_pages"
            image_dir = root_dir / "image_pages"
            if not text_dir.exists():
                raise FileNotFoundError("Run Create files to generate text files first.")
            if not image_dir.exists():
                raise FileNotFoundError("Run Create files to generate image files first.")
            classification_dir = root_dir / "classification"
            settings = load_advanced_classify_settings()
            self._validate_vision_settings(settings)
            _split_page, _total_pages, need_rt, need_ct, _split_mode = _resolve_rt_ct_split(
                root_dir, text_dir
            )
            rt_basic_path = classification_dir / "RT_basic.jsonl"
            ct_basic_path = classification_dir / "CT_basic.jsonl"
            rt_advanced_path = classification_dir / "RT_basic_advanced.jsonl"
            ct_advanced_path = classification_dir / "CT_basic_advanced.jsonl"
            classification_dir.mkdir(parents=True, exist_ok=True)
            if need_rt and not rt_basic_path.exists():
                raise FileNotFoundError(
                    "Run Classification basic to generate RT_basic.jsonl first."
                )
            if need_ct and not ct_basic_path.exists():
                raise FileNotFoundError(
                    "Run Classification basic to generate CT_basic.jsonl first."
                )

            def _maybe_update_page_type(
                entry: dict[str, Any],
                target_types: tuple[str, ...],
                updated_type: str,
                prompt: str,
                truthy_keys: tuple[str, ...],
            ) -> bool:
                page_type = _extract_entry_value(entry, "page_type", "pagetype").strip().lower()
                if page_type not in target_types:
                    return False
                file_name = _extract_entry_value(entry, "file_name", "filename")
                if not file_name:
                    return False
                image_path = _image_path_for_filename(file_name, image_dir)
                payload = {
                    "api_url": settings["api_url"],
                    "model_id": settings["model_id"],
                    "api_key": settings["api_key"],
                    "prompt": prompt,
                    "disable_reasoning": bool(
                        settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)
                    ),
                }
                response = self._classify_image(payload, file_name, image_path)
                if _is_truthy(_extract_entry_value(response, *truthy_keys)):
                    entry["page_type"] = updated_type
                    return True
                return False

            updates = 0
            if need_rt:
                rt_entries = _load_jsonl_entries(rt_basic_path)
                if not rt_entries:
                    raise FileNotFoundError("No entries found in RT_basic.jsonl.")
                rt_entries.sort(
                    key=lambda entry: _natural_sort_key(
                        _extract_entry_value(entry, "file_name", "filename")
                    )
                )
                rt_done = _load_jsonl_file_names(rt_advanced_path)
                rt_last_done = _last_jsonl_file_name(rt_advanced_path)
                rt_resume_key = _natural_sort_key(rt_last_done) if rt_last_done else None
                if rt_last_done:
                    GLib.idle_add(
                        self.show_toast,
                        f"Classification advanced RT resume: continuing after {rt_last_done}.",
                    )
                rt_mode = "a" if rt_done else "w"
                with rt_advanced_path.open(rt_mode, encoding="utf-8") as handle:
                    for entry in rt_entries:
                        self._raise_if_stop_requested()
                        file_name = _extract_entry_value(entry, "file_name", "filename")
                        if file_name and rt_resume_key is not None:
                            if _natural_sort_key(file_name) <= rt_resume_key:
                                continue
                        if file_name and file_name in rt_done:
                            continue
                        if _maybe_update_page_type(
                            entry,
                            ("rt_body", "hearing_page", "hearing"),
                            "RT_body_first_page",
                            settings["hearing_prompt"],
                            (
                                "first_page",
                                "first",
                                "is_first_page",
                                "is_first",
                            ),
                        ):
                            updates += 1
                        handle.write(json.dumps(entry))
                        handle.write("\n")
                        if file_name:
                            rt_done.add(file_name)

            if need_ct:
                ct_entries = _load_jsonl_entries(ct_basic_path)
                if not ct_entries:
                    raise FileNotFoundError("No entries found in CT_basic.jsonl.")
                ct_entries.sort(
                    key=lambda entry: _natural_sort_key(
                        _extract_entry_value(entry, "file_name", "filename")
                    )
                )
                ct_done = _load_jsonl_file_names(ct_advanced_path)
                ct_last_done = _last_jsonl_file_name(ct_advanced_path)
                ct_resume_key = _natural_sort_key(ct_last_done) if ct_last_done else None
                if ct_last_done:
                    GLib.idle_add(
                        self.show_toast,
                        f"Classification advanced CT resume: continuing after {ct_last_done}.",
                    )
                ct_mode = "a" if ct_done else "w"
                with ct_advanced_path.open(ct_mode, encoding="utf-8") as handle:
                    for entry in ct_entries:
                        self._raise_if_stop_requested()
                        file_name = _extract_entry_value(entry, "file_name", "filename")
                        if file_name and ct_resume_key is not None:
                            if _natural_sort_key(file_name) <= ct_resume_key:
                                continue
                        if file_name and file_name in ct_done:
                            continue
                        if _maybe_update_page_type(
                            entry,
                            ("ct_minute_order",),
                            "CT_minute_order_first_page",
                            settings["minute_prompt"],
                            ("first_page", "first", "is_first_page", "is_first"),
                        ):
                            updates += 1
                            handle.write(json.dumps(entry))
                            handle.write("\n")
                            if file_name:
                                ct_done.add(file_name)
                            continue
                        if _maybe_update_page_type(
                            entry,
                            ("ct_form",),
                            "CT_form_first_page",
                            settings["form_prompt"],
                            ("first_page", "first", "is_first_page", "is_first"),
                        ):
                            updates += 1
                        handle.write(json.dumps(entry))
                        handle.write("\n")
                        if file_name:
                            ct_done.add(file_name)
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Classification advanced failed: {exc}")
        else:
            success = True
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "classify_advanced",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            GLib.idle_add(
                self.show_toast,
                f"Classification advanced complete. {updates} updates applied.",
            )
        finally:
            GLib.idle_add(self.step_advanced_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_advanced_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True

    def _run_step_correct_advanced(self) -> bool:
        success: bool | None = False
        try:
            self._raise_if_stop_requested()
            root_dir = self._resolve_case_root()
            if root_dir is None:
                if self.selected_pdfs:
                    raise ValueError("Selected PDFs must be in the same folder.")
                raise ValueError("Choose PDF files or select a saved case first.")
            text_dir = root_dir / "text_pages"
            if not text_dir.exists():
                raise FileNotFoundError("Run Create files to generate text files first.")
            classification_dir = root_dir / "classification"
            _split_page, _total_pages, need_rt, need_ct, _split_mode = _resolve_rt_ct_split(
                root_dir, text_dir
            )
            rt_advanced_path = classification_dir / "RT_basic_advanced.jsonl"
            ct_advanced_path = classification_dir / "CT_basic_advanced.jsonl"
            rt_corrected_path = classification_dir / "RT_basic_advanced_corrected.jsonl"
            ct_corrected_path = classification_dir / "CT_basic_advanced_corrected.jsonl"
            if need_rt and not rt_advanced_path.exists():
                raise FileNotFoundError(
                    "Run Advanced classification to generate RT_basic_advanced.jsonl first."
                )
            if need_ct and not ct_advanced_path.exists():
                raise FileNotFoundError(
                    "Run Advanced classification to generate CT_basic_advanced.jsonl first."
                )

            updates = 0

            if need_rt:
                rt_entries = _load_jsonl_entries(rt_advanced_path)
                if not rt_entries:
                    raise FileNotFoundError(
                        "No entries found in RT_basic_advanced.jsonl."
                    )
                rt_entries.sort(
                    key=lambda entry: _natural_sort_key(
                        _extract_entry_value(entry, "file_name", "filename")
                    )
                )
                previous_was_first = False
                previous_page_type = ""
                with rt_corrected_path.open("w", encoding="utf-8") as handle:
                    for entry in rt_entries:
                        self._raise_if_stop_requested()
                        page_type = _extract_entry_value(
                            entry, "page_type", "pagetype"
                        ).strip().lower()
                        if (
                            page_type == "rt_body"
                            and previous_page_type in {"rt_cover", "rt_index"}
                        ):
                            entry["page_type"] = "RT_body_first_page"
                            page_type = "rt_body_first_page"
                            updates += 1
                        is_rt_first_page = page_type == "rt_body_first_page"
                        if is_rt_first_page and previous_was_first:
                            entry["page_type"] = "RT_body"
                            page_type = "rt_body"
                            is_rt_first_page = False
                            updates += 1
                        previous_was_first = is_rt_first_page
                        previous_page_type = page_type
                        handle.write(json.dumps(entry))
                        handle.write("\n")

            if need_ct:
                ct_entries = _load_jsonl_entries(ct_advanced_path)
                if not ct_entries:
                    raise FileNotFoundError(
                        "No entries found in CT_basic_advanced.jsonl."
                    )
                ct_entries.sort(
                    key=lambda entry: _natural_sort_key(
                        _extract_entry_value(entry, "file_name", "filename")
                    )
                )
                with ct_corrected_path.open("w", encoding="utf-8") as handle:
                    for entry in ct_entries:
                        self._raise_if_stop_requested()
                        handle.write(json.dumps(entry))
                        handle.write("\n")
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(
                self.show_toast, f"Correct classification advanced failed: {exc}"
            )
        else:
            success = True
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "correct_classify_advanced",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            GLib.idle_add(
                self.show_toast,
                f"Correct classification advanced complete. {updates} updates applied.",
            )
        finally:
            GLib.idle_add(self.step_correct_advanced_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_correct_advanced_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True

    def _run_step_dates(self) -> bool:
        success: bool | None = False
        try:
            self._raise_if_stop_requested()
            root_dir = self._resolve_case_root()
            if root_dir is None:
                if self.selected_pdfs:
                    raise ValueError("Selected PDFs must be in the same folder.")
                raise ValueError("Choose PDF files or select a saved case first.")
            text_dir = root_dir / "text_pages"
            image_dir = root_dir / "image_pages"
            if not text_dir.exists():
                raise FileNotFoundError("Run Create files to generate text files first.")
            if not image_dir.exists():
                raise FileNotFoundError("Run Create files to generate image files first.")
            classification_dir = root_dir / "classification"
            settings = load_classify_dates_settings()
            shared_settings = load_classifier_settings()
            self._validate_vision_settings(shared_settings)
            _split_page, _total_pages, need_rt, need_ct, _split_mode = _resolve_rt_ct_split(
                root_dir, text_dir
            )
            rt_advanced_path = classification_dir / "RT_basic_advanced_corrected.jsonl"
            ct_advanced_path = classification_dir / "CT_basic_advanced_corrected.jsonl"
            rt_dated_path = classification_dir / "RT_basic_advanced_corrected_dates.jsonl"
            ct_dated_path = classification_dir / "CT_basic_advanced_corrected_dates.jsonl"
            if need_rt and not rt_advanced_path.exists():
                raise FileNotFoundError(
                    "Run Correct classification advanced to generate RT_basic_advanced_corrected.jsonl first."
                )
            if need_ct and not ct_advanced_path.exists():
                raise FileNotFoundError(
                    "Run Correct classification advanced to generate CT_basic_advanced_corrected.jsonl first."
                )

            minute_first_types = {
                "ct_minute_order_first_page",
            }
            updates = 0

            if need_rt:
                rt_entries = _load_jsonl_entries(rt_advanced_path)
                if not rt_entries:
                    raise FileNotFoundError(
                        "No entries found in RT_basic_advanced_corrected.jsonl."
                    )
                hearing_first_types = {
                    "rt_body_first_page",
                }
                rt_entries.sort(
                    key=lambda entry: _natural_sort_key(
                        _extract_entry_value(entry, "file_name", "filename")
                    )
                )
                rt_done = _load_jsonl_file_names(rt_dated_path)
                rt_last_done = _last_jsonl_file_name(rt_dated_path)
                rt_resume_key = _natural_sort_key(rt_last_done) if rt_last_done else None
                if rt_last_done:
                    GLib.idle_add(
                        self.show_toast,
                        f"Classification dates RT resume: continuing after {rt_last_done}.",
                    )
                rt_mode = "a" if rt_done else "w"
                with rt_dated_path.open(rt_mode, encoding="utf-8") as handle:
                    for entry in rt_entries:
                        self._raise_if_stop_requested()
                        page_type = _extract_entry_value(entry, "page_type", "pagetype").strip().lower()
                        file_name = _extract_entry_value(entry, "file_name", "filename")
                        if file_name and rt_resume_key is not None:
                            if _natural_sort_key(file_name) <= rt_resume_key:
                                continue
                        if file_name and file_name in rt_done:
                            continue
                        if page_type in hearing_first_types and not _extract_entry_value(entry, "date") and file_name:
                            image_path = _image_path_for_filename(file_name, image_dir)
                            response = self._classify_image(
                                {
                                    "api_url": shared_settings["api_url"],
                                    "model_id": shared_settings["model_id"],
                                    "api_key": shared_settings["api_key"],
                                    "prompt": settings["hearing_prompt"],
                                    "disable_reasoning": bool(
                                        shared_settings.get(
                                            "disable_reasoning",
                                            DEFAULT_DISABLE_REASONING,
                                        )
                                    ),
                                },
                                file_name,
                                image_path,
                            )
                            date_value = _extract_entry_value(response, "date")
                            if date_value:
                                entry["date"] = date_value
                                updates += 1
                        handle.write(json.dumps(entry))
                        handle.write("\n")
                        if file_name:
                            rt_done.add(file_name)

            if need_ct:
                ct_entries = _load_jsonl_entries(ct_advanced_path)
                if not ct_entries:
                    raise FileNotFoundError(
                        "No entries found in CT_basic_advanced_corrected.jsonl."
                    )
                ct_entries.sort(
                    key=lambda entry: _natural_sort_key(
                        _extract_entry_value(entry, "file_name", "filename")
                    )
                )
                ct_done = _load_jsonl_file_names(ct_dated_path)
                ct_last_done = _last_jsonl_file_name(ct_dated_path)
                ct_resume_key = _natural_sort_key(ct_last_done) if ct_last_done else None
                if ct_last_done:
                    GLib.idle_add(
                        self.show_toast,
                        f"Classification dates CT resume: continuing after {ct_last_done}.",
                    )
                ct_mode = "a" if ct_done else "w"
                with ct_dated_path.open(ct_mode, encoding="utf-8") as handle:
                    for entry in ct_entries:
                        self._raise_if_stop_requested()
                        page_type = _extract_entry_value(entry, "page_type", "pagetype").strip().lower()
                        file_name = _extract_entry_value(entry, "file_name", "filename")
                        if file_name and ct_resume_key is not None:
                            if _natural_sort_key(file_name) <= ct_resume_key:
                                continue
                        if file_name and file_name in ct_done:
                            continue
                        if page_type in minute_first_types and not _extract_entry_value(entry, "date") and file_name:
                            image_path = _image_path_for_filename(file_name, image_dir)
                            response = self._classify_image(
                                {
                                    "api_url": shared_settings["api_url"],
                                    "model_id": shared_settings["model_id"],
                                    "api_key": shared_settings["api_key"],
                                    "prompt": settings["minute_prompt"],
                                    "disable_reasoning": bool(
                                        shared_settings.get(
                                            "disable_reasoning",
                                            DEFAULT_DISABLE_REASONING,
                                        )
                                    ),
                                },
                                file_name,
                                image_path,
                            )
                            date_value = _extract_entry_value(response, "date")
                            if date_value:
                                entry["date"] = date_value
                                updates += 1
                        handle.write(json.dumps(entry))
                        handle.write("\n")
                        if file_name:
                            ct_done.add(file_name)
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Classification dates failed: {exc}")
        else:
            success = True
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "classify_dates",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            GLib.idle_add(self.show_toast, f"Classification dates complete. {updates} updates applied.")
        finally:
            GLib.idle_add(self.step_dates_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_dates_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True

    def _run_step_names(self) -> bool:
        success: bool | None = False
        try:
            self._raise_if_stop_requested()
            root_dir = self._resolve_case_root()
            if root_dir is None:
                if self.selected_pdfs:
                    raise ValueError("Selected PDFs must be in the same folder.")
                raise ValueError("Choose PDF files or select a saved case first.")
            text_dir = root_dir / "text_pages"
            image_dir = root_dir / "image_pages"
            if not text_dir.exists():
                raise FileNotFoundError("Run Create files to generate text files first.")
            if not image_dir.exists():
                raise FileNotFoundError("Run Create files to generate image files first.")
            classification_dir = root_dir / "classification"
            settings = load_classify_names_settings()
            shared_settings = load_classifier_settings()
            self._validate_vision_settings(shared_settings)
            split_page, _total_pages, need_rt, need_ct, _split_mode = _resolve_rt_ct_split(
                root_dir, text_dir
            )
            rt_dated_path = classification_dir / "RT_basic_advanced_corrected_dates.jsonl"
            ct_dated_path = classification_dir / "CT_basic_advanced_corrected_dates.jsonl"
            rt_named_path = classification_dir / "RT_basic_advanced_corrected_dates_names.jsonl"
            ct_named_path = classification_dir / "CT_basic_advanced_corrected_dates_names.jsonl"
            if need_rt and not rt_dated_path.exists():
                raise FileNotFoundError(
                    "Run Classification dates to generate RT_basic_advanced_corrected_dates.jsonl first."
                )
            if need_ct and not ct_dated_path.exists():
                raise FileNotFoundError(
                    "Run Classification dates to generate CT_basic_advanced_corrected_dates.jsonl first."
                )
            report_types = {"ct_report"}
            form_first_types = {"ct_form_first_page"}
            updates = 0

            if need_rt:
                rt_entries = _load_jsonl_entries(rt_dated_path)
                if not rt_entries:
                    raise FileNotFoundError(
                        "No entries found in RT_basic_advanced_corrected_dates.jsonl."
                    )
                rt_entries.sort(
                    key=lambda entry: _natural_sort_key(
                        _extract_entry_value(entry, "file_name", "filename")
                    )
                )
                rt_done = _load_jsonl_file_names(rt_named_path)
                rt_last_done = _last_jsonl_file_name(rt_named_path)
                rt_resume_key = _natural_sort_key(rt_last_done) if rt_last_done else None
                if rt_last_done:
                    GLib.idle_add(
                        self.show_toast,
                        f"Classification names RT resume: continuing after {rt_last_done}.",
                    )
                rt_mode = "a" if rt_done else "w"
                with rt_named_path.open(rt_mode, encoding="utf-8") as handle:
                    for entry in rt_entries:
                        self._raise_if_stop_requested()
                        file_name = _extract_entry_value(entry, "file_name", "filename")
                        if file_name and rt_resume_key is not None:
                            if _natural_sort_key(file_name) <= rt_resume_key:
                                continue
                        if file_name and file_name in rt_done:
                            continue
                        handle.write(json.dumps(entry))
                        handle.write("\n")
                        if file_name:
                            rt_done.add(file_name)

            if need_ct:
                ct_entries = _load_jsonl_entries(ct_dated_path)
                if not ct_entries:
                    raise FileNotFoundError(
                        "No entries found in CT_basic_advanced_corrected_dates.jsonl."
                    )
                ct_entries.sort(
                    key=lambda entry: _natural_sort_key(
                        _extract_entry_value(entry, "file_name", "filename")
                    )
                )
                ct_done = _load_jsonl_file_names(ct_named_path)
                ct_last_done = _last_jsonl_file_name(ct_named_path)
                ct_resume_key = _natural_sort_key(ct_last_done) if ct_last_done else None
                if ct_last_done:
                    GLib.idle_add(
                        self.show_toast,
                        f"Classification names CT resume: continuing after {ct_last_done}.",
                    )
                ct_mode = "a" if ct_done else "w"
                previous_report = False
                with ct_named_path.open(ct_mode, encoding="utf-8") as handle:
                    for entry in ct_entries:
                        self._raise_if_stop_requested()
                        page_type = _extract_entry_value(entry, "page_type", "pagetype").strip().lower()
                        is_report_start = page_type in report_types and not previous_report
                        previous_report = page_type in report_types
                        file_name = _extract_entry_value(entry, "file_name", "filename")
                        if file_name and ct_resume_key is not None:
                            if _natural_sort_key(file_name) <= ct_resume_key:
                                continue
                        if file_name and file_name in ct_done:
                            continue
                        if is_report_start and not _extract_entry_value(entry, "name") and file_name:
                            image_path = _image_path_for_filename(file_name, image_dir)
                            response = self._classify_image(
                                {
                                    "api_url": shared_settings["api_url"],
                                    "model_id": shared_settings["model_id"],
                                    "api_key": shared_settings["api_key"],
                                    "prompt": settings["report_prompt"],
                                    "disable_reasoning": bool(
                                        shared_settings.get(
                                            "disable_reasoning",
                                            DEFAULT_DISABLE_REASONING,
                                        )
                                    ),
                                },
                                file_name,
                                image_path,
                            )
                            name_value = _extract_entry_value(response, "name", "report_name")
                            if name_value:
                                entry["name"] = name_value
                                updates += 1
                        elif page_type in form_first_types and not _extract_entry_value(entry, "name") and file_name:
                            image_path = _image_path_for_filename(file_name, image_dir)
                            response = self._classify_image(
                                {
                                    "api_url": shared_settings["api_url"],
                                    "model_id": shared_settings["model_id"],
                                    "api_key": shared_settings["api_key"],
                                    "prompt": settings["form_prompt"],
                                    "disable_reasoning": bool(
                                        shared_settings.get(
                                            "disable_reasoning",
                                            DEFAULT_DISABLE_REASONING,
                                        )
                                    ),
                                },
                                file_name,
                                image_path,
                            )
                            name_value = _extract_entry_value(response, "name", "form_name")
                            if name_value:
                                entry["name"] = name_value
                                updates += 1
                        handle.write(json.dumps(entry))
                        handle.write("\n")
                        if file_name:
                            ct_done.add(file_name)
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Classification names failed: {exc}")
        else:
            success = True
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "classify_names",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            GLib.idle_add(self.show_toast, f"Classification names complete. {updates} updates applied.")
        finally:
            GLib.idle_add(self.step_names_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_names_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True

    def _run_step_six(self) -> bool:
        success: bool | None = False
        try:
            self._raise_if_stop_requested()
            root_dir = self._resolve_case_root()
            if root_dir is None:
                if self.selected_pdfs:
                    raise ValueError("Selected PDFs must be in the same folder.")
                raise ValueError("Choose PDF files or select a saved case first.")
            classification_dir = root_dir / "classification"
            derived_dir = root_dir / "artifacts"
            text_dir = root_dir / "text_pages"
            if not text_dir.exists():
                raise FileNotFoundError("Run Create files to generate text files first.")
            split_page, _total_pages, need_rt, need_ct, _split_mode = _resolve_rt_ct_split(
                root_dir, text_dir
            )
            rt_named_path = classification_dir / "RT_basic_advanced_corrected_dates_names.jsonl"
            ct_named_path = classification_dir / "CT_basic_advanced_corrected_dates_names.jsonl"
            if need_rt and not rt_named_path.exists():
                raise FileNotFoundError(
                    "Run Classification dates and names to generate RT_basic_advanced_corrected_dates_names.jsonl first."
                )
            if need_ct and not ct_named_path.exists():
                raise FileNotFoundError(
                    "Run Classification dates and names to generate CT_basic_advanced_corrected_dates_names.jsonl first."
                )
            derived_dir.mkdir(parents=True, exist_ok=True)
            paths: list[Path] = []
            if need_rt:
                paths.append(rt_named_path)
            if need_ct:
                paths.append(ct_named_path)
            basic_entries = _load_combined_jsonl_entries(paths)
            if not basic_entries:
                raise FileNotFoundError("No entries found in classified JSONL files.")
            date_by_file: dict[str, str] = {}
            for entry in basic_entries:
                self._raise_if_stop_requested()
                file_name = _extract_entry_value(entry, "file_name", "filename")
                if not file_name:
                    continue
                date_value = _extract_entry_value(entry, "date")
                if date_value:
                    date_by_file[file_name] = date_value
            form_lines: list[str] = []
            report_lines: list[str] = []
            report_types = {
                "ct_report",
            }
            form_first_types = {
                "ct_form_first_page",
            }
            for entry in basic_entries:
                self._raise_if_stop_requested()
                page_type = _extract_entry_value(entry, "page_type", "pagetype").strip().lower()
                name_value = _extract_entry_value(entry, "name", "report_name", "form_name")
                if not name_value:
                    continue
                file_name = _extract_entry_value(entry, "file_name", "filename")
                page_number = _extract_page_number(file_name)
                if page_number is None or page_number <= split_page:
                    continue
                page = _page_label_from_filename(file_name)
                if page_type in form_first_types:
                    form_lines.append(_format_toc_line(name_value, page))
                elif page_type in report_types:
                    report_lines.append(_format_toc_line(name_value, page))
            minute_order_lines: list[str] = []
            hearing_lines: list[str] = []
            minute_first_types = {
                "ct_minute_order_first_page",
            }
            hearing_first_types = {
                "rt_body_first_page",
            }
            for entry in basic_entries:
                self._raise_if_stop_requested()
                file_name = _extract_entry_value(entry, "file_name", "filename")
                if not file_name:
                    continue
                page_type = _extract_entry_value(entry, "page_type", "pagetype").strip().lower()
                date_value = _extract_entry_value(entry, "date").strip()
                if not date_value:
                    continue
                page_number = _extract_page_number(file_name)
                if page_number is None:
                    continue
                page = _page_label_from_filename(file_name)
                line = _format_toc_line(date_value, page)
                if page_type in minute_first_types:
                    if page_number <= split_page:
                        continue
                    minute_order_lines.append(line)
                elif page_type in hearing_first_types:
                    if page_number > split_page:
                        continue
                    hearing_lines.append(line)
            toc_lines: list[str] = [
                "FORMS",
                *form_lines,
                "",
                "REPORTS",
                *report_lines,
                "",
                "MINUTE ORDERS",
                *minute_order_lines,
                "",
                "HEARINGS",
                *hearing_lines,
            ]
            toc_path = derived_dir / "toc.txt"
            toc_path.write_text("\n".join(toc_lines).rstrip() + "\n", encoding="utf-8")
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Build TOC failed: {exc}")
        else:
            success = True
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "build_toc",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            GLib.idle_add(self.show_toast, "Build TOC complete.")
        finally:
            GLib.idle_add(self.step_six_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_six_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
            GLib.idle_add(self._update_toc_button)
        return success is True

    def _run_step_correct_toc(self) -> bool:
        success: bool | None = False
        try:
            self._raise_if_stop_requested()
            root_dir = self._resolve_case_root()
            if root_dir is None:
                if self.selected_pdfs:
                    raise ValueError("Selected PDFs must be in the same folder.")
                raise ValueError("Choose PDF files or select a saved case first.")
            derived_dir = root_dir / "artifacts"
            toc_path = derived_dir / "toc.txt"
            if not toc_path.exists():
                raise FileNotFoundError("Run Build TOC to generate artifacts/toc.txt first.")
            toc_lines = toc_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            corrected_lines: list[str] = []
            in_minute_orders = False
            seen_dates: set[str] = set()
            for line in toc_lines:
                self._raise_if_stop_requested()
                stripped = line.strip()
                if stripped == "MINUTE ORDERS":
                    in_minute_orders = True
                    seen_dates.clear()
                    corrected_lines.append(line)
                    continue
                if stripped in {"FORMS", "REPORTS", "HEARINGS"}:
                    in_minute_orders = False
                    corrected_lines.append(line)
                    continue
                if in_minute_orders:
                    if not stripped:
                        corrected_lines.append(line)
                        continue
                    if not line.startswith("\t"):
                        corrected_lines.append(line)
                        continue
                    entry_text = line.lstrip()
                    date_value = entry_text.rsplit(" ", 1)[0].strip() if " " in entry_text else entry_text
                    if not date_value or date_value in seen_dates:
                        continue
                    seen_dates.add(date_value)
                    corrected_lines.append(line)
                    continue
                corrected_lines.append(line)
            toc_path.write_text("\n".join(corrected_lines).rstrip() + "\n", encoding="utf-8")
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Correct TOC failed: {exc}")
        else:
            success = True
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "correct_toc",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            GLib.idle_add(self.show_toast, "Correct TOC complete.")
        finally:
            GLib.idle_add(self.step_correct_toc_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_correct_toc_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
            GLib.idle_add(self._update_toc_button)
        return success is True

    def _run_step_seven(self) -> bool:
        success: bool | str | None = False
        try:
            self._raise_if_stop_requested()
            root_dir = self._resolve_case_root()
            if root_dir is None:
                if self.selected_pdfs:
                    raise ValueError("Selected PDFs must be in the same folder.")
                raise ValueError("Choose PDF files or select a saved case first.")
            classification_dir = root_dir / "classification"
            derived_dir = root_dir / "artifacts"
            text_dir = root_dir / "text_pages"
            if not text_dir.exists():
                raise FileNotFoundError("Run Create files to generate text files first.")
            split_page, _total_pages, need_rt, need_ct, _split_mode = _resolve_rt_ct_split(
                root_dir, text_dir
            )
            rt_named_path = classification_dir / "RT_basic_advanced_corrected_dates_names.jsonl"
            ct_named_path = classification_dir / "CT_basic_advanced_corrected_dates_names.jsonl"
            if need_rt and not rt_named_path.exists():
                raise FileNotFoundError(
                    "Run Classification dates and names to generate RT_basic_advanced_corrected_dates_names.jsonl first."
                )
            if need_ct and not ct_named_path.exists():
                raise FileNotFoundError(
                    "Run Classification dates and names to generate CT_basic_advanced_corrected_dates_names.jsonl first."
                )
            derived_dir.mkdir(parents=True, exist_ok=True)
            date_by_file: dict[str, str] = {}
            report_name_by_file: dict[str, str] = {}
            paths: list[Path] = []
            if need_rt:
                paths.append(rt_named_path)
            if need_ct:
                paths.append(ct_named_path)
            payload_entries = _load_combined_jsonl_entries(paths)
            for entry in payload_entries:
                self._raise_if_stop_requested()
                file_name = _extract_entry_value(entry, "file_name", "filename")
                if not file_name:
                    continue
                date_value = _extract_entry_value(entry, "date")
                if date_value:
                    date_by_file[file_name] = date_value
                page_type = _extract_entry_value(entry, "page_type", "pagetype").strip().lower()
                name_value = _extract_entry_value(entry, "name", "report_name")
                if page_type in {"ct_report"} and name_value:
                    report_name_by_file[file_name] = name_value
            relevant_report_files: set[str] | None = None
            hearing_boundaries: list[dict[str, str]] = []
            report_boundaries: list[dict[str, str]] = []
            minutes_boundaries: list[dict[str, str]] = []
            entries: list[tuple[str, str, int]] = []
            for entry in payload_entries:
                file_name = _extract_entry_value(entry, "file_name", "filename")
                page_type = _extract_entry_value(entry, "page_type", "pagetype").strip().lower()
                if not file_name or not page_type:
                    continue
                page_number = _extract_page_number(file_name)
                if page_number is None:
                    continue
                entries.append((file_name, page_type, page_number))
            if not entries:
                raise FileNotFoundError("No entries found in classified JSONL files.")
            current_report_start: str | None = None
            current_report_end: str | None = None
            report_sequence_relevant = False
            for file_name, page_type, page_number in entries:
                self._raise_if_stop_requested()
                if page_number <= split_page:
                    if current_report_start:
                        if report_sequence_relevant:
                            self._append_boundary_entry(
                                "report",
                                current_report_start,
                                current_report_end,
                                date_by_file,
                                report_name_by_file,
                                hearing_boundaries,
                                report_boundaries,
                                minutes_boundaries,
                            )
                        current_report_start = None
                        current_report_end = None
                        report_sequence_relevant = False
                    continue
                if page_type not in {"ct_report"}:
                    if current_report_start:
                        if report_sequence_relevant:
                            self._append_boundary_entry(
                                "report",
                                current_report_start,
                                current_report_end,
                                date_by_file,
                                report_name_by_file,
                                hearing_boundaries,
                                report_boundaries,
                                minutes_boundaries,
                            )
                        current_report_start = None
                        current_report_end = None
                        report_sequence_relevant = False
                    continue
                if (
                    current_report_end is not None
                    and _extract_page_number(current_report_end) == page_number - 1
                ):
                    current_report_end = file_name
                else:
                    if current_report_start:
                        if report_sequence_relevant:
                            self._append_boundary_entry(
                                "report",
                                current_report_start,
                                current_report_end,
                                date_by_file,
                                report_name_by_file,
                                hearing_boundaries,
                                report_boundaries,
                                minutes_boundaries,
                            )
                    current_report_start = file_name
                    current_report_end = file_name
                    report_sequence_relevant = (
                        True
                        if relevant_report_files is None
                        else file_name in relevant_report_files
                    )
            if current_report_start:
                if report_sequence_relevant:
                    self._append_boundary_entry(
                        "report",
                        current_report_start,
                        current_report_end,
                        date_by_file,
                        report_name_by_file,
                        hearing_boundaries,
                        report_boundaries,
                        minutes_boundaries,
                    )

            hearing_start_types = {
                "rt_body_first_page",
            }
            hearing_body_types = {
                "rt_body",
            }
            minute_start_types = {
                "ct_minute_order_first_page",
            }
            minute_body_types = {
                "ct_minute_order",
            }
            index = 0
            total = len(entries)
            while index < total:
                self._raise_if_stop_requested()
                file_name, page_type, page_number = entries[index]
                if page_type in hearing_start_types:
                    if page_number > split_page:
                        index += 1
                        continue
                    end_file = file_name
                    last_number = page_number
                    index += 1
                    while index < total:
                        self._raise_if_stop_requested()
                        next_file, next_type, next_number = entries[index]
                        if next_number > split_page:
                            break
                        if (
                            next_type not in hearing_body_types
                            or next_number != last_number + 1
                        ):
                            break
                        end_file = next_file
                        last_number = next_number
                        index += 1
                    self._append_boundary_entry(
                        "hearing",
                        file_name,
                        end_file,
                        date_by_file,
                        report_name_by_file,
                        hearing_boundaries,
                        report_boundaries,
                        minutes_boundaries,
                    )
                    continue
                if page_type in minute_start_types:
                    if page_number <= split_page:
                        index += 1
                        continue
                    end_file = file_name
                    last_number = page_number
                    index += 1
                    while index < total:
                        self._raise_if_stop_requested()
                        next_file, next_type, next_number = entries[index]
                        if next_number <= split_page:
                            break
                        if (
                            next_type not in minute_body_types
                            or next_number != last_number + 1
                        ):
                            break
                        end_file = next_file
                        last_number = next_number
                        index += 1
                    self._append_boundary_entry(
                        "minute_order",
                        file_name,
                        end_file,
                        date_by_file,
                        report_name_by_file,
                        hearing_boundaries,
                        report_boundaries,
                        minutes_boundaries,
                    )
                    continue
                index += 1
            hearing_path = derived_dir / "hearing_boundaries.json"
            hearing_path.write_text(
                json.dumps(hearing_boundaries, indent=2),
                encoding="utf-8",
            )
            report_path = derived_dir / "report_boundaries.json"
            report_path.write_text(
                json.dumps(report_boundaries, indent=2),
                encoding="utf-8",
            )
            filtered_minutes: list[dict[str, str]] = []
            seen_minute_dates: set[str] = set()
            for entry in minutes_boundaries:
                date_value = str(entry.get("date", "")).strip()
                if not date_value or date_value in seen_minute_dates:
                    continue
                seen_minute_dates.add(date_value)
                filtered_minutes.append(entry)
            minutes_path = derived_dir / "minutes_boundaries.json"
            minutes_path.write_text(
                json.dumps(filtered_minutes, indent=2),
                encoding="utf-8",
            )
            total_boundaries = (
                len(hearing_boundaries)
                + len(report_boundaries)
                + len(filtered_minutes)
            )
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Find boundaries failed: {exc}")
        else:
            success = True
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "find_boundaries",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            if total_boundaries == 0:
                GLib.idle_add(
                    self.show_toast,
                    "No boundaries detected. Continuing with any remaining steps that can still run.",
                    "WARN",
                )
            else:
                GLib.idle_add(self.show_toast, "Find boundaries complete.")
        finally:
            GLib.idle_add(self.step_seven_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_seven_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True

    def _run_step_correct_boundaries(self) -> bool:
        success: bool | str | None = False
        try:
            self._raise_if_stop_requested()
            root_dir = self._resolve_case_root()
            if root_dir is None:
                if self.selected_pdfs:
                    raise ValueError("Selected PDFs must be in the same folder.")
                raise ValueError("Choose PDF files or select a saved case first.")
            derived_dir = root_dir / "artifacts"
            hearing_path = derived_dir / "hearing_boundaries.json"
            report_path = derived_dir / "report_boundaries.json"
            if not hearing_path.exists() or not report_path.exists():
                raise FileNotFoundError(
                    "Run Find boundaries to generate hearing/report boundaries first."
                )
            hearing_entries = _load_json_entries(hearing_path)
            report_entries = _load_json_entries(report_path)
            if not hearing_entries and not report_entries:
                GLib.idle_add(
                    self.show_toast,
                    "No hearing/report boundaries found. Skipping Correct boundaries.",
                    "WARN",
                )
                success = "Skipped"
                return True

            hearing_removed = 0
            filtered_hearings: list[dict[str, str]] = []
            for entry in hearing_entries:
                self._raise_if_stop_requested()
                date_value = _extract_entry_value(entry, "date")
                if not date_value:
                    hearing_removed += 1
                    continue
                filtered_hearings.append(entry)
            hearing_path.write_text(
                json.dumps(filtered_hearings, indent=2),
                encoding="utf-8",
            )

            report_removed = 0
            filtered_reports: list[dict[str, str]] = []
            for entry in report_entries:
                self._raise_if_stop_requested()
                start_label = _extract_entry_value(entry, "start_page")
                end_label = _extract_entry_value(entry, "end_page")
                start_number = _page_number_from_label(start_label)
                end_number = _page_number_from_label(end_label)
                if start_number is None or end_number is None:
                    is_single = start_label == end_label and bool(start_label)
                else:
                    is_single = start_number == end_number
                report_name = _extract_entry_value(entry, "report_name", "report", "name")
                if is_single and "last minute" not in report_name.lower():
                    report_removed += 1
                    continue
                filtered_reports.append(entry)
            report_path.write_text(
                json.dumps(filtered_reports, indent=2),
                encoding="utf-8",
            )
            removed = hearing_removed + report_removed
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Correct boundaries failed: {exc}")
        else:
            success = True
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "correct_boundaries",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            GLib.idle_add(
                self.show_toast,
                "Correct boundaries complete. "
                f"{hearing_removed} hearing entries without dates and "
                f"{report_removed} report entries removed ({removed} total).",
            )
        finally:
            GLib.idle_add(self.step_correct_boundaries_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_correct_boundaries_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True or success == "Skipped"

    def _run_step_eight(self) -> bool:
        success: bool | str | None = False
        try:
            self._raise_if_stop_requested()
            root_dir = self._resolve_case_root()
            if root_dir is None:
                if self.selected_pdfs:
                    raise ValueError("Selected PDFs must be in the same folder.")
                raise ValueError("Choose PDF files or select a saved case first.")
            derived_dir = root_dir / "artifacts"
            text_dir = root_dir / "text_pages"
            if not text_dir.exists():
                raise FileNotFoundError("Run Create files to generate text files first.")
            hearing_path = derived_dir / "hearing_boundaries.json"
            report_path = derived_dir / "report_boundaries.json"
            if not hearing_path.exists() or not report_path.exists():
                raise FileNotFoundError("Run Find boundaries to generate boundary JSON files first.")
            artifacts_dir = root_dir / "artifacts"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            hearing_entries = _load_json_entries(hearing_path)
            report_entries = _load_json_entries(report_path)
            minutes_path = derived_dir / "minutes_boundaries.json"
            minute_entries = (
                _load_json_entries(minutes_path)
                if minutes_path.exists()
                else []
            )
            hearing_sections = _build_hearing_sections(hearing_entries, text_dir, minute_entries)
            report_sections = _build_report_sections(report_entries, text_dir)
            raw_hearings = _compile_raw_sections_text(hearing_sections)
            raw_reports = _compile_raw_sections_text(report_sections)
            (artifacts_dir / "raw_hearings.txt").write_text(raw_hearings, encoding="utf-8")
            (artifacts_dir / "raw_reports.txt").write_text(raw_reports, encoding="utf-8")
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Create raw failed: {exc}")
        else:
            success = True
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "create_raw",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            if not hearing_entries and not report_entries:
                GLib.idle_add(
                    self.show_toast,
                    "No hearing/report boundaries found. Created empty raw files and continued.",
                    "WARN",
                )
            else:
                GLib.idle_add(self.show_toast, "Create raw complete.")
        finally:
            GLib.idle_add(self.step_eight_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_eight_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True

    def _run_step_preoptimized(self) -> bool:
        success: bool | str | None = False
        try:
            self._raise_if_stop_requested()
            root_dir = self._resolve_case_root()
            if root_dir is None:
                if self.selected_pdfs:
                    raise ValueError("Selected PDFs must be in the same folder.")
                raise ValueError("Choose PDF files or select a saved case first.")
            artifacts_dir = root_dir / "artifacts"
            text_dir = root_dir / "text_pages"
            hearing_path = artifacts_dir / "hearing_boundaries.json"
            report_path = artifacts_dir / "report_boundaries.json"
            if not text_dir.exists():
                raise FileNotFoundError("Run Create files to generate text files first.")
            if not hearing_path.exists() or not report_path.exists():
                raise FileNotFoundError(
                    "Run Find boundaries to generate hearing/report boundaries first."
                )
            optimize_settings = load_optimize_settings()
            chunk_size = DEFAULT_OPTIMIZE_CHUNK_SIZE
            chunk_size_raw = optimize_settings.get("chunk_size", "")
            if chunk_size_raw:
                try:
                    chunk_size = max(1, int(chunk_size_raw))
                except ValueError:
                    chunk_size = DEFAULT_OPTIMIZE_CHUNK_SIZE
            hearing_entries = _load_json_entries(hearing_path)
            report_entries = _load_json_entries(report_path)
            minutes_path = artifacts_dir / "minutes_boundaries.json"
            minute_entries = (
                _load_json_entries(minutes_path)
                if minutes_path.exists()
                else []
            )
            hearing_sections = _build_hearing_sections(hearing_entries, text_dir, minute_entries)
            report_sections = _build_report_sections(report_entries, text_dir)
            GLib.idle_add(
                self._append_log_message,
                (
                    "Create pre-optimized: extracting counsel roles from the first two "
                    "pages of each hearing."
                ),
                "INFO",
            )
            counsel_role_evidence = _build_case_counsel_role_evidence(
                hearing_entries,
                text_dir,
            )
            counsel_role_chunks = _chunk_text_for_artifacts(
                counsel_role_evidence,
                COUNSEL_ROLE_EXTRACTION_CHUNK_SIZE,
            )
            GLib.idle_add(
                self._append_log_message,
                (
                    "Create pre-optimized: counsel role evidence built from "
                    f"{len(hearing_entries)} hearing(s), "
                    f"{len(counsel_role_evidence):,} characters, "
                    f"{len(counsel_role_chunks)} extraction chunk(s)."
                ),
                "INFO",
            )
            counsel_roles = self._extract_counsel_roles(
                optimize_settings,
                counsel_role_evidence,
            )
            _create_preoptimized_chunks(
                root_dir,
                hearing_sections,
                report_sections,
                chunk_size,
                counsel_role_evidence=counsel_role_evidence,
                counsel_roles=counsel_roles,
            )
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Create pre-optimized failed: {exc}")
        else:
            success = True
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "create_preoptimized",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            GLib.idle_add(self.show_toast, "Create pre-optimized complete.")
        finally:
            GLib.idle_add(self.step_preoptimized_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_preoptimized_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True

    def _optimize_report_chunk(
        self,
        settings: dict[str, Any],
        chunk: str,
    ) -> str:
        request_settings = _build_optimize_report_request_settings(settings)
        response = self._request_plain_text(request_settings, chunk)
        return _normalize_optimized_text(response) if response else ""

    def _extract_counsel_roles(
        self,
        optimize_settings: dict[str, Any],
        evidence_text: str,
    ) -> dict[str, Any]:
        cleaned_evidence = evidence_text.strip()
        empty_roles = {"roles": [], "unknown_speaker_labels": [], "notes": ""}
        if not cleaned_evidence:
            GLib.idle_add(
                self._append_log_message,
                "Counsel role extraction skipped: no evidence text was available.",
                "WARN",
            )
            return empty_roles
        attorney_settings = _build_attorney_request_settings(optimize_settings)
        if (
            not attorney_settings["api_url"]
            or not attorney_settings["model_id"]
            or not attorney_settings["api_key"]
        ):
            raise ValueError(
                "Configure counsel role extraction API URL, model ID, and API key in Settings."
            )
        evidence_chunks = _chunk_text_for_artifacts(
            cleaned_evidence,
            COUNSEL_ROLE_EXTRACTION_CHUNK_SIZE,
        )
        total_chunks = len(evidence_chunks)
        GLib.idle_add(
            self._append_log_message,
            (
                "Counsel role extraction: "
                f"{len(cleaned_evidence):,} characters of evidence across "
                f"{total_chunks} request chunk(s)."
            ),
            "INFO",
        )
        payloads: list[dict[str, Any]] = []
        for chunk_index, chunk in enumerate(evidence_chunks, start=1):
            GLib.idle_add(
                self._append_log_message,
                (
                    "Counsel role extraction: "
                    f"starting chunk {chunk_index}/{total_chunks} "
                    f"({len(chunk):,} characters)."
                ),
                "INFO",
            )
            attorney_response = self._request_plain_text(attorney_settings, chunk)
            try:
                attorney_payload = json.loads(self._extract_json_payload(attorney_response))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Counsel role extraction returned invalid JSON: {exc}"
                ) from exc
            normalized_payload = _normalize_counsel_role_json_payload(attorney_payload)
            GLib.idle_add(
                self._append_log_message,
                (
                    "Counsel role extraction: "
                    f"finished chunk {chunk_index}/{total_chunks} with "
                    f"{len(normalized_payload['roles'])} role(s) and "
                    f"{len(normalized_payload['unknown_speaker_labels'])} "
                    "unresolved label(s)."
                ),
                "INFO",
            )
            payloads.append(normalized_payload)
        merged_payload = _merge_counsel_role_payloads(payloads) if payloads else empty_roles
        GLib.idle_add(
            self._append_log_message,
            (
                "Counsel role extraction complete: "
                f"{len(merged_payload['roles'])} final role(s) and "
                f"{len(merged_payload['unknown_speaker_labels'])} unresolved label(s)."
            ),
            "INFO",
        )
        return merged_payload

    def _run_step_nine(self) -> bool:
        success: bool | str | None = False
        try:
            self._raise_if_stop_requested()
            root_dir = self._resolve_case_root()
            if root_dir is None:
                if self.selected_pdfs:
                    raise ValueError("Selected PDFs must be in the same folder.")
                raise ValueError("Choose PDF files or select a saved case first.")
            artifacts_dir = root_dir / "artifacts"
            preoptimized_dir = artifacts_dir / "preoptimized"
            preoptimized_hearings_dir = preoptimized_dir / "hearings"
            preoptimized_reports_dir = preoptimized_dir / "reports"
            if not preoptimized_hearings_dir.exists() or not preoptimized_reports_dir.exists():
                raise FileNotFoundError(
                    "Run Create pre-optimized to generate hearing/report chunk files first."
                )
            settings = load_optimize_settings()
            hearing_request_settings = _build_optimize_hearing_request_settings(settings)
            report_request_settings = _build_optimize_report_request_settings(settings)
            counsel_roles_path = preoptimized_dir / "counsel_roles.json"
            if not counsel_roles_path.exists():
                raise FileNotFoundError(
                    "Run Create pre-optimized to generate counsel_roles.json first."
                )
            raw_counsel_roles = counsel_roles_path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
            try:
                counsel_roles_payload = _normalize_counsel_role_json_payload(
                    json.loads(raw_counsel_roles)
                )
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid counsel_roles.json: {exc}"
                ) from exc
            hearing_files = _load_chunked_section_files(
                preoptimized_hearings_dir,
                "hearing",
                "hearing_date",
            )
            report_files = _load_chunked_section_files(
                preoptimized_reports_dir,
                "report",
                "report_name",
            )
            if hearing_files and (
                not hearing_request_settings["api_url"]
                or not hearing_request_settings["model_id"]
                or not hearing_request_settings["api_key"]
            ):
                raise ValueError(
                    "Configure hearing optimize API URL, model ID, and API key in Settings."
                )
            if report_files and (
                not report_request_settings["api_url"]
                or not report_request_settings["model_id"]
                or not report_request_settings["api_key"]
            ):
                raise ValueError(
                    "Configure report optimize API URL, model ID, and API key in Settings."
                )
            if not hearing_files and not report_files:
                (artifacts_dir / "optimized_hearings.txt").write_text("", encoding="utf-8")
                (artifacts_dir / "optimized_reports.txt").write_text("", encoding="utf-8")
                _create_optimized_output_dirs(root_dir)
                self._safe_update_manifest(
                    root_dir,
                    {
                        "last_completed_step": "create_optimized",
                        "last_failed_step": None,
                        "last_failed_at": None,
                    },
                )
                GLib.idle_add(
                    self.show_toast,
                    "No hearing/report boundary content found. Created empty optimized files and continued.",
                    "WARN",
                )
                success = "Skipped"
                return True

            optimized_hearings_dir, optimized_reports_dir = _create_optimized_output_dirs(root_dir)
            optimized_hearings: list[str] = []
            total_hearing_sections = len(hearing_files)
            for section_index, section in enumerate(hearing_files, start=1):
                self._raise_if_stop_requested()
                if not section.chunk_paths:
                    continue
                hearing_date = str(section.metadata.get("hearing_date", "")).strip() or section.label or "Unknown date"
                GLib.idle_add(
                    self._append_log_message,
                    (
                        f"Create optimized: hearing section {section_index}/{total_hearing_sections} "
                        f"({hearing_date}), loading counsel roles."
                    ),
                    "INFO",
                )
                section_paragraphs: list[str] = []
                output_section_dir = optimized_hearings_dir / section.directory.name
                output_section_dir.mkdir(parents=True, exist_ok=True)
                (output_section_dir / "label.txt").write_text(hearing_date + "\n", encoding="utf-8")
                total_chunks = len(section.chunk_paths)
                for chunk_index, chunk_path in enumerate(section.chunk_paths, start=1):
                    self._raise_if_stop_requested()
                    chunk = chunk_path.read_text(encoding="utf-8", errors="ignore")
                    GLib.idle_add(
                        self._append_log_message,
                        (
                            f"Create optimized: hearing section {section_index}/{total_hearing_sections} "
                            f"({hearing_date}), chunk {chunk_index}/{total_chunks}."
                        ),
                        "INFO",
                    )
                    payload = _build_optimize_hearing_payload(
                        _render_counsel_role_json(counsel_roles_payload),
                        chunk,
                    )
                    response = self._request_plain_text(
                        hearing_request_settings,
                        payload,
                    )
                    if response:
                        normalized_response = _normalize_optimized_text(response)
                        if normalized_response:
                            normalized_response = _normalize_hearing_speaker_labels(
                                normalized_response,
                                counsel_roles_payload,
                            )
                            (output_section_dir / f"{chunk_index:04d}.txt").write_text(
                                normalized_response,
                                encoding="utf-8",
                            )
                            section_paragraphs.extend(_split_paragraphs(normalized_response))
                if section_paragraphs:
                    total_paragraphs = len(section_paragraphs)
                    GLib.idle_add(
                        self._append_log_message,
                        (
                            f"Create optimized: hearing section {section_index}/{total_hearing_sections} "
                            f"({hearing_date}) complete with {total_paragraphs} output chunk(s)."
                        ),
                        "INFO",
                    )
                    optimized_hearings.extend(section_paragraphs)

            optimized_reports: list[str] = []
            total_report_sections = len(report_files)
            for section_index, section in enumerate(report_files, start=1):
                self._raise_if_stop_requested()
                if not section.chunk_paths:
                    continue
                report_name = str(section.metadata.get("report_name", "")).strip() or section.label or "Unknown report"
                section_paragraphs: list[str] = []
                output_section_dir = optimized_reports_dir / section.directory.name
                output_section_dir.mkdir(parents=True, exist_ok=True)
                (output_section_dir / "label.txt").write_text(report_name + "\n", encoding="utf-8")
                total_chunks = len(section.chunk_paths)
                for chunk_index, chunk_path in enumerate(section.chunk_paths, start=1):
                    self._raise_if_stop_requested()
                    chunk = chunk_path.read_text(encoding="utf-8", errors="ignore")
                    GLib.idle_add(
                        self._append_log_message,
                        (
                            f"Create optimized: report section {section_index}/{total_report_sections} "
                            f"({report_name}), chunk {chunk_index}/{total_chunks}."
                        ),
                        "INFO",
                    )
                    response = self._optimize_report_chunk(
                        settings,
                        chunk,
                    )
                    if response:
                        normalized_response = _normalize_optimized_text(response)
                        if normalized_response:
                            (output_section_dir / f"{chunk_index:04d}.txt").write_text(
                                normalized_response,
                                encoding="utf-8",
                            )
                            section_paragraphs.extend(_split_paragraphs(normalized_response))
                if section_paragraphs:
                    total_paragraphs = len(section_paragraphs)
                    GLib.idle_add(
                        self._append_log_message,
                        (
                            f"Create optimized: report section {section_index}/{total_report_sections} "
                            f"({report_name}) complete with {total_paragraphs} output chunk(s)."
                        ),
                        "INFO",
                    )
                    optimized_reports.extend(section_paragraphs)

            (artifacts_dir / "optimized_hearings.txt").write_text(
                _collapse_blank_lines("\n\n".join(optimized_hearings)) if optimized_hearings else "",
                encoding="utf-8",
            )
            (artifacts_dir / "optimized_reports.txt").write_text(
                _collapse_blank_lines("\n\n".join(optimized_reports)) if optimized_reports else "",
                encoding="utf-8",
            )
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Create optimized failed: {exc}")
        else:
            success = True
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "create_optimized",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            GLib.idle_add(self.show_toast, "Create optimized complete.")
        finally:
            GLib.idle_add(self.step_nine_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_nine_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True or success == "Skipped"

    def _run_step_ten(self) -> bool:
        success: bool | None = False
        try:
            self._raise_if_stop_requested()
            root_dir = self._resolve_case_root()
            if root_dir is None:
                if self.selected_pdfs:
                    raise ValueError("Selected PDFs must be in the same folder.")
                raise ValueError("Choose PDF files or select a saved case first.")
            artifacts_dir = root_dir / "artifacts"
            summaries_dir = root_dir / "summaries"
            summaries_path, reports_path = _summary_output_paths(root_dir)
            minutes_path = _minutes_summary_output_path(root_dir)
            text_dir = root_dir / "text_pages"
            optimized_hearings_path = artifacts_dir / "optimized_hearings.txt"
            optimized_reports_path = artifacts_dir / "optimized_reports.txt"
            if not optimized_hearings_path.exists() or not optimized_reports_path.exists():
                raise FileNotFoundError("Run Create optimized to generate optimized files first.")
            if not text_dir.exists():
                raise FileNotFoundError("Run Create files to generate text files first.")
            report_boundaries_path = artifacts_dir / "report_boundaries.json"
            minutes_boundaries_path = artifacts_dir / "minutes_boundaries.json"
            if not minutes_boundaries_path.exists() or not report_boundaries_path.exists():
                raise FileNotFoundError(
                    "Run Find boundaries to generate minute order and report boundaries first."
                )
            settings = load_summarize_settings()
            if not settings["api_url"] or not settings["model_id"] or not settings["api_key"]:
                raise ValueError("Configure summarize API URL, model ID, and API key in Settings.")
            chunk_size = DEFAULT_SUMMARIZE_CHUNK_SIZE
            chunk_size_raw = settings.get("chunk_size", "")
            if chunk_size_raw:
                try:
                    chunk_size = max(1, int(chunk_size_raw))
                except ValueError:
                    chunk_size = DEFAULT_SUMMARIZE_CHUNK_SIZE

            case_name, _root_dir = load_case_context()
            display_case_name = case_name.replace("_", " ") if case_name else ""
            summary_hearings: list[str] = []
            summary_reports: list[str] = []

            if display_case_name:
                summary_hearings.extend(["Hearings Summary", display_case_name, ""])
            else:
                summary_hearings.append("Hearings Summary")

            hearing_groups: list[tuple[str, list[str]]] = []
            hearing_sections = _load_labeled_chunk_directories(
                artifacts_dir / "optimized" / "hearings",
                "hearing",
                "hearing_date",
            )
            for section in hearing_sections:
                self._raise_if_stop_requested()
                metadata = section.get("metadata")
                metadata = metadata if isinstance(metadata, dict) else {}
                date_value = _normalize_hearing_date(
                    str(metadata.get("hearing_date", "")).strip() or "HEARING"
                )
                paragraphs = [
                    _remove_standalone_date_lines(_remove_hearing_date_mentions(paragraph))
                    for paragraph in _expand_section_chunk_paragraphs(
                        list(section.get("chunks", []))
                    )
                    if str(paragraph).strip()
                ]
                if paragraphs:
                    hearing_groups.append((date_value, paragraphs))

            hearing_responses: list[str] = []
            for date_value, paragraphs in hearing_groups:
                self._raise_if_stop_requested()
                for chunk in _chunk_paragraphs(paragraphs, chunk_size):
                    self._raise_if_stop_requested()
                    response = self._request_plain_text(
                        {
                            "api_url": settings["api_url"],
                            "model_id": settings["model_id"],
                            "api_key": settings["api_key"],
                            "disable_reasoning": bool(
                                settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)
                            ),
                            "prompt": settings["hearings_prompt"],
                        },
                        chunk,
                    )
                    cleaned_response = response.strip() if response else ""
                    hearing_responses.append(cleaned_response)

            first_section = True
            hearing_chunk_index = 0
            for date_value, paragraphs in hearing_groups:
                self._raise_if_stop_requested()
                if not first_section:
                    summary_hearings.append("")
                summary_hearings.append(date_value or "HEARING")
                summary_hearings.append("")
                first_section = False
                for chunk in _chunk_paragraphs(paragraphs, chunk_size):
                    self._raise_if_stop_requested()
                    response = hearing_responses[hearing_chunk_index] if hearing_chunk_index < len(hearing_responses) else ""
                    hearing_chunk_index += 1
                    if response:
                        cleaned_response = _remove_hearing_date_mentions(response.strip())
                        summary_hearings.append(_remove_standalone_date_lines(cleaned_response))
                        summary_hearings.append("")

            if display_case_name:
                summary_reports.extend(["Reports Summary", display_case_name, "", ""])
            else:
                summary_reports.extend(["Reports Summary", ""])

            report_entries = _load_json_entries(report_boundaries_path)
            report_page_by_name: dict[str, str] = {}
            for entry in report_entries:
                report_name = _extract_entry_value(entry, "report_name", "report", "name").strip()
                if not report_name:
                    continue
                page_str = _extract_start_page_for_date_links(entry)
                if not page_str:
                    continue
                report_page_by_name.setdefault(report_name, page_str)

            report_groups: list[tuple[str, list[str]]] = []
            report_sections = _load_labeled_chunk_directories(
                artifacts_dir / "optimized" / "reports",
                "report",
                "report_name",
            )
            for section in report_sections:
                metadata = section.get("metadata")
                metadata = metadata if isinstance(metadata, dict) else {}
                report_name = str(metadata.get("report_name", "")).strip() or "Report"
                paragraphs = _expand_section_chunk_paragraphs(
                    list(section.get("chunks", []))
                )
                if paragraphs:
                    report_groups.append((report_name, paragraphs))
            report_responses: list[str] = []
            report_group_chunk_counts: list[int] = []
            for _report_name, paragraphs in report_groups:
                group_chunk_count = 0
                for chunk in _chunk_paragraphs(paragraphs, chunk_size):
                    self._raise_if_stop_requested()
                    response = self._request_plain_text(
                        {
                            "api_url": settings["api_url"],
                            "model_id": settings["model_id"],
                            "api_key": settings["api_key"],
                            "disable_reasoning": bool(
                                settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)
                            ),
                            "prompt": settings["reports_prompt"],
                        },
                        chunk,
                    )
                    cleaned_response = response.strip() if response else ""
                    report_responses.append(cleaned_response)
                    group_chunk_count += 1
                report_group_chunk_counts.append(group_chunk_count)

            report_chunk_index = 0
            for group_index, (report_name, paragraphs) in enumerate(report_groups):
                self._raise_if_stop_requested()
                heading = report_name or "Report"
                first_page = report_page_by_name.get(report_name, "")
                if first_page:
                    heading = f"{heading} [Report](page:{first_page})"
                if summary_reports and summary_reports[-1].strip():
                    summary_reports.append("")
                summary_reports.append(heading)
                summary_reports.append("")
                expected_chunks = (
                    report_group_chunk_counts[group_index]
                    if group_index < len(report_group_chunk_counts)
                    else 0
                )
                emitted_chunks = 0
                for _chunk in _chunk_paragraphs(paragraphs, chunk_size):
                    self._raise_if_stop_requested()
                    if expected_chunks and emitted_chunks >= expected_chunks:
                        break
                    response = (
                        report_responses[report_chunk_index]
                        if report_chunk_index < len(report_responses)
                        else ""
                    )
                    report_chunk_index += 1
                    emitted_chunks += 1
                    if response:
                        summary_reports.append(response.strip())
                        summary_reports.append("")

            minutes_outline: list[str] = []
            if display_case_name:
                minutes_outline.extend(["Minutes Summary", display_case_name, ""])
            else:
                minutes_outline.append("Minutes Summary")

            minute_entries = _load_json_entries(minutes_boundaries_path)
            minutes_index = 0
            for entry in minute_entries:
                self._raise_if_stop_requested()
                date_value = _extract_entry_value(entry, "date").strip()
                start_label = _extract_entry_value(entry, "start_page", "start", "starte_page").strip()
                end_label = _extract_entry_value(entry, "end_page", "end", "endpage").strip()
                start_page = _page_number_from_label(start_label)
                end_page = _page_number_from_label(end_label)
                if start_page is None or end_page is None:
                    raise ValueError("Minute order boundary entry missing start/end page.")
                if end_page < start_page:
                    raise ValueError("Minute order boundary entry has end page before start page.")
                minutes_outline.append(date_value or "Minute Order")
                minutes_outline.append("")
                page_texts: list[str] = []
                for page in range(start_page, end_page + 1):
                    self._raise_if_stop_requested()
                    page_path = text_dir / f"{page:04d}.txt"
                    if not page_path.exists():
                        raise FileNotFoundError(f"Missing text file {page_path.name}.")
                    page_texts.append(page_path.read_text(encoding="utf-8", errors="ignore"))
                minutes_payload = "\n".join(page_texts).strip()
                response = ""
                if minutes_payload:
                    response = self._request_plain_text(
                        {
                            "api_url": settings["api_url"],
                            "model_id": settings["model_id"],
                            "api_key": settings["api_key"],
                            "disable_reasoning": bool(
                                settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)
                            ),
                            "prompt": settings["minutes_prompt"],
                        },
                        minutes_payload,
                    )
                response = response.strip() if response else ""
                if response:
                    minutes_outline.append(" ".join(response.split()))
                else:
                    minutes_outline.append("")
                minutes_outline.append("")
                minutes_index += 1

            summaries_dir.mkdir(parents=True, exist_ok=True)
            summaries_path.write_text(
                _collapse_blank_lines("\n".join(summary_hearings)),
                encoding="utf-8",
            )
            reports_path.write_text(
                _collapse_blank_lines("\n".join(summary_reports)),
                encoding="utf-8",
            )
            minutes_path.write_text(
                _collapse_blank_lines("\n".join(minutes_outline)),
                encoding="utf-8",
            )
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Create summaries failed: {exc}")
        else:
            success = True
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "create_summaries",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            GLib.idle_add(self.show_toast, "Create summaries complete.")
        finally:
            GLib.idle_add(self.step_ten_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_ten_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True

    def _run_step_add_hearing_date_links(self) -> bool:
        success: bool | str | None = False
        try:
            self._raise_if_stop_requested()
            root_dir = self._resolve_case_root()
            if root_dir is None:
                if self.selected_pdfs:
                    raise ValueError("Selected PDFs must be in the same folder.")
                raise ValueError("Choose PDF files or select a saved case first.")
            artifacts_dir = root_dir / "artifacts"
            summaries_path, _reports_path = _summary_output_paths(root_dir)
            if not summaries_path.exists():
                raise FileNotFoundError("Run Create summaries to generate hearing summaries first.")
            hearing_boundaries_path = artifacts_dir / "hearing_boundaries.json"
            minutes_boundaries_path = artifacts_dir / "minutes_boundaries.json"
            if not hearing_boundaries_path.exists() or not minutes_boundaries_path.exists():
                raise FileNotFoundError(
                    "Run Find boundaries to generate hearing/minute boundaries first."
                )

            hearing_entries = _load_json_entries(hearing_boundaries_path)
            minute_entries = _load_json_entries(minutes_boundaries_path)
            if not hearing_entries and not minute_entries:
                GLib.idle_add(
                    self.show_toast,
                    "No hearing or minute boundaries found. Skipping Add date links to hearing Sum.",
                    "WARN",
                )
                success = "Skipped"
                return True

            hearing_page_by_date: dict[str, str] = {}
            minute_page_by_date: dict[str, str] = {}
            display_date_by_key: dict[str, str] = {}

            for entry in hearing_entries:
                date_value = _extract_entry_value(entry, "date").strip()
                if not date_value:
                    continue
                page_str = _extract_start_page_for_date_links(entry)
                if not page_str:
                    continue
                date_key = _hearing_date_key(date_value)
                if not date_key:
                    continue
                hearing_page_by_date.setdefault(date_key, page_str)
                display_date_by_key.setdefault(date_key, _format_long_us_date(date_value))

            for entry in minute_entries:
                date_value = _extract_entry_value(entry, "date").strip()
                if not date_value:
                    continue
                page_str = _extract_start_page_for_date_links(entry)
                if not page_str:
                    continue
                date_key = _hearing_date_key(date_value)
                if not date_key:
                    continue
                minute_page_by_date.setdefault(date_key, page_str)
                display_date_by_key.setdefault(date_key, _format_long_us_date(date_value))

            hearing_summary_lines = summaries_path.read_text(
                encoding="utf-8",
                errors="ignore",
            ).splitlines()

            def _heading_date_key(line: str) -> str | None:
                stripped = line.strip()
                if not stripped:
                    return None
                without_links = re.sub(r"\[[^\]]+\]\(page:\d{4}\)", "", stripped)
                without_links = re.sub(r"\s+", " ", without_links).strip()
                date_key = _hearing_date_key(without_links)
                if not date_key or date_key not in display_date_by_key:
                    return None
                return date_key

            def _date_sort_tuple(date_key: str) -> tuple[int, datetime.datetime, str]:
                display = display_date_by_key.get(date_key, "").strip()
                try:
                    parsed = datetime.datetime.strptime(display, "%B %d, %Y")
                except ValueError:
                    return (1, datetime.datetime.max, date_key)
                return (0, parsed, date_key)

            def _render_heading_line(date_key: str) -> str:
                display_date = display_date_by_key.get(date_key, "")
                hearing_page = hearing_page_by_date.get(date_key)
                minute_page = minute_page_by_date.get(date_key)
                pieces = [display_date or date_key]
                if hearing_page:
                    pieces.append(f"[Hearing](page:{hearing_page})")
                if minute_page:
                    pieces.append(f"[Minute Order](page:{minute_page})")
                return " ".join(pieces).strip()

            preamble_lines: list[str] = []
            sections: list[dict[str, Any]] = []
            current_section: dict[str, Any] | None = None

            for line in hearing_summary_lines:
                self._raise_if_stop_requested()
                date_key = _heading_date_key(line)
                if date_key:
                    current_section = {"date_key": date_key, "body_lines": []}
                    sections.append(current_section)
                    continue
                if current_section is None:
                    preamble_lines.append(line)
                else:
                    current_section["body_lines"].append(line)

            existing_section_keys = [str(section["date_key"]) for section in sections]
            missing_minute_keys = [
                key for key in minute_page_by_date if key not in set(existing_section_keys)
            ]
            missing_minute_keys.sort(key=_date_sort_tuple)

            for missing_key in missing_minute_keys:
                self._raise_if_stop_requested()
                missing_sort = _date_sort_tuple(missing_key)
                insert_at = len(sections)
                for index, section in enumerate(sections):
                    current_key = str(section["date_key"])
                    if _date_sort_tuple(current_key) > missing_sort:
                        insert_at = index
                        break
                sections.insert(insert_at, {"date_key": missing_key, "body_lines": []})

            if not sections:
                raise ValueError("No date headings found and no minute dates available to add links.")

            linked_lines: list[str] = list(preamble_lines)
            modified = 0
            inserted = 0
            existing_key_set = set(existing_section_keys)

            for section in sections:
                self._raise_if_stop_requested()
                date_key = str(section["date_key"])
                body_lines = list(section["body_lines"])
                heading_line = _render_heading_line(date_key)
                if not heading_line:
                    continue
                if linked_lines and linked_lines[-1].strip():
                    linked_lines.append("")
                linked_lines.append(heading_line)
                if date_key not in existing_key_set:
                    inserted += 1
                else:
                    modified += 1
                if body_lines:
                    linked_lines.extend(body_lines)

            if modified == 0 and inserted == 0:
                raise ValueError("No hearing/minute date headings matched boundary dates.")

            summaries_path.write_text(
                _collapse_blank_lines("\n".join(linked_lines)),
                encoding="utf-8",
            )
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Add date links to hearing Sum failed: {exc}")
        else:
            success = True
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "add_hearing_date_links",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            GLib.idle_add(self.show_toast, "Add date links to hearing Sum complete.")
        finally:
            GLib.idle_add(self.step_add_hearing_date_links_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_add_hearing_date_links_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True or success == "Skipped"

    def _run_step_eleven(self) -> bool:
        success: bool | str | None = False
        try:
            self._raise_if_stop_requested()
            root_dir = self._resolve_case_root()
            if root_dir is None:
                if self.selected_pdfs:
                    raise ValueError("Selected PDFs must be in the same folder.")
                raise ValueError("Choose PDF files or select a saved case first.")
            summaries_path, reports_path = _summary_output_paths(root_dir)
            minutes_path = _minutes_summary_output_path(root_dir)
            if (
                not summaries_path.exists()
                or not reports_path.exists()
                or not minutes_path.exists()
            ):
                raise FileNotFoundError(
                    "Run Create summaries to generate hearing, report, and minute summaries first."
                )
            settings = load_overview_settings()
            if not settings["api_url"] or not settings["model_id"] or not settings["api_key"]:
                raise ValueError("Configure overview API URL, model ID, and API key in Settings.")
            hearings_text = summaries_path.read_text(encoding="utf-8", errors="ignore")
            reports_text = reports_path.read_text(encoding="utf-8", errors="ignore")
            minutes_text = minutes_path.read_text(encoding="utf-8", errors="ignore")
            generic_lines = {
                "hearings summary",
                "reports summary",
                "minutes summary",
            }
            case_name, _root_dir = load_case_context()
            display_case_name = case_name.replace("_", " ").strip() if case_name else ""

            def _has_meaningful_summary_content(text: str) -> bool:
                for line in text.splitlines():
                    cleaned = " ".join(line.split()).strip()
                    if not cleaned:
                        continue
                    if cleaned.lower() in generic_lines:
                        continue
                    if display_case_name and cleaned == display_case_name:
                        continue
                    return True
                return False

            if not any(
                _has_meaningful_summary_content(text)
                for text in (hearings_text, reports_text, minutes_text)
            ):
                GLib.idle_add(
                    self.show_toast,
                    "No summary content available for Case overview. Skipping.",
                    "WARN",
                )
                success = "Skipped"
                return True
            combined = "\n\n".join(
                [
                    "Summarized Hearings:",
                    hearings_text.strip(),
                    "",
                    "Summarized Reports:",
                    reports_text.strip(),
                    "",
                    "Summarized Minute Orders:",
                    minutes_text.strip(),
                ]
            ).strip()
            overview = self._request_plain_text(
                {
                    "api_url": settings["api_url"],
                    "model_id": settings["model_id"],
                    "api_key": settings["api_key"],
                    "disable_reasoning": bool(
                        settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)
                    ),
                    "prompt": settings["prompt"],
                },
                combined,
            )
            if not overview:
                raise ValueError("Overview response was empty.")
            rag_dir = root_dir / "rag"
            rag_dir.mkdir(parents=True, exist_ok=True)
            (rag_dir / "case_overview.txt").write_text(
                _collapse_blank_lines(overview),
                encoding="utf-8",
            )
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Case overview failed: {exc}")
        else:
            success = True
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "case_overview",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            GLib.idle_add(self.show_toast, "Case overview complete.")
        finally:
            GLib.idle_add(self.step_eleven_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_eleven_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True or success == "Skipped"

    def _run_step_twelve(self) -> bool:
        success: bool | str | None = False
        try:
            self._raise_if_stop_requested()
            root_dir = self._resolve_case_root()
            if root_dir is None:
                if self.selected_pdfs:
                    raise ValueError("Selected PDFs must be in the same folder.")
                raise ValueError("Choose PDF files or select a saved case first.")
            artifacts_dir = root_dir / "artifacts"
            optimized_hearings_path = artifacts_dir / "optimized_hearings.txt"
            optimized_reports_path = artifacts_dir / "optimized_reports.txt"
            if not optimized_hearings_path.exists() or not optimized_reports_path.exists():
                raise FileNotFoundError(
                    "Run Create optimized to generate optimized files first."
                )
            settings = load_rag_settings()
            provider = settings.get("provider", DEFAULT_RAG_PROVIDER)
            try:
                from langchain_chroma import Chroma  # type: ignore
                from langchain_core.documents import Document  # type: ignore
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(
                    "Missing langchain/chroma dependencies. See uv add instructions."
                ) from exc

            rag_dir = root_dir / "rag"
            vector_dir = rag_dir / "vector_database"
            _prepare_directory(vector_dir)

            if provider == RAG_PROVIDER_VOYAGE:
                if not settings["voyage_api_key"] or not settings["voyage_model"]:
                    raise ValueError("Configure Voyage credentials in Settings.")
                try:
                    voyage_module = importlib.import_module("langchain_voyageai")
                    rag_embedder_class = getattr(
                        voyage_module,
                        "VoyageAI" + "Emb" + "eddings",
                    )
                except Exception as exc:  # noqa: BLE001
                    raise RuntimeError(
                        "Missing Voyage embedding dependencies. Run `uv add langchain-voyageai voyageai`."
                    ) from exc
                rag_embedder = rag_embedder_class(
                    voyage_api_key=settings["voyage_api_key"],
                    model=settings["voyage_model"],
                )
            elif provider == RAG_PROVIDER_ISAACUS:
                if not settings["isaacus_api_key"] or not settings["isaacus_model"]:
                    raise ValueError("Configure Isaacus credentials in Settings.")
                try:
                    isaacus_module = importlib.import_module("isaacus")
                    isaacus_client_class = getattr(isaacus_module, "Isaacus")
                except Exception as exc:  # noqa: BLE001
                    raise RuntimeError(
                        "Missing Isaacus SDK dependency. Run `uv add isaacus`."
                    ) from exc
                isaacus_client = isaacus_client_class(api_key=settings["isaacus_api_key"])
                rag_embedder = IsaacusEmbeddings(
                    client=isaacus_client,
                    model=settings["isaacus_model"],
                )
            else:
                raise ValueError(f"Unsupported RAG embedding provider: {provider}")

            vectorstore = Chroma(
                persist_directory=str(vector_dir),
                embedding_function=rag_embedder,
            )

            hearing_sections = _load_labeled_chunk_directories(
                artifacts_dir / "optimized" / "hearings",
                "hearing",
                "hearing_date",
            )
            report_sections = _load_labeled_chunk_directories(
                artifacts_dir / "optimized" / "reports",
                "report",
                "report_name",
            )
            if not hearing_sections and not report_sections:
                GLib.idle_add(
                    self.show_toast,
                    "No optimized content available for RAG index. Skipping.",
                    "WARN",
                )
                success = "Skipped"
                return True

            documents: list[Document] = []
            for section in hearing_sections:
                self._raise_if_stop_requested()
                metadata = section.get("metadata")
                metadata = metadata if isinstance(metadata, dict) else {}
                section_paragraphs = _expand_section_chunk_paragraphs(
                    list(section.get("chunks", []))
                )
                total_paragraphs = len(section_paragraphs)
                for paragraph_index, content in enumerate(section_paragraphs, start=1):
                    cleaned = str(content or "").strip()
                    if not cleaned:
                        continue
                    document_metadata = {"source": optimized_hearings_path.name}
                    document_metadata.update(metadata)
                    document_metadata["chunk_index"] = paragraph_index
                    document_metadata["chunk_total"] = total_paragraphs
                    documents.append(
                        Document(
                            page_content=cleaned,
                            metadata=document_metadata,
                        )
                    )
            for section in report_sections:
                self._raise_if_stop_requested()
                metadata = section.get("metadata")
                metadata = metadata if isinstance(metadata, dict) else {}
                section_paragraphs = _expand_section_chunk_paragraphs(
                    list(section.get("chunks", []))
                )
                total_paragraphs = len(section_paragraphs)
                for paragraph_index, content in enumerate(section_paragraphs, start=1):
                    cleaned = str(content or "").strip()
                    if not cleaned:
                        continue
                    document_metadata = {"source": optimized_reports_path.name}
                    document_metadata.update(metadata)
                    document_metadata["chunk_index"] = paragraph_index
                    document_metadata["chunk_total"] = total_paragraphs
                    documents.append(
                        Document(
                            page_content=cleaned,
                            metadata=document_metadata,
                        )
                    )
            if not documents:
                raise ValueError("No paragraphs found to embed.")
            vectorstore.add_documents(documents)

        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Create RAG index failed: {exc}")
        else:
            success = True
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "create_rag_index",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            GLib.idle_add(self.show_toast, "Create RAG index complete.")
        finally:
            GLib.idle_add(self.step_twelve_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_twelve_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True or success == "Skipped"

    def _append_boundary_entry(
        self,
        page_type: str | None,
        start_file: str | None,
        end_file: str | None,
        date_by_file: dict[str, str],
        report_name_by_file: dict[str, str],
        hearing_boundaries: list[dict[str, str]],
        report_boundaries: list[dict[str, str]],
        minutes_boundaries: list[dict[str, str]],
    ) -> None:
        if not page_type or not start_file or not end_file:
            return
        start_page = _page_label_from_filename(start_file)
        end_page = _page_label_from_filename(end_file)
        if page_type in {
            "hearing",
            "hearing_first_page",
            "hearing_page",
            "rt_body",
            "rt_body_first_page",
        }:
            hearing_boundaries.append(
                {
                    "date": date_by_file.get(start_file, ""),
                    "start_page": start_page,
                    "end_page": end_page,
                }
            )
            return
        if page_type in {"report", "report_page"}:
            report_name = report_name_by_file.get(start_file, "").strip()
            if not report_name:
                return
            report_boundaries.append(
                {
                    "report_name": report_name,
                    "start_page": start_page,
                    "end_page": end_page,
                }
            )
            return
        if page_type in {
            "minute_order",
            "minute_order_first_page",
            "minute_order_page",
            "minute_order_page_first_page",
            "ct_minute_order",
            "ct_minute_order_first_page",
        }:
            minutes_boundaries.append(
                {
                    "date": date_by_file.get(start_file, ""),
                    "start_page": start_page,
                    "end_page": end_page,
                }
            )

    def _classify_image(
        self,
        settings: dict[str, Any],
        filename: str,
        image_path: Path,
    ) -> dict[str, str]:
        self._raise_if_stop_requested()
        image_base64 = base64.b64encode(image_path.read_bytes()).decode()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "RecordPrep/0.1",
        }
        api_key = settings.get("api_key", "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        body = {
            "model": settings["model_id"],
            "stream": False,
            "messages": [
                {"role": "system", "content": settings["prompt"]},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            },
                        }
                    ],
                },
            ],
        }
        if bool(settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)):
            body["thinking"] = {"type": "disabled"}
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(settings["api_url"], data=data, headers=headers, method="POST")
        payload = _post_json_with_retries(req, timeout=300, error_label="Classifier request failed")
        response_text = self._extract_response_text(payload)
        try:
            parsed = json.loads(self._extract_json_payload(response_text))
        except json.JSONDecodeError:
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}
        if not _extract_entry_value(parsed, "page_type", "pagetype"):
            fallback_page_type = _extract_page_type_from_jsonish(response_text)
            if fallback_page_type:
                parsed["page_type"] = fallback_page_type
        expected_keys = _extract_prompt_keys(settings.get("prompt", ""))
        filename_key = "file_name"
        if not expected_keys:
            result = {str(key): str(value) if value is not None else "" for key, value in parsed.items()}
            result[filename_key] = filename
            return result
        if filename_key not in expected_keys:
            expected_keys = [filename_key, *expected_keys]
        normalized_parsed = {_normalize_key(key): key for key in parsed.keys()}
        result: dict[str, str] = {}
        for expected_key in expected_keys:
            normalized_expected = _normalize_key(expected_key)
            if "filename" in normalized_expected and filename:
                result[expected_key] = filename
                continue
            source_key = normalized_parsed.get(normalized_expected)
            if source_key is not None:
                value = parsed.get(source_key)
                result[expected_key] = str(value) if value is not None else ""
            else:
                result[expected_key] = ""
        return result

    def _classify_text(
        self,
        settings: dict[str, Any],
        filename: str,
        content: str,
    ) -> dict[str, str]:
        self._raise_if_stop_requested()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {settings['api_key']}",
            "User-Agent": "RecordPrep/0.1",
        }
        body = {
            "model": settings["model_id"],
            "stream": False,
            "messages": [
                {"role": "system", "content": settings["prompt"]},
                {"role": "user", "content": content},
            ],
        }
        if bool(settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)):
            body["thinking"] = {"type": "disabled"}
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(settings["api_url"], data=data, headers=headers, method="POST")
        payload = _post_json_with_retries(req, timeout=300, error_label="Classifier request failed")
        response_text = self._extract_response_text(payload)
        try:
            parsed = json.loads(self._extract_json_payload(response_text))
        except json.JSONDecodeError:
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}
        if not _extract_entry_value(parsed, "page_type", "pagetype"):
            fallback_page_type = _extract_page_type_from_jsonish(response_text)
            if fallback_page_type:
                parsed["page_type"] = fallback_page_type
        expected_keys = _extract_prompt_keys(settings.get("prompt", ""))
        filename_key = "file_name"
        if not expected_keys:
            result = {str(key): str(value) if value is not None else "" for key, value in parsed.items()}
            result[filename_key] = filename
            return result
        if filename_key not in expected_keys:
            expected_keys = [filename_key, *expected_keys]
        normalized_parsed = {_normalize_key(key): key for key in parsed.keys()}
        result: dict[str, str] = {}
        for expected_key in expected_keys:
            normalized_expected = _normalize_key(expected_key)
            if "filename" in normalized_expected and filename:
                result[expected_key] = filename
                continue
            source_key = normalized_parsed.get(normalized_expected)
            if source_key is not None:
                value = parsed.get(source_key)
                result[expected_key] = str(value) if value is not None else ""
            else:
                result[expected_key] = ""
        return result

    def _request_plain_text(self, settings: dict[str, Any], content: str) -> str:
        self._raise_if_stop_requested()
        api_url = str(settings.get("api_url", "") or "").strip()
        model_id = str(settings.get("model_id", "") or "").strip()
        api_key = str(settings.get("api_key", "") or "").strip()
        max_tokens_raw = str(settings.get("max_tokens", "") or "").strip()
        if not api_url:
            raise ValueError("API URL is empty.")
        if not model_id:
            raise ValueError("Model ID is empty.")
        if not api_key:
            raise ValueError("API key is empty.")
        max_tokens: int | None = None
        if max_tokens_raw:
            try:
                max_tokens = max(1, int(max_tokens_raw))
            except ValueError:
                max_tokens = None
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "RecordPrep/0.1",
        }
        disable_reasoning = bool(
            settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)
        )
        body = {
            "model": model_id,
            "stream": False,
            "messages": [
                {"role": "system", "content": settings["prompt"]},
                {"role": "user", "content": content},
            ],
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if disable_reasoning:
            if _model_looks_deepseek(model_id) or _model_looks_kimi(model_id):
                body["thinking"] = {"type": "disabled"}
            else:
                body["reasoning_effort"] = "none"
        error_label = "Classifier request failed"
        attempted_without_thinking = False
        attempted_without_reasoning_effort = False

        while True:
            data = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(api_url, data=data, headers=headers, method="POST")
            try:
                if body.get("stream"):
                    return self._stream_text_with_retries(
                        req,
                        timeout=300,
                        error_label=error_label,
                    ).strip()
                payload = _post_json_with_retries(req, timeout=300, error_label=error_label)
                response_text = self._extract_response_text(payload).strip()
                if response_text:
                    return response_text
                # Some OpenAI-compatible providers behave better with SSE than JSON mode.
                body["stream"] = True
                continue
            except RuntimeError as exc:
                message = str(exc).lower()
                if (
                    not attempted_without_thinking
                    and "thinking" in body
                    and "thinking" in message
                    and any(marker in message for marker in ("unsupported", "unknown", "invalid"))
                ):
                    attempted_without_thinking = True
                    body.pop("thinking", None)
                    continue
                if (
                    not attempted_without_reasoning_effort
                    and "reasoning_effort" in body
                    and "reasoning_effort" in message
                    and any(marker in message for marker in ("unsupported", "unknown", "invalid"))
                ):
                    attempted_without_reasoning_effort = True
                    body.pop("reasoning_effort", None)
                    continue
                raise

    def _stream_text_with_retries(
        self,
        req: urllib.request.Request,
        *,
        timeout: int,
        error_label: str,
    ) -> str:
        for attempt in range(1, LLM_MAX_RETRIES + 1):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return self._read_sse_text_response(resp)
            except urllib.error.HTTPError as exc:
                retry_after = _retry_after_seconds(exc)
                if exc.code in LLM_RETRYABLE_HTTP_CODES and attempt < LLM_MAX_RETRIES:
                    time.sleep(_retry_delay_seconds(attempt, retry_after))
                    continue
                error_body = ""
                try:
                    error_body = exc.read().decode("utf-8", errors="ignore")
                except Exception:
                    error_body = ""
                detail = error_body.strip() or exc.reason or "request failed"
                raise RuntimeError(f"{error_label}: HTTP {exc.code} {detail}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt < LLM_MAX_RETRIES:
                    time.sleep(_retry_delay_seconds(attempt, None))
                    continue
                raise RuntimeError(f"{error_label}: {exc}") from exc
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"{error_label}: {exc}") from exc
        raise RuntimeError(f"{error_label}: exhausted retries")

    def _read_sse_text_response(self, resp: Any) -> str:
        parts: list[str] = []
        while True:
            self._raise_if_stop_requested()
            raw = resp.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            payload_text = ""
            if line.startswith("data:"):
                payload_text = line[5:].lstrip()
            else:
                payload_text = line
            if payload_text == "[DONE]":
                break
            if not payload_text:
                continue
            try:
                payload = json.loads(payload_text)
            except json.JSONDecodeError:
                continue
            answer_text, _reasoning_text = self._extract_stream_text_parts(payload)
            if answer_text:
                parts.append(answer_text)
        return "".join(parts).strip()

    def _extract_stream_text_parts(self, payload: Any) -> tuple[str, str]:
        answer_text = ""
        reasoning_text = ""
        choices = payload.get("choices") if isinstance(payload, dict) else None
        if isinstance(choices, list) and choices:
            first = choices[0] or {}
            delta = first.get("delta") or first.get("message") or first
            if isinstance(delta, dict):
                answer_text = self._coerce_stream_text(
                    delta.get("content") if "content" in delta else delta.get("text")
                )
                reasoning_text = self._coerce_stream_text(
                    delta.get("reasoning_content")
                    if "reasoning_content" in delta
                    else delta.get("reasoning")
                    if "reasoning" in delta
                    else delta.get("thinking")
                )
        if isinstance(payload, dict):
            fallback = payload.get("data") or payload.get("text")
            if isinstance(fallback, str):
                answer_text = answer_text or fallback
        return answer_text, reasoning_text

    def _coerce_stream_text(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if not isinstance(value, list):
            return ""
        merged: list[str] = []
        for item in value:
            if isinstance(item, dict):
                candidate = item.get("text")
                if isinstance(candidate, str):
                    merged.append(candidate)
            elif isinstance(item, str):
                merged.append(item)
        return "".join(merged)

    def _extract_response_text(self, payload: Any) -> str:
        if isinstance(payload, dict):
            choices = payload.get("choices")
            if isinstance(choices, list) and choices:
                first = choices[0] or {}
                message = first.get("message") or {}
                content = message.get("content")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    parts: list[str] = []
                    for part in content:
                        if isinstance(part, str):
                            parts.append(part)
                        elif isinstance(part, dict):
                            text_value = part.get("text")
                            if isinstance(text_value, str):
                                parts.append(text_value)
                    if parts:
                        return "\n".join(parts)
            for key in ("output", "text", "data"):
                value = payload.get(key)
                if isinstance(value, str):
                    return value
        return ""

    def _extract_json_payload(self, text: str) -> str:
        if not text:
            return ""
        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return stripped
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if match:
            return match.group(0).strip()
        return stripped


class RecordPrepApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APPLICATION_ID)

    def do_activate(self) -> None:
        _log_startup("do_activate: begin")
        win = self.props.active_window
        if not win:
            _log_startup("do_activate: creating window")
            win = RecordPrepWindow(self)
            _log_startup("do_activate: window created")
        else:
            _log_startup("do_activate: using existing window")
        win.present()
        _log_startup("do_activate: present called")


def main() -> None:
    _log_startup("main: begin")
    app = RecordPrepApp()
    _log_startup("main: app created")
    app.run(None)
    _log_startup("main: app run returned")


if __name__ == "__main__":
    main()
