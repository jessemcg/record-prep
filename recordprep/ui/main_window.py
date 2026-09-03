#!/usr/bin/env python3

from __future__ import annotations

import base64
import concurrent.futures
import sys
import datetime
import os
import json
import random
import re
import signal
import shutil
import subprocess
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, GObject, Pango  # type: ignore

Vte = None  # type: ignore[assignment]
try:
    gi.require_version("Vte", "3.91")
    from gi.repository import Vte as VteModule  # type: ignore

    Vte = VteModule  # type: ignore[assignment]
except (ImportError, ValueError):
    Vte = None  # type: ignore[assignment]

import fitz
import pdftotext
from pypdf import PdfReader, PdfWriter
from pypdf.errors import DependencyError
import requests
from bs4 import BeautifulSoup
from bs4.element import NavigableString
from pylatexenc.latex2text import LatexNodes2Text
from tabulate import tabulate

from recordprep import APPLICATION_ID, APPLICATION_NAME
from recordprep.classification import run_classifier_jobs
from recordprep.pi_bundle import (
    PARTICIPANT_TEMPLATE_WARNING,
    pi_step_complete,
    validate_participant_index_output,
)
from recordprep.transcript_layout import (
    TranscriptLayoutError,
    apply_manual_override,
    capture_layout_rebind_guard,
    detection_status,
    diagnose_layout,
    finalize_layout_rebind,
    layout_display_summary,
    legacy_manifest_split,
    read_resolved_layout,
    resolve_rt_ct_split as resolve_layout_rt_ct_split,
)
from recordprep.pi_runtime import (
    DEFAULT_PI_AGENT_COMMAND,
    PiModel,
    PiRuntimeError,
    PiSettingsError,
    available_pi_models,
    current_project_pi_model,
    current_project_pi_thinking_level,
    discover_pi_agent_command,
    incompatible_pi_agent_flag,
    resolve_pi_agent_argv,
    save_project_pi_model,
    save_project_pi_thinking_level,
)

STARTUP_LOG_PATH = Path("/tmp/recordprep_startup.log")
PI_MODEL_DROPDOWN_WIDTH_CHARS = 64
PI_MODEL_DROPDOWN_MAX_WIDTH_CHARS = 80

GLib.set_application_name(APPLICATION_NAME)


def _setup_pi_model_list_item(
    _factory: Gtk.SignalListItemFactory,
    list_item: Gtk.ListItem,
) -> None:
    label = Gtk.Label(xalign=0)
    label.set_width_chars(PI_MODEL_DROPDOWN_WIDTH_CHARS)
    label.set_max_width_chars(PI_MODEL_DROPDOWN_MAX_WIDTH_CHARS)
    label.set_wrap(True)
    label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    label.set_margin_top(6)
    label.set_margin_bottom(6)
    label.set_margin_start(12)
    label.set_margin_end(12)
    list_item.set_child(label)


def _bind_pi_model_list_item(
    _factory: Gtk.SignalListItemFactory,
    list_item: Gtk.ListItem,
) -> None:
    item = list_item.get_item()
    label = list_item.get_child()
    if isinstance(item, Gtk.StringObject) and isinstance(label, Gtk.Label):
        label.set_label(item.get_string())

LLM_MAX_RETRIES = 5
LLM_RETRY_BASE_SECONDS = 1.0
LLM_RETRY_MAX_SECONDS = 30.0
LLM_RETRYABLE_HTTP_CODES = {408, 409, 429, 500, 502, 503, 504}
LOCAL_OCR_SERVER_STARTUP_SECONDS = 1.0
DEFAULT_LOCAL_OCR_WORKERS = 4
DEFAULT_LOCAL_OCR_SLOTS = 4
DEFAULT_CLASSIFIER_WORKERS = 1
LOCAL_VISION_SERVER_STARTUP_SECONDS = 2.0
LOCAL_SERVER_READY_TIMEOUT_SECONDS = 120.0
LOCAL_SERVER_READY_POLL_SECONDS = 1.0
VISION_CLASSIFICATION_STEP_IDS = {
    "classify_basic",
    "classify_advanced",
    "classify_dates",
    "classify_names",
}
# Steps that can launch without a resolved transcript layout. Detection is a
# PI stage and must never join VISION_CLASSIFICATION_STEP_IDS.
NO_RESOLVED_LAYOUT_STEP_IDS = {"create_files", "detect_transcript_layout"}
PIPELINE_PHASES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "prepare",
        "Prepare",
        (
            "create_files",
            "detect_transcript_layout",
            "strip_characters",
            "infer_case",
        ),
    ),
    (
        "classify",
        "Classify",
        (
            "classify_basic",
            "classify_advanced",
            "correct_classify_advanced",
            "classify_dates",
            "classify_names",
        ),
    ),
    (
        "organize",
        "Organize",
        ("build_toc", "correct_toc", "find_boundaries", "correct_boundaries"),
    ),
    (
        "record_context",
        "Record Context",
        ("number_transcript_pages", "build_participant_index"),
    ),
    (
        "summarize",
        "Summarize",
        (
            "create_hearing_summaries",
            "create_report_summaries",
            "create_minute_order_summaries",
            "add_hearing_date_links",
        ),
    ),
    (
        "agent_search",
        "Agent Search",
        ("create_case_overview", "build_source_map"),
    ),
)
PIPELINE_STEP_PHASE = {
    step_id: phase_id
    for phase_id, _title, step_ids in PIPELINE_PHASES
    for step_id in step_ids
}
COMPLETED_STEP_STATUSES = {"Done", "Skipped"}
SETTINGS_NAV_GROUPS: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = (
    (
        "prepare",
        "Prepare",
        (
            ("text-source", "Create files"),
            ("local-ocr", "Local OCR"),
            ("case-name", "Infer case"),
        ),
    ),
    (
        "classify",
        "Classify",
        (
            ("classify-basic", "Basic"),
            ("classify-advanced", "Advanced"),
            ("classify-dates", "Dates"),
            ("classify-names", "Names"),
        ),
    ),
    (
        "summarize",
        "Summarize",
        (("summarize", "Summarize"),),
    ),
    (
        "agent",
        "Agent",
        (("pi", "PI"),),
    ),
)
TEST_PROMPT_GROUPS: tuple[
    tuple[str, str, tuple[tuple[str, str], ...]], ...
] = (
    (
        "classification",
        "Classification",
        (
            ("basic_rt", "Basic — RT"),
            ("basic_ct", "Basic — CT"),
            ("advanced_hearing", "Advanced — Hearing"),
            ("advanced_minute", "Advanced — Minute order"),
            ("advanced_form", "Advanced — Form"),
            ("dates_hearing", "Dates — Hearing"),
            ("dates_minute", "Dates — Minute order"),
            ("names_report", "Names — Report"),
            ("names_form", "Names — Form"),
        ),
    ),
    (
        "summarize",
        "Summarize",
        (
            ("summarize_hearings", "Hearings"),
            ("summarize_reports", "Reports"),
            ("summarize_minutes", "Minute orders"),
        ),
    ),
)
MODEL_ID = "LightOnOCR-2-1B-Q8_0.gguf"
DEFAULT_SERVER_URL = "http://localhost:8000/v1/chat/completions"
START_SERVER_COMMAND = """\
cd $HOME/llama.cpp/build/bin
./llama-server \
-m $HOME/llama.cpp/models/LightOnOCR-2-1B-Q8_0.gguf \
--mmproj $HOME/llama.cpp/models/mmproj-LightOnOCR-2-1B-Q8_0.gguf \
--parallel {slots} \
-ngl 999 --port 8000 --flash-attn on
"""


class StopRequested(RuntimeError):
    pass


def _phase_progress_text(
    step_ids: Sequence[str],
    statuses: Mapping[str, str],
) -> str:
    completed = sum(
        statuses.get(step_id) in COMPLETED_STEP_STATUSES for step_id in step_ids
    )
    inactive_statuses = COMPLETED_STEP_STATUSES | {"Pending"}
    running = any(
        statuses.get(step_id, "Pending") not in inactive_statuses
        for step_id in step_ids
    )
    summary = f"{completed} of {len(step_ids)} complete"
    return f"{summary} • Running" if running else summary


def _first_incomplete_phase_id(completed_step_ids: set[str]) -> str | None:
    for phase_id, _title, step_ids in PIPELINE_PHASES:
        if any(step_id not in completed_step_ids for step_id in step_ids):
            return phase_id
    return None


def _transcript_summary(split_mode: str, split_page: int | None) -> str:
    if split_mode == "rt_only":
        return "Reporter's transcript only"
    if split_mode == "ct_only":
        return "Clerk's transcript only"
    if split_page:
        return f"RT + CT • RT through page {split_page}"
    return "RT + CT • split page not set"


def _pipeline_split_validation_message(
    split_mode: str | None,
    split_page: int | None,
) -> str | None:
    if (
        _normalize_rt_ct_split_mode(split_mode) == "split"
        and _normalize_rt_ct_split_page(split_page) is None
    ):
        return "Enter the last RT page before starting the pipeline."
    return None


def _step_requires_resolved_layout(step_id: str) -> bool:
    """True when a step may launch only after a resolved layout exists."""
    return step_id not in NO_RESOLVED_LAYOUT_STEP_IDS


def _layout_matches_legacy(root_dir: Path) -> bool:
    """Compare the resolved artifact against the legacy manifest mirrors.

    Returns True when the legacy mirrors are absent, when they match the
    resolved layout, or when no resolved layout exists. The legacy value is
    never accepted automatically; it is only compared.
    """
    resolved = read_resolved_layout(root_dir)
    if resolved is None:
        return True
    legacy_mode, legacy_page = legacy_manifest_split(root_dir)
    if legacy_mode not in {"rt_only", "ct_only", "split"}:
        return True
    resolved_mode = str(resolved.get("mode") or "")
    if resolved_mode == "rt_only":
        return legacy_mode == "rt_only"
    if resolved_mode == "ct_only":
        return legacy_mode == "ct_only"
    return (
        legacy_mode == "split"
        and legacy_page is not None
        and legacy_page == int(resolved.get("rt_end_file_page") or 0)
    )


def _settings_destination_keys() -> tuple[str, ...]:
    return tuple(
        key
        for _group_id, _title, destinations in SETTINGS_NAV_GROUPS
        for key, _label in destinations
    )


def _test_prompt_options(group_id: str) -> tuple[tuple[str, str], ...]:
    for candidate_id, _label, options in TEST_PROMPT_GROUPS:
        if candidate_id == group_id:
            return options
    return ()


def _test_prompt_input_kind(mode_id: str) -> str:
    classification_modes = {
        value for value, _label in TEST_PROMPT_GROUPS[0][2]
    }
    return "image" if mode_id in classification_modes else "text"


def _log_startup(message: str) -> None:
    try:
        timestamp = datetime.datetime.now().isoformat(sep=" ", timespec="seconds")
        with STARTUP_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"{timestamp} {message}\n")
    except OSError:
        pass


def _rgba_color(spec: str) -> Gdk.RGBA:
    color = Gdk.RGBA()
    if not color.parse(spec):
        raise ValueError(f"Invalid color: {spec}")
    return color


TERMINAL_PALETTE = (
    "#2e3436",
    "#cc0000",
    "#4e9a06",
    "#c4a000",
    "#3465a4",
    "#75507b",
    "#06989a",
    "#d3d7cf",
    "#555753",
    "#ef2929",
    "#8ae234",
    "#fce94f",
    "#729fcf",
    "#ad7fa8",
    "#34e2e2",
    "#eeeeec",
)


def _apply_recordprep_terminal_theme(terminal: Any) -> None:
    dark = Adw.StyleManager.get_default().get_dark()
    foreground = _rgba_color("#f2f4f8" if dark else "#20242c")
    background = _rgba_color("#3d3d3d" if dark else "#f5f5f5")
    selection = _rgba_color("#365a7a" if dark else "#c9e6ff")
    terminal.set_colors(
        foreground,
        background,
        [_rgba_color(spec) for spec in TERMINAL_PALETTE],
    )
    terminal.set_color_foreground(foreground)
    terminal.set_color_background(background)
    terminal.set_color_highlight(selection)
    terminal.set_color_highlight_foreground(foreground)
    terminal.set_clear_background(True)


def _install_recordprep_css() -> Gtk.CssProvider:
    provider = Gtk.CssProvider()
    provider.load_from_data(
        b"""
.recordprep-terminal-surface {
  border-radius: 12px;
  background-color: alpha(@window_fg_color, 0.08);
  border: none;
  box-shadow: none;
}
.recordprep-terminal-scroller {
  background-color: transparent;
  border: none;
  box-shadow: none;
}
.recordprep-terminal {
  border-radius: 12px;
  padding: 8px;
  background-color: @window_bg_color;
  background-image: none;
  color: @window_fg_color;
}
"""
    )
    display = Gdk.Display.get_default()
    if display is not None:
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
    return provider


def _sanitize_terminal_log_text(value: object, *, preserve_newlines: bool) -> str:
    text = str(value)
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", "", text)
    if preserve_newlines:
        return text.rstrip("\r\n")
    return " ".join(text.split()).strip()


def _terminal_log_line(message: object, level: str = "INFO") -> str:
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    normalized = str(level or "INFO").upper()
    color = {
        "INFO": "\x1b[36m",
        "WARN": "\x1b[33m",
        "ERROR": "\x1b[31m",
    }.get(normalized, "\x1b[36m")
    text = _sanitize_terminal_log_text(message, preserve_newlines=True)
    return f"\x1b[2m[{timestamp}]\x1b[0m {color}[{normalized}]\x1b[0m {text}\r\n"


PROJECT_DIR = Path(__file__).resolve().parents[2]
CONFIG_FILE = PROJECT_DIR / "config.json"
PI_PROJECT_DIR = PROJECT_DIR / ".pi"
PI_SKILL_RUNNER = PI_PROJECT_DIR / "scripts" / "run_recordprep_skill.py"
CONFIG_KEY_PI_AGENT_COMMAND = "pi_agent_command"
PI_THINKING_LEVEL_OPTIONS: tuple[tuple[str, str | None], ...] = (
    ("Use global PI default", None),
    ("Off", "off"),
    ("Minimal", "minimal"),
    ("Low", "low"),
    ("Medium", "medium"),
    ("High", "high"),
    ("Extra high", "xhigh"),
    ("Maximum", "max"),
)
INPUT_IDENTITY_VERSION = 1
GENERATED_CASE_BUNDLE_DIRS = (
    "text_pages",
    "image_pages",
    "classification",
    "artifacts",
    "summaries",
    "rag",
    "temp",
)
GENERATED_CASE_BUNDLE_FILES = (
    "case_name.txt",
    "manifest.json",
)
CONFIG_KEY_CLASSIFIER_API_URL = "classifier_api_url"
CONFIG_KEY_CLASSIFIER_MODEL_ID = "classifier_model_id"
CONFIG_KEY_CLASSIFIER_API_KEY = "classifier_api_key"
CONFIG_KEY_CLASSIFIER_PROMPT = "classifier_prompt"
CONFIG_KEY_CLASSIFIER_RT_PROMPT = "classifier_rt_prompt"
CONFIG_KEY_CLASSIFIER_CT_PROMPT = "classifier_ct_prompt"
CONFIG_KEY_CLASSIFIER_THINKING_ENABLED = "classifier_thinking_enabled"
CONFIG_KEY_CLASSIFIER_DISABLE_REASONING = "classifier_disable_reasoning"
CONFIG_KEY_CLASSIFIER_WORKERS = "classifier_workers"
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
CONFIG_KEY_LOCAL_OCR_WORKERS = "local_ocr_workers"
CONFIG_KEY_LOCAL_OCR_SLOTS = "local_ocr_slots"
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
CONFIG_KEY_SUMMARIZE_API_URL = "summarize_api_url"
CONFIG_KEY_SUMMARIZE_MODEL_ID = "summarize_model_id"
CONFIG_KEY_SUMMARIZE_API_KEY = "summarize_api_key"
CONFIG_KEY_SUMMARIZE_DISABLE_REASONING = "summarize_disable_reasoning"
CONFIG_KEY_SUMMARIZE_HEARINGS_PROMPT = "summarize_hearings_prompt"
CONFIG_KEY_SUMMARIZE_REPORTS_PROMPT = "summarize_reports_prompt"
CONFIG_KEY_SUMMARIZE_MINUTES_PROMPT = "summarize_minutes_prompt"
CONFIG_KEY_SUMMARIZE_WINDOW_TARGET_CHARS = "summarize_window_target_chars"
CONFIG_KEY_SUMMARIZE_WINDOW_MAX_PAGES = "summarize_window_max_pages"
LEGACY_CONFIG_KEY_SUMMARIZE_CHUNK_SIZE = "summarize_chunk_size"
CONFIG_KEY_SELECTED_PDFS = "selected_pdfs"
CONFIG_KEY_RUN_UNTIL_STEP = "run_until_step"
TEXT_SOURCE_EMBEDDED = "embedded"
TEXT_SOURCE_LOCAL_OCR = "local_ocr"
DEFAULT_TEXT_SOURCE = TEXT_SOURCE_EMBEDDED
DEFAULT_LOCAL_VISION_START_COMMAND = ""
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
    "Also extract the report date from the first page if present. "
    "For detention, jurisdiction, disposition, review, and other child-welfare reports, "
    "the report date may appear as a hearing date near the report title. "
    "Return JSON with keys: name, date. "
    "name must be the matching report title from the list; otherwise use an empty string. "
    "date should be a long-form U.S. date if present; otherwise use an empty string."
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
PREVIOUS_DEFAULT_SUMMARIZE_HEARINGS_PROMPT = (
    "You are summarizing one window of source pages from a juvenile dependency court "
    "hearing. The user message is organized into these labeled sections:\n\n"
    "1. PARTICIPANT INDEX CONTEXT — FOR ATTRIBUTION ONLY. This is validated metadata "
    "created in an earlier RecordPrep step. It identifies counsel roles, non-counsel "
    "participants, witness status, and mapped examinations. Use it only to attribute "
    "statements and classify sworn testimony; do not reproduce it as an appearance or "
    "participant roster. The transcript pages remain the factual source. If the metadata "
    "is unknown, conflicting, or inconsistent with the transcript, use neutral wording "
    "rather than guessing.\n"
    "2. OPTIONAL PRECEDING CONTEXT PAGE — DO NOT SUMMARIZE. When present, use this page "
    "only to understand a sentence or exchange that continues into the primary pages.\n"
    "3. PRIMARY SOURCE PAGES — SUMMARIZE ALL MATERIAL DETAILS. Summarize only these pages.\n\n"
    "Attribution rules: identify attorneys and non-counsel participants by hearing role "
    "on every material attribution; a name may follow parenthetically but never replaces "
    "the role. Use testified or testimony only for a verified witness within a mapped "
    "examination. Q/A formatting alone does not establish testimony. Describe unsworn "
    "colloquy with terms such as stated, answered, confirmed, or advised. Attribute "
    "questions to the examiner and answers to the mapped witness.\n\n"
    "Output requirements: return exactly one concise prose paragraph in plain English, "
    "with no internal line breaks. RecordPrep inserts a blank line between this paragraph "
    "and each adjacent summary-window paragraph. Include several legally significant "
    "verbatim quotes, "
    "each an uninterrupted two-to-five-word sequence in quotation marks. Do not alter "
    "quoted text or use ellipses. Do not begin with prefatory language, include the hearing "
    "date, add commentary, use Markdown, list appearances, recite the participant context, "
    "or add a standalone statement about whether testimony occurred."
)
DEFAULT_SUMMARIZE_HEARINGS_PROMPT = PREVIOUS_DEFAULT_SUMMARIZE_HEARINGS_PROMPT.replace(
    "Use testified or testimony only for a verified witness within a mapped "
    "examination. Q/A formatting alone does not establish testimony. Describe unsworn ",
    "Use testified or testimony to describe testimony occurring at the current hearing "
    "only for a verified witness within a mapped examination. A clearly qualified "
    "reference to prior, future, proposed, anticipated, stipulated, conditional, "
    "excluded, or absent testimony is permitted only when the wording unmistakably "
    "does not claim that testimony occurred at the current hearing. Q/A formatting "
    "alone does not establish testimony. Describe unsworn ",
)
NO_SUMMARIZABLE_REPORT_CONTENT = "NO_SUMMARIZABLE_REPORT_CONTENT"
PREVIOUS_DEFAULT_SUMMARIZE_REPORTS_PROMPT = (
    "You are summarizing one window of source pages from a report in a juvenile dependency "
    "case. The user message is organized into these labeled sections:\n\n"
    "1. OPTIONAL PRECEDING CONTEXT PAGE — DO NOT SUMMARIZE. When present, use this page "
    "only to understand a sentence or passage that continues into the primary pages.\n"
    "2. PRIMARY SOURCE PAGES — SUMMARIZE ALL MATERIAL DETAILS. Summarize only these pages. "
    "The source pages, not headings or metadata added by RecordPrep, supply the facts.\n\n"
    "Output requirements: return exactly one concise prose paragraph in plain English, "
    "with no internal line breaks. RecordPrep inserts a blank line between this paragraph "
    "and each adjacent summary-window paragraph. Preserve every material fact, recommendation, "
    "and procedural development in the primary pages "
    "at a consistent level of detail. Include several legally significant verbatim quotes, "
    "each an uninterrupted two-to-five-word sequence in quotation marks. Do not alter "
    "quoted text or use ellipses. Do not begin with prefatory language, add commentary, or "
    "use Markdown. Do not summarize the optional preceding context page again."
)
PREVIOUS_PROPOSAL_SCOPE_SUMMARIZE_REPORTS_PROMPT = (
    "You are summarizing one window of source pages from a report in a juvenile dependency "
    "case. The user message is organized into these labeled sections:\n\n"
    "1. OPTIONAL PRECEDING CONTEXT PAGE — DO NOT SUMMARIZE. When present, use this page "
    "only to understand a sentence or passage that continues into the primary pages.\n"
    "2. PRIMARY SOURCE PAGES — SUMMARIZE ALL MATERIAL DETAILS. Summarize only these pages. "
    "The source pages, not headings or metadata added by RecordPrep, supply the facts.\n"
    "3. REPORT PROPOSAL EXCLUSION CONTEXT — FOR SCOPE ONLY. When present, this section "
    "marks a formal package of proposed or recommended advisements, findings, and orders, "
    "together with associated boilerplate, offered for court adoption. A scope delimiter "
    "in the source text marks exactly where that package begins; on a later window this "
    "section instead warns that the formal proposal may still be continuing. Omit that "
    "formal package from your summary entirely: do not qualify, disclaim, or restate it. "
    "Never present a proposed or recommended finding or order as if it were a finding of "
    "fact, an order the court actually made, or a settled factual conclusion, and never use "
    "proposed wording to satisfy the verbatim-quotation requirement. Remain eligible: factual "
    "narrative, interviews, observations, assessments, procedural history, a high-level agency "
    "recommendation stated apart from the formal template with accurate agency attribution, "
    "and actual historical orders the report says the court already made, with accurate "
    "attribution.\n\n"
    "Output requirements: return exactly one concise prose paragraph in plain English, with "
    "no internal line breaks. RecordPrep inserts a blank line between this paragraph and each "
    "adjacent summary-window paragraph. Preserve every material fact, substantive assessment, "
    "and actual procedural development in the eligible portions of the primary pages at a "
    "consistent level of detail. If a window mixes eligible narrative and formal proposed "
    "material, summarize only the eligible narrative. Include several legally significant "
    "verbatim quotes, each an uninterrupted two-to-five-word sequence in quotation marks, "
    "taken only from eligible material. Do not alter quoted text or use ellipses. Do not begin "
    "with prefatory language, add commentary, or use Markdown. Do not summarize the optional "
    "preceding context page again. If, after omitting the formal proposed advisements, findings, "
    "orders, and associated boilerplate, a window contains no eligible report narrative, return "
    "exactly this value and nothing else: " + NO_SUMMARIZABLE_REPORT_CONTENT
)
DEFAULT_SUMMARIZE_REPORTS_PROMPT = PREVIOUS_PROPOSAL_SCOPE_SUMMARIZE_REPORTS_PROMPT.replace(
    "Include several legally significant "
    "verbatim quotes, each an uninterrupted two-to-five-word sequence in quotation marks, "
    "taken only from eligible material. Do not alter quoted text or use ellipses.",
    "Include at least six legally significant verbatim quotes, each an uninterrupted "
    "two-to-five-word sequence in quotation marks, taken only from eligible material, "
    "whenever the eligible primary pages contain at least six suitable quotations. If fewer "
    "than six suitable quotations exist, include every suitable quotation; never invent, "
    "alter, or pad the summary with insignificant or out-of-scope quotations. Distribute the "
    "quotations across the material facts, observations, interviews, and assessments rather "
    "than clustering them around one point, and never sacrifice material factual coverage "
    "merely to reach the quotation target. Do not alter quoted text or use ellipses.",
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
DEFAULT_SUMMARIZE_WINDOW_MAX_PAGES = 6
DEFAULT_SUMMARIZE_WINDOW_TARGET_CHARS = 6000
DEFAULT_SUMMARIZE_WINDOW_MAX_CHARS = 12000
MINUTE_SUMMARY_WINDOW_GUIDANCE = (
    "\n\nThe user message labels any preceding page as optional context only and labels "
    "the pages to summarize as primary source pages. Do not summarize the optional "
    "preceding context page again. Summarize every material detail in the primary pages "
    "and return one concise prose paragraph only."
)
DEFAULT_DISABLE_REASONING = False


def _model_looks_kimi(model_id: str) -> bool:
    normalized = (model_id or "").strip().lower()
    return "kimi" in normalized or "moonshot" in normalized


def _model_looks_deepseek(model_id: str) -> bool:
    normalized = (model_id or "").strip().lower()
    return "deepseek" in normalized


def _apply_disable_reasoning_to_body(
    body: dict[str, Any],
    *,
    model_id: str,
    disable_reasoning: bool,
) -> None:
    if not disable_reasoning:
        return
    if _model_looks_deepseek(model_id):
        body["reasoning_effort"] = "none"
    elif _model_looks_kimi(model_id):
        body["thinking"] = {"type": "disabled"}
    else:
        body["reasoning_effort"] = "none"


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


def _count_text_pages(text_dir: Path) -> int:
    if not text_dir.exists():
        return 0
    try:
        return len(list(text_dir.glob("*.txt")))
    except OSError:
        return 0


def _resolve_rt_ct_split(root_dir: Path, text_dir: Path) -> tuple[int, int, bool, bool, str]:
    """Route downstream RT/CT work exclusively from the validated artifact.

    Raises TranscriptLayoutError when the layout is unresolved or needs
    review; the caller surfaces the message as a clean pipeline pause.
    """
    return resolve_layout_rt_ct_split(root_dir, text_dir)


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


def _correct_toc_lines(
    toc_lines: list[str],
    raise_if_stop: Callable[[], None] | None = None,
) -> tuple[list[str], int]:
    """Return TOC lines with duplicate minute-order dates removed and the removal count.

    Inspects only tab-indented entries inside the ``MINUTE ORDERS`` section,
    retaining the first entry for each exact date. Headings, blank lines, other
    sections, and unrelated formatting are preserved. Idempotent on an already
    corrected TOC because no removable duplicates remain.
    """
    corrected_lines: list[str] = []
    in_minute_orders = False
    seen_dates: set[str] = set()
    removals = 0
    for line in toc_lines:
        if raise_if_stop is not None:
            raise_if_stop()
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
            date_value = (
                entry_text.rsplit(" ", 1)[0].strip()
                if " " in entry_text
                else entry_text
            )
            if not date_value or date_value in seen_dates:
                removals += 1
                continue
            seen_dates.add(date_value)
            corrected_lines.append(line)
            continue
        corrected_lines.append(line)
    return corrected_lines, removals


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


@dataclass
class _SummaryStepContext:
    """Shared resolved inputs for one summary-generation step."""

    root_dir: Path
    artifacts_dir: Path
    text_dir: Path
    citation_by_page: dict[int, str]
    settings: dict[str, Any]
    target_chars: int
    max_pages: int
    request_window: Callable[[str, str], str]
    display_case_name: str
    participant_by_range: dict[tuple[int, int], dict[str, Any]]


def _strip_nonstandard_characters(text: str) -> str:
    cleaned_chars: list[str] = []
    for ch in text:
        if ch in {"\n", "\t"}:
            cleaned_chars.append(ch)
        elif unicodedata.category(ch) != "Cc":
            cleaned_chars.append(ch)
    return "".join(cleaned_chars)






























def _collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).rstrip() + "\n"


def _append_summary_paragraph(lines: list[str], paragraph: str) -> None:
    """Append one normalized paragraph with a deterministic blank-line separator."""
    normalized = " ".join(paragraph.split()).strip()
    if not normalized:
        return
    if lines and lines[-1]:
        lines.append("")
    lines.extend((normalized, ""))








def _cleanup_legacy_generated_artifacts(root: Path) -> list[str]:
    """Remove only obsolete, reproducible artifacts in the selected bundle."""
    candidates = (
        root / "artifacts" / "raw",
        root / "artifacts" / "preoptimized",
        root / "artifacts" / "optimized",
        root / "artifacts" / "chunks",
        root / "artifacts" / "chunk_metadata",
        root / "artifacts" / "raw_hearings.txt",
        root / "artifacts" / "raw_reports.txt",
        root / "artifacts" / "optimized_hearings.txt",
        root / "artifacts" / "optimized_reports.txt",
        root / "rag",
        *sorted((root / "summaries").glob("*_organized.txt")),
    )
    removed: list[str] = []
    for path in candidates:
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed.append(path.relative_to(root).as_posix())
    return removed


# --- Formal proposed findings/orders detection (report summaries only) ---
# These markers are ephemeral and never persisted: they only drive per-window
# scope hints to the summarization model. Detection is deliberately conservative
# and fires only on bounded structural signatures of a formal package of
# proposed/recommended advisements, findings, and orders offered for court
# adoption. A bare "Recommendation" heading, a change-in-recommendation note, a
# substantive treatment/assessment recommendation, a singular request for an
# assessment order, and narrative references to orders the court already made
# are all deliberately out of scope.

REPORT_PROPOSAL_MARKER_TITLE = "proposed_findings_and_orders_title"
REPORT_PROPOSAL_MARKER_LEAD_IN = "proposed_findings_and_orders_lead_in"
REPORT_PROPOSAL_MARKER_SPLIT = "proposed_findings_then_orders_split"
REPORT_PROPOSAL_MARKER_FIND_ORDER = "proposed_find_and_order_template"

REPORT_PROPOSAL_SCOPE_HEADING = "REPORT PROPOSAL EXCLUSION CONTEXT — FOR SCOPE ONLY"
REPORT_PROPOSAL_SCOPE_DELIMITER = (
    "\n\n<<< FORMAL PROPOSED FINDINGS/ORDERS START HERE "
    "— EXCLUDED FROM REPORT SUMMARY >>>\n\n"
)


@dataclass(frozen=True)
class ReportProposalMarker:
    source_page: int
    offset: int
    line_number: int
    kind: str


_RE_PROPOSED_FINDINGS_ORDERS_TITLE = re.compile(
    r"^\s*(?:[#>*-]*\s*|\d+[:.)]\s*)(?:PROPOSED|RECOMMENDED)\s+FINDINGS?\s+"
    r"(?:AND\s+|/)\s*ORDERS?\s*[#>*-]*\s*[.:]?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_RE_PROPOSED_FINDINGS_HEADING = re.compile(
    r"^\s*(?:[#>*-]*\s*|\d+[:.)]\s*)(?:PROPOSED|RECOMMENDED)\s+FINDINGS?\s*[#>*-]*\s*[.:]?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_RE_PROPOSED_ORDERS_HEADING = re.compile(
    r"^\s*(?:[#>*-]*\s*|\d+[:.)]\s*)(?:PROPOSED|RECOMMENDED)\s+ORDERS?\s*[#>*-]*\s*[.:]?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_RE_PROPOSED_LEAD_IN = re.compile(
    r"\b(?:(?:respectfully|humbly)\s+)?recommends?\s+(?:that\s+)?the\s+court\s+"
    r"(?:make|enter|adopt|issue)\s+the\s+following\s+"
    r"(?:proposed\s+|recommended\s+)?findings?\s+and\s+orders?\b",
    re.IGNORECASE,
)
_RE_PROPOSED_FIND_ORDER = re.compile(
    r"\b(?:recommends?|requests?)\b[^.\n]{0,200}?\bthe\s+court\b[^.\n]{0,200}?\bfind\b[^.\n]{0,200}?\band\s+order\b",
    re.IGNORECASE,
)


def _detect_report_proposal_marker(
    page_text: dict[int, str],
    start_page: int,
    end_page: int,
) -> ReportProposalMarker | None:
    """Return the first high-confidence formal proposal marker in a report range.

    Scans the already-loaded page text for one report range and returns the
    earliest structural marker, or ``None`` when no formal package is present.
    Marker text is never returned or emitted; only the page, offset, line
    number, and a non-sensitive kind are carried through.
    """
    best: ReportProposalMarker | None = None

    def _consider(page: int, offset: int, kind: str) -> None:
        nonlocal best
        if best is None or (page, offset) < (best.source_page, best.offset):
            line_number = page_text[page].count("\n", 0, offset) + 1
            best = ReportProposalMarker(page, offset, line_number, kind)

    # Split template: a formal proposed-findings heading followed later in the
    # same report by a formal proposed-orders heading.
    findings_at: tuple[int, int] | None = None
    for page in range(start_page, end_page + 1):
        text = page_text.get(page) or ""
        match = _RE_PROPOSED_FINDINGS_HEADING.search(text)
        if match:
            findings_at = (page, match.start())
            break
    if findings_at is not None:
        findings_page, findings_offset = findings_at
        for page in range(findings_page, end_page + 1):
            text = page_text.get(page) or ""
            search_from = findings_offset if page == findings_page else 0
            match = _RE_PROPOSED_ORDERS_HEADING.search(text, search_from)
            if match:
                orders_at = (page, match.start())
                if orders_at > findings_at:
                    _consider(
                        findings_at[0],
                        findings_at[1],
                        REPORT_PROPOSAL_MARKER_SPLIT,
                    )
                break

    # Single-page structural markers, earliest offset within each page wins.
    for page in range(start_page, end_page + 1):
        text = page_text.get(page)
        if not text:
            continue
        for kind, pattern in (
            (REPORT_PROPOSAL_MARKER_TITLE, _RE_PROPOSED_FINDINGS_ORDERS_TITLE),
            (REPORT_PROPOSAL_MARKER_LEAD_IN, _RE_PROPOSED_LEAD_IN),
            (REPORT_PROPOSAL_MARKER_FIND_ORDER, _RE_PROPOSED_FIND_ORDER),
        ):
            match = pattern.search(text)
            if match:
                _consider(page, match.start(), kind)

    return best


def _report_proposal_scope_note(
    window: dict[str, Any],
    report_marker: ReportProposalMarker | None,
) -> str:
    """Return the scope-only instruction for a window relative to the marker."""
    if report_marker is None:
        return ""
    primary_pages = window.get("primary_pages") or []
    if not primary_pages:
        return ""
    marker_page = report_marker.source_page
    if marker_page in primary_pages:
        return (
            "A scope delimiter in the source text below marks where a formal package "
            "of proposed or recommended advisements, findings, and orders, with "
            "associated boilerplate, begins. Omit that formal package from your summary; "
            "summarize only the eligible report narrative that precedes the delimiter."
        )
    if primary_pages[0] > marker_page:
        return (
            "A formal package of proposed or recommended findings and orders began on an "
            "earlier page and may still be continuing. Summarize only clearly separate "
            "factual narrative or clearly separate attachments; omit any continuing "
            "proposed findings or orders."
        )
    return ""


def _insert_report_proposal_delimiter(text: str, offset: int) -> str:
    bounded = max(0, min(offset, len(text)))
    return f"{text[:bounded]}{REPORT_PROPOSAL_SCOPE_DELIMITER}{text[bounded:]}"


def _summary_page_windows(
    text_dir: Path,
    start_page: int,
    end_page: int,
    *,
    max_pages: int = DEFAULT_SUMMARIZE_WINDOW_MAX_PAGES,
    target_chars: int = DEFAULT_SUMMARIZE_WINDOW_TARGET_CHARS,
    max_chars: int = DEFAULT_SUMMARIZE_WINDOW_MAX_CHARS,
    preferred_breaks: set[int] | None = None,
) -> list[dict[str, Any]]:
    """Create adaptive, page-aligned, exactly-once primary-page windows."""
    if start_page <= 0 or end_page < start_page:
        raise ValueError("Invalid summary source page range.")
    page_text: dict[int, str] = {}
    for number in range(start_page, end_page + 1):
        path = text_dir / f"{number:04d}.txt"
        if not path.is_file():
            raise FileNotFoundError(f"Missing text file {path.name}.")
        page_text[number] = path.read_text(encoding="utf-8", errors="ignore")
    breaks = sorted(
        value
        for value in (preferred_breaks or set())
        if start_page < value <= end_page
    )
    page_limit = max(1, max_pages)
    character_limit = max(1, max_chars)
    character_target = min(max(1, target_chars), character_limit)
    windows: list[dict[str, Any]] = []
    current = start_page
    while current <= end_page:
        candidate_end = min(end_page, current + page_limit - 1)
        chars = 0
        primary_end = current - 1
        for number in range(current, candidate_end + 1):
            page_chars = len(page_text[number])
            combined = chars + page_chars
            if primary_end >= current:
                if combined > character_limit:
                    break
                if combined > character_target:
                    under_distance = character_target - chars
                    over_distance = combined - character_target
                    if over_distance > under_distance:
                        break
            chars = combined
            primary_end = number
        if primary_end < current:
            primary_end = current
        examination_breaks = [
            value for value in breaks if current < value <= primary_end
        ]
        if examination_breaks:
            primary_end = examination_breaks[0] - 1
        windows.append(
            {
                "primary_start": current,
                "primary_end": primary_end,
                "primary_pages": list(range(current, primary_end + 1)),
                "context_page": current - 1 if current > start_page else None,
                "page_text": page_text,
            }
        )
        current = primary_end + 1
    return windows


def _summary_window_limits(settings: dict[str, Any]) -> tuple[int, int]:
    target_chars = DEFAULT_SUMMARIZE_WINDOW_TARGET_CHARS
    max_pages = DEFAULT_SUMMARIZE_WINDOW_MAX_PAGES
    try:
        target_chars = max(1, int(settings.get("target_chars") or target_chars))
    except (TypeError, ValueError):
        pass
    try:
        max_pages = max(1, int(settings.get("max_pages") or max_pages))
    except (TypeError, ValueError):
        pass
    return target_chars, max_pages


def _participant_role_label(role_id: str) -> str:
    labels = {
        "mothers_counsel": "Mother’s counsel",
        "fathers_counsel": "Father’s counsel",
        "alleged_fathers_counsel": "Alleged father’s counsel",
        "presumed_fathers_counsel": "Presumed father’s counsel",
        "parents_counsel": "Parent’s counsel",
        "minors_counsel": "Minor’s counsel",
        "county_counsel": "County counsel",
        "tribes_counsel": "Tribe’s counsel",
        "guardian_ad_litem": "Guardian ad litem",
        "other_counsel": "Other counsel",
        "unresolved_counsel": "Unresolved counsel",
    }
    return labels.get(role_id, role_id.replace("_", " ").title())


def _hearing_context_lines(hearing: dict[str, Any]) -> tuple[str, str]:
    counsel_parts: list[str] = []
    for counsel in hearing.get("counsel", []):
        if not isinstance(counsel, dict):
            continue
        role_id = str(counsel.get("role_id") or "")
        role = _participant_role_label(role_id) if role_id else str(counsel.get("role_label") or "").strip()
        name = str(counsel.get("name") or "").strip() or "not identified"
        metadata: list[str] = []
        organization = str(counsel.get("organization") or "").strip()
        aliases = [str(value).strip() for value in counsel.get("aliases", []) if str(value).strip()]
        appearance = str(counsel.get("appearance_status") or "").strip().replace("_", " ")
        if organization:
            metadata.append(f"organization: {organization}")
        if aliases:
            metadata.append(f"personal aliases: {', '.join(aliases)}")
        if appearance:
            metadata.append(f"appearance: {appearance}")
        suffix = f" ({'; '.join(metadata)})" if metadata else ""
        counsel_parts.append(f"{role} — {name}{suffix}")
    counsel_line = "Counsel: " + ("; ".join(counsel_parts) if counsel_parts else "Not reliably identified.") + "."
    status = str(hearing.get("witness_status") or "unknown")
    witnesses = [item for item in hearing.get("witnesses", []) if isinstance(item, dict)]
    if status == "none":
        testimony_line = "Testimony: None."
    elif status == "unknown":
        testimony_line = "Testimony: Not reliably identified from the available witness index or sworn-examination evidence."
    elif status == "conflict":
        names = ", ".join(str(item.get("name") or "unnamed witness") for item in witnesses)
        testimony_line = f"Testimony: Conflicting attribution evidence; supported witness entries: {names or 'none'}; review warnings."
    else:
        parts: list[str] = []
        for witness in witnesses:
            name = str(witness.get("name") or "unnamed witness")
            description = str(witness.get("description") or "").strip()
            exams: list[str] = []
            start_labels: list[str] = []
            end_labels: list[str] = []
            for exam in witness.get("examinations", []):
                if not isinstance(exam, dict):
                    continue
                exam_type = str(exam.get("type") or "examination").replace("_", " ")
                examiner_role = _participant_role_label(str(exam.get("examiner_role_id") or ""))
                exams.append(f"{exam_type} by {examiner_role}" if examiner_role else exam_type)
                if exam.get("start_citation_label"):
                    start_labels.append(str(exam["start_citation_label"]))
                if exam.get("end_citation_label"):
                    end_labels.append(str(exam["end_citation_label"]))
            citation = ""
            if start_labels:
                citation_end = end_labels[-1] if end_labels else start_labels[-1]
                citation = start_labels[0] if citation_end == start_labels[0] else f"{start_labels[0]}–{citation_end}"
            detail = f" ({description})" if description else ""
            suffix = "; ".join(exams)
            if citation:
                suffix = f"{suffix}; {citation}" if suffix else citation
            parts.append(f"{name}{detail}" + (f" ({suffix})" if suffix else ""))
        testimony_line = "Testimony: " + ("; ".join(parts) if parts else "Verified witness evidence was recorded without a resolved name") + "."
    return counsel_line, testimony_line


def _hearing_participant_context(hearing: dict[str, Any]) -> str:
    """Render participant-index guidance; this text is never added to the summary."""
    counsel_line, testimony_line = _hearing_context_lines(hearing)
    participant_parts: list[str] = []
    for participant in hearing.get("participants", []):
        if not isinstance(participant, dict):
            continue
        role = str(participant.get("role_label") or "").strip()
        name = str(participant.get("name") or "").strip()
        identity = f"{role} — {name}" if role and name else role or name or "Unresolved participant"
        attendance = str(participant.get("attendance_status") or "unknown").replace("_", " ")
        speaking = str(participant.get("speaking_status") or "unknown").replace("_", " ")
        sworn = str(participant.get("sworn_status") or "unknown").replace("_", " ")
        participant_parts.append(
            f"{identity} (attendance: {attendance}; speaking: {speaking}; sworn: {sworn})"
        )
    participants_line = "Participants: " + (
        "; ".join(participant_parts) if participant_parts else "No additional participant metadata recorded."
    )
    return "\n".join((counsel_line, participants_line, testimony_line))


def _render_summary_window_payload(
    window: dict[str, Any],
    citation_by_page: dict[int, str],
    *,
    participant_context: str = "",
    report_marker: ReportProposalMarker | None = None,
) -> str:
    page_text = window["page_text"]
    sections: list[str] = []
    if participant_context:
        sections.extend([
            "PARTICIPANT INDEX CONTEXT — FOR ATTRIBUTION ONLY",
            participant_context,
            "",
        ])
    context_page = window.get("context_page")
    if isinstance(context_page, int):
        citation = citation_by_page.get(context_page, "")
        sections.extend([
            f"OPTIONAL PRECEDING CONTEXT PAGE — DO NOT SUMMARIZE "
            f"[{citation or f'file page {context_page}'}]",
            page_text[context_page].strip(),
            "",
        ])
    scope_note = _report_proposal_scope_note(window, report_marker)
    if scope_note:
        sections.extend([
            REPORT_PROPOSAL_SCOPE_HEADING,
            scope_note,
            "",
        ])
    sections.append("PRIMARY SOURCE PAGES — SUMMARIZE ALL MATERIAL DETAILS")
    for number in window["primary_pages"]:
        citation = citation_by_page.get(number, "")
        sections.append(f"[{citation or f'file page {number}'} | source text_pages/{number:04d}.txt]")
        text = page_text[number]
        if report_marker is not None and number == report_marker.source_page:
            text = _insert_report_proposal_delimiter(text, report_marker.offset)
        sections.append(text.strip())
    return "\n".join(sections).strip()


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


def _format_report_label(report_name: str, report_date: str) -> str:
    normalized_name = re.sub(r"\s+", " ", report_name.strip())
    normalized_date = _format_long_us_date(report_date) or _normalize_hearing_date(report_date)
    if normalized_date and normalized_name:
        return f"{normalized_date} - {normalized_name}"
    return normalized_name or normalized_date or "Report"


def _report_id_from_start_page(start_page: str) -> str:
    page_number = _page_number_from_label(start_page)
    if page_number is not None:
        return f"report:{page_number:04d}"
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", start_page.strip()).strip("_")
    return f"report:{normalized}" if normalized else ""


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


def _strip_page_markdown_links(text: str) -> str:
    return re.sub(r"\s*\[[^\]]+\]\(page:\d{4}\)", "", text).strip()


def _strip_minute_order_body_links(body_lines: list[str]) -> list[str]:
    cleaned_lines: list[str] = []
    for line in body_lines:
        cleaned = re.sub(r"^\s*\[(?:MO|M>)\]\(page:\d{4}\)\s*", "", line).strip()
        cleaned = re.sub(r"\s*\[:M\]\(page:\d{4}\)\s*$", "", cleaned).strip()
        if not cleaned:
            cleaned_lines.append(line)
        else:
            cleaned_lines.append(cleaned)
    return cleaned_lines


def _split_summary_sections(
    lines: list[str],
    heading_key_for_line: Callable[[str], str | None],
) -> tuple[list[str], list[dict[str, Any]]]:
    preamble_lines: list[str] = []
    sections: list[dict[str, Any]] = []
    current_section: dict[str, Any] | None = None

    for line in lines:
        key = heading_key_for_line(line)
        if key:
            current_section = {
                "key": key,
                "heading": _strip_page_markdown_links(line.strip()) or line.strip(),
                "body_lines": [],
            }
            sections.append(current_section)
            continue
        if current_section is None:
            preamble_lines.append(line)
        else:
            current_section["body_lines"].append(line)

    return preamble_lines, sections


def _render_summary_sections(
    preamble_lines: list[str],
    sections: list[dict[str, Any]],
) -> str:
    rendered: list[str] = list(preamble_lines)
    for section in sections:
        heading = str(section.get("heading", "")).strip()
        if not heading:
            continue
        if rendered and rendered[-1].strip():
            rendered.append("")
        rendered.append(heading)
        body_lines = list(section.get("body_lines", []))
        if body_lines:
            if body_lines[0].strip():
                rendered.append("")
            rendered.extend(body_lines)
    return _collapse_blank_lines("\n".join(rendered))


def _add_page_links_to_hearing_summary_text(
    hearing_summary_text: str,
    hearing_entries: list[dict[str, Any]],
    minute_entries: list[dict[str, Any]],
) -> tuple[str, int, int]:
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

    def _heading_date_key(line: str) -> str | None:
        stripped = line.strip()
        if not stripped:
            return None
        without_links = _strip_page_markdown_links(stripped)
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

    for line in hearing_summary_text.splitlines():
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
            linked_lines.extend(_strip_minute_order_body_links(body_lines))

    if modified == 0 and inserted == 0:
        raise ValueError("No hearing/minute date headings matched boundary dates.")

    return _collapse_blank_lines("\n".join(linked_lines)), modified, inserted


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


def _format_create_files_error(exc: Exception) -> str:
    if isinstance(exc, DependencyError) and "AES algorithm" in str(exc):
        return (
            "Create files failed: an input PDF uses AES encryption, "
            "and the current Python environment is missing the "
            "`cryptography` package required by pypdf."
        )
    return f"Create files failed: {exc}"


PI_STAGE_STATUS_RELATIVE = Path("temp") / ".pi_stage_status.json"
PI_STAGE_STATUS_ARTIFACT = "recordprep-pi-stage-status"
PI_STAGE_STATUS_POLL_SECONDS = 2.0
PARTICIPANT_PROGRESS_POLL_SECONDS = 5.0
_CASE_NUMBER_PATTERN = re.compile(r"B\d{5,6}")


def _read_pi_stage_status(
    root_dir: Path | None,
    runner_pid: int | None,
) -> dict[str, Any] | None:
    """Read the runner's stage-status file, ignoring stale/foreign writes."""
    if root_dir is None or runner_pid is None:
        return None
    path = root_dir / PI_STAGE_STATUS_RELATIVE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("artifact") != PI_STAGE_STATUS_ARTIFACT:
        return None
    try:
        if int(payload.get("runner_pid") or 0) != runner_pid:
            return None
    except (TypeError, ValueError):
        return None
    return payload


def _participant_review_progress(root_dir: Path | None) -> tuple[int, int] | None:
    """Count hearings reviewed so far (no template placeholder) over total."""
    if root_dir is None:
        return None
    path = root_dir / "artifacts" / "participant_index.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    hearings = payload.get("hearings")
    if not isinstance(hearings, list) or not hearings:
        return None
    total = len(hearings)
    reviewed = 0
    for hearing in hearings:
        if not isinstance(hearing, dict):
            continue
        warnings = hearing.get("warnings")
        reviewed += 1
        if isinstance(warnings, list) and any(
            isinstance(item, str) and item == PARTICIPANT_TEMPLATE_WARNING
            for item in warnings
        ):
            reviewed -= 1
    return reviewed, total


def case_identity_conflicts(root_dir: Path) -> list[str]:
    """Warn when folder naming conflicts with the bundle's record identity.

    The folder chain (up to three levels) is compared against the manifest's
    input PDF filenames and case_name.txt. RecordPrep never moves or renames
    private case data; this exists to surface mismatched selections.
    """
    root_dir = Path(root_dir)
    folder_tokens: set[str] = set()
    for candidate in (
        root_dir.parent,
        root_dir.parent.parent,
        root_dir.parent.parent.parent,
    ):
        folder_tokens.update(_CASE_NUMBER_PATTERN.findall(candidate.name or ""))
    record_tokens: set[str] = set()
    try:
        for pdf_path in _manifest_input_pdf_paths(root_dir):
            record_tokens.update(_CASE_NUMBER_PATTERN.findall(pdf_path.stem or ""))
    except Exception:
        pass
    try:
        case_name = (root_dir / "case_name.txt").read_text(
            encoding="utf-8", errors="ignore"
        )
    except OSError:
        case_name = ""
    if case_name.strip():
        record_tokens.update(_CASE_NUMBER_PATTERN.findall(case_name))
    conflicts: list[str] = []
    if folder_tokens and record_tokens and folder_tokens.isdisjoint(record_tokens):
        folder_label = ", ".join(sorted(folder_tokens))
        record_label = ", ".join(sorted(record_tokens))
        name_suffix = f" ({case_name.strip()})" if case_name.strip() else ""
        conflicts.append(
            f"The case folder suggests {folder_label} but this bundle's record "
            f"is {record_label}{name_suffix}. Continuing with the selected "
            "bundle; no files will be moved or renamed."
        )
    return conflicts


def _ensure_case_bundle_dirs(base_dir: Path) -> tuple[Path, Path, Path]:
    root = base_dir / "case_bundle"
    text_dir = root / "text_pages"
    image_pages_dir = root / "image_pages"
    text_dir.mkdir(parents=True, exist_ok=True)
    image_pages_dir.mkdir(parents=True, exist_ok=True)
    return root, text_dir, image_pages_dir


def _normalized_pdf_paths(paths: Sequence[Path]) -> tuple[Path, ...]:
    return tuple(path.expanduser().resolve(strict=False) for path in paths)


def _pdf_selections_equal(first: Sequence[Path], second: Sequence[Path]) -> bool:
    return _normalized_pdf_paths(first) == _normalized_pdf_paths(second)


def _case_bundle_root_for_pdfs(paths: Sequence[Path]) -> Path | None:
    parents = {path.expanduser().resolve(strict=False).parent for path in paths}
    if len(parents) != 1:
        return None
    return parents.pop() / "case_bundle"


def _case_context_matches_selection(
    case_name: str,
    root_dir: Path | None,
    selected_pdfs: Sequence[Path],
) -> bool:
    """True when persisted case context belongs to the current selection.

    With no PDF selection (an explicit case-bundle choice), the saved
    context is authoritative. With a selection, it is current only when the
    prospective bundle exists and its manifest records exactly those PDFs;
    a fresh selection awaiting Create files never inherits the prior name.
    """
    if not case_name or root_dir is None:
        return False
    if not selected_pdfs:
        return True
    prospective = _case_bundle_root_for_pdfs(selected_pdfs)
    if prospective is None or prospective != root_dir.expanduser().resolve(strict=False):
        return False
    manifest_pdfs = _manifest_input_pdf_paths(root_dir)
    return bool(manifest_pdfs) and _pdf_selections_equal(manifest_pdfs, selected_pdfs)


def _reset_generated_case_bundle(root_dir: Path) -> None:
    for name in GENERATED_CASE_BUNDLE_DIRS:
        path = root_dir / name
        if path.exists():
            shutil.rmtree(path)
    for name in GENERATED_CASE_BUNDLE_FILES:
        path = root_dir / name
        if path.exists():
            path.unlink()


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
    recent_output: Callable[[], str] | None = None,
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
            if recent_output is not None:
                output = recent_output()
            elif process.stdout is not None:
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


def _update_rt_ct_split_manifest(
    root_dir: Path,
    split_page: int | None,
    split_mode: str | None,
) -> bool:
    manifest_path = _manifest_path(root_dir)
    if not manifest_path.exists():
        return False
    manifest = _read_manifest(root_dir)
    if not manifest:
        return False
    manifest["rt_ct_split_page"] = _normalize_rt_ct_split_page(split_page)
    manifest["rt_ct_split_mode"] = _normalize_rt_ct_split_mode(split_mode)
    manifest["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return True


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
    input_pdfs = [_relpath(path) for path in selected_pdfs]
    if not input_pdfs and isinstance(existing.get("input_pdfs"), list):
        input_pdfs = list(existing["input_pdfs"])
    files_payload = (
        dict(existing.get("files"))
        if isinstance(existing.get("files"), dict)
        else {}
    )
    for obsolete_key in (
        "raw_hearings", "raw_reports", "preoptimized_hearings", "preoptimized_reports",
        "optimized_hearings", "optimized_reports", "optimized_hearing_sections",
        "optimized_report_sections", "chunk_metadata", "organized_hearings",
        "organized_reports", "vector_database",
    ):
        files_payload.pop(obsolete_key, None)
    files_payload.update(
        {
            "merged_pdf": _relpath(temp_dir / "merged.pdf"),
            "toc": _relpath(artifacts_dir / "toc.txt"),
            "hearing_boundaries": _relpath(
                artifacts_dir / "hearing_boundaries.json"
            ),
            "report_boundaries": _relpath(
                artifacts_dir / "report_boundaries.json"
            ),
            "minutes_boundaries": _relpath(
                artifacts_dir / "minutes_boundaries.json"
            ),
            "transcript_page_numbers": _relpath(artifacts_dir / "transcript_page_numbers.json"),
            "transcript_page_number_series": _relpath(artifacts_dir / "transcript_page_number_series.md"),
            "participant_index": _relpath(artifacts_dir / "participant_index.json"),
            "source_map": _relpath(artifacts_dir / "source_map.json"),
            "summarized_hearings": _relpath(summarized_hearings_path),
            "summarized_reports": _relpath(summarized_reports_path),
            "summarized_minutes": _relpath(summarized_minutes_path),
        }
    )

    payload: dict[str, Any] = {
        "schema_version": 2,
        "input_identity_version": INPUT_IDENTITY_VERSION,
        "created_at": created_at,
        "updated_at": now,
        "root_dir": ".",
        "rt_ct_split_page": split_page_value,
        "rt_ct_split_mode": split_mode_value,
        "input_pdfs": input_pdfs,
        "dirs": {
            "text_pages": _relpath(text_dir),
            "image_pages": _relpath(image_pages_dir),
            "classification": _relpath(classification_dir),
            "artifacts": _relpath(artifacts_dir),
            "summaries": _relpath(summaries_dir),
            "temp": _relpath(temp_dir),
        },
        "files": files_payload,
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
        "pipeline": pipeline,
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _manifest_input_pdf_paths(root_dir: Path) -> list[Path]:
    manifest = _read_manifest(root_dir)
    raw_paths = manifest.get("input_pdfs")
    if not isinstance(raw_paths, list):
        return []
    result: list[Path] = []
    for value in raw_paths:
        if not isinstance(value, str):
            continue
        resolved = (root_dir / value).resolve(strict=False)
        result.append(resolved)
    return result


def _bundle_inputs_changed(root_dir: Path, selected_pdfs: Sequence[Path]) -> bool:
    manifest_pdfs = _manifest_input_pdf_paths(root_dir)
    if not manifest_pdfs:
        return False
    if not _pdf_selections_equal(manifest_pdfs, selected_pdfs):
        return True
    manifest = _read_manifest(root_dir)
    return manifest.get("input_identity_version") != INPUT_IDENTITY_VERSION


OBSOLETE_PIPELINE_CONFIG_KEYS = {
    "optimize_hearing_api_url", "optimize_hearing_model_id", "optimize_hearing_api_key",
    "optimize_hearing_disable_reasoning", "optimize_report_api_url", "optimize_report_model_id",
    "optimize_report_api_key", "optimize_report_disable_reasoning", "optimize_attorney_api_url",
    "optimize_attorney_model_id", "optimize_attorney_api_key", "optimize_attorney_disable_reasoning",
    "optimize_chunk_size", "optimize_max_tokens", "optimize_attorneys_prompt",
    "optimize_hearings_prompt", "optimize_reports_prompt", "summarize_chunk_size",
    "summarize_window_pages", "overview_api_url", "overview_model_id", "overview_api_key",
    "overview_disable_reasoning", "overview_prompt",
    "rag_provider", "rag_voyage_api_key", "rag_voyage_model", "rag_isaacus_api_key",
    "rag_isaacus_model",
    "rt_ct_split_page",
}


def _read_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        raw = CONFIG_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            cleaned = {
                key: value for key, value in data.items()
                if key not in OBSOLETE_PIPELINE_CONFIG_KEYS
            }
            if cleaned != data:
                CONFIG_FILE.write_text(json.dumps(cleaned, indent=2), encoding="utf-8")
            return cleaned
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _write_config(config: dict[str, Any]) -> None:
    serializable: dict[str, Any] = {}
    for key, value in config.items():
        if not isinstance(key, str) or key in OBSOLETE_PIPELINE_CONFIG_KEYS:
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


def _read_config_int(
    config: dict[str, Any],
    key: str,
    default: int,
    *,
    minimum: int = 1,
) -> int:
    value = config.get(key, default)
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return max(minimum, parsed)


def load_run_until_step_setting() -> str | None:
    config = _read_config()
    value = config.get(CONFIG_KEY_RUN_UNTIL_STEP)
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    migrated = {
        "create_raw": "create_minute_order_summaries",
        "create_preoptimized": "create_minute_order_summaries",
        "create_optimized": "create_minute_order_summaries",
        "create_summaries": "create_minute_order_summaries",
        "case_overview": "create_case_overview",
        "create_rag_index": "build_source_map",
    }.get(normalized, normalized)
    if migrated != normalized:
        config[CONFIG_KEY_RUN_UNTIL_STEP] = migrated
        _write_config(config)
    return migrated or None


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
    workers = _read_config_int(
        config,
        CONFIG_KEY_CLASSIFIER_WORKERS,
        DEFAULT_CLASSIFIER_WORKERS,
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
        "workers": workers,
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
    workers: str | int,
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
    config[CONFIG_KEY_CLASSIFIER_WORKERS] = _read_config_int(
        {CONFIG_KEY_CLASSIFIER_WORKERS: workers},
        CONFIG_KEY_CLASSIFIER_WORKERS,
        DEFAULT_CLASSIFIER_WORKERS,
    )
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
        "workers": int(shared.get("workers", DEFAULT_CLASSIFIER_WORKERS) or DEFAULT_CLASSIFIER_WORKERS),
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
        "workers": int(shared.get("workers", DEFAULT_CLASSIFIER_WORKERS) or DEFAULT_CLASSIFIER_WORKERS),
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
        "workers": int(shared.get("workers", DEFAULT_CLASSIFIER_WORKERS) or DEFAULT_CLASSIFIER_WORKERS),
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

def load_local_ocr_settings() -> dict[str, Any]:
    config = _read_config()
    server_url = str(
        config.get(CONFIG_KEY_LOCAL_OCR_SERVER_URL, DEFAULT_SERVER_URL) or ""
    ).strip()
    model_id = str(config.get(CONFIG_KEY_LOCAL_OCR_MODEL_ID, MODEL_ID) or "").strip()
    start_command = str(
        config.get(CONFIG_KEY_LOCAL_OCR_START_COMMAND, START_SERVER_COMMAND) or ""
    ).strip()
    workers = _read_config_int(
        config,
        CONFIG_KEY_LOCAL_OCR_WORKERS,
        DEFAULT_LOCAL_OCR_WORKERS,
    )
    slots = _read_config_int(
        config,
        CONFIG_KEY_LOCAL_OCR_SLOTS,
        DEFAULT_LOCAL_OCR_SLOTS,
    )
    return {
        "server_url": server_url or DEFAULT_SERVER_URL,
        "model_id": model_id or MODEL_ID,
        "start_command": start_command or START_SERVER_COMMAND,
        "workers": workers,
        "slots": slots,
    }


def save_local_ocr_settings(
    server_url: str,
    model_id: str,
    start_command: str,
    workers: str | int,
    slots: str | int,
) -> None:
    config = _read_config()
    config[CONFIG_KEY_LOCAL_OCR_SERVER_URL] = server_url or DEFAULT_SERVER_URL
    config[CONFIG_KEY_LOCAL_OCR_MODEL_ID] = model_id or MODEL_ID
    config[CONFIG_KEY_LOCAL_OCR_START_COMMAND] = start_command or START_SERVER_COMMAND
    config[CONFIG_KEY_LOCAL_OCR_WORKERS] = _read_config_int(
        {CONFIG_KEY_LOCAL_OCR_WORKERS: workers},
        CONFIG_KEY_LOCAL_OCR_WORKERS,
        DEFAULT_LOCAL_OCR_WORKERS,
    )
    config[CONFIG_KEY_LOCAL_OCR_SLOTS] = _read_config_int(
        {CONFIG_KEY_LOCAL_OCR_SLOTS: slots},
        CONFIG_KEY_LOCAL_OCR_SLOTS,
        DEFAULT_LOCAL_OCR_SLOTS,
    )
    _write_config(config)

def _generate_text_files(pdf_path: Path, text_dir: Path) -> None:
    with pdf_path.open("rb") as handle:
        pdf = pdftotext.PDF(handle, physical=True)
    for index, page_text in enumerate(pdf, start=1):
        target = text_dir / f"{index:04d}.txt"
        if target.exists():
            continue
        target.write_text(page_text, encoding="utf-8")


def _count_pdf_pages(pdf_path: Path) -> int:
    doc = fitz.open(str(pdf_path))
    try:
        return len(doc)
    finally:
        doc.close()


def _expected_page_numbers_from_pdfs(pdf_paths: Sequence[Path]) -> set[str]:
    total_pages = 0
    for pdf_path in pdf_paths:
        total_pages += _count_pdf_pages(pdf_path)
    return {f"{index:04d}" for index in range(1, total_pages + 1)}


def _existing_numbered_stems(path: Path, pattern: str) -> set[str]:
    try:
        return {
            item.stem
            for item in path.glob(pattern)
            if item.is_file() and item.stem.isdigit()
        }
    except OSError:
        return set()


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
            target = image_pages_dir / f"{index + 1:04d}.png"
            if target.exists():
                continue
            pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY)
            pix.save(str(target))
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




def _strip_markdown(content: str) -> str:
    content = re.sub(r"(?m)^[ \t]*!\[[^]]*]\([^)\s]+\)[ \t]*\n?", "", content)
    return content


def _format_elapsed(seconds: float) -> str:
    seconds = max(0.0, seconds)
    minutes, remaining_seconds = divmod(seconds, 60)
    hours, remaining_minutes = divmod(int(minutes), 60)
    if hours:
        return f"{hours}h {remaining_minutes}m {remaining_seconds:.1f}s"
    if remaining_minutes:
        return f"{remaining_minutes}m {remaining_seconds:.1f}s"
    return f"{remaining_seconds:.1f}s"


def _resolve_local_ocr_start_command(start_command: str, slots: int) -> str:
    slots = max(1, int(slots))
    command = (start_command or START_SERVER_COMMAND).strip()
    if "{slots}" in command:
        return command.replace("{slots}", str(slots))

    parallel_pattern = re.compile(r"(?P<prefix>--parallel(?:=|\s+))\d+")
    if parallel_pattern.search(command):
        return parallel_pattern.sub(rf"\g<prefix>{slots}", command, count=1)

    np_pattern = re.compile(r"(?P<prefix>-np(?:=|\s+))\d+")
    if np_pattern.search(command):
        return np_pattern.sub(rf"\g<prefix>{slots}", command, count=1)

    if "llama-server" not in command:
        return command

    parallel_args = f"--parallel {slots}"

    lines = command.splitlines()
    for index, line in enumerate(lines):
        if "llama-server" not in line:
            continue
        indent = re.match(r"\s*", line).group(0)
        if line.rstrip().endswith("\\"):
            lines.insert(index + 1, f"{indent}{parallel_args} \\")
        else:
            lines[index] = f"{line} {parallel_args}"
        return "\n".join(lines)
    return command


def _server_slots_url(server_url: str) -> str:
    parsed = urllib.parse.urlsplit(server_url)
    path = parsed.path
    for suffix in ("/v1/chat/completions", "/chat/completions"):
        if path.endswith(suffix):
            path = f"{path[:-len(suffix)]}/slots"
            break
    else:
        path = "/slots"
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _get_server_slot_count(server_url: str) -> int | None:
    response = requests.get(_server_slots_url(server_url), timeout=5)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        if isinstance(data.get("total_slots"), int):
            return data["total_slots"]
        slots = data.get("slots")
        if isinstance(slots, list):
            return len(slots)
    return None


def _print_server_slot_report(server_url: str, expected_slots: int) -> None:
    try:
        slot_count = _get_server_slot_count(server_url)
    except requests.RequestException as exc:
        print(f"Could not read llama.cpp /slots endpoint: {exc}", file=sys.stderr)
        return

    if slot_count is None:
        print("Could not determine llama.cpp slot count from /slots.", file=sys.stderr)
        return

    print(f"llama.cpp server reports {slot_count} slot(s).")
    if slot_count < expected_slots:
        print(
            f"Warning: local OCR slots is {expected_slots}, but server has only "
            f"{slot_count} slot(s).",
            file=sys.stderr,
        )


def _start_server(command: str) -> subprocess.Popen[str]:
    command = command.strip()
    if not command:
        raise RuntimeError("Start server command is empty.")
    return subprocess.Popen(
        ["bash", "-lc", command],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def _start_server_output_reader(
    process: subprocess.Popen[str],
) -> Callable[[], str]:
    recent_output: deque[str] = deque(maxlen=40)
    partial_output = ""
    output_lock = threading.Lock()

    def read_server_output() -> None:
        nonlocal partial_output
        if process.stdout is None:
            return
        try:
            while chunk := os.read(process.stdout.fileno(), 4096):
                text = chunk.decode(errors="replace")
                with output_lock:
                    lines = (partial_output + text).splitlines(keepends=True)
                    partial_output = ""
                    for line in lines:
                        if line.endswith(("\r", "\n")):
                            recent_output.append(line.rstrip("\r\n"))
                        else:
                            partial_output = line[-8192:]
        except (OSError, TypeError, ValueError):
            pass

    def recent_output_text() -> str:
        with output_lock:
            output = list(recent_output)
            if partial_output:
                output.append(partial_output)
            return "\n".join(output)

    threading.Thread(
        target=read_server_output,
        name="recordprep-local-ocr-server-log-reader",
        daemon=True,
    ).start()
    return recent_output_text


def _stop_server(process: subprocess.Popen[str]) -> None:
    process_group_id = process.pid
    try:
        os.killpg(process_group_id, signal.SIGTERM)
    except ProcessLookupError:
        if process.poll() is None:
            process.terminate()

    deadline = time.monotonic() + 10
    if process.poll() is None:
        try:
            process.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass

    while time.monotonic() < deadline:
        try:
            os.killpg(process_group_id, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        try:
            os.killpg(process_group_id, signal.SIGKILL)
        except ProcessLookupError:
            pass

    if process.poll() is None:
        process.kill()
        process.wait(timeout=10)
    if process.stdout is not None:
        process.stdout.close()


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


def _ocr_images(
    image_paths: list[Path],
    *,
    server_url: str,
    model_id: str,
    text_dir: Path,
    workers: int,
    stop_check: Callable[[], None] | None = None,
) -> None:
    if not image_paths:
        return
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        future_to_image_path = {
            executor.submit(_ocr_image, image_path, server_url, model_id): image_path
            for image_path in image_paths
        }
        for future in concurrent.futures.as_completed(future_to_image_path):
            if stop_check:
                stop_check()
            image_path = future_to_image_path[future]
            text = future.result()
            target = text_dir / f"{image_path.stem}.txt"
            target.write_text(text, encoding="utf-8")
            print(f"OCR {image_path.name} -> {target.name}")


def _generate_text_files_with_local_ocr(
    pdf_path: Path,
    text_dir: Path,
    image_pages_dir: Path,
    stop_check: Callable[[], None] | None = None,
    server_process_changed: (
        Callable[[subprocess.Popen[str] | None], None] | None
    ) = None,
    server_url: str = DEFAULT_SERVER_URL,
    start_command: str = START_SERVER_COMMAND,
    model_id: str = MODEL_ID,
    workers: int = DEFAULT_LOCAL_OCR_WORKERS,
    slots: int = DEFAULT_LOCAL_OCR_SLOTS,
    sleep_seconds: float = LOCAL_OCR_SERVER_STARTUP_SECONDS,
) -> None:
    workers = max(1, int(workers))
    slots = max(1, int(slots))
    if workers > slots:
        print(
            f"Warning: local OCR workers is {workers}, but slots is {slots}. "
            "Extra workers will wait for a llama.cpp slot.",
            file=sys.stderr,
        )

    job_started_at = time.monotonic()
    server_process: subprocess.Popen[str] | None = None

    def set_server_process(process: subprocess.Popen[str] | None) -> None:
        if server_process_changed is not None:
            server_process_changed(process)

    def stop_server(process: subprocess.Popen[str]) -> None:
        try:
            _stop_server(process)
        finally:
            set_server_process(None)

    def start_server(server_slots: int) -> subprocess.Popen[str]:
        resolved_start_command = _resolve_local_ocr_start_command(
            start_command,
            server_slots,
        )
        process = _start_server(resolved_start_command)
        recent_output = _start_server_output_reader(process)
        set_server_process(process)
        try:
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
            _wait_for_endpoint_ready(
                server_url,
                process=process,
                recent_output=recent_output,
                stop_check=stop_check,
            )
            _print_server_slot_report(server_url, server_slots)
        except Exception:
            stop_server(process)
            raise
        return process

    try:
        server_process = start_server(slots)

        if stop_check:
            stop_check()
        _generate_image_page_files(pdf_path, image_pages_dir)
        image_paths = sorted(image_pages_dir.glob("*.png"))
        if not image_paths:
            raise RuntimeError("No images generated for OCR.")
        image_paths_to_ocr = [
            image_path
            for image_path in image_paths
            if not (text_dir / f"{image_path.stem}.txt").exists()
        ]
        if not image_paths_to_ocr:
            print("All OCR text pages already exist; skipping OCR.")
            return

        ocr_started_at = time.monotonic()
        try:
            _ocr_images(
                image_paths_to_ocr,
                server_url=server_url,
                model_id=model_id,
                text_dir=text_dir,
                workers=workers,
                stop_check=stop_check,
            )
        except requests.ConnectionError:
            print(
                "Local OCR connection closed unexpectedly; restarting the server "
                "and retrying unfinished pages one at a time.",
                file=sys.stderr,
            )
            stop_server(server_process)
            server_process = None
            if stop_check:
                stop_check()
            server_process = start_server(1)
            remaining_image_paths = [
                image_path
                for image_path in image_paths_to_ocr
                if not (text_dir / f"{image_path.stem}.txt").exists()
            ]
            try:
                _ocr_images(
                    remaining_image_paths,
                    server_url=server_url,
                    model_id=model_id,
                    text_dir=text_dir,
                    workers=1,
                    stop_check=stop_check,
                )
            except requests.ConnectionError as exc:
                raise RuntimeError(
                    "Local OCR server closed the connection again after an "
                    "automatic sequential retry."
                ) from exc
        ocr_elapsed = time.monotonic() - ocr_started_at
        print(f"OCR request phase completed in {_format_elapsed(ocr_elapsed)}.")
        job_elapsed = time.monotonic() - job_started_at
        print(
            "OCR job completed in "
            f"{_format_elapsed(job_elapsed)} "
            f"({len(image_paths_to_ocr)} page(s), {workers} worker(s), {slots} slot(s))."
        )

    finally:
        if server_process is not None:
            stop_server(server_process)

@dataclass
class ClassifySettingsWidgets:
    api_url_row: Adw.EntryRow
    model_row: Adw.EntryRow
    api_key_row: Adw.EntryRow
    prompt_buffer: Gtk.TextBuffer
    ct_prompt_buffer: Gtk.TextBuffer | None = None
    disable_reasoning_switch: Gtk.Switch | None = None
    workers_row: Adw.EntryRow | None = None
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
    workers_row: Adw.EntryRow
    slots_row: Adw.EntryRow
    start_command_buffer: Gtk.TextBuffer


@dataclass
class AdvancedClassificationSettingsWidgets:
    hearing_prompt_buffer: Gtk.TextBuffer
    minute_prompt_buffer: Gtk.TextBuffer
    form_prompt_buffer: Gtk.TextBuffer




@dataclass
class SummarizeSettingsWidgets:
    api_url_row: Adw.EntryRow
    model_row: Adw.EntryRow
    api_key_row: Adw.EntryRow
    disable_reasoning_row: Adw.SwitchRow
    window_target_chars_row: Adw.EntryRow
    window_max_pages_row: Adw.EntryRow
    hearings_prompt_buffer: Gtk.TextBuffer
    reports_prompt_buffer: Gtk.TextBuffer
    minutes_prompt_buffer: Gtk.TextBuffer






@dataclass
class AgentSettingsWidgets:
    pi_agent_command_row: Adw.EntryRow
    pi_thinking_level_row: Adw.ComboRow






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
    target_chars_raw = str(
        config.get(CONFIG_KEY_SUMMARIZE_WINDOW_TARGET_CHARS, "") or ""
    ).strip()
    target_chars = DEFAULT_SUMMARIZE_WINDOW_TARGET_CHARS
    if target_chars_raw:
        try:
            target_chars = max(1, int(target_chars_raw))
        except ValueError:
            target_chars = DEFAULT_SUMMARIZE_WINDOW_TARGET_CHARS
    max_pages_raw = str(
        config.get(CONFIG_KEY_SUMMARIZE_WINDOW_MAX_PAGES, "") or ""
    ).strip()
    max_pages = DEFAULT_SUMMARIZE_WINDOW_MAX_PAGES
    if max_pages_raw:
        try:
            max_pages = max(1, int(max_pages_raw))
        except ValueError:
            max_pages = DEFAULT_SUMMARIZE_WINDOW_MAX_PAGES
    hearings_prompt = str(
        config.get(CONFIG_KEY_SUMMARIZE_HEARINGS_PROMPT, DEFAULT_SUMMARIZE_HEARINGS_PROMPT) or ""
    ).strip()
    reports_prompt = str(
        config.get(CONFIG_KEY_SUMMARIZE_REPORTS_PROMPT, DEFAULT_SUMMARIZE_REPORTS_PROMPT) or ""
    ).strip()
    if hearings_prompt == PREVIOUS_DEFAULT_SUMMARIZE_HEARINGS_PROMPT or hearings_prompt.startswith(
        (
            "Summarize the following court hearing in one very concise paragraph",
            "Summarize the primary court-hearing source pages in one concise paragraph",
            "I need to understand the factual and procedural history of this juvenile "
            "dependency case. Therefore, summarize the following court hearing",
        )
    ):
        hearings_prompt = DEFAULT_SUMMARIZE_HEARINGS_PROMPT
    if (
        reports_prompt == PREVIOUS_DEFAULT_SUMMARIZE_REPORTS_PROMPT
        or reports_prompt == PREVIOUS_PROPOSAL_SCOPE_SUMMARIZE_REPORTS_PROMPT
        or reports_prompt.startswith(
            (
                "Summarize the following reports in one very concise paragraph",
                "Summarize the primary report source pages in one concise paragraph",
                "I need to understand the factual and procedural history of this juvenile "
                "dependency case. Therefore, summarize the following report",
            )
        )
    ):
        reports_prompt = DEFAULT_SUMMARIZE_REPORTS_PROMPT
    minutes_prompt = str(
        config.get(CONFIG_KEY_SUMMARIZE_MINUTES_PROMPT, DEFAULT_SUMMARIZE_MINUTES_PROMPT) or ""
    ).strip()
    return {
        "api_url": api_url,
        "model_id": model_id,
        "api_key": api_key,
        "disable_reasoning": disable_reasoning,
        "target_chars": str(target_chars),
        "max_pages": str(max_pages),
        "hearings_prompt": hearings_prompt or DEFAULT_SUMMARIZE_HEARINGS_PROMPT,
        "reports_prompt": reports_prompt or DEFAULT_SUMMARIZE_REPORTS_PROMPT,
        "minutes_prompt": minutes_prompt or DEFAULT_SUMMARIZE_MINUTES_PROMPT,
    }


def save_summarize_settings(
    api_url: str,
    model_id: str,
    api_key: str,
    disable_reasoning: bool,
    target_chars: str,
    max_pages: str,
    hearings_prompt: str,
    reports_prompt: str,
    minutes_prompt: str,
) -> None:
    config = _read_config()
    config[CONFIG_KEY_SUMMARIZE_API_URL] = api_url
    config[CONFIG_KEY_SUMMARIZE_MODEL_ID] = model_id
    config[CONFIG_KEY_SUMMARIZE_API_KEY] = api_key
    config[CONFIG_KEY_SUMMARIZE_DISABLE_REASONING] = bool(disable_reasoning)
    config[CONFIG_KEY_SUMMARIZE_WINDOW_TARGET_CHARS] = target_chars
    config[CONFIG_KEY_SUMMARIZE_WINDOW_MAX_PAGES] = max_pages
    config.pop(LEGACY_CONFIG_KEY_SUMMARIZE_CHUNK_SIZE, None)
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










def load_pi_agent_command_setting() -> str:
    config = _read_config()
    command = str(config.get(CONFIG_KEY_PI_AGENT_COMMAND, "") or "").strip()
    return command or discover_pi_agent_command(path_env=os.environ.get("PATH"))


def save_pi_agent_command_setting(command: str) -> None:
    config = _read_config()
    config[CONFIG_KEY_PI_AGENT_COMMAND] = (
        command.strip() or discover_pi_agent_command(path_env=os.environ.get("PATH"))
    )
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
        self._settings_group_rows: dict[str, Adw.ExpanderRow] = {}
        self._settings_group_destinations: dict[str, tuple[str, ...]] = {}
        self._settings_key_groups: dict[str, str] = {}
        self._settings_destination_labels: dict[str, str] = {}
        self._settings_destination_markers: dict[str, Gtk.Image] = {}
        self._settings_nav_updating = False
        self._active_settings_key: str | None = None
        self._text_source_row: Adw.ComboRow | None = None
        self._text_source_values: list[str] = []
        self._agent_widgets: AgentSettingsWidgets | None = None
        self._pi_model_options: list[PiModel | None] = []
        self._pi_model_generation = 0
        self._pi_model_closed = False
        self._pi_model_applying = False
        self._pi_model_selection_changed = False
        self._pi_model_settings_error = ""
        try:
            self._original_pi_model_key = current_project_pi_model()
            self._original_pi_thinking_level = current_project_pi_thinking_level()
        except PiSettingsError as exc:
            self._original_pi_model_key = None
            self._original_pi_thinking_level = None
            self._pi_model_settings_error = str(exc)
        self._build_ui()
        self.connect("close-request", self._on_pi_settings_close_request)
        self._load_pi_models()

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
        header.set_title_widget(Adw.WindowTitle(title="Settings"))
        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.add_css_class("flat")
        save_btn.set_action_name("app.save-settings")
        header.pack_end(save_btn)
        view.add_top_bar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(18)
        box.set_margin_bottom(12)
        box.set_margin_start(18)
        box.set_margin_end(18)

        split = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        split.set_hexpand(True)
        split.set_vexpand(True)

        prompt_list = Gtk.ListBox()
        prompt_list.set_selection_mode(Gtk.SelectionMode.NONE)
        prompt_list.add_css_class("boxed-list")
        prompt_list.set_valign(Gtk.Align.START)
        prompt_list.set_vexpand(False)
        self._prompt_list = prompt_list

        for group_id, title, destinations in SETTINGS_NAV_GROUPS:
            group_row = Adw.ExpanderRow(
                title=title,
                subtitle=f"{len(destinations)} settings",
            )
            group_row.set_expanded(False)
            group_row.connect(
                "notify::expanded",
                self._on_settings_group_expanded,
                group_id,
            )
            self._settings_group_rows[group_id] = group_row
            self._settings_group_destinations[group_id] = tuple(
                key for key, _label in destinations
            )
            prompt_list.append(group_row)

        prompt_list_scroller = Gtk.ScrolledWindow()
        prompt_list_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        prompt_list_scroller.set_min_content_width(240)
        prompt_list_scroller.set_size_request(240, -1)
        prompt_list_scroller.set_child(prompt_list)

        prompt_stack = Gtk.Stack()
        prompt_stack.set_hexpand(True)
        prompt_stack.set_vexpand(True)
        prompt_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self._prompt_stack = prompt_stack

        self._add_settings_destination("prepare", "text-source", "Create files")
        text_source_page = self._build_text_source_page()
        prompt_stack.add_named(text_source_page, "text-source")

        self._add_settings_destination("prepare", "local-ocr", "Local OCR")
        local_ocr_page = self._build_local_ocr_page(load_local_ocr_settings())
        prompt_stack.add_named(local_ocr_page, "local-ocr")

        prompt_definitions = [
            ("case-name", "Infer Case Name", load_case_name_settings(), DEFAULT_CASE_NAME_PROMPT),
        ]
        for key, title, settings, default_prompt in prompt_definitions:
            self._add_settings_destination("prepare", key, "Infer case")
            page = self._build_prompt_page(key, title, settings, default_prompt)
            prompt_stack.add_named(page, key)

        self._add_settings_destination("classify", "classify-basic", "Basic")
        classify_page = self._build_prompt_page(
            "classify-basic",
            "Classification basic",
            load_classifier_settings(),
            DEFAULT_CLASSIFIER_PROMPT,
        )
        prompt_stack.add_named(classify_page, "classify-basic")

        self._add_settings_destination("classify", "classify-advanced", "Advanced")
        classify_advanced_page = self._build_advanced_classify_prompt_page()
        prompt_stack.add_named(classify_advanced_page, "classify-advanced")

        self._add_settings_destination("classify", "classify-dates", "Dates")
        classify_dates_page = self._build_classify_dates_prompt_page()
        prompt_stack.add_named(classify_dates_page, "classify-dates")

        self._add_settings_destination("classify", "classify-names", "Names")
        classify_names_page = self._build_classify_names_prompt_page()
        prompt_stack.add_named(classify_names_page, "classify-names")

        self._add_settings_destination("summarize", "summarize", "Summarize")
        summarize_page = self._build_summarize_prompt_page(load_summarize_settings())
        prompt_stack.add_named(summarize_page, "summarize")

        self._add_settings_destination("agent", "pi", "PI")
        pi_page = self._build_pi_settings_page()
        prompt_stack.add_named(pi_page, "pi")

        self._set_settings_group_expanded("prepare")
        self._select_settings_page("text-source")

        split.append(prompt_list_scroller)
        split.append(prompt_stack)
        box.append(split)

        view.set_content(box)
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
            label=(
                "Configure the local OCR server and model used for Create files. "
                "Use {slots} in the start command to insert the llama.cpp slot count."
            ),
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

        workers_row = Adw.EntryRow(title="OCR Workers")
        workers_row.set_text(str(settings.get("workers", DEFAULT_LOCAL_OCR_WORKERS)))
        if hasattr(workers_row, "set_input_purpose"):
            workers_row.set_input_purpose(Gtk.InputPurpose.NUMBER)
        server_group.add(workers_row)

        slots_row = Adw.EntryRow(title="llama.cpp Slots")
        slots_row.set_text(str(settings.get("slots", DEFAULT_LOCAL_OCR_SLOTS)))
        if hasattr(slots_row, "set_input_purpose"):
            slots_row.set_input_purpose(Gtk.InputPurpose.NUMBER)
        server_group.add(slots_row)

        command_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        command_section.set_hexpand(True)
        command_section.set_vexpand(True)

        command_scroller, command_buffer = self._build_prompt_editor(
            settings.get("start_command", START_SERVER_COMMAND)
        )
        self._set_prompt_editor_height(command_scroller, 180)
        command_section.append(command_scroller)
        page_box.append(
            self._build_disclosure(
                "Advanced",
                command_section,
                subtitle="Local server start command",
            )
        )

        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.set_hexpand(True)
        page.set_vexpand(True)
        page.set_child(page_box)

        self._local_ocr_widgets = LocalOcrSettingsWidgets(
            server_url_row=server_url_row,
            model_row=model_row,
            workers_row=workers_row,
            slots_row=slots_row,
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
        workers_row: Adw.EntryRow | None = None
        local_server_switch: Gtk.Switch | None = None
        local_start_command_buffer: Gtk.TextBuffer | None = None
        disable_reasoning_row: Adw.SwitchRow | None = None
        if is_classify_basic:
            workers_row = Adw.EntryRow(title="Classification Workers")
            workers_row.set_tooltip_text(
                "Concurrent classification requests for basic, advanced, dates, and names."
            )
            workers_row.set_text(str(settings.get("workers", DEFAULT_CLASSIFIER_WORKERS)))
            if hasattr(workers_row, "set_input_purpose"):
                workers_row.set_input_purpose(Gtk.InputPurpose.NUMBER)
            credentials_group.add(workers_row)

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

            command_scroller, local_start_command_buffer = self._build_prompt_editor(
                settings.get("local_vision_start_command", DEFAULT_LOCAL_VISION_START_COMMAND)
            )
            self._set_prompt_editor_height(command_scroller, 160)
            command_section.append(command_scroller)
            page_box.append(
                self._build_disclosure(
                    "Advanced",
                    command_section,
                    subtitle="Local vision server start command",
                )
            )

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
        page_box.append(self._build_disclosure("Prompts", prompt_section))

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
            workers_row=workers_row,
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

        hearing_scroller, hearing_buffer = self._build_prompt_editor(
            settings.get("hearing_prompt") or DEFAULT_ADVANCED_HEARING_PROMPT
        )
        self._set_prompt_editor_height(hearing_scroller, 240)
        prompt_section.append(
            self._build_disclosure(
                "Hearing first page prompt", hearing_scroller, expanded=True
            )
        )

        minute_scroller, minute_buffer = self._build_prompt_editor(
            settings.get("minute_prompt") or DEFAULT_ADVANCED_MINUTE_PROMPT
        )
        self._set_prompt_editor_height(minute_scroller, 240)
        prompt_section.append(
            self._build_disclosure("Minute order first page prompt", minute_scroller)
        )

        forms_scroller, forms_buffer = self._build_prompt_editor(
            settings.get("form_prompt") or DEFAULT_ADVANCED_FORM_PROMPT
        )
        self._set_prompt_editor_height(forms_scroller, 240)
        prompt_section.append(
            self._build_disclosure("Form first page prompt", forms_scroller)
        )

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

        hearing_scroller, hearing_buffer = self._build_prompt_editor(
            settings.get("hearing_prompt") or DEFAULT_CLASSIFY_HEARING_DATES_PROMPT
        )
        self._set_prompt_editor_height(hearing_scroller, 240)
        prompt_section.append(
            self._build_disclosure("Hearing date prompt", hearing_scroller, expanded=True)
        )

        minute_scroller, minute_buffer = self._build_prompt_editor(
            settings.get("minute_prompt") or DEFAULT_CLASSIFY_MINUTE_DATES_PROMPT
        )
        self._set_prompt_editor_height(minute_scroller, 240)
        prompt_section.append(
            self._build_disclosure("Minute order date prompt", minute_scroller)
        )

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

        reports_scroller, reports_buffer = self._build_prompt_editor(
            settings.get("report_prompt") or DEFAULT_CLASSIFY_REPORT_NAMES_PROMPT
        )
        self._set_prompt_editor_height(reports_scroller, 240)
        prompt_section.append(
            self._build_disclosure(
                "Report name and date prompt", reports_scroller, expanded=True
            )
        )

        forms_scroller, forms_buffer = self._build_prompt_editor(
            settings.get("form_prompt") or DEFAULT_CLASSIFY_FORM_NAMES_PROMPT
        )
        self._set_prompt_editor_height(forms_scroller, 240)
        prompt_section.append(self._build_disclosure("Form name prompt", forms_scroller))

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

        window_target_chars_row = Adw.EntryRow(
            title="Summary window target (source characters)"
        )
        window_target_chars_row.set_text(
            settings.get(
                "target_chars",
                str(DEFAULT_SUMMARIZE_WINDOW_TARGET_CHARS),
            )
        )
        credentials_group.add(window_target_chars_row)

        window_max_pages_row = Adw.EntryRow(
            title="Maximum source pages per summary window"
        )
        window_max_pages_row.set_text(
            settings.get("max_pages", str(DEFAULT_SUMMARIZE_WINDOW_MAX_PAGES))
        )
        credentials_group.add(window_max_pages_row)

        prompt_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        prompt_section.set_hexpand(True)
        prompt_section.set_vexpand(True)

        hearings_scroller, hearings_buffer = self._build_prompt_editor(
            settings.get("hearings_prompt") or DEFAULT_SUMMARIZE_HEARINGS_PROMPT
        )
        self._set_prompt_editor_height(hearings_scroller, 240)
        prompt_section.append(
            self._build_disclosure("Summarize hearings prompt", hearings_scroller)
        )

        reports_scroller, reports_buffer = self._build_prompt_editor(
            settings.get("reports_prompt") or DEFAULT_SUMMARIZE_REPORTS_PROMPT
        )
        self._set_prompt_editor_height(reports_scroller, 240)
        prompt_section.append(
            self._build_disclosure("Summarize reports prompt", reports_scroller)
        )

        minutes_scroller, minutes_buffer = self._build_prompt_editor(
            settings.get("minutes_prompt") or DEFAULT_SUMMARIZE_MINUTES_PROMPT
        )
        self._set_prompt_editor_height(minutes_scroller, 240)
        prompt_section.append(
            self._build_disclosure("Summarize minute orders prompt", minutes_scroller)
        )

        page_box.append(
            self._build_disclosure(
                "Prompts",
                prompt_section,
                subtitle="Hearings, reports, and minute orders",
            )
        )

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
            window_target_chars_row=window_target_chars_row,
            window_max_pages_row=window_max_pages_row,
            hearings_prompt_buffer=hearings_buffer,
            reports_prompt_buffer=reports_buffer,
            minutes_prompt_buffer=minutes_buffer,
        )
        return page



    def _build_pi_settings_page(self) -> Gtk.Widget:
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page_box.set_margin_top(12)
        page_box.set_margin_bottom(12)
        page_box.set_margin_start(12)
        page_box.set_margin_end(12)
        page_box.set_vexpand(True)

        title_label = Gtk.Label(label="PI", xalign=0)
        title_label.add_css_class("title-3")
        page_box.append(title_label)

        launch_group = Adw.PreferencesGroup(
            title="Agent Refinement",
            description=(
                "PI runs four project-local skills sequentially in the final "
                "pipeline group."
            ),
        )
        launch_group.add_css_class("list-stack")
        launch_group.set_hexpand(True)
        page_box.append(launch_group)

        command_row = Adw.EntryRow(title="PI command")
        command_row.set_hexpand(True)
        command_row.set_text(load_pi_agent_command_setting())
        launch_group.add(command_row)

        model_row = Adw.ComboRow(
            title="PI model",
            subtitle=self._pi_model_settings_error or "Loading models authorized in PI…",
        )
        model_row.set_model(Gtk.StringList.new(["Loading PI models…"]))
        model_list_factory = Gtk.SignalListItemFactory()
        model_list_factory.connect("setup", _setup_pi_model_list_item)
        model_list_factory.connect("bind", _bind_pi_model_list_item)
        model_row.set_list_factory(model_list_factory)
        model_row.set_sensitive(False)
        model_row.connect("notify::selected", self._on_pi_model_selected)
        refresh_button = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_button.add_css_class("flat")
        refresh_button.set_tooltip_text("Refresh available PI models")
        refresh_button.connect("clicked", self._on_refresh_pi_models)
        model_row.add_suffix(refresh_button)
        launch_group.add(model_row)

        thinking_level_row = Adw.ComboRow(
            title="PI reasoning level",
            subtitle=(
                "Applied to each new RecordPrep PI session; PI adjusts levels "
                "unsupported by the selected model."
            ),
        )
        thinking_level_row.set_model(
            Gtk.StringList.new([label for label, _level in PI_THINKING_LEVEL_OPTIONS])
        )
        configured_level = self._original_pi_thinking_level
        selected_thinking_index = next(
            (
                index
                for index, (_label, level) in enumerate(PI_THINKING_LEVEL_OPTIONS)
                if level == configured_level
            ),
            0,
        )
        thinking_level_row.set_selected(selected_thinking_index)
        launch_group.add(thinking_level_row)

        configuration_row = Adw.ActionRow(
            title="PI configuration",
            subtitle=(
                "Provider, model, and reasoning level are saved in project "
                ".pi/settings.json. Credentials remain in your global PI configuration."
            ),
        )
        launch_group.add(configuration_row)

        access_row = Adw.ActionRow(
            title="Skill access",
            subtitle=(
                "Four project skills use narrow local-file tools; no web-search "
                "tools are enabled."
            ),
        )
        launch_group.add(access_row)

        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.set_hexpand(True)
        page.set_vexpand(True)
        page.set_child(page_box)

        self._agent_widgets = AgentSettingsWidgets(
            pi_agent_command_row=command_row,
            pi_thinking_level_row=thinking_level_row,
        )
        self._pi_model_row = model_row
        self._pi_model_refresh_button = refresh_button
        return page

    def _on_pi_settings_close_request(self, *_args: object) -> bool:
        self._pi_model_closed = True
        self._pi_model_generation += 1
        return False

    def _selected_pi_model(self) -> PiModel | None:
        selected = int(self._pi_model_row.get_selected())
        if 0 <= selected < len(self._pi_model_options):
            return self._pi_model_options[selected]
        return None

    def _update_pi_model_subtitle(self) -> None:
        model = self._selected_pi_model()
        if model is not None:
            self._pi_model_row.set_subtitle(
                f"Project-wide setting: {model.provider} / {model.model_id}"
            )

    def _on_pi_model_selected(
        self,
        _row: Adw.ComboRow,
        _parameter: object,
    ) -> None:
        if self._pi_model_applying:
            return
        model = self._selected_pi_model()
        if model is None:
            return
        self._pi_model_selection_changed = (
            model.settings_key != self._original_pi_model_key
        )
        self._update_pi_model_subtitle()

    def _on_refresh_pi_models(self, _button: Gtk.Button) -> None:
        self._load_pi_models()

    def _load_pi_models(self) -> None:
        if self._pi_model_closed:
            return
        if self._pi_model_settings_error:
            try:
                self._original_pi_model_key = current_project_pi_model()
                self._original_pi_thinking_level = current_project_pi_thinking_level()
                self._pi_model_settings_error = ""
            except PiSettingsError as exc:
                self._pi_model_row.set_subtitle(str(exc))
                self._pi_model_row.set_sensitive(False)
                self._pi_model_refresh_button.set_sensitive(True)
                return

        selected = self._selected_pi_model()
        desired_key = (
            selected.settings_key
            if self._pi_model_selection_changed and selected is not None
            else self._original_pi_model_key
        )
        self._pi_model_generation += 1
        generation = self._pi_model_generation
        command = (
            self._agent_widgets.pi_agent_command_row.get_text().strip()
            if self._agent_widgets is not None
            else DEFAULT_PI_AGENT_COMMAND
        )
        try:
            command_argv = resolve_pi_agent_argv(
                command or DEFAULT_PI_AGENT_COMMAND,
                path_env=os.environ.get("PATH"),
            )
        except ValueError as exc:
            self._finish_pi_model_load(
                generation,
                [],
                f"Invalid PI command: {exc}",
                desired_key,
            )
            return
        if not command_argv:
            self._finish_pi_model_load(
                generation,
                [],
                "PI command is empty.",
                desired_key,
            )
            return
        incompatible_flag = incompatible_pi_agent_flag(command_argv)
        if incompatible_flag:
            self._finish_pi_model_load(
                generation,
                [],
                f"PI option {incompatible_flag} is incompatible with RecordPrep.",
                desired_key,
            )
            return

        self._pi_model_row.set_sensitive(False)
        self._pi_model_row.set_subtitle("Loading models authorized in PI…")
        self._pi_model_refresh_button.set_sensitive(False)

        def worker() -> None:
            try:
                models = available_pi_models(command_argv)
                error = ""
            except PiRuntimeError as exc:
                models = []
                error = str(exc)
            GLib.idle_add(
                self._finish_pi_model_load,
                generation,
                models,
                error,
                desired_key,
            )

        threading.Thread(
            target=worker,
            name="recordprep-pi-models",
            daemon=True,
        ).start()

    def _finish_pi_model_load(
        self,
        generation: int,
        models: list[PiModel],
        error: str,
        desired_key: tuple[str, str] | None,
    ) -> bool:
        if self._pi_model_closed or generation != self._pi_model_generation:
            return False
        self._pi_model_refresh_button.set_sensitive(True)
        if error:
            current = self._original_pi_model_key
            if current is None:
                self._pi_model_options = [None]
                labels = ["PI models unavailable"]
            else:
                current_model = PiModel(
                    provider=current[0],
                    model_id=current[1],
                    name=current[1],
                )
                self._pi_model_options = [current_model]
                labels = [f"{current_model.label} (currently configured)"]
            self._pi_model_applying = True
            self._pi_model_row.set_model(Gtk.StringList.new(labels))
            self._pi_model_row.set_selected(0)
            self._pi_model_applying = False
            self._pi_model_selection_changed = False
            self._pi_model_row.set_sensitive(False)
            self._pi_model_row.set_subtitle(error)
            return False

        available_keys = {model.settings_key for model in models}
        options: list[PiModel | None] = []
        labels: list[str] = []
        current = self._original_pi_model_key
        if current is not None and current not in available_keys:
            unavailable = PiModel(
                provider=current[0],
                model_id=current[1],
                name=current[1],
            )
            options.append(unavailable)
            labels.append(f"{unavailable.label} (currently configured; unavailable)")
        options.extend(models)
        labels.extend(model.label for model in models)
        if not options:
            options = [None]
            labels = ["No authenticated PI models found"]

        selected_index = 0
        if desired_key is not None:
            for index, model in enumerate(options):
                if model is not None and model.settings_key == desired_key:
                    selected_index = index
                    break
        self._pi_model_options = options
        self._pi_model_applying = True
        self._pi_model_row.set_model(Gtk.StringList.new(labels))
        self._pi_model_row.set_selected(selected_index)
        self._pi_model_applying = False
        selected_model = self._selected_pi_model()
        self._pi_model_selection_changed = bool(
            selected_model is not None
            and selected_model.settings_key != self._original_pi_model_key
        )
        self._pi_model_row.set_sensitive(bool(models))
        if selected_model is None:
            self._pi_model_row.set_subtitle(
                "Authorize a provider in PI, then refresh this list."
            )
        else:
            self._update_pi_model_subtitle()
        return False

    def _prompt_text(self, buffer: Gtk.TextBuffer) -> str:
        start, end = buffer.get_bounds()
        return buffer.get_text(start, end, True)

    def _add_settings_destination(
        self,
        group_id: str,
        key: str,
        label: str,
    ) -> None:
        row = Adw.ActionRow(title=label)
        row.set_activatable(True)
        marker = Gtk.Image.new_from_icon_name("object-select-symbolic")
        marker.set_visible(False)
        row.add_suffix(marker)
        row.connect(
            "activated",
            lambda _row, destination=key: self._select_settings_page(destination),
        )
        self._settings_key_groups[key] = group_id
        self._settings_destination_labels[key] = label
        self._settings_destination_markers[key] = marker
        self._settings_group_rows[group_id].add_row(row)

    def _set_settings_group_expanded(self, group_id: str | None) -> None:
        self._settings_nav_updating = True
        try:
            for candidate_id, row in self._settings_group_rows.items():
                row.set_expanded(candidate_id == group_id)
        finally:
            self._settings_nav_updating = False

    def _on_settings_group_expanded(
        self,
        row: Adw.ExpanderRow,
        _pspec: GObject.ParamSpec,
        group_id: str,
    ) -> None:
        if self._settings_nav_updating or not row.get_expanded():
            return
        self._set_settings_group_expanded(group_id)
        if self._settings_key_groups.get(self._active_settings_key or "") != group_id:
            destinations = self._settings_group_destinations.get(group_id, ())
            if destinations:
                self._select_settings_page(destinations[0])

    def _select_settings_page(self, key: str) -> None:
        if key not in self._settings_destination_labels:
            return
        group_id = self._settings_key_groups[key]
        self._active_settings_key = key
        self._set_settings_group_expanded(group_id)
        self._prompt_stack.set_visible_child_name(key)
        for destination, marker in self._settings_destination_markers.items():
            marker.set_visible(destination == key)
        for candidate_id, _title, destinations in SETTINGS_NAV_GROUPS:
            group_row = self._settings_group_rows[candidate_id]
            if candidate_id == group_id:
                group_row.set_subtitle(self._settings_destination_labels[key])
            else:
                group_row.set_subtitle(f"{len(destinations)} settings")

    def _build_disclosure(
        self,
        title: str,
        child: Gtk.Widget | None = None,
        *,
        expanded: bool = False,
        subtitle: str | None = None,
    ) -> Adw.ExpanderRow:
        row = Adw.ExpanderRow(title=title, subtitle=subtitle or "")
        row.set_expanded(expanded)
        if child is not None:
            row.add_row(child)
        return row

    def _save_settings(self) -> None:
        case_widgets = self._prompt_editors.get("case-name")
        classify_basic_widgets = self._prompt_editors.get("classify-basic")
        advanced_classify_widgets = self._advanced_classify_widgets
        classify_dates_widgets = self._classify_dates_widgets
        classify_names_widgets = self._classify_names_widgets
        local_ocr_widgets = self._local_ocr_widgets
        summarize_widgets = getattr(self, "_summarize_widgets", None)
        agent_widgets = self._agent_widgets
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
                    classify_basic_widgets.workers_row.get_text().strip()
                    if classify_basic_widgets.workers_row
                    else DEFAULT_CLASSIFIER_WORKERS
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
                local_ocr_widgets.workers_row.get_text().strip(),
                local_ocr_widgets.slots_row.get_text().strip(),
            )
        if summarize_widgets:
            save_summarize_settings(
                summarize_widgets.api_url_row.get_text().strip(),
                summarize_widgets.model_row.get_text().strip(),
                summarize_widgets.api_key_row.get_text().strip(),
                bool(summarize_widgets.disable_reasoning_row.get_active()),
                summarize_widgets.window_target_chars_row.get_text().strip(),
                summarize_widgets.window_max_pages_row.get_text().strip(),
                self._prompt_text(summarize_widgets.hearings_prompt_buffer).strip(),
                self._prompt_text(summarize_widgets.reports_prompt_buffer).strip(),
                self._prompt_text(summarize_widgets.minutes_prompt_buffer).strip(),
            )
        if agent_widgets:
            pi_command = agent_widgets.pi_agent_command_row.get_text().strip()
            try:
                pi_argv = resolve_pi_agent_argv(
                    pi_command or DEFAULT_PI_AGENT_COMMAND,
                    path_env=os.environ.get("PATH"),
                )
            except ValueError as exc:
                self._pi_model_row.set_subtitle(f"Invalid PI command: {exc}")
                self._select_settings_page("pi")
                return
            incompatible_flag = incompatible_pi_agent_flag(pi_argv)
            if not pi_argv or incompatible_flag:
                detail = (
                    "PI command is empty."
                    if not pi_argv
                    else f"PI option {incompatible_flag} is incompatible with RecordPrep."
                )
                self._pi_model_row.set_subtitle(detail)
                self._select_settings_page("pi")
                return
            selected_model = self._selected_pi_model()
            if self._pi_model_selection_changed and selected_model is not None:
                try:
                    save_project_pi_model(selected_model)
                except PiSettingsError as exc:
                    self._pi_model_row.set_subtitle(str(exc))
                    self._select_settings_page("pi")
                    return
                self._original_pi_model_key = selected_model.settings_key
                self._pi_model_selection_changed = False
            thinking_index = int(agent_widgets.pi_thinking_level_row.get_selected())
            thinking_level = (
                PI_THINKING_LEVEL_OPTIONS[thinking_index][1]
                if 0 <= thinking_index < len(PI_THINKING_LEVEL_OPTIONS)
                else None
            )
            try:
                save_project_pi_thinking_level(thinking_level)
            except PiSettingsError as exc:
                agent_widgets.pi_thinking_level_row.set_subtitle(str(exc))
                self._select_settings_page("pi")
                return
            self._original_pi_thinking_level = thinking_level
            save_pi_agent_command_setting(pi_command)
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
        header.set_title_widget(Adw.WindowTitle(title="Edit TOC"))
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


class TestPromptsWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, parent: "RecordPrepWindow") -> None:
        super().__init__(application=app, title="Test prompts")
        self.set_default_size(900, 640)
        self.set_resizable(True)
        self._parent = parent
        self._selected_image_path: Path | None = None
        self._group_values = [group_id for group_id, _label, _options in TEST_PROMPT_GROUPS]
        self._mode_values: list[str] = []
        self._running = False
        self._updating_mode = False
        self._paned_position_set = False
        self._build_ui()

    def _build_ui(self) -> None:
        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.add_css_class("flat")
        header.set_title_widget(Adw.WindowTitle(title="Test prompts"))
        view.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(18)
        content.set_margin_bottom(12)
        content.set_margin_start(18)
        content.set_margin_end(18)

        settings_group = Adw.PreferencesGroup(title="Test settings")
        settings_group.add_css_class("list-stack")
        content.append(settings_group)

        group_row = Adw.ComboRow(title="Group")
        group_row.set_model(
            Gtk.StringList.new(
                [label for _group_id, label, _options in TEST_PROMPT_GROUPS]
            )
        )
        group_row.set_selected(0)
        group_row.connect("notify::selected", self._on_group_changed)
        settings_group.add(group_row)
        self._group_row = group_row

        mode_row = Adw.ComboRow(title="Prompt")
        mode_row.connect("notify::selected", self._on_mode_changed)
        settings_group.add(mode_row)
        self._mode_row = mode_row

        details_row = Adw.ActionRow(title="Input")
        settings_group.add(details_row)
        self._details_row = details_row

        image_row = Adw.ActionRow(
            title="Image file",
            subtitle="Choose a PNG page image.",
        )
        choose_button = Gtk.Button(label="Choose image")
        choose_button.add_css_class("flat")
        choose_button.connect("clicked", self._on_choose_image_clicked)
        image_row.add_suffix(choose_button)
        settings_group.add(image_row)
        self._image_row = image_row
        self._choose_image_button = choose_button

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_hexpand(True)
        paned.set_vexpand(True)
        paned.set_shrink_start_child(False)
        paned.set_shrink_end_child(False)
        paned.set_resize_start_child(True)
        paned.set_resize_end_child(True)
        self._paned = paned

        input_stack = Gtk.Stack()
        input_stack.set_hexpand(True)
        input_stack.set_vexpand(True)
        input_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._input_stack = input_stack

        preview_frame = Gtk.Frame()
        preview_frame.set_margin_top(6)
        preview_frame.set_margin_end(6)
        preview_frame.set_hexpand(True)
        preview_frame.set_vexpand(True)
        preview_picture = Gtk.Picture()
        preview_picture.set_can_shrink(True)
        preview_picture.set_hexpand(True)
        preview_picture.set_vexpand(True)
        preview_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        preview_frame.set_child(preview_picture)
        input_stack.add_named(preview_frame, "image")
        self._preview_picture = preview_picture

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
        input_stack.add_named(input_box, "text")
        self._input_view = input_view
        self._input_buffer = input_view.get_buffer()

        output_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        output_box.set_hexpand(True)
        output_box.set_vexpand(True)
        output_box.set_margin_top(6)
        output_box.append(Gtk.Label(label="Output", xalign=0))
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
        self._output_view = output_view
        self._output_buffer = output_view.get_buffer()

        paned.set_start_child(input_stack)
        paned.set_end_child(output_box)
        content.append(paned)

        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        run_button = Gtk.Button(label="Run test")
        run_button.add_css_class("suggested-action")
        run_button.add_css_class("flat")
        run_button.connect("clicked", self._on_run_clicked)
        action_box.append(run_button)
        status_spinner = Gtk.Spinner()
        status_label = Gtk.Label(label="Idle", xalign=0)
        status_label.set_hexpand(True)
        status_label.set_ellipsize(3)
        action_box.append(status_spinner)
        action_box.append(status_label)
        content.append(action_box)
        self._run_button = run_button
        self._status_spinner = status_spinner
        self._status_label = status_label

        view.set_content(content)
        self.set_content(view)
        self._update_mode_options()
        GLib.idle_add(self._set_initial_paned_position)

    def _current_group_id(self) -> str | None:
        selected = self._group_row.get_selected()
        if 0 <= selected < len(self._group_values):
            return self._group_values[selected]
        return None

    def _current_mode_id(self) -> str | None:
        selected = self._mode_row.get_selected()
        if 0 <= selected < len(self._mode_values):
            return self._mode_values[selected]
        return None

    def _buffer_text(self, buffer: Gtk.TextBuffer) -> str:
        start, end = buffer.get_bounds()
        return buffer.get_text(start, end, True)

    def _mode_details(self, mode_id: str) -> str:
        if _test_prompt_input_kind(mode_id) == "image":
            return "Choose a page image; the test uses the saved classification prompt."
        if mode_id == "summarize_hearings":
            return "Paste direct hearing source text; separate simulated source pages with form feeds if needed."
        if mode_id == "summarize_reports":
            return "Paste direct report source text; uses the production summary-window path."
        if mode_id == "summarize_minutes":
            return "Paste minute-order text; uses the saved minute summary prompt."
        return "Uses the saved prompt for the selected mode."

    def _update_mode_options(self) -> None:
        group_id = self._current_group_id()
        options = _test_prompt_options(group_id or "")
        self._updating_mode = True
        self._mode_values = [value for value, _label in options]
        self._mode_row.set_model(Gtk.StringList.new([label for _value, label in options]))
        self._mode_row.set_selected(0 if options else Gtk.INVALID_LIST_POSITION)
        self._updating_mode = False
        self._apply_selected_mode()

    def _apply_selected_mode(self) -> None:
        mode_id = self._current_mode_id()
        if not mode_id:
            return
        input_kind = _test_prompt_input_kind(mode_id)
        self._input_stack.set_visible_child_name(input_kind)
        self._image_row.set_visible(input_kind == "image")
        self._details_row.set_subtitle(self._mode_details(mode_id))
        self._output_view.set_wrap_mode(
            Gtk.WrapMode.NONE if input_kind == "image" else Gtk.WrapMode.WORD_CHAR
        )
        self._output_buffer.set_text("")
        self._set_status("Idle", False)

    def _on_group_changed(
        self,
        _row: Adw.ComboRow,
        _pspec: GObject.ParamSpec,
    ) -> None:
        if not self._running:
            self._update_mode_options()

    def _on_mode_changed(
        self,
        _row: Adw.ComboRow,
        _pspec: GObject.ParamSpec,
    ) -> None:
        if not self._updating_mode and not self._running:
            self._apply_selected_mode()

    def _set_status(self, message: str, running: bool) -> None:
        self._status_label.set_text(message)
        if running:
            self._status_spinner.start()
        else:
            self._status_spinner.stop()

    def _set_running(self, running: bool) -> None:
        self._running = running
        self._run_button.set_sensitive(not running)
        self._group_row.set_sensitive(not running)
        self._mode_row.set_sensitive(not running)
        self._choose_image_button.set_sensitive(not running)
        self._input_view.set_editable(not running)

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
        mode_id = self._current_mode_id()
        if not mode_id:
            self._set_status("Choose a prompt.", False)
            return
        self._output_buffer.set_text("")
        self._set_running(True)
        self._set_status("Running…", True)

        def _on_done(output: str, error: str | None) -> None:
            if error:
                self._set_status(f"Failed: {error}", False)
                output = error
            else:
                self._set_status("Done", False)
            self._output_buffer.set_text(output)
            self._set_running(False)

        if _test_prompt_input_kind(mode_id) == "image":
            image_path = self._selected_image_path
            if image_path is None or not image_path.exists():
                self._set_running(False)
                self._set_status("Choose an image first.", False)
                return
            self._parent.run_test_classification(mode_id, image_path, _on_done)
            return

        raw_text = self._buffer_text(self._input_buffer).strip()
        if not raw_text:
            self._set_running(False)
            self._set_status("Enter raw text first.", False)
            return
        self._parent.run_test_summarize(mode_id, raw_text, {}, _on_done)


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
        self._step_status_values: dict[str, str] = {}
        self._step_rows_by_id: dict[str, Adw.ActionRow] = {}
        self._step_ids_by_row: dict[Adw.ActionRow, str] = {}
        self._step_menu_buttons: dict[Adw.ActionRow, Gtk.MenuButton] = {}
        self._phase_rows: dict[str, Adw.ExpanderRow] = {}
        self._phase_expansion_updating = False
        self._active_step_id: str | None = None
        self._rt_ct_split_spin: Gtk.SpinButton | None = None
        self._rt_ct_split_label: Gtk.Label | None = None
        self._rt_ct_split_dropdown: Adw.ComboRow | None = None
        self._rt_ct_split_entry: Gtk.Entry | None = None
        self._rt_ct_split_page_row: Adw.ActionRow | None = None
        self._source_row: Adw.ExpanderRow | None = None
        self._activity_status_label: Gtk.Label | None = None
        self._edit_toc_button: Gtk.Button | None = None
        self._rt_ct_split_pending: int | None = None
        self._rt_ct_split_mode_pending: str | None = None
        self._rt_ct_split_updating = False
        self._bundle_reset_required = False
        self._test_prompts_window: TestPromptsWindow | None = None
        self._log_buffer: Gtk.TextBuffer | None = None
        self._log_view: Gtk.TextView | None = None
        self._activity_terminal: Any | None = None
        self._pi_terminal_pid: int | None = None
        self._pi_terminal_active = False
        self._pi_terminal_done: threading.Event | None = None
        self._pi_terminal_exit_status: int | None = None
        self._pi_stall_warned = False
        self._active_bundle_root: str | None = None
        self._bundle_identity_warning_roots: set[str] = set()
        self._pi_terminal_spawn_error: str | None = None
        self._pi_terminal_sequence_started = False
        self._run_until_dropdown: Gtk.DropDown | None = None
        self._run_until_values: list[str | None] = [None]
        self._run_completion_message: str | None = None
        self._run_pause_message: str | None = None
        self._local_ocr_server_process: subprocess.Popen[str] | None = None
        self._local_ocr_server_lock = threading.Lock()
        self._local_vision_server_process: subprocess.Popen[str] | None = None
        self._local_vision_server_owned = False
        self._local_vision_server_log_thread: threading.Thread | None = None
        self._local_vision_server_recent_output: deque[str] = deque(maxlen=40)
        self._local_vision_server_log_lock = threading.Lock()
        self._css_provider = _install_recordprep_css()
        self.connect("close-request", self._on_main_close_request)

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

        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        status_box.set_halign(Gtk.Align.CENTER)
        self.status_spinner = Gtk.Spinner()
        self.status_label = Gtk.Label(label=APPLICATION_NAME, xalign=0)
        self.status_label.set_ellipsize(3)
        self.status_label.set_max_width_chars(52)
        status_box.append(self.status_spinner)
        status_box.append(self.status_label)
        header_bar.set_title_widget(status_box)

        self.menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic")
        self.menu_button.add_css_class("flat")
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

        log_scroller = Gtk.ScrolledWindow()
        log_scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        log_scroller.set_hexpand(True)
        log_scroller.set_vexpand(True)
        log_scroller.add_css_class("recordprep-terminal-scroller")
        if Vte is not None:
            terminal = Vte.Terminal()
            terminal.set_hexpand(True)
            terminal.set_vexpand(True)
            terminal.set_scrollback_lines(10_000)
            terminal.set_mouse_autohide(True)
            terminal.set_input_enabled(False)
            terminal.add_css_class("recordprep-terminal")
            _apply_recordprep_terminal_theme(terminal)
            terminal.connect("child-exited", self._on_activity_terminal_child_exited)
            terminal_keys = Gtk.EventControllerKey()
            terminal_keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            terminal_keys.connect("key-pressed", self._on_activity_terminal_key_pressed)
            terminal.add_controller(terminal_keys)
            Adw.StyleManager.get_default().connect(
                "notify::dark",
                lambda *_args: _apply_recordprep_terminal_theme(terminal),
            )
            log_scroller.set_child(terminal)
            self._activity_terminal = terminal
        else:
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
            self._log_view = log_view
            self._log_buffer = log_view.get_buffer()
            self._log_buffer.set_text(
                "Embedded terminal support requires GTK4 VTE "
                "(gir1.2-vte-3.91 and libvte-2.91-gtk4-0).\n"
            )

        source_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        source_list.add_css_class("boxed-list")
        source_list.append(self._build_transcript_split_section())
        content.append(source_list)

        self.selected_label = Gtk.Label(label="Selected: None")
        self.selected_label.connect(
            "notify::label", lambda *_args: self._update_source_summary()
        )

        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.run_all_button = Gtk.Button(label="Run")
        self.run_all_button.set_halign(Gtk.Align.START)
        self.run_all_button.connect("clicked", self.on_run_all_clicked)
        action_box.append(self.run_all_button)

        self.resume_button = Gtk.Button(label="Resume")
        self.resume_button.set_halign(Gtk.Align.START)
        self.resume_button.connect("clicked", self.on_resume_clicked)
        action_box.append(self.resume_button)

        self.stop_button = Gtk.Button(label="Stop")
        self.stop_button.add_css_class("destructive-action")
        self.stop_button.set_halign(Gtk.Align.START)
        self.stop_button.set_sensitive(False)
        self.stop_button.connect("clicked", self.on_stop_clicked)
        action_box.append(self.stop_button)

        run_target_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        run_target_box.set_hexpand(True)
        run_target_label = Gtk.Label(label="Run through", xalign=0)
        run_target_box.append(run_target_label)
        self._run_until_dropdown = Gtk.DropDown.new_from_strings(["End of pipeline"])
        self._run_until_dropdown.set_hexpand(True)
        self._run_until_dropdown.set_tooltip_text(
            "Stop automatically after the selected step when running or resuming "
            "the pipeline."
        )
        self._run_until_dropdown.connect("notify::selected", self._on_run_until_changed)
        run_target_box.append(self._run_until_dropdown)
        action_box.append(run_target_box)

        self._edit_toc_button = Gtk.Button(label="Edit TOC")
        self._edit_toc_button.connect("clicked", self.on_edit_toc_clicked)
        action_box.append(self._edit_toc_button)

        content.append(action_box)

        activity_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        activity_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        activity_title = Gtk.Label(label="Activity", xalign=0)
        activity_title.add_css_class("dim-label")
        activity_header.append(activity_title)
        activity_status = Gtk.Label(label="No activity yet", xalign=0)
        activity_status.set_hexpand(True)
        activity_status.set_ellipsize(3)
        activity_status.add_css_class("caption")
        activity_status.add_css_class("dim-label")
        activity_header.append(activity_status)
        activity_section.append(activity_header)
        self._activity_status_label = activity_status

        terminal_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        terminal_frame.set_hexpand(True)
        terminal_frame.set_vexpand(False)
        terminal_frame.set_size_request(-1, 440)
        terminal_frame.set_overflow(Gtk.Overflow.HIDDEN)
        terminal_frame.add_css_class("recordprep-terminal-surface")
        terminal_frame.append(log_scroller)
        activity_section.append(terminal_frame)
        content.append(activity_section)

        self.step_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.step_list.add_css_class("boxed-list")
        content.append(self.step_list)
        self._build_pipeline_phase_rows()

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

        self.step_detect_transcript_layout_row = Adw.ActionRow(
            title="Detect transcript layout",
            subtitle="PI searches extracted text and opens only selected page images.",
        )
        self.step_detect_transcript_layout_row.set_activatable(False)
        self._attach_step_controls(
            "detect_transcript_layout",
            self.step_detect_transcript_layout_row,
            lambda _btn: self.on_step_detect_transcript_layout_clicked(
                self.step_detect_transcript_layout_row
            ),
        )
        self._attach_step_status(self.step_detect_transcript_layout_row)

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

        self.step_hearing_summaries_row = Adw.ActionRow(
            title="Create hearing summaries",
            subtitle="Summarize hearing testimony into concise paragraphs.",
        )
        self.step_hearing_summaries_row.set_activatable(False)
        self._attach_step_controls(
            "create_hearing_summaries",
            self.step_hearing_summaries_row,
            lambda _btn: self.on_create_hearing_summaries_clicked(
                self.step_hearing_summaries_row
            ),
        )
        self._attach_step_status(self.step_hearing_summaries_row)

        self.step_report_summaries_row = Adw.ActionRow(
            title="Create report summaries",
            subtitle="Summarize named reports into concise paragraphs.",
        )
        self.step_report_summaries_row.set_activatable(False)
        self._attach_step_controls(
            "create_report_summaries",
            self.step_report_summaries_row,
            lambda _btn: self.on_create_report_summaries_clicked(
                self.step_report_summaries_row
            ),
        )
        self._attach_step_status(self.step_report_summaries_row)

        self.step_minute_order_summaries_row = Adw.ActionRow(
            title="Create minute-order summaries",
            subtitle="Summarize dated minute orders into concise paragraphs.",
        )
        self.step_minute_order_summaries_row.set_activatable(False)
        self._attach_step_controls(
            "create_minute_order_summaries",
            self.step_minute_order_summaries_row,
            lambda _btn: self.on_create_minute_order_summaries_clicked(
                self.step_minute_order_summaries_row
            ),
        )
        self._attach_step_status(self.step_minute_order_summaries_row)

        self.step_add_hearing_date_links_row = Adw.ActionRow(
            title="Add links to summaries",
            subtitle="Add Markdown page links for hearing and minute-order first pages.",
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

        self.step_number_transcript_pages_row = Adw.ActionRow(
            title="Number transcript pages",
            subtitle="Identify official RT/CT page numbers and citation series with PI.",
        )
        self.step_build_participant_index_row = Adw.ActionRow(
            title="Build participant and witness index",
            subtitle="Verify hearing-scoped counsel, witnesses, and examinations with PI.",
        )
        self.step_create_case_overview_row = Adw.ActionRow(
            title="Create case overview",
            subtitle="Create a concise nonauthoritative orientation aid with PI.",
        )
        self.step_build_source_map_row = Adw.ActionRow(
            title="Build source map",
            subtitle="Publish direct-source Agent search metadata and source_map.json.",
        )
        agent_stage_rows = (
            (
                "number_transcript_pages",
                self.step_number_transcript_pages_row,
            ),
            (
                "build_participant_index",
                self.step_build_participant_index_row,
            ),
            (
                "create_case_overview",
                self.step_create_case_overview_row,
            ),
            (
                "build_source_map",
                self.step_build_source_map_row,
            ),
        )
        for step_id, row in agent_stage_rows:
            row.set_activatable(False)
            self._attach_step_controls(
                step_id,
                row,
                lambda _btn, current_step=step_id, current_row=row: (
                    self.on_agent_refinement_step_clicked(current_step, current_row)
                ),
            )
            self._attach_step_status(row)

        self._setup_menu(app)
        self._populate_run_until_dropdown()
        self._load_selected_pdfs()
        self._load_case_context()
        self._load_rt_ct_split()
        self._set_status(APPLICATION_NAME, False)
        self._refresh_step_statuses_from_artifacts()

    def _setup_menu(self, app: Adw.Application) -> None:
        menu = Gio.Menu()
        menu.append("Settings", "app.settings")
        menu.append("Test prompts…", "app.test-prompts")
        self.menu_button.set_menu_model(menu)

        action = Gio.SimpleAction.new("settings", None)
        action.connect("activate", self.on_settings)
        app.add_action(action)

        if app.lookup_action("save-settings") is None:
            save_action = Gio.SimpleAction.new("save-settings", None)
            save_action.connect("activate", self._on_action_save_settings)
            app.add_action(save_action)

        if app.lookup_action("test-prompts") is None:
            test_action = Gio.SimpleAction.new("test-prompts", None)
            test_action.connect("activate", self.on_test_prompts)
            app.add_action(test_action)

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

    def on_test_prompts(self, _action: Gio.SimpleAction, _param: object) -> None:
        if self._test_prompts_window:
            self._test_prompts_window.present()
            return
        test_window = TestPromptsWindow(self.get_application(), parent=self)
        test_window.connect("close-request", self._on_test_prompts_close_request)
        self._test_prompts_window = test_window
        test_window.present()

    def _on_test_prompts_close_request(self, _window: TestPromptsWindow) -> bool:
        self._test_prompts_window = None
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

    def _build_test_summarize_settings(self, mode_id: str) -> dict[str, Any]:
        if mode_id not in {"summarize_hearings", "summarize_reports", "summarize_minutes"}:
            raise ValueError(f"Unknown summarize test mode: {mode_id}")
        settings = load_summarize_settings()
        prompt_key = {
            "summarize_hearings": "hearings_prompt",
            "summarize_reports": "reports_prompt",
            "summarize_minutes": "minutes_prompt",
        }[mode_id]
        prompt = settings[prompt_key]
        if mode_id == "summarize_minutes":
            prompt += MINUTE_SUMMARY_WINDOW_GUIDANCE
        return {**settings, "prompt": prompt}

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


    def _test_summary_payloads(
        self,
        raw_text: str,
        settings: dict[str, Any],
        *,
        participant_context: str = "",
        report_marker: ReportProposalMarker | None = None,
    ) -> list[str]:
        source_pages = raw_text.split("\f") if "\f" in raw_text else [raw_text]
        with tempfile.TemporaryDirectory(prefix="recordprep-summary-test.") as temporary:
            text_dir = Path(temporary) / "text_pages"
            text_dir.mkdir()
            for index, text in enumerate(source_pages, start=1):
                (text_dir / f"{index:04d}.txt").write_text(text, encoding="utf-8")
            target_chars, max_pages = _summary_window_limits(settings)
            windows = _summary_page_windows(
                text_dir,
                1,
                len(source_pages),
                max_pages=max_pages,
                target_chars=target_chars,
                max_chars=DEFAULT_SUMMARIZE_WINDOW_MAX_CHARS,
            )
            return [
                _render_summary_window_payload(
                    window,
                    {page: f"TEST {page}" for page in range(1, len(source_pages) + 1)},
                    participant_context=participant_context,
                    report_marker=report_marker,
                )
                for window in windows
            ]

    def run_test_summarize(
        self,
        mode_id: str,
        raw_text: str,
        overrides: dict[str, Any],
        on_done: Callable[[str, str | None], None],
    ) -> None:
        def _worker() -> None:
            try:
                settings = self._build_test_summarize_settings(mode_id)
                settings.update({key: value for key, value in overrides.items() if value not in (None, "")})
                if not settings["api_url"] or not settings["model_id"] or not settings["api_key"]:
                    raise ValueError("Enter API URL, model ID, and API key.")
                participant_context = ""
                if mode_id == "summarize_hearings":
                    participant_context = "\n".join(
                        _hearing_context_lines({"counsel": [], "witness_status": "unknown", "witnesses": []})
                    )
                report_marker = None
                if mode_id == "summarize_reports":
                    source_pages = raw_text.split("\f") if "\f" in raw_text else [raw_text]
                    report_marker = _detect_report_proposal_marker(
                        {index: text for index, text in enumerate(source_pages, start=1)},
                        1,
                        len(source_pages),
                    )
                payloads = self._test_summary_payloads(
                    raw_text,
                    settings,
                    participant_context=participant_context,
                    report_marker=report_marker,
                )
                responses: list[str] = []
                for payload in payloads:
                    self._raise_if_stop_requested()
                    response = self._request_plain_text(settings, payload)
                    normalized = " ".join(response.split()).strip()
                    if mode_id == "summarize_reports" and normalized == NO_SUMMARIZABLE_REPORT_CONTENT:
                        continue
                    if normalized:
                        responses.append(normalized)
                GLib.idle_add(on_done, "\n\n".join(responses).strip(), None)
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

    def _feed_activity_terminal(self, text: str) -> None:
        terminal = self._activity_terminal
        if terminal is None or not text:
            return
        terminal.feed(text.encode("utf-8", errors="replace"))

    def _on_activity_terminal_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        terminal = self._activity_terminal
        if terminal is None:
            return False
        required = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
        if state & required != required:
            return False
        if keyval in (Gdk.KEY_c, Gdk.KEY_C):
            terminal.copy_clipboard_format(Vte.Format.TEXT)
            return True
        if keyval in (Gdk.KEY_v, Gdk.KEY_V):
            terminal.paste_clipboard()
            return True
        return False

    def _on_activity_terminal_child_exited(
        self,
        _terminal: Any,
        status: int,
    ) -> None:
        self._pi_terminal_active = False
        self._pi_terminal_pid = None
        try:
            self._pi_terminal_exit_status = os.waitstatus_to_exitcode(status)
        except (AttributeError, ValueError):
            self._pi_terminal_exit_status = int(status)
        done = self._pi_terminal_done
        if done is not None:
            done.set()
        if self._activity_terminal is not None:
            self._activity_terminal.set_input_enabled(False)

    def _append_log_message(self, message: str, level: str = "INFO") -> bool:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        text = _sanitize_terminal_log_text(message, preserve_newlines=False)
        if not text:
            return False
        level_normalized = str(level or "").upper()
        if level_normalized not in {"INFO", "WARN", "ERROR"}:
            level_normalized = self._infer_log_level(text)
        if self._activity_terminal is not None:
            self._feed_activity_terminal(_terminal_log_line(text, level_normalized))
        elif self._log_buffer is not None:
            end_iter = self._log_buffer.get_end_iter()
            self._log_buffer.insert(
                end_iter,
                f"[{timestamp}] [{level_normalized}] {text}\n",
            )
        if self._activity_status_label is not None:
            summary = text if len(text) <= 120 else f"{text[:117]}…"
            self._activity_status_label.set_label(summary)
            if level_normalized == "ERROR":
                self._open_phase_for_step(self._active_step_id)
        if self._log_view is not None:
            end_iter = self._log_buffer.get_end_iter()
            self._log_view.scroll_to_iter(end_iter, 0.0, False, 0.0, 1.0)
        return False

    def _append_raw_log_message(self, message: str, level: str = "INFO") -> bool:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        text = _sanitize_terminal_log_text(message, preserve_newlines=True)
        level_normalized = str(level or "INFO").upper()
        if self._activity_terminal is not None:
            self._feed_activity_terminal(_terminal_log_line(text, level_normalized))
        elif self._log_buffer is not None:
            end_iter = self._log_buffer.get_end_iter()
            self._log_buffer.insert(
                end_iter,
                f"[{timestamp}] [{level_normalized}] {text}\n",
            )
        if self._activity_status_label is not None and text:
            summary = text if len(text) <= 120 else f"{text[:117]}…"
            self._activity_status_label.set_label(summary)
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
        if self._edit_toc_button is not None:
            self._edit_toc_button.set_visible(enabled and not self._pipeline_running)
            self._edit_toc_button.set_sensitive(enabled and not self._pipeline_running)

    def _set_status(self, message: str, active: bool) -> None:
        self.status_label.set_text(message)
        if active:
            self.status_spinner.start()
        else:
            self.status_spinner.stop()

    def _build_pipeline_phase_rows(self) -> None:
        for phase_id, title, step_ids in PIPELINE_PHASES:
            phase_row = Adw.ExpanderRow(
                title=title,
                subtitle=_phase_progress_text(step_ids, self._step_status_values),
            )
            phase_row.set_expanded(False)
            phase_row.connect(
                "notify::expanded",
                self._on_phase_expanded,
                phase_id,
            )
            self._phase_rows[phase_id] = phase_row
            self.step_list.append(phase_row)

    def _on_phase_expanded(
        self,
        row: Adw.ExpanderRow,
        _pspec: GObject.ParamSpec,
        phase_id: str,
    ) -> None:
        if self._phase_expansion_updating or not row.get_expanded():
            return
        self._set_expanded_phase(phase_id)

    def _set_expanded_phase(self, phase_id: str | None) -> None:
        self._phase_expansion_updating = True
        try:
            for candidate_id, phase_row in self._phase_rows.items():
                phase_row.set_expanded(candidate_id == phase_id)
        finally:
            self._phase_expansion_updating = False

    def _refresh_phase_summaries(self) -> None:
        for phase_id, _title, step_ids in PIPELINE_PHASES:
            phase_row = self._phase_rows.get(phase_id)
            if phase_row is not None:
                phase_row.set_subtitle(
                    _phase_progress_text(step_ids, self._step_status_values)
                )

    def _open_first_incomplete_phase(self) -> None:
        completed = {
            step_id
            for step_id, status in self._step_status_values.items()
            if status in COMPLETED_STEP_STATUSES
        }
        self._set_expanded_phase(_first_incomplete_phase_id(completed))

    def _open_phase_for_step(self, step_id: str | None) -> None:
        if step_id:
            self._set_expanded_phase(PIPELINE_STEP_PHASE.get(step_id))

    def _attach_step_status(self, row: Adw.ActionRow) -> None:
        status_label = Gtk.Label(label="Pending", xalign=1)
        status_label.add_css_class("dim-label")
        row.add_suffix(status_label)
        menu_button = self._step_menu_buttons.get(row)
        if menu_button is not None:
            row.add_suffix(menu_button)
        self._step_status_labels[row] = status_label
        step_id = self._step_ids_by_row.get(row)
        if step_id:
            self._step_status_values[step_id] = "Pending"
        self._refresh_phase_summaries()

    def _attach_step_controls(
        self,
        step_id: str,
        row: Adw.ActionRow,
        run_one: Callable[[Gtk.Button], None],
    ) -> None:
        phase_id = PIPELINE_STEP_PHASE[step_id]
        self._step_rows_by_id[step_id] = row
        self._step_ids_by_row[row] = step_id
        self._phase_rows[phase_id].add_row(row)

        menu_button = Gtk.MenuButton(icon_name="view-more-symbolic")
        menu_button.add_css_class("flat")
        menu_button.set_tooltip_text(f"Actions for {row.get_title() or step_id}")
        popover = Gtk.Popover()
        action_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        action_box.set_margin_top(6)
        action_box.set_margin_bottom(6)
        action_box.set_margin_start(6)
        action_box.set_margin_end(6)
        run_one_button = Gtk.Button(label="Run this step")
        run_one_button.add_css_class("flat")
        run_from_button = Gtk.Button(label="Run from here")
        run_from_button.add_css_class("flat")

        def _run_one_clicked(button: Gtk.Button) -> None:
            popover.popdown()
            run_one(button)

        def _run_from_clicked(_button: Gtk.Button) -> None:
            popover.popdown()
            self.on_run_from_step_clicked(step_id)

        run_one_button.connect("clicked", _run_one_clicked)
        run_from_button.connect("clicked", _run_from_clicked)
        action_box.append(run_one_button)
        action_box.append(run_from_button)
        popover.set_child(action_box)
        menu_button.set_popover(popover)
        self._step_menu_buttons[row] = menu_button

    def _set_step_status(self, row: Adw.ActionRow, status: str) -> None:
        label = self._step_status_labels.get(row)
        if label is not None:
            label.set_text("✓" if status == "Done" else status)
            label.set_tooltip_text(status)
            if status == "Pending":
                label.add_css_class("dim-label")
            else:
                label.remove_css_class("dim-label")
        step_id = self._step_ids_by_row.get(row)
        if step_id:
            self._step_status_values[step_id] = status
        self._refresh_phase_summaries()

    def _report_step_progress(
        self,
        row: Adw.ActionRow,
        status: str,
        message: str | None = None,
        level: str = "INFO",
    ) -> None:
        GLib.idle_add(self._set_step_status, row, status)
        title = row.get_title() or "Working"
        GLib.idle_add(self._set_status, f"{title} — {status}", True)
        if message:
            GLib.idle_add(self._append_log_message, message, level)

    def _reset_step_statuses(self) -> None:
        for row in self._step_status_labels:
            self._set_step_status(row, "Pending")
        self._open_first_incomplete_phase()
        self._sync_pipeline_controls()

    def _refresh_step_statuses_from_artifacts(self) -> None:
        if self._pipeline_running:
            return
        root_dir = self._resolve_case_root()
        if root_dir is None:
            self._open_first_incomplete_phase()
            self._sync_pipeline_controls()
            return

        def _set_done(row: Adw.ActionRow, done: bool) -> None:
            self._set_step_status(row, "Done" if done else "Pending")

        for step_id, row, _handler in self._pipeline_steps():
            _set_done(row, self._step_artifact_complete(step_id, root_dir, self.selected_pdfs))
        self._open_first_incomplete_phase()
        self._sync_pipeline_controls()

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

    def _expected_create_files_page_numbers(
        self,
        root_dir: Path,
        selected_pdfs: Sequence[Path] | None = None,
    ) -> set[str]:
        pdf_paths = [path for path in (selected_pdfs or []) if path.exists()]
        if not pdf_paths:
            merged_pdf = root_dir / "temp" / "merged.pdf"
            if merged_pdf.exists():
                pdf_paths = [merged_pdf]
        if not pdf_paths:
            pdf_paths = [path for path in _manifest_input_pdf_paths(root_dir) if path.exists()]
        if not pdf_paths:
            return set()
        try:
            return _expected_page_numbers_from_pdfs(pdf_paths)
        except Exception:
            return set()

    def _step_artifact_complete(
        self,
        step_id: str,
        root_dir: Path,
        selected_pdfs: Sequence[Path] | None = None,
    ) -> bool:
        def _dir_has_files(path: Path, pattern: str) -> bool:
            try:
                return path.exists() and any(path.glob(pattern))
            except OSError:
                return False

        text_dir = root_dir / "text_pages"
        image_dir = root_dir / "image_pages"
        classification_dir = root_dir / "classification"
        artifacts_dir = root_dir / "artifacts"
        summaries_path, reports_path = _summary_output_paths(root_dir)
        minutes_path = _minutes_summary_output_path(root_dir)

        if step_id == "create_files":
            expected_pages = self._expected_create_files_page_numbers(root_dir, selected_pdfs)
            text_pages = _existing_numbered_stems(text_dir, "*.txt")
            image_pages = _existing_numbered_stems(image_dir, "*.png")
            if expected_pages:
                return text_pages >= expected_pages and image_pages >= expected_pages
            return bool(text_pages) and bool(image_pages)
        if step_id == "detect_transcript_layout":
            return read_resolved_layout(root_dir) is not None
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
            toc_path = artifacts_dir / "toc.txt"
            try:
                toc_lines = toc_path.read_text(
                    encoding="utf-8", errors="ignore"
                ).splitlines()
            except OSError:
                return False
            _corrected_lines, removals = _correct_toc_lines(toc_lines)
            return removals == 0
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
        if step_id == "create_hearing_summaries":
            return summaries_path.exists()
        if step_id == "create_report_summaries":
            return reports_path.exists()
        if step_id == "create_minute_order_summaries":
            return minutes_path.exists()
        if step_id == "add_hearing_date_links":
            return _has_page_markdown_links(summaries_path)
        if step_id in {
            "number_transcript_pages",
            "build_participant_index",
            "create_case_overview",
            "build_source_map",
        }:
            return pi_step_complete(step_id, root_dir)
        return False

    def _finish_step(self, row: Adw.ActionRow, success: bool | str | None) -> None:
        if isinstance(success, str):
            self._set_step_status(row, success)
            return
        self._set_step_status(row, "Done" if success else "Pending")

    def _start_step(self, row: Adw.ActionRow) -> None:
        title = row.get_title() or "Working"
        self._active_step_id = self._step_ids_by_row.get(row)
        self._open_phase_for_step(self._active_step_id)
        self._set_step_status(row, "Running")
        self._set_status(f"Working: {title}", True)
        self.show_toast(f"Working on {title}.", "INFO")

    def _stop_status(self) -> None:
        self._active_step_id = None
        self._set_status(APPLICATION_NAME, False)

    def _stop_status_if_idle(self) -> None:
        if not self._pipeline_running:
            self._stop_status()

    def _stop_button_if_idle(self) -> None:
        if not self._pipeline_running:
            self.stop_button.set_sensitive(False)
            self._sync_pipeline_controls()

    def _resume_is_available(self) -> bool:
        root_dir = self._resolve_case_root()
        if root_dir is None or not root_dir.exists():
            return False
        if not any(status == "Done" for status in self._step_status_values.values()):
            return False
        try:
            start_index = self._resume_start_index(
                root_dir,
                self._selected_run_until_step(),
            )
        except ValueError:
            return False
        if start_index is None:
            return False
        step_id = self._pipeline_steps()[start_index][0]
        return step_id != "create_files" or bool(self.selected_pdfs)

    def _sync_pipeline_controls(self) -> None:
        running = self._pipeline_running
        self.run_all_button.set_visible(not running)
        self.run_all_button.set_sensitive(not running and bool(self.selected_pdfs))
        self.resume_button.set_visible(not running and self._resume_is_available())
        self.resume_button.set_sensitive(not running)
        self.stop_button.set_visible(running)
        self.stop_button.set_sensitive(running and not self._stop_event.is_set())
        if self._run_until_dropdown is not None:
            self._run_until_dropdown.set_sensitive(not running)
        for menu_button in self._step_menu_buttons.values():
            menu_button.set_sensitive(not running)
        if self._rt_ct_split_dropdown is not None:
            self._rt_ct_split_dropdown.set_sensitive(not running)
        manual_split_selected = bool(
            self._rt_ct_split_dropdown is not None
            and self._rt_ct_split_dropdown.get_selected() == 1
        )
        if self._rt_ct_split_entry is not None:
            self._rt_ct_split_entry.set_sensitive(
                not running and manual_split_selected
            )
        if self._rt_ct_split_page_row is not None:
            self._rt_ct_split_page_row.set_sensitive(
                not running and manual_split_selected
            )
        self._update_toc_button()

    def _build_transcript_split_section(self) -> Adw.ExpanderRow:
        source_row = Adw.ExpanderRow(
            title="No case selected",
            subtitle="Choose a case bundle or PDF files",
        )
        source_row.set_expanded(False)

        dropdown = Adw.ComboRow(
            title="Transcript layout",
            subtitle=(
                "Automatic detection is the default; manual choices override "
                "the detected layout for this case only."
            ),
        )
        dropdown.set_model(
            Gtk.StringList.new(
                [
                    "Automatic detection",
                    "RT + CT",
                    "Reporter's transcript only",
                    "Clerk's transcript only",
                ]
            )
        )
        dropdown.connect("notify::selected", self._on_rt_ct_split_mode_changed)
        source_row.add_row(dropdown)

        page_row = Adw.ActionRow(
            title="RT ends at page",
            subtitle=(
                "Combined PDF file page, not an official RT citation page. "
                "Must be less than the combined PDF page count."
            ),
        )

        entry = Gtk.Entry()
        entry.set_width_chars(3)
        entry.set_max_width_chars(5)
        entry.set_max_length(5)
        entry.set_input_purpose(Gtk.InputPurpose.NUMBER)
        entry.connect("changed", self._on_rt_ct_split_entry_changed)
        entry.connect("activate", self._on_rt_ct_split_commit)
        entry.connect("notify::has-focus", self._on_rt_ct_split_focus_notify)
        page_row.add_suffix(entry)
        source_row.add_row(page_row)

        self._source_row = source_row
        self._rt_ct_split_dropdown = dropdown
        self._rt_ct_split_spin = None
        self._rt_ct_split_entry = entry
        self._rt_ct_split_page_row = page_row
        self._rt_ct_split_label = None
        return source_row

    def _loaded_layout_mode(self, root_dir: Path | None) -> str:
        if root_dir is not None:
            status, mode = detection_status(root_dir)
            if status == "resolved" and mode in {"rt_only", "ct_only", "split"}:
                return mode
        return "auto"

    def _update_source_summary(
        self,
        split_page: int | None = None,
        split_mode: str | None = None,
    ) -> None:
        source_row = self._source_row
        if source_row is None:
            return
        case_name, _base_dir = load_case_context()
        root_dir = self._resolve_case_root()
        case_current = _case_context_matches_selection(
            case_name, root_dir, self.selected_pdfs
        )
        if self.selected_pdfs and not case_current:
            case_name = ""
        display_case = _display_case_name(case_name) if case_name else ""
        if display_case:
            title = display_case
        elif len(self.selected_pdfs) == 1:
            title = self.selected_pdfs[0].name
        elif self.selected_pdfs:
            title = f"{len(self.selected_pdfs)} PDFs selected"
        else:
            title = "No case selected"

        if not display_case and not self.selected_pdfs:
            subtitle = "Choose a case bundle or PDF files"
        else:
            if root_dir is not None and root_dir.exists() and case_current:
                summary = layout_display_summary(root_dir)
            elif split_mode is not None and case_current:
                summary = _transcript_summary(split_mode or "split", split_page)
            else:
                summary = "Detection pending"
            source_description = "Existing case bundle"
            if len(self.selected_pdfs) == 1:
                source_description = self.selected_pdfs[0].name
            elif self.selected_pdfs:
                source_description = f"{len(self.selected_pdfs)} PDFs"
            subtitle = f"{source_description} • {summary}"
        source_row.set_title(title)
        source_row.set_subtitle(subtitle)

    def _set_rt_ct_split_ui(
        self, split_page: int | None, total_pages: int | None, split_mode: str
    ) -> None:
        entry = self._rt_ct_split_entry
        dropdown = self._rt_ct_split_dropdown
        if entry is None or dropdown is None:
            return
        self._rt_ct_split_updating = True
        if not entry.has_focus():
            entry.set_text(
                str(split_page)
                if split_page is not None and split_mode == "split"
                else ""
            )
        if split_mode == "rt_only":
            selected_index = 2
        elif split_mode == "ct_only":
            selected_index = 3
        elif split_mode == "split":
            selected_index = 1
        else:
            selected_index = 0
        dropdown.set_selected(selected_index)
        self._rt_ct_split_updating = False
        page_sensitive = split_mode == "split" and not self._pipeline_running
        entry.set_sensitive(page_sensitive)
        if self._rt_ct_split_page_row is not None:
            self._rt_ct_split_page_row.set_sensitive(page_sensitive)
        if split_mode == "split":
            entry.remove_css_class("dim-label")
        else:
            entry.add_css_class("dim-label")
        self._update_source_summary(split_page, split_mode)

    def _apply_pending_manual_layout(
        self, root_dir: Path
    ) -> None:
        """Apply an in-memory manual choice to a fresh bundle after Create files.

        The old cross-case config value is never used; a pending override is
        only ever case-local and is applied only when the bundle has no
        resolved artifact.
        """
        if self._rt_ct_split_mode_pending in {"split", "rt_only", "ct_only"}:
            mode = self._rt_ct_split_mode_pending
            rt_end = self._rt_ct_split_pending
            try:
                apply_manual_override(
                    root_dir,
                    mode=mode,
                    rt_end_file_page=rt_end,
                    note="Manual layout chosen before Create files completed.",
                )
                self._rt_ct_split_mode_pending = None
                self._rt_ct_split_pending = None
            except TranscriptLayoutError:
                self._rt_ct_split_mode_pending = None
                self._rt_ct_split_pending = None

    def _load_rt_ct_split(self) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None or not root_dir.exists():
            self._set_rt_ct_split_ui(None, None, "auto")
            return
        status, mode = detection_status(root_dir)
        if status != "resolved" and self._rt_ct_split_mode_pending in {
            "split",
            "rt_only",
            "ct_only",
        }:
            self._apply_pending_manual_layout(root_dir)
            status, mode = detection_status(root_dir)
        split_mode = "auto"
        split_page: int | None = None
        if status == "resolved" and mode in {"rt_only", "ct_only", "split"}:
            split_mode = mode
            if mode == "split":
                resolved = read_resolved_layout(root_dir)
                if resolved is not None:
                    split_page = int(resolved.get("rt_end_file_page") or 0) or None
        total_pages = _count_text_pages(root_dir / "text_pages")
        self._set_rt_ct_split_ui(split_page, total_pages, split_mode)
        self._update_source_summary(split_page, split_mode)

    def _on_rt_ct_split_mode_changed(
        self, dropdown: Gtk.DropDown, _pspec: GObject.ParamSpec
    ) -> None:
        if self._rt_ct_split_updating:
            return
        if self._pipeline_running:
            self.show_toast("Stop the pipeline before changing the transcript layout.")
            self._load_rt_ct_split()
            return
        selected = dropdown.get_selected()
        if selected == 0:
            self._rt_ct_split_mode_pending = None
            self._rt_ct_split_pending = None
            self._load_rt_ct_split()
            self._refresh_step_statuses_from_artifacts()
            return
        mode = "split" if selected == 1 else ("rt_only" if selected == 2 else "ct_only")
        root_dir = self._resolve_case_root()
        if root_dir is None or not root_dir.exists():
            self._rt_ct_split_mode_pending = mode
            self._set_rt_ct_split_ui(
                self._rt_ct_split_pending, None, mode
            )
            self.show_toast(
                "Create files first, then choose a manual transcript layout.",
                "INFO",
            )
            return
        if not (root_dir / "text_pages").exists():
            self._rt_ct_split_mode_pending = mode
            self._set_rt_ct_split_ui(
                self._rt_ct_split_pending, None, mode
            )
            self.show_toast(
                "Run Create files first, then choose a manual transcript layout.",
                "INFO",
            )
            return
        self._rt_ct_split_mode_pending = mode
        self._try_apply_manual_layout()
        self._refresh_step_statuses_from_artifacts()

    def _try_apply_manual_layout(self) -> bool:
        root_dir = self._resolve_case_root()
        mode = self._rt_ct_split_mode_pending
        if root_dir is None or mode not in {"split", "rt_only", "ct_only"}:
            return False
        if not (root_dir / "text_pages").exists():
            return False
        rt_end = self._rt_ct_split_pending
        if mode == "split" and rt_end is None:
            self._load_rt_ct_split()
            return False
        try:
            apply_manual_override(
                root_dir,
                mode=mode,
                rt_end_file_page=rt_end,
                note=(
                    "Manual transcript layout chosen in the transcript "
                    "expander."
                ),
            )
        except TranscriptLayoutError as exc:
            self.show_toast(str(exc), "WARN")
            if self._source_row is not None:
                self._source_row.set_expanded(True)
            return False
        self._rt_ct_split_mode_pending = None
        self._rt_ct_split_pending = None
        if self._has_layout_dependent_work(root_dir):
            self._bundle_reset_required = True
            self.show_toast(
                "Transcript layout changed; re-run Create files to rebuild "
                "from the new layout.",
                "WARN",
            )
        else:
            self.show_toast("Transcript layout updated.")
        return True

    def _commit_rt_ct_split_entry(self, entry: Gtk.Entry, allow_ui_update: bool) -> None:
        if self._rt_ct_split_updating:
            return
        raw = entry.get_text().strip()
        split_page = None
        if raw.isdigit():
            split_page = int(raw)
        self._rt_ct_split_pending = split_page
        if self._pipeline_running:
            return
        if self._try_apply_manual_layout():
            if allow_ui_update and not entry.has_focus():
                self._load_rt_ct_split()
        else:
            if allow_ui_update and not entry.has_focus():
                self._load_rt_ct_split()
            self._refresh_step_statuses_from_artifacts()

    def _on_rt_ct_split_commit(self, entry: Gtk.Entry) -> None:
        self._commit_rt_ct_split_entry(entry, allow_ui_update=False)

    def _on_rt_ct_split_entry_changed(self, entry: Gtk.Entry) -> None:
        raw = entry.get_text().strip()
        split_page = _normalize_rt_ct_split_page(int(raw) if raw.isdigit() else None)
        if split_page is not None:
            entry.remove_css_class("error")

    def _on_rt_ct_split_focus_notify(
        self, entry: Gtk.Entry, _pspec: GObject.ParamSpec
    ) -> None:
        has_focus = (
            entry.has_focus() if hasattr(entry, "has_focus") else entry.get_property("has-focus")
        )
        if not has_focus:
            self._commit_rt_ct_split_entry(entry, allow_ui_update=True)

    def _current_rt_ct_split_selection(self) -> tuple[str, int | None]:
        dropdown = self._rt_ct_split_dropdown
        entry = self._rt_ct_split_entry
        if dropdown is not None:
            selected = dropdown.get_selected()
            split_mode = "auto"
            if selected == 1:
                split_mode = "split"
            elif selected == 2:
                split_mode = "rt_only"
            elif selected == 3:
                split_mode = "ct_only"
        else:
            root_dir = self._resolve_case_root()
            split_mode = self._loaded_layout_mode(root_dir)
        if entry is not None:
            raw = entry.get_text().strip()
            split_page = _normalize_rt_ct_split_page(int(raw) if raw.isdigit() else None)
        else:
            root_dir = self._resolve_case_root()
            split_page = self._rt_ct_split_pending
        return split_mode, split_page

    def _has_layout_dependent_work(self, root_dir: Path) -> bool:
        """True when layout-dependent (destructive-cleanup) work exists."""
        if not root_dir.exists():
            return False
        classification = root_dir / "classification"
        if classification.is_dir() and any(classification.iterdir()):
            return True
        artifacts = root_dir / "artifacts"
        if artifacts.is_dir():
            for item in artifacts.iterdir():
                if item.name == "transcript_layout.json":
                    continue
                if item.is_file() or (item.is_dir() and any(item.iterdir())):
                    return True
        return False

    def _require_resolved_layout(
        self,
        allow_unresolved: bool = False,
    ) -> bool:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            self.show_toast("Choose PDF files or a case bundle first.", "WARN")
            return False
        if not root_dir.exists():
            # A fresh PDF selection may run pre-layout steps (Create files)
            # before the prospective case_bundle exists. Layout-dependent
            # steps stay gated until the bundle and transcript layout exist.
            fresh_pdf_selection = bool(
                allow_unresolved
                and self.selected_pdfs
                and _case_bundle_root_for_pdfs(self.selected_pdfs)
                == root_dir.expanduser().resolve(strict=False)
            )
            if not fresh_pdf_selection:
                self.show_toast("Choose PDF files or a case bundle first.", "WARN")
                return False
            return True
        mode, split_page = self._current_rt_ct_split_selection()
        if mode != "auto":
            self._rt_ct_split_mode_pending = mode
            self._rt_ct_split_pending = split_page
            if self._try_apply_manual_layout():
                return True
            self._load_rt_ct_split()
            return False
        if allow_unresolved:
            return True
        diagnostic = diagnose_layout(root_dir)
        if diagnostic.code != "resolved":
            if self._source_row is not None:
                self._source_row.set_expanded(True)
            self.show_toast(diagnostic.message, "WARN")
            return False
        return True

    def _ensure_rt_ct_split_ready(self) -> bool:
        return self._require_resolved_layout(allow_unresolved=False)

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

    def _classifier_worker_count(self, settings: dict[str, Any]) -> int:
        try:
            return max(1, int(settings.get("workers", DEFAULT_CLASSIFIER_WORKERS)))
        except (TypeError, ValueError):
            return DEFAULT_CLASSIFIER_WORKERS

    def _classify_image_with_page_type(
        self,
        settings: dict[str, Any],
        filename: str,
        image_path: Path,
        max_attempts: int = 3,
    ) -> dict[str, str]:
        entry: dict[str, str] = {}
        for attempt in range(1, max_attempts + 1):
            self._raise_if_stop_requested()
            entry = self._classify_image(settings, filename, image_path)
            page_type = _extract_entry_value(entry, "page_type", "pagetype").strip()
            if page_type:
                return entry
        raise RuntimeError(
            f"Classification basic returned blank page_type for {filename} "
            f"after {max_attempts} attempts."
        )

    def _run_classifier_jobs(
        self,
        jobs: list[tuple[Callable[..., dict[str, str]], tuple[Any, ...]]],
        workers: int,
    ) -> list[dict[str, str]]:
        return run_classifier_jobs(
            jobs,
            workers=workers,
            stop_check=self._raise_if_stop_requested,
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
        self._start_local_vision_server_log_reader(process)
        if LOCAL_VISION_SERVER_STARTUP_SECONDS > 0:
            time.sleep(LOCAL_VISION_SERVER_STARTUP_SECONDS)
        try:
            _wait_for_endpoint_ready(
                api_url,
                process=process,
                recent_output=self._local_vision_server_recent_output_text,
                stop_check=self._raise_if_stop_requested,
            )
        except Exception:
            self._stop_local_vision_server()
            raise
        return True

    def _start_local_vision_server_log_reader(self, process: subprocess.Popen[str]) -> None:
        with self._local_vision_server_log_lock:
            self._local_vision_server_recent_output.clear()
        if process.stdout is None:
            return

        def read_server_output() -> None:
            try:
                assert process.stdout is not None
                for line in process.stdout:
                    text = line.rstrip("\r\n")
                    with self._local_vision_server_log_lock:
                        self._local_vision_server_recent_output.append(text)
                    GLib.idle_add(self._append_raw_log_message, text, "SERVER")
            except Exception as exc:
                GLib.idle_add(
                    self._append_log_message,
                    f"Stopped reading llama.cpp server output: {exc}",
                    "WARN",
                )

        thread = threading.Thread(
            target=read_server_output,
            name="recordprep-llama-server-log-reader",
            daemon=True,
        )
        self._local_vision_server_log_thread = thread
        thread.start()

    def _local_vision_server_recent_output_text(self) -> str:
        with self._local_vision_server_log_lock:
            return "\n".join(self._local_vision_server_recent_output)

    def _stop_local_vision_server(self) -> None:
        process = self._local_vision_server_process
        owned = self._local_vision_server_owned
        self._local_vision_server_process = None
        self._local_vision_server_owned = False
        if process is None or not owned:
            return
        _stop_server(process)

    def _set_local_ocr_server_process(
        self,
        process: subprocess.Popen[str] | None,
    ) -> None:
        with self._local_ocr_server_lock:
            self._local_ocr_server_process = process

    def _stop_local_ocr_server(self) -> None:
        with self._local_ocr_server_lock:
            process = self._local_ocr_server_process
            self._local_ocr_server_process = None
        if process is not None:
            _stop_server(process)

    def on_stop_clicked(self, _button: Gtk.Button) -> None:
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        self.stop_button.set_sensitive(False)
        self._sync_pipeline_controls()
        self.show_toast("Stop requested.")
        self._stop_local_ocr_server()
        self._stop_local_vision_server()
        if self._pi_terminal_active:
            self._terminate_pi_terminal()

    def _on_main_close_request(self, *_args: object) -> bool:
        self._stop_event.set()
        self._stop_local_ocr_server()
        self._stop_local_vision_server()
        self._terminate_pi_terminal()
        return False

    def _terminate_pi_terminal(self) -> bool:
        pid = self._pi_terminal_pid
        if pid is None:
            return False
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return False
        except OSError as exc:
            self.show_toast(f"Unable to stop PI process: {exc}", "WARN")
            return False

        def _force_stop() -> bool:
            if self._pi_terminal_active and self._pi_terminal_pid == pid:
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
            return False

        GLib.timeout_add_seconds(3, _force_stop)
        return False

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
        self._bundle_reset_required = False
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
        selected_pdfs = sorted(paths, key=_natural_sort_key)
        root_dir = _case_bundle_root_for_pdfs(selected_pdfs)
        previous_root = _case_bundle_root_for_pdfs(self.selected_pdfs)
        selection_changed_in_place = bool(
            root_dir is not None
            and previous_root == root_dir
            and self.selected_pdfs
            and not _pdf_selections_equal(self.selected_pdfs, selected_pdfs)
        )
        manifest_inputs_changed = bool(
            root_dir is not None
            and _bundle_inputs_changed(root_dir, selected_pdfs)
        )
        self._bundle_reset_required = (
            selection_changed_in_place or manifest_inputs_changed
        )
        self.selected_pdfs = selected_pdfs
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
        root_dir = _case_bundle_root_for_pdfs(self.selected_pdfs)
        self._bundle_reset_required = bool(
            root_dir is not None
            and _bundle_inputs_changed(root_dir, self.selected_pdfs)
        )
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
        # A PDF selection is the source-identity authority; the persisted
        # name may only drive presentation when no PDFs are selected (an
        # explicit case-bundle choice). The prior context is not discarded.
        if not self.selected_pdfs and case_name:
            display_name = _display_case_name(case_name) or case_name
            self.selected_label.set_text(f"Selected: {display_name}")
        self._load_rt_ct_split()
        self._update_toc_button()
        self._refresh_step_statuses_from_artifacts()

    def _pipeline_steps(self) -> list[tuple[str, Adw.ActionRow, Callable[[], bool]]]:
        return [
            ("create_files", self.step_one_row, self._run_step_one),
            (
                "detect_transcript_layout",
                self.step_detect_transcript_layout_row,
                self._run_step_detect_transcript_layout,
            ),
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
            (
                "number_transcript_pages",
                self.step_number_transcript_pages_row,
                self._run_step_number_transcript_pages,
            ),
            (
                "build_participant_index",
                self.step_build_participant_index_row,
                self._run_step_build_participant_index,
            ),
            (
                "create_hearing_summaries",
                self.step_hearing_summaries_row,
                self._run_step_create_hearing_summaries,
            ),
            (
                "create_report_summaries",
                self.step_report_summaries_row,
                self._run_step_create_report_summaries,
            ),
            (
                "create_minute_order_summaries",
                self.step_minute_order_summaries_row,
                self._run_step_create_minute_order_summaries,
            ),
            (
                "add_hearing_date_links",
                self.step_add_hearing_date_links_row,
                self._run_step_add_hearing_date_links,
            ),
            (
                "create_case_overview",
                self.step_create_case_overview_row,
                self._run_step_create_case_overview,
            ),
            (
                "build_source_map",
                self.step_build_source_map_row,
                self._run_step_build_source_map,
            ),
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
        self._sync_pipeline_controls()

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
            if not self._step_artifact_complete(step_id, root_dir, self.selected_pdfs):
                return index
        return None

    def on_run_all_clicked(self, _button: Gtk.Button) -> None:
        if not self.selected_pdfs:
            self.show_toast("Choose PDF files first.")
            return
        if self._pipeline_running:
            self.show_toast("Pipeline already running.")
            return
        if not self._require_resolved_layout(allow_unresolved=True):
            return
        end_step_id = self._selected_run_until_step()
        self._stop_event.clear()
        self._run_completion_message = None
        self._run_pause_message = None
        self._pi_terminal_sequence_started = False
        self._pipeline_running = True
        self.run_all_button.set_sensitive(False)
        self.resume_button.set_sensitive(False)
        self.stop_button.set_sensitive(True)
        if self._run_until_dropdown:
            self._run_until_dropdown.set_sensitive(False)
        self._sync_pipeline_controls()
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
        start_needs_resolved = _step_requires_resolved_layout(start_step_id)
        if not self._require_resolved_layout(allow_unresolved=not start_needs_resolved):
            return
        if start_step_id == "create_files" and not self.selected_pdfs:
            self.show_toast("Choose PDF files first to resume Create files.")
            return
        label = start_row.get_title() or start_step_id
        self.show_toast(f"Resuming at {label}.", "INFO")
        self._stop_event.clear()
        self._run_completion_message = None
        self._run_pause_message = None
        self._pi_terminal_sequence_started = False
        self._pipeline_running = True
        self.run_all_button.set_sensitive(False)
        self.resume_button.set_sensitive(False)
        self.stop_button.set_sensitive(True)
        if self._run_until_dropdown:
            self._run_until_dropdown.set_sensitive(False)
        self._sync_pipeline_controls()
        threading.Thread(
            target=self._run_steps_from_index,
            args=(start_index, root_dir, end_step_id, True),
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
        if _step_requires_resolved_layout(step_id):
            root_dir = self._resolve_case_root()
            if root_dir is None or not root_dir.exists():
                if self.selected_pdfs:
                    self.show_toast("Selected PDFs must be in the same folder.")
                else:
                    self.show_toast("Choose PDF files or select a saved case first.")
                return
        if not self._require_resolved_layout(
            allow_unresolved=not _step_requires_resolved_layout(step_id)
        ):
            return
        start_index = step_ids.index(step_id)
        root_dir = self._resolve_case_root()
        self._stop_event.clear()
        self._run_completion_message = None
        self._run_pause_message = None
        self._pi_terminal_sequence_started = False
        self._pipeline_running = True
        self.run_all_button.set_sensitive(False)
        self.resume_button.set_sensitive(False)
        self.stop_button.set_sensitive(True)
        if self._run_until_dropdown:
            self._run_until_dropdown.set_sensitive(False)
        self._sync_pipeline_controls()
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
        if not self._require_resolved_layout(
            allow_unresolved=not _step_requires_resolved_layout(
                step_id or ""
            )
        ):
            return
        self._stop_event.clear()
        self._run_completion_message = None
        self._run_pause_message = None
        self._pi_terminal_sequence_started = False
        self._pipeline_running = True
        self.run_all_button.set_sensitive(False)
        self.resume_button.set_sensitive(False)
        self.stop_button.set_sensitive(True)
        if self._run_until_dropdown:
            self._run_until_dropdown.set_sensitive(False)
        self._sync_pipeline_controls()
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
                root_dir = self._resolve_case_root()
                if root_dir is None:
                    raise ValueError("Choose PDF files or a case bundle first.")
                diagnostic = diagnose_layout(root_dir)
                if diagnostic.code != "resolved":
                    raise ValueError(diagnostic.message)
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
        self._sync_pipeline_controls()
        pause_message = self._run_pause_message
        self._run_pause_message = None
        if pause_message:
            self.show_toast(pause_message, "WARN")

    def on_step_one_clicked(self, _row: Adw.ActionRow) -> None:
        if not self.selected_pdfs:
            self.show_toast("Choose PDF files first.")
            return
        self._launch_single_step(
            self.step_one_row, self._run_step_one, "create_files"
        )

    def on_step_detect_transcript_layout_clicked(
        self, _row: Adw.ActionRow
    ) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None or not root_dir.exists():
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        text_dir = root_dir / "text_pages"
        if not text_dir.exists() or not any(text_dir.glob("*.txt")):
            self.show_toast("Run Create files to generate text files first.")
            return
        self._launch_single_step(
            self.step_detect_transcript_layout_row,
            self._run_step_detect_transcript_layout,
            "detect_transcript_layout",
        )

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
            root_dir = base_dir / "case_bundle"
            pending_split = self._rt_ct_split_pending
            pending_mode = self._rt_ct_split_mode_pending
            reset_required = (
                self._bundle_reset_required
                or _bundle_inputs_changed(root_dir, self.selected_pdfs)
            )
            if reset_required:
                GLib.idle_add(
                    self._append_log_message,
                    "New PDF selection detected; clearing the previous generated bundle.",
                    "INFO",
                )
                _reset_generated_case_bundle(root_dir)
                self._bundle_reset_required = False
            root_dir, text_dir, image_pages_dir = _ensure_case_bundle_dirs(base_dir)
            if len(self.selected_pdfs) > 1:
                temp_dir = root_dir / "temp"
                temp_dir.mkdir(parents=True, exist_ok=True)
                merged_path = temp_dir / "merged.pdf"
                pdf_path = _merge_pdfs(self.selected_pdfs, merged_path)
            else:
                pdf_path = self.selected_pdfs[0]
            _write_manifest(
                root_dir,
                self.selected_pdfs,
                pipeline_info={"active_step": "create_files"},
                rt_ct_split_page=pending_split,
                rt_ct_split_mode=pending_mode,
            )
            self._raise_if_stop_requested()
            text_source = load_text_source_setting()
            if text_source == TEXT_SOURCE_LOCAL_OCR:
                ocr_settings = load_local_ocr_settings()
                _generate_text_files_with_local_ocr(
                    pdf_path,
                    text_dir,
                    image_pages_dir,
                    stop_check=self._raise_if_stop_requested,
                    server_process_changed=self._set_local_ocr_server_process,
                    server_url=ocr_settings["server_url"],
                    start_command=ocr_settings["start_command"],
                    model_id=ocr_settings["model_id"],
                    workers=ocr_settings["workers"],
                    slots=ocr_settings["slots"],
                )
            else:
                _generate_text_files(pdf_path, text_dir)
                self._raise_if_stop_requested()
                _generate_image_page_files(pdf_path, image_pages_dir)
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, _format_create_files_error(exc))
        else:
            success = True
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "create_files",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            GLib.idle_add(self._load_rt_ct_split)
            if (
                self._rt_ct_split_mode_pending in {"split", "rt_only", "ct_only"}
                and read_resolved_layout(root_dir) is None
            ):
                self._apply_pending_manual_layout(root_dir)
                GLib.idle_add(self._load_rt_ct_split)
            GLib.idle_add(self.show_toast, "Create files complete.")
        finally:
            GLib.idle_add(self.step_one_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_one_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True

    def _run_step_detect_transcript_layout(self) -> bool:
        """Run the PI detection skill, then apply legacy-mismatch handling.

        A structurally valid needs_review artifact is accepted by the PI
        runner but is not pipeline-complete: the pipeline pauses with a
        "needs review" message and the user chooses a manual layout.
        """
        success = self._run_pi_skill_step(
            "detect_transcript_layout",
            self.step_detect_transcript_layout_row,
        )
        if not success:
            return False
        root_dir = self._resolve_case_root()
        if root_dir is None:
            return True
        status, _mode = detection_status(root_dir)
        if status != "resolved":
            self._run_pause_message = (
                "Transcript layout needs review: choose a manual layout to "
                "continue (open the transcript expander)."
            )
            return False
        if _layout_matches_legacy(root_dir):
            return True
        if not self._has_layout_dependent_work(root_dir):
            return True
        self._run_pause_message = (
            "Detected transcript layout differs from the legacy split; "
            "re-run Create files to rebuild from the new layout."
        )
        self._bundle_reset_required = True
        return False

    def _run_step_strip_nonstandard(self) -> bool:
        success: bool | None = False
        guard = None
        rewritten_sizes: dict[str, int] = {}

        def _rebind_after_writes() -> None:
            if guard is not None and rewritten_sizes:
                finalize_layout_rebind(guard, rewritten_sizes)

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
            try:
                guard = capture_layout_rebind_guard(root_dir)
                split_page, _ct_start, _need_rt, _need_ct, split_mode = (
                    _resolve_rt_ct_split(root_dir, text_dir)
                )
            except TranscriptLayoutError as exc:
                raise ValueError(str(exc)) from exc
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
                    try:
                        text_path.write_text(processed, encoding="utf-8")
                    finally:
                        if text_path.is_file():
                            rewritten_sizes[text_path.name] = text_path.stat().st_size
            _rebind_after_writes()
        except StopRequested:
            try:
                _rebind_after_writes()
            except TranscriptLayoutError as exc:
                success = False
                GLib.idle_add(
                    self.show_toast,
                    f"Process text files failed while refreshing transcript layout: {exc}",
                )
            else:
                success = None
        except Exception as exc:
            rebind_error: Exception | None = (
                exc if isinstance(exc, TranscriptLayoutError) else None
            )
            if rebind_error is None:
                try:
                    _rebind_after_writes()
                except TranscriptLayoutError as caught:
                    rebind_error = caught
            if rebind_error is not None and rebind_error is not exc:
                exc = ValueError(f"{exc}; transcript-layout refresh failed: {rebind_error}")
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




    def on_create_hearing_summaries_clicked(self, _row: Adw.ActionRow) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(
            self.step_hearing_summaries_row,
            self._run_step_create_hearing_summaries,
        )

    def on_create_report_summaries_clicked(self, _row: Adw.ActionRow) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(
            self.step_report_summaries_row,
            self._run_step_create_report_summaries,
        )

    def on_create_minute_order_summaries_clicked(self, _row: Adw.ActionRow) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(
            self.step_minute_order_summaries_row,
            self._run_step_create_minute_order_summaries,
        )

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



    def on_agent_refinement_step_clicked(
        self,
        step_id: str,
        row: Adw.ActionRow,
    ) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        handlers = {
            "number_transcript_pages": self._run_step_number_transcript_pages,
            "build_participant_index": self._run_step_build_participant_index,
            "create_case_overview": self._run_step_create_case_overview,
            "build_source_map": self._run_step_build_source_map,
        }
        handler = handlers.get(step_id)
        if handler is None:
            self.show_toast(f"Unknown Agent Refinement step: {step_id}")
            return
        self._launch_single_step(
            row,
            handler,
            step_id,
        )

    def _run_all_steps(self, end_step_id: str | None = None) -> None:
        root_dir = self._resolve_case_root()
        self._run_steps_from_index(0, root_dir, end_step_id=end_step_id)

    def _run_steps_from_index(
        self,
        start_index: int,
        root_dir: Path | None,
        end_step_id: str | None = None,
        skip_completed_steps: bool = False,
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
            and not (
                skip_completed_steps
                and root_dir is not None
                and self._step_artifact_complete(
                    step_id,
                    root_dir,
                    self.selected_pdfs,
                )
            )
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
                if (
                    skip_completed_steps
                    and root_dir is not None
                    and self._step_artifact_complete(
                        step_id,
                        root_dir,
                        self.selected_pdfs,
                    )
                ):
                    GLib.idle_add(self._finish_step, row, "Skipped")
                    continue
                if manage_local_vision and offset == first_classify_offset:
                    if root_dir is None:
                        raise ValueError("Choose PDF files or a case bundle first.")
                    diagnostic = diagnose_layout(root_dir)
                    if diagnostic.code != "resolved":
                        raise ValueError(diagnostic.message)
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
        self._sync_pipeline_controls()
        pause_message = self._run_pause_message
        self._run_pause_message = None
        completion_message = self._run_completion_message
        self._run_completion_message = None
        if stop_requested:
            self.show_toast("Pipeline stopped.")
        elif pause_message:
            self.show_toast(pause_message, "WARN")
        elif completion_message:
            self.show_toast(completion_message)
        elif success:
            self.show_toast("Pipeline complete.")
        else:
            self.show_toast("Pipeline stopped. Fix the errors and try again.")

    def _spawn_pi_skill_terminal(
        self,
        root_dir: Path,
        command_argv: list[str],
        step_id: str,
        step_title: str,
        done: threading.Event,
    ) -> bool:
        terminal = self._activity_terminal
        if Vte is None or terminal is None:
            self._pi_terminal_spawn_error = (
                "Embedded terminal support requires GTK4 VTE "
                "(gir1.2-vte-3.91 and libvte-2.91-gtk4-0)."
            )
            done.set()
            return False
        env = os.environ.copy()
        env.update(
            {
                "RECORDPREP_CASE_BUNDLE": str(root_dir),
                "RECORDPREP_PI_PROJECT_DIR": str(PI_PROJECT_DIR),
                "RECORDPREP_PI_COMMAND_ARGC": str(len(command_argv)),
            }
        )
        for index, arg in enumerate(command_argv):
            env[f"RECORDPREP_PI_COMMAND_ARG_{index}"] = arg
        executable = Path(command_argv[0]).expanduser()
        if executable.is_absolute():
            env["PATH"] = str(executable.parent) + os.pathsep + env.get("PATH", "")

        self._pi_terminal_done = done
        self._pi_terminal_exit_status = None
        self._pi_terminal_spawn_error = None
        self._pi_terminal_active = True
        self._pi_terminal_pid = None
        self._pi_stall_warned = False
        if not self._pi_terminal_sequence_started:
            terminal.reset(False, False)
            self._pi_terminal_sequence_started = True
        terminal.set_input_enabled(True)
        _apply_recordprep_terminal_theme(terminal)
        if self._activity_status_label is not None:
            self._activity_status_label.set_label(f"{step_title} running…")
        try:
            terminal.spawn_async(
                Vte.PtyFlags.DEFAULT,
                str(PROJECT_DIR),
                [sys.executable, str(PI_SKILL_RUNNER), step_id],
                [f"{key}={value}" for key, value in env.items()],
                GLib.SpawnFlags.DEFAULT,
                None,
                None,
                -1,
                None,
                self._on_pi_skill_terminal_spawned,
                None,
            )
        except Exception as exc:  # noqa: BLE001
            self._pi_terminal_active = False
            self._pi_terminal_spawn_error = str(exc)
            done.set()
        return False

    def _on_pi_skill_terminal_spawned(
        self,
        _terminal: Any,
        pid: int,
        error: GLib.Error | None,
        _user_data: object,
    ) -> None:
        if error is not None:
            self._pi_terminal_active = False
            self._pi_terminal_pid = None
            self._pi_terminal_spawn_error = error.message
            if self._pi_terminal_done is not None:
                self._pi_terminal_done.set()
            return
        self._pi_terminal_pid = pid
        if self._activity_terminal is not None:
            self._activity_terminal.grab_focus()
        if self._stop_event.is_set():
            self._terminate_pi_terminal()

    def _run_pi_skill_step(
        self,
        step_id: str,
        row: Adw.ActionRow,
    ) -> bool:
        success: bool | None = False
        root_dir: Path | None = None
        step_title = (row.get_title() or step_id).strip() or step_id
        try:
            self._raise_if_stop_requested()
            root_dir = self._resolve_case_root()
            if root_dir is None:
                raise ValueError("Choose a case bundle first.")
            if Vte is None or self._activity_terminal is None:
                raise ValueError(
                    f"GTK4 VTE is required for {step_title} "
                    "(gir1.2-vte-3.91 and libvte-2.91-gtk4-0)."
                )
            if not PI_SKILL_RUNNER.is_file():
                raise ValueError(f"PI skill runner not found: {PI_SKILL_RUNNER}")

            command = load_pi_agent_command_setting()
            try:
                command_argv = resolve_pi_agent_argv(
                    command,
                    path_env=os.environ.get("PATH"),
                )
            except ValueError as exc:
                raise ValueError(f"Invalid PI command: {exc}") from exc
            if not command_argv:
                raise ValueError("PI command is empty.")
            incompatible_flag = incompatible_pi_agent_flag(command_argv)
            if incompatible_flag:
                raise ValueError(
                    f"PI option {incompatible_flag} is incompatible with RecordPrep."
                )
            executable = command_argv[0]
            if os.path.sep in executable:
                executable_path = Path(executable).expanduser()
                if not executable_path.is_file() or not os.access(
                    executable_path,
                    os.X_OK,
                ):
                    raise ValueError(
                        "PI executable not found. Install PI or set the PI command "
                        "in Settings."
                    )
                command_argv[0] = str(executable_path)
            elif shutil.which(executable) is None:
                raise ValueError(
                    "PI executable not found. Install PI or set the PI command in Settings."
                )

            self._active_bundle_root = str(root_dir)
            GLib.idle_add(self._append_log_message, f"Case bundle: {root_dir}", "INFO")
            if str(root_dir) not in self._bundle_identity_warning_roots:
                self._bundle_identity_warning_roots.add(str(root_dir))
                for message in case_identity_conflicts(root_dir):
                    GLib.idle_add(self.show_toast, message, "WARN")
                    GLib.idle_add(self._append_log_message, message, "WARN")

            done = threading.Event()
            GLib.idle_add(
                self._spawn_pi_skill_terminal,
                root_dir,
                command_argv,
                step_id,
                step_title,
                done,
            )
            next_stall_poll = 0.0
            next_progress_poll = 0.0
            revealed_progress: tuple[int, int] | None = None
            while not done.wait(0.1):
                if self._stop_event.is_set():
                    GLib.idle_add(self._terminate_pi_terminal)
                    break
                now = time.monotonic()
                if now >= next_stall_poll:
                    next_stall_poll = now + PI_STAGE_STATUS_POLL_SECONDS
                    status = _read_pi_stage_status(root_dir, self._pi_terminal_pid)
                    if (
                        status is not None
                        and status.get("state") == "stalled"
                        and not self._pi_stall_warned
                    ):
                        self._pi_stall_warned = True
                        message = (
                            f"{step_title} may be stalled: PI has no session "
                            "progress and may be spinning or hung. "
                            + str(status.get("message") or "")
                            + " Use the Stop button to terminate it."
                        )
                        GLib.idle_add(self.show_toast, message, "WARN")
                        GLib.idle_add(self._append_log_message, message, "WARN")
                if (
                    step_id == "build_participant_index"
                    and now >= next_progress_poll
                ):
                    next_progress_poll = now + PARTICIPANT_PROGRESS_POLL_SECONDS
                    progress = _participant_review_progress(root_dir)
                    if progress != revealed_progress:
                        revealed_progress = progress
                        if progress is not None:
                            GLib.idle_add(
                                self._set_activity_status_text,
                                f"{step_title} — reviewed {progress[0]} of "
                                f"{progress[1]} hearings",
                            )
            self._raise_if_stop_requested()
            if self._pi_terminal_spawn_error:
                raise ValueError(
                    f"Unable to start embedded PI: {self._pi_terminal_spawn_error}"
                )
            if self._pi_terminal_exit_status != 0:
                raise ValueError(
                    f"{step_title} failed with exit code "
                    f"{self._pi_terminal_exit_status}."
                )

            success = True
            GLib.idle_add(self.show_toast, f"{step_title} complete.")
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"{step_title} failed: {exc}")
        finally:
            self._pi_terminal_done = None
            self._cleanup_pi_stage_status(root_dir)
            GLib.idle_add(row.set_sensitive, True)
            GLib.idle_add(self._finish_step, row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True

    def _cleanup_pi_stage_status(self, root_dir: Path | None) -> None:
        if root_dir is None:
            return
        try:
            (root_dir / PI_STAGE_STATUS_RELATIVE).unlink(missing_ok=True)
        except OSError:
            pass

    def _set_activity_status_text(self, text: str) -> None:
        if self._activity_status_label is not None:
            self._activity_status_label.set_label(text)

    def _run_step_number_transcript_pages(self) -> bool:
        return self._run_pi_skill_step(
            "number_transcript_pages",
            self.step_number_transcript_pages_row,
        )

    def _run_step_build_participant_index(self) -> bool:
        return self._run_pi_skill_step(
            "build_participant_index",
            self.step_build_participant_index_row,
        )

    def _run_step_create_case_overview(self) -> bool:
        return self._run_pi_skill_step(
            "create_case_overview",
            self.step_create_case_overview_row,
        )

    def _run_step_build_source_map(self) -> bool:
        return self._run_pi_skill_step(
            "build_source_map",
            self.step_build_source_map_row,
        )

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
            local_vision_enabled = bool(shared_settings.get("local_vision_enabled", False))
            workers = self._classifier_worker_count(shared_settings)
            pending_pages: list[tuple[bool, str]] = []
            jobs: list[tuple[Callable[..., dict[str, str]], tuple[Any, ...]]] = []

            def append_basic_entry(is_rt: bool, file_name: str, entry: dict[str, str]) -> None:
                target_path = rt_basic_path if is_rt else ct_basic_path
                with target_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(entry))
                    handle.write("\n")
                if is_rt:
                    done_rt.add(file_name)
                else:
                    done_ct.add(file_name)

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
                pending_pages.append((is_rt, text_path.name))
                jobs.append(
                    (
                        self._classify_image_with_page_type,
                        (
                            basic_rt_settings if is_rt else basic_ct_settings,
                            text_path.name,
                            image_path,
                            3,
                        ),
                    )
                )
            for (is_rt, file_name), entry in zip(
                pending_pages,
                self._run_classifier_jobs(jobs, workers),
                strict=True,
            ):
                self._raise_if_stop_requested()
                append_basic_entry(is_rt, file_name, entry)
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
            workers = self._classifier_worker_count(settings)

            def _queue_page_type_update(
                jobs: list[tuple[Callable[..., dict[str, str]], tuple[Any, ...]]],
                metadata: list[tuple[dict[str, Any], str, tuple[str, ...]]],
                entry: dict[str, Any],
                target_types: tuple[str, ...],
                updated_type: str,
                prompt: str,
                truthy_keys: tuple[str, ...],
            ) -> None:
                page_type = _extract_entry_value(entry, "page_type", "pagetype").strip().lower()
                if page_type not in target_types:
                    return
                file_name = _extract_entry_value(entry, "file_name", "filename")
                if not file_name:
                    return
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
                jobs.append((self._classify_image, (payload, file_name, image_path)))
                metadata.append((entry, updated_type, truthy_keys))

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
                rt_pending_entries: list[dict[str, Any]] = []
                rt_jobs: list[tuple[Callable[..., dict[str, str]], tuple[Any, ...]]] = []
                rt_metadata: list[tuple[dict[str, Any], str, tuple[str, ...]]] = []
                for entry in rt_entries:
                    self._raise_if_stop_requested()
                    file_name = _extract_entry_value(entry, "file_name", "filename")
                    if file_name and rt_resume_key is not None:
                        if _natural_sort_key(file_name) <= rt_resume_key:
                            continue
                    if file_name and file_name in rt_done:
                        continue
                    rt_pending_entries.append(entry)
                    _queue_page_type_update(
                        rt_jobs,
                        rt_metadata,
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
                    )
                for (entry, updated_type, truthy_keys), response in zip(
                    rt_metadata,
                    self._run_classifier_jobs(rt_jobs, workers),
                    strict=True,
                ):
                    if _is_truthy(_extract_entry_value(response, *truthy_keys)):
                        entry["page_type"] = updated_type
                        updates += 1
                with rt_advanced_path.open(rt_mode, encoding="utf-8") as handle:
                    for entry in rt_pending_entries:
                        self._raise_if_stop_requested()
                        file_name = _extract_entry_value(entry, "file_name", "filename")
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
                ct_pending_entries: list[dict[str, Any]] = []
                ct_jobs: list[tuple[Callable[..., dict[str, str]], tuple[Any, ...]]] = []
                ct_metadata: list[tuple[dict[str, Any], str, tuple[str, ...]]] = []
                for entry in ct_entries:
                    self._raise_if_stop_requested()
                    file_name = _extract_entry_value(entry, "file_name", "filename")
                    if file_name and ct_resume_key is not None:
                        if _natural_sort_key(file_name) <= ct_resume_key:
                            continue
                    if file_name and file_name in ct_done:
                        continue
                    ct_pending_entries.append(entry)
                    _queue_page_type_update(
                        ct_jobs,
                        ct_metadata,
                        entry,
                        ("ct_minute_order",),
                        "CT_minute_order_first_page",
                        settings["minute_prompt"],
                        ("first_page", "first", "is_first_page", "is_first"),
                    )
                    _queue_page_type_update(
                        ct_jobs,
                        ct_metadata,
                        entry,
                        ("ct_form",),
                        "CT_form_first_page",
                        settings["form_prompt"],
                        ("first_page", "first", "is_first_page", "is_first"),
                    )
                for (entry, updated_type, truthy_keys), response in zip(
                    ct_metadata,
                    self._run_classifier_jobs(ct_jobs, workers),
                    strict=True,
                ):
                    if _is_truthy(_extract_entry_value(response, *truthy_keys)):
                        entry["page_type"] = updated_type
                        updates += 1
                with ct_advanced_path.open(ct_mode, encoding="utf-8") as handle:
                    for entry in ct_pending_entries:
                        self._raise_if_stop_requested()
                        file_name = _extract_entry_value(entry, "file_name", "filename")
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
            workers = self._classifier_worker_count(shared_settings)
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
                rt_pending_entries: list[dict[str, Any]] = []
                rt_jobs: list[tuple[Callable[..., dict[str, str]], tuple[Any, ...]]] = []
                rt_metadata: list[dict[str, Any]] = []
                for entry in rt_entries:
                    self._raise_if_stop_requested()
                    page_type = _extract_entry_value(entry, "page_type", "pagetype").strip().lower()
                    file_name = _extract_entry_value(entry, "file_name", "filename")
                    if file_name and rt_resume_key is not None:
                        if _natural_sort_key(file_name) <= rt_resume_key:
                            continue
                    if file_name and file_name in rt_done:
                        continue
                    rt_pending_entries.append(entry)
                    if page_type in hearing_first_types and not _extract_entry_value(entry, "date") and file_name:
                        image_path = _image_path_for_filename(file_name, image_dir)
                        rt_jobs.append(
                            (
                                self._classify_image,
                                (
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
                                ),
                            )
                        )
                        rt_metadata.append(entry)
                for entry, response in zip(
                    rt_metadata,
                    self._run_classifier_jobs(rt_jobs, workers),
                    strict=True,
                ):
                    date_value = _extract_entry_value(response, "date")
                    if date_value:
                        entry["date"] = date_value
                        updates += 1
                with rt_dated_path.open(rt_mode, encoding="utf-8") as handle:
                    for entry in rt_pending_entries:
                        self._raise_if_stop_requested()
                        file_name = _extract_entry_value(entry, "file_name", "filename")
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
                ct_pending_entries: list[dict[str, Any]] = []
                ct_jobs: list[tuple[Callable[..., dict[str, str]], tuple[Any, ...]]] = []
                ct_metadata: list[dict[str, Any]] = []
                for entry in ct_entries:
                    self._raise_if_stop_requested()
                    page_type = _extract_entry_value(entry, "page_type", "pagetype").strip().lower()
                    file_name = _extract_entry_value(entry, "file_name", "filename")
                    if file_name and ct_resume_key is not None:
                        if _natural_sort_key(file_name) <= ct_resume_key:
                            continue
                    if file_name and file_name in ct_done:
                        continue
                    ct_pending_entries.append(entry)
                    if page_type in minute_first_types and not _extract_entry_value(entry, "date") and file_name:
                        image_path = _image_path_for_filename(file_name, image_dir)
                        ct_jobs.append(
                            (
                                self._classify_image,
                                (
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
                                ),
                            )
                        )
                        ct_metadata.append(entry)
                for entry, response in zip(
                    ct_metadata,
                    self._run_classifier_jobs(ct_jobs, workers),
                    strict=True,
                ):
                    date_value = _extract_entry_value(response, "date")
                    if date_value:
                        entry["date"] = date_value
                        updates += 1
                with ct_dated_path.open(ct_mode, encoding="utf-8") as handle:
                    for entry in ct_pending_entries:
                        self._raise_if_stop_requested()
                        file_name = _extract_entry_value(entry, "file_name", "filename")
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
            workers = self._classifier_worker_count(shared_settings)
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
                ct_pending_entries: list[dict[str, Any]] = []
                ct_jobs: list[tuple[Callable[..., dict[str, str]], tuple[Any, ...]]] = []
                ct_metadata: list[tuple[dict[str, Any], tuple[str, ...], bool]] = []
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
                    ct_pending_entries.append(entry)
                    if (
                        is_report_start
                        and (
                            not _extract_entry_value(entry, "name", "report_name")
                            or not _extract_entry_value(entry, "date", "report_date")
                        )
                        and file_name
                    ):
                        image_path = _image_path_for_filename(file_name, image_dir)
                        ct_jobs.append(
                            (
                                self._classify_image,
                                (
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
                                ),
                            )
                        )
                        ct_metadata.append((entry, ("name", "report_name"), True))
                    elif page_type in form_first_types and not _extract_entry_value(entry, "name") and file_name:
                        image_path = _image_path_for_filename(file_name, image_dir)
                        ct_jobs.append(
                            (
                                self._classify_image,
                                (
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
                                ),
                            )
                        )
                        ct_metadata.append((entry, ("name", "form_name"), False))
                for (entry, name_keys, capture_report_date), response in zip(
                    ct_metadata,
                    self._run_classifier_jobs(ct_jobs, workers),
                    strict=True,
                ):
                    name_value = _extract_entry_value(response, *name_keys)
                    if name_value:
                        entry["name"] = name_value
                        updates += 1
                    if capture_report_date:
                        report_date = _extract_entry_value(response, "date", "report_date")
                        if report_date and not _extract_entry_value(entry, "date"):
                            entry["date"] = report_date
                            updates += 1
                with ct_named_path.open(ct_mode, encoding="utf-8") as handle:
                    for entry in ct_pending_entries:
                        self._raise_if_stop_requested()
                        file_name = _extract_entry_value(entry, "file_name", "filename")
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
                    report_date = _extract_entry_value(entry, "date", "report_date").strip()
                    report_lines.append(
                        _format_toc_line(_format_report_label(name_value, report_date), page)
                    )
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
            toc_lines = toc_path.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines()
            corrected_lines, _removals = _correct_toc_lines(
                toc_lines, self._raise_if_stop_requested
            )
            toc_path.write_text(
                "\n".join(corrected_lines).rstrip() + "\n", encoding="utf-8"
            )
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







    def _prepare_summary_step(
        self,
        *,
        require_participant_index: bool,
    ) -> _SummaryStepContext:
        """Resolve the shared inputs for one summary-generation step."""
        self._raise_if_stop_requested()
        root_dir = self._resolve_case_root()
        if root_dir is None:
            raise ValueError("Choose PDF files or select a saved case first.")
        artifacts_dir = root_dir / "artifacts"
        _cleanup_legacy_generated_artifacts(root_dir)
        text_dir = root_dir / "text_pages"
        if not text_dir.is_dir():
            raise FileNotFoundError("Run Create files to generate text pages first.")
        participant_by_range: dict[tuple[int, int], dict[str, Any]] = {}
        if require_participant_index:
            participant_issues = validate_participant_index_output(root_dir)
            if participant_issues:
                raise ValueError(
                    "Participant index validation failed: "
                    + " ".join(participant_issues)
                )
            participant_payload = json.loads(
                (artifacts_dir / "participant_index.json").read_text(encoding="utf-8")
            )
            participant_hearings = [
                item
                for item in participant_payload.get("hearings", [])
                if isinstance(item, dict)
            ]
            participant_by_range = {
                (int(item.get("start_page") or 0), int(item.get("end_page") or 0)): item
                for item in participant_hearings
            }
        transcript_payload = json.loads(
            (artifacts_dir / "transcript_page_numbers.json").read_text(encoding="utf-8")
        )
        citation_by_page = {
            int(
                item.get("file_page")
                or _page_number_from_label(str(item.get("file_name") or ""))
                or 0
            ): str(item.get("citation_label") or "")
            for item in transcript_payload.get("entries", [])
            if isinstance(item, dict)
        }
        settings = load_summarize_settings()
        if not settings["api_url"] or not settings["model_id"] or not settings["api_key"]:
            raise ValueError(
                "Configure Summarize API URL, model ID, and API key in Settings."
            )
        target_chars, max_pages = _summary_window_limits(settings)
        request_base = {
            "api_url": settings["api_url"],
            "model_id": settings["model_id"],
            "api_key": settings["api_key"],
            "disable_reasoning": bool(
                settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)
            ),
        }

        def request_window(prompt: str, payload: str) -> str:
            response = self._request_plain_text(
                {**request_base, "prompt": prompt}, payload
            )
            return " ".join((response or "").split())

        case_name, _ = load_case_context()
        display_case_name = case_name.replace("_", " ") if case_name else ""
        return _SummaryStepContext(
            root_dir=root_dir,
            artifacts_dir=artifacts_dir,
            text_dir=text_dir,
            citation_by_page=citation_by_page,
            settings=settings,
            target_chars=target_chars,
            max_pages=max_pages,
            request_window=request_window,
            display_case_name=display_case_name,
            participant_by_range=participant_by_range,
        )

    def _run_step_create_hearing_summaries(self) -> bool:
        """Create hearing summaries through nonpersisted page windows."""
        success: bool | None = False
        root_dir: Path | None = None
        try:
            step = self._prepare_summary_step(require_participant_index=True)
            root_dir = step.root_dir
            hearing_boundaries = _load_json_entries(
                step.artifacts_dir / "hearing_boundaries.json"
            )
            hearing_output = [
                "Hearings Summary",
                *([step.display_case_name] if step.display_case_name else []),
                "",
            ]
            total_hearings = len(hearing_boundaries)
            for hearing_number, boundary in enumerate(hearing_boundaries, start=1):
                self._raise_if_stop_requested()
                start = _page_number_from_label(
                    _extract_entry_value(boundary, "start_page", "start")
                )
                end = _page_number_from_label(
                    _extract_entry_value(boundary, "end_page", "end")
                )
                if start is None or end is None:
                    raise ValueError("Hearing boundary is missing a page range.")
                participant = step.participant_by_range.get((start, end))
                if participant is None:
                    raise ValueError(
                        f"Participant index has no hearing for source pages {start}-{end}."
                    )
                date_value = _normalize_hearing_date(
                    _extract_entry_value(boundary, "date", "hearing_date")
                    or str(participant.get("date") or "HEARING")
                )
                participant_context = _hearing_participant_context(participant)
                preferred_breaks: set[int] = set()
                for witness in participant.get("witnesses", []):
                    if not isinstance(witness, dict):
                        continue
                    for exam in witness.get("examinations", []):
                        if isinstance(exam, dict):
                            try:
                                value = int(exam.get("start_file_page") or 0)
                            except (TypeError, ValueError):
                                value = 0
                            if value:
                                preferred_breaks.add(value)
                windows = _summary_page_windows(
                    step.text_dir,
                    start,
                    end,
                    max_pages=step.max_pages,
                    target_chars=step.target_chars,
                    max_chars=DEFAULT_SUMMARIZE_WINDOW_MAX_CHARS,
                    preferred_breaks=preferred_breaks,
                )
                hearing_output.extend([date_value or "HEARING", ""])
                for window_number, window in enumerate(windows, start=1):
                    self._raise_if_stop_requested()
                    self._report_step_progress(
                        self.step_hearing_summaries_row,
                        f"Hearing {hearing_number}/{total_hearings} window {window_number}/{len(windows)}",
                        f"Create hearing summaries: direct-source hearing pages {window['primary_start']}-{window['primary_end']}.",
                    )
                    payload = _render_summary_window_payload(
                        window, step.citation_by_page, participant_context=participant_context
                    )
                    response = step.request_window(
                        step.settings["hearings_prompt"], payload
                    )
                    if response:
                        _append_summary_paragraph(hearing_output, response)
                hearing_output.append("")
            summaries_dir = root_dir / "summaries"
            summaries_dir.mkdir(parents=True, exist_ok=True)
            summaries_path, _reports_path = _summary_output_paths(root_dir)
            summaries_path.write_text(
                _collapse_blank_lines("\n".join(hearing_output)), encoding="utf-8"
            )
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Create hearing summaries failed: {exc}")
        else:
            success = True
            assert root_dir is not None
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "create_hearing_summaries",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            GLib.idle_add(self.show_toast, "Create hearing summaries complete.")
        finally:
            GLib.idle_add(self.step_hearing_summaries_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_hearing_summaries_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True

    def _run_step_create_report_summaries(self) -> bool:
        """Create report summaries through nonpersisted page windows."""
        success: bool | None = False
        root_dir: Path | None = None
        try:
            step = self._prepare_summary_step(require_participant_index=False)
            root_dir = step.root_dir
            report_boundaries = _load_json_entries(
                step.artifacts_dir / "report_boundaries.json"
            )
            report_output = [
                "Reports Summary",
                *([step.display_case_name] if step.display_case_name else []),
                "",
            ]
            total_reports = len(report_boundaries)
            reports_with_proposals = 0
            proposal_only_windows_skipped = 0
            for report_number, boundary in enumerate(report_boundaries, start=1):
                start = _page_number_from_label(
                    _extract_entry_value(boundary, "start_page", "start")
                )
                end = _page_number_from_label(
                    _extract_entry_value(boundary, "end_page", "end")
                )
                if start is None or end is None:
                    raise ValueError("Report boundary is missing a page range.")
                label = (
                    _extract_entry_value(boundary, "report_label", "report_name")
                    or f"Report {report_number}"
                )
                windows = _summary_page_windows(
                    step.text_dir,
                    start,
                    end,
                    max_pages=step.max_pages,
                    target_chars=step.target_chars,
                    max_chars=DEFAULT_SUMMARIZE_WINDOW_MAX_CHARS,
                )
                report_marker = (
                    _detect_report_proposal_marker(windows[0]["page_text"], start, end)
                    if windows
                    else None
                )
                if report_marker is not None:
                    reports_with_proposals += 1
                    GLib.idle_add(
                        self._append_log_message,
                        f"Report {report_number}: formal proposed findings/orders "
                        f"detected on source page {report_marker.source_page}.",
                        "INFO",
                    )
                report_paragraphs: list[str] = []
                for window_number, window in enumerate(windows, start=1):
                    self._raise_if_stop_requested()
                    self._report_step_progress(
                        self.step_report_summaries_row,
                        f"Report {report_number}/{total_reports} window {window_number}/{len(windows)}",
                        f"Create report summaries: direct-source report pages {window['primary_start']}-{window['primary_end']}.",
                    )
                    response = step.request_window(
                        step.settings["reports_prompt"],
                        _render_summary_window_payload(
                            window, step.citation_by_page, report_marker=report_marker
                        ),
                    )
                    if response == NO_SUMMARIZABLE_REPORT_CONTENT:
                        proposal_only_windows_skipped += 1
                        continue
                    if response:
                        report_paragraphs.append(response)
                if report_paragraphs:
                    report_output.extend([label, ""])
                    for paragraph in report_paragraphs:
                        _append_summary_paragraph(report_output, paragraph)
                    report_output.append("")
            summaries_dir = root_dir / "summaries"
            summaries_dir.mkdir(parents=True, exist_ok=True)
            _summaries_path, reports_path = _summary_output_paths(root_dir)
            reports_path.write_text(
                _collapse_blank_lines("\n".join(report_output)), encoding="utf-8"
            )
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Create report summaries failed: {exc}")
        else:
            success = True
            assert root_dir is not None
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "create_report_summaries",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            completion = "Create report summaries complete."
            if reports_with_proposals or proposal_only_windows_skipped:
                completion += (
                    f" Excluded formal proposed findings/orders in "
                    f"{reports_with_proposals} report(s); skipped "
                    f"{proposal_only_windows_skipped} proposal-only window(s)."
                )
            GLib.idle_add(self.show_toast, completion)
        finally:
            GLib.idle_add(self.step_report_summaries_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_report_summaries_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True

    def _run_step_create_minute_order_summaries(self) -> bool:
        """Create minute-order summaries through nonpersisted page windows."""
        success: bool | None = False
        root_dir: Path | None = None
        try:
            step = self._prepare_summary_step(require_participant_index=False)
            root_dir = step.root_dir
            minute_boundaries = _load_json_entries(
                step.artifacts_dir / "minutes_boundaries.json"
            )
            minute_output = [
                "Minutes Summary",
                *([step.display_case_name] if step.display_case_name else []),
                "",
            ]
            total_minutes = len(minute_boundaries)
            for minute_number, boundary in enumerate(minute_boundaries, start=1):
                start = _page_number_from_label(
                    _extract_entry_value(boundary, "start_page", "start")
                )
                end = _page_number_from_label(
                    _extract_entry_value(boundary, "end_page", "end")
                )
                if start is None or end is None:
                    raise ValueError("Minute-order boundary is missing a page range.")
                label = (
                    _extract_entry_value(boundary, "date")
                    or f"Minute Order {minute_number}"
                )
                minute_output.extend([label, ""])
                windows = _summary_page_windows(
                    step.text_dir,
                    start,
                    end,
                    max_pages=step.max_pages,
                    target_chars=step.target_chars,
                    max_chars=DEFAULT_SUMMARIZE_WINDOW_MAX_CHARS,
                )
                for window_number, window in enumerate(windows, start=1):
                    self._raise_if_stop_requested()
                    self._report_step_progress(
                        self.step_minute_order_summaries_row,
                        f"Minutes {minute_number}/{total_minutes} window {window_number}/{len(windows)}",
                        f"Create minute-order summaries: direct-source minute-order pages {window['primary_start']}-{window['primary_end']}.",
                    )
                    response = step.request_window(
                        step.settings["minutes_prompt"] + MINUTE_SUMMARY_WINDOW_GUIDANCE,
                        _render_summary_window_payload(
                            window, step.citation_by_page
                        ),
                    )
                    if response:
                        minute_output.append(response)
                minute_output.append("")
            summaries_dir = root_dir / "summaries"
            summaries_dir.mkdir(parents=True, exist_ok=True)
            minutes_path = _minutes_summary_output_path(root_dir)
            minutes_path.write_text(
                _collapse_blank_lines("\n".join(minute_output)), encoding="utf-8"
            )
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(
                self.show_toast, f"Create minute-order summaries failed: {exc}"
            )
        else:
            success = True
            assert root_dir is not None
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "create_minute_order_summaries",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            GLib.idle_add(self.show_toast, "Create minute-order summaries complete.")
        finally:
            GLib.idle_add(self.step_minute_order_summaries_row.set_sensitive, True)
            GLib.idle_add(
                self._finish_step, self.step_minute_order_summaries_row, success
            )
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True


    def _build_summarize_request_settings(
        self,
        summarize_settings: dict[str, Any],
        prompt: str,
    ) -> dict[str, Any]:
        return {
            "api_url": summarize_settings["api_url"],
            "model_id": summarize_settings["model_id"],
            "api_key": summarize_settings["api_key"],
            "disable_reasoning": bool(
                summarize_settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)
            ),
            "prompt": prompt,
        }

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
                raise FileNotFoundError(
                    "Run Create hearing summaries to generate hearing summaries first."
                )
            hearing_boundaries_path = artifacts_dir / "hearing_boundaries.json"
            minutes_boundaries_path = artifacts_dir / "minutes_boundaries.json"
            if (
                not hearing_boundaries_path.exists()
                or not minutes_boundaries_path.exists()
            ):
                raise FileNotFoundError(
                    "Run Find boundaries to generate hearing and minute boundaries first."
                )

            hearing_entries = _load_json_entries(hearing_boundaries_path)
            minute_entries = _load_json_entries(minutes_boundaries_path)
            if not hearing_entries and not minute_entries:
                GLib.idle_add(
                    self.show_toast,
                    "No hearing or minute boundaries found. Skipping Add links to summaries.",
                    "WARN",
                )
                success = "Skipped"
                return True

            linked_hearings, _modified, _inserted = (
                _add_page_links_to_hearing_summary_text(
                    summaries_path.read_text(encoding="utf-8", errors="ignore"),
                    hearing_entries,
                    minute_entries,
                )
            )
            summaries_path.write_text(linked_hearings, encoding="utf-8")
        except StopRequested:
            success = None
        except Exception as exc:
            GLib.idle_add(self.show_toast, f"Add links to summaries failed: {exc}")
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
            GLib.idle_add(self.show_toast, "Add links to summaries complete.")
        finally:
            GLib.idle_add(self.step_add_hearing_date_links_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_add_hearing_date_links_row, success)
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
            report_date = date_by_file.get(start_file, "").strip()
            report_boundaries.append(
                {
                    "report_name": report_name,
                    "report_date": report_date,
                    "report_label": _format_report_label(report_name, report_date),
                    "report_id": _report_id_from_start_page(start_page),
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
        _apply_disable_reasoning_to_body(
            body,
            model_id=str(settings["model_id"]),
            disable_reasoning=bool(settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)),
        )
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
        _apply_disable_reasoning_to_body(
            body,
            model_id=str(settings["model_id"]),
            disable_reasoning=bool(settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)),
        )
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
        _apply_disable_reasoning_to_body(
            body,
            model_id=model_id,
            disable_reasoning=disable_reasoning,
        )
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
