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
from recordprep.case_name_prompt import CASE_NAME_PROMPT as DEFAULT_CASE_NAME_PROMPT
from recordprep.classification import run_classifier_jobs
from recordprep.classification_profiles import ClassificationRun, ClassifierResponseError, classifier_prompt
from recordprep.document_naming import NamingContract
from recordprep.pi_bundle import (
    PARTICIPANT_TEMPLATE_WARNING,
    pi_step_complete,
    validate_participant_index_output,
)
from recordprep.summary_editions import (
    SUMMARY_EDITION_KINDS,
    SummaryEdition,
    SummaryEditionError,
    build_summary_edition,
    publish_summary_edition,
    remove_summary_edition,
    summary_edition_is_complete,
    summary_edition_output_paths,
    validate_summary_edition_files,
)
from recordprep.transcript_layout import (
    CT_ONLY_SKIP_LABEL,
    TranscriptLayoutError,
    apply_manual_override,
    capture_layout_rebind_guard,
    ct_only_skip_message,
    detection_status,
    diagnose_layout,
    finalize_layout_rebind,
    is_ct_only,
    layout_display_summary,
    legacy_manifest_split,
    read_resolved_layout,
    resolve_rt_ct_split as resolve_layout_rt_ct_split,
)
from recordprep import summary_agents as _summary_agents
from recordprep import minute_summaries as _minute_summaries
from recordprep.summary_agents import (  # noqa: F401 — compatibility aliases
    DEFAULT_SUMMARIZE_WINDOW_MAX_CHARS,
    DEFAULT_SUMMARIZE_WINDOW_MAX_PAGES,
    DEFAULT_SUMMARIZE_WINDOW_TARGET_CHARS,
    DEFAULT_SUMMARIZE_HEARINGS_WINDOW_TARGET_CHARS,
    DEFAULT_SUMMARIZE_HEARINGS_WINDOW_MAX_PAGES,
    DEFAULT_SUMMARIZE_REPORTS_WINDOW_TARGET_CHARS,
    DEFAULT_SUMMARIZE_REPORTS_WINDOW_MAX_PAGES,
    DEFAULT_SUMMARIZE_MINUTES_WINDOW_TARGET_CHARS,
    DEFAULT_SUMMARIZE_MINUTES_WINDOW_MAX_PAGES,
    # Historical direct-API extraction prompts: still the live defaults of
    # compatibility loaders; frozen historical texts for PI
    # guidance migration.
    DEFAULT_SUMMARIZE_HEARINGS_PROMPT,
    DEFAULT_SUMMARIZE_REPORTS_PROMPT,
    PREVIOUS_DEFAULT_SUMMARIZE_HEARINGS_PROMPT,
    PREVIOUS_DEFAULT_SUMMARIZE_REPORTS_PROMPT,
    PREVIOUS_PROPOSAL_SCOPE_SUMMARIZE_REPORTS_PROMPT,
    PREVIOUS_SIX_QUOTE_SUMMARIZE_REPORTS_PROMPT,
    NO_SUMMARIZABLE_REPORT_CONTENT,
    _hearing_context_lines,
    _hearing_participant_context,
    _participant_role_label,
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
    preflight_summary_context,
    resolve_pi_agent_argv,
    save_project_pi_model,
    save_project_pi_thinking_level,
    PI_THINKING_LEVELS,
)

from recordprep.paths import (application_config_path, resource_root, pi_settings_path,
                              config_dir, startup_log_path, atomic_private_json)

STARTUP_LOG_PATH = startup_log_path()
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
LOCAL_OCR_MAX_TOKENS = 4096
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
            "build_summary_editions",
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
COMPLETED_STEP_STATUSES = {"Done", "Already complete", "Skipped"}
SETTINGS_NAV_GROUPS: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = (
    (
        "ocr",
        "OCR",
        (("ocr", "OCR"),),
    ),
    (
        "classify",
        "Classify",
        (
            ("classify-basic", "Vision API"),
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


def _log_startup(message: str) -> None:
    try:
        timestamp = datetime.datetime.now().isoformat(sep=" ", timespec="seconds")
        fd = os.open(STARTUP_LOG_PATH, os.O_APPEND | os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
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
CONFIG_FILE = application_config_path()
PI_PROJECT_DIR = resource_root()
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
CONFIG_KEY_SUMMARIZE_HEARINGS_WINDOW_TARGET_CHARS = "summarize_hearings_window_target_chars"
CONFIG_KEY_SUMMARIZE_HEARINGS_WINDOW_MAX_PAGES = "summarize_hearings_window_max_pages"
CONFIG_KEY_SUMMARIZE_REPORTS_WINDOW_TARGET_CHARS = "summarize_reports_window_target_chars"
CONFIG_KEY_SUMMARIZE_REPORTS_WINDOW_MAX_PAGES = "summarize_reports_window_max_pages"
CONFIG_KEY_SUMMARIZE_MINUTES_WINDOW_TARGET_CHARS = "summarize_minutes_window_target_chars"
CONFIG_KEY_SUMMARIZE_MINUTES_WINDOW_MAX_PAGES = "summarize_minutes_window_max_pages"
# Retired soft word-target keys (summarize_hearings_target_words,
# summarize_reports_target_words, and the legacy
# summarize_reports_window_target_words) remain stored but are inert: no
# code reads them, the Settings-save flow preserves any existing values
# untouched, and new configurations never create them.
CONFIG_KEY_SUMMARY_EXTRACT_PI_PROVIDER = "summary_extract_pi_provider"
CONFIG_KEY_SUMMARY_EXTRACT_PI_MODEL = "summary_extract_pi_model"
CONFIG_KEY_SUMMARY_EXTRACT_PI_THINKING = "summary_extract_pi_thinking"
CONFIG_KEY_SUMMARY_SYNTHESIZE_PI_PROVIDER = "summary_synthesize_pi_provider"
CONFIG_KEY_SUMMARY_SYNTHESIZE_PI_MODEL = "summary_synthesize_pi_model"
CONFIG_KEY_SUMMARY_SYNTHESIZE_PI_THINKING = "summary_synthesize_pi_thinking"
CONFIG_KEY_SUMMARIZE_HEARINGS_SYNTHESIS_PROMPT = "summarize_hearings_synthesis_prompt"
CONFIG_KEY_SUMMARIZE_REPORTS_SYNTHESIS_PROMPT = "summarize_reports_synthesis_prompt"
LEGACY_CONFIG_KEY_SUMMARIZE_WINDOW_TARGET_CHARS = "summarize_window_target_chars"
LEGACY_CONFIG_KEY_SUMMARIZE_WINDOW_MAX_PAGES = "summarize_window_max_pages"
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
DEFAULT_SUMMARIZE_MINUTES_PROMPT = _minute_summaries.DEFAULT_MINUTES_PROMPT
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


def _toc_date_key(value: str) -> str | None:
    """Recognize supported dates only; unresolved labels never deduplicate."""
    cleaned = _normalize_hearing_date(value)
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _correct_toc_lines(
    toc_lines: list[str],
    raise_if_stop: Callable[[], None] | None = None,
) -> tuple[list[str], int]:
    """Return TOC lines with duplicate minute-order dates removed and the removal count.

    Inspects only tab-indented entries inside the ``MINUTE ORDERS`` section,
    retaining the first entry for each recognized date. Unknown dates are independent.
    Headings, blank lines, other
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
            date_key = _toc_date_key(date_value)
            if date_key is not None:
                if date_key in seen_dates:
                    removals += 1
                    continue
                seen_dates.add(date_key)
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


def _summary_edition_sources(root_dir: Path) -> dict[str, Path]:
    """Map each edition category to its canonical summary text path."""
    hearings_path, reports_path = _summary_output_paths(root_dir)
    return {
        "hearings": hearings_path,
        "reports": reports_path,
        "minutes": _minutes_summary_output_path(root_dir),
    }


def _summary_editions_complete(root_dir: Path) -> bool:
    """True when every category's edition validates against its current source."""
    for kind, source_path in _summary_edition_sources(root_dir).items():
        if not summary_edition_is_complete(kind, source_path, root_dir):
            return False
    return True


def _strip_nonstandard_characters(text: str) -> str:
    cleaned_chars: list[str] = []
    for ch in text:
        if ch in {"\n", "\t"}:
            cleaned_chars.append(ch)
        elif unicodedata.category(ch) != "Cc":
            cleaned_chars.append(ch)
    return "".join(cleaned_chars)


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
    # Two-stage summary artifacts (facts JSONL and metadata sidecars) are
    # generated data cleared with the bundle restart scope.
    for path in _summary_agents.summary_generated_artifact_paths(root_dir).values():
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
    # Companion page-matched edition keys are additive and optional: present
    # only while the generated PDF and page-map sidecar exist on disk, so
    # invalidation removes them and older Focus versions never see them.
    for kind, summary_path in (
        ("hearings", summarized_hearings_path),
        ("reports", summarized_reports_path),
        ("minutes", summarized_minutes_path),
    ):
        edition_pdf, edition_pages = summary_edition_output_paths(summary_path)
        pdf_key = f"summarized_{kind}_pdf"
        pages_key = f"summarized_{kind}_pages"
        if edition_pdf.exists() and edition_pages.exists():
            files_payload[pdf_key] = _relpath(edition_pdf)
            files_payload[pages_key] = _relpath(edition_pages)
        else:
            files_payload.pop(pdf_key, None)
            files_payload.pop(pages_key, None)

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

# Per-stage native PI model/reasoning overrides were retired: the single
# project default now applies to all five stages. Drop the old keys when local
# config is loaded or saved so they cannot linger.
OBSOLETE_PIPELINE_CONFIG_KEYS |= {
    f"pi_stage_{step_id}_pi_{field}"
    for step_id in (
        "detect_transcript_layout",
        "number_transcript_pages",
        "build_participant_index",
        "create_case_overview",
        "build_source_map",
    )
    for field in ("provider", "model", "thinking")
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
            # Reading settings (including profile preflight/export preview) must
            # never migrate or rewrite the user's private configuration. Only an
            # explicit settings-save flow may persist normalized settings.
            return cleaned
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _write_config(config: dict[str, Any], *, preserve_obsolete: bool = False, raise_errors: bool = False) -> None:
    serializable: dict[str, Any] = {}
    for key, value in config.items():
        if not isinstance(key, str) or (not preserve_obsolete and key in OBSOLETE_PIPELINE_CONFIG_KEYS):
            continue
        serializable[key] = value
    # Atomic replace: a crash or concurrent Dropbox sync mid-write must never
    # leave a truncated config.json whose next read would look like an empty
    # settings store.
    try:
        if config_dir() is not None:
            atomic_private_json(CONFIG_FILE, serializable)
            return
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp = CONFIG_FILE.with_name(f".{CONFIG_FILE.name}.{os.getpid()}.tmp")
        try:
            with temp.open("w", encoding="utf-8") as handle:
                handle.write(json.dumps(serializable, indent=2))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, CONFIG_FILE)
        finally:
            temp.unlink(missing_ok=True)
    except OSError:
        if raise_errors:
            raise


def clear_case_context() -> None:
    """Explicit user action: forget selection, preserving every other setting."""
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8")) if CONFIG_FILE.exists() else {}
    if not isinstance(config, dict):
        raise ValueError("Invalid application settings; current selection was not cleared.")
    config.update({CONFIG_KEY_CASE_NAME: "", CONFIG_KEY_CASE_ROOT_DIR: "", CONFIG_KEY_SELECTED_PDFS: []})
    _write_config(config, preserve_obsolete=True, raise_errors=True)


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
        # The Add-links pipeline step was retired; its old stopping point was
        # the minute-order summaries, before edition generation.
        "add_hearing_date_links": "create_minute_order_summaries",
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
    from recordprep.classification_profiles import classifier_model_settings
    model_settings = classifier_model_settings(config)
    api_url, model_id = model_settings["api_url"], model_settings["model_id"]
    disable_reasoning = model_settings["disable_reasoning"]
    api_key = str(config.get(CONFIG_KEY_CLASSIFIER_API_KEY, "") or "").strip()
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
    """Retired import compatibility only; production inference uses native Pi."""
    config = _read_config()
    api_url = str(config.get(CONFIG_KEY_CASE_NAME_API_URL, "") or "").strip()
    model_id = str(config.get(CONFIG_KEY_CASE_NAME_MODEL_ID, "") or "").strip()
    api_key = str(config.get(CONFIG_KEY_CASE_NAME_API_KEY, "") or "").strip()
    disable_reasoning = _read_config_bool(
        config,
        CONFIG_KEY_CASE_NAME_DISABLE_REASONING,
        DEFAULT_DISABLE_REASONING,
    )
    return {
        "api_url": api_url,
        "model_id": model_id,
        "api_key": api_key,
        "disable_reasoning": disable_reasoning,
        "prompt": DEFAULT_CASE_NAME_PROMPT,
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
                        },
                        # LightOnOCR-3's supported layout-aware mode includes
                        # footer/page-number regions, not just the main body.
                        {"type": "text", "text": "grounding"},
                    ],
                }
            ],
            "max_tokens": LOCAL_OCR_MAX_TOKENS,
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
    disable_reasoning_switch: Gtk.Switch | None = None
    workers_row: Adw.EntryRow | None = None
    local_server_switch: Gtk.Switch | None = None
    local_start_command_buffer: Gtk.TextBuffer | None = None
    disable_reasoning_row: Adw.SwitchRow | None = None


@dataclass
class LocalOcrSettingsWidgets:
    server_url_row: Adw.EntryRow
    model_row: Adw.EntryRow
    workers_row: Adw.EntryRow
    slots_row: Adw.EntryRow
    start_command_buffer: Gtk.TextBuffer


@dataclass
class SummarizeSettingsWidgets:
    extract_model_row: Adw.ComboRow
    extract_thinking_row: Adw.ComboRow
    synthesize_model_row: Adw.ComboRow
    synthesize_thinking_row: Adw.ComboRow


@dataclass
class AgentSettingsWidgets:
    pi_agent_command_row: Adw.EntryRow
    pi_thinking_level_row: Adw.ComboRow


def load_summary_model_settings() -> dict[str, Any]:
    config = _read_config()
    return {f"{phase}_{field}": str(config.get(f"summary_{phase}_pi_{field}", "") or "").strip()
            for phase in ("extract", "synthesize") for field in ("provider", "model", "thinking")}


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
    hearings_prompt = str(
        config.get(CONFIG_KEY_SUMMARIZE_HEARINGS_PROMPT, "") or ""
    )
    reports_prompt = str(
        config.get(CONFIG_KEY_SUMMARIZE_REPORTS_PROMPT, "") or ""
    )
    # One effective-guidance contract: Settings edits only the custom
    # additional guidance, preserved byte-for-byte and always subordinate to
    # the immutable built-in contract the runner composes. Recognized
    # historical built-ins (including the direct-API window-era prompts older
    # installations stored) resolve to no custom guidance. Migration is
    # applied in memory only until the user saves Settings.
    hearings_guidance = _summary_agents.resolve_phase_guidance(
        "hearings", "extract", hearings_prompt
    )
    reports_guidance = _summary_agents.resolve_phase_guidance(
        "reports", "extract", reports_prompt
    )
    hearings_synthesis_prompt = str(
        config.get(CONFIG_KEY_SUMMARIZE_HEARINGS_SYNTHESIS_PROMPT, "") or ""
    )
    reports_synthesis_prompt = str(
        config.get(CONFIG_KEY_SUMMARIZE_REPORTS_SYNTHESIS_PROMPT, "") or ""
    )
    hearings_synthesis_guidance = _summary_agents.resolve_phase_guidance(
        "hearings", "synthesize", hearings_synthesis_prompt
    )
    reports_synthesis_guidance = _summary_agents.resolve_phase_guidance(
        "reports", "synthesize", reports_synthesis_prompt
    )
    minutes_prompt = str(
        config.get(CONFIG_KEY_SUMMARIZE_MINUTES_PROMPT, DEFAULT_SUMMARIZE_MINUTES_PROMPT) or ""
    ).strip()
    minutes_prompt = minutes_prompt or DEFAULT_SUMMARIZE_MINUTES_PROMPT

    legacy_pair = _legacy_summary_window_pair(config)

    def _window_value(
        primary_key: str,
        legacy_index: int,
        *,
        category_default: int,
    ) -> int:
        """Resolve one category window value from explicit, legacy, or default."""
        explicit_raw = str(config.get(primary_key, "") or "").strip()
        if explicit_raw:
            try:
                return max(1, int(explicit_raw))
            except ValueError:
                pass
        if legacy_pair is not None:
            return legacy_pair[legacy_index]
        return category_default

    minutes_target = _window_value(
        CONFIG_KEY_SUMMARIZE_MINUTES_WINDOW_TARGET_CHARS,
        0,
        category_default=DEFAULT_SUMMARIZE_MINUTES_WINDOW_TARGET_CHARS,
    )
    minutes_pages = _window_value(
        CONFIG_KEY_SUMMARIZE_MINUTES_WINDOW_MAX_PAGES,
        1,
        category_default=DEFAULT_SUMMARIZE_MINUTES_WINDOW_MAX_PAGES,
    )

    return {
        "api_url": api_url,
        "model_id": model_id,
        "api_key": api_key,
        "disable_reasoning": disable_reasoning,
        "minutes_target_chars": str(minutes_target),
        "minutes_max_pages": str(minutes_pages),
        "hearings_prompt": hearings_guidance.custom_guidance,
        "reports_prompt": reports_guidance.custom_guidance,
        "minutes_prompt": minutes_prompt,
        "hearings_synthesis_prompt": hearings_synthesis_guidance.custom_guidance,
        "reports_synthesis_prompt": reports_synthesis_guidance.custom_guidance,
        "extract_provider": str(config.get(CONFIG_KEY_SUMMARY_EXTRACT_PI_PROVIDER, "") or "").strip(),
        "extract_model": str(config.get(CONFIG_KEY_SUMMARY_EXTRACT_PI_MODEL, "") or "").strip(),
        "extract_thinking": str(config.get(CONFIG_KEY_SUMMARY_EXTRACT_PI_THINKING, "") or "").strip(),
        "synthesize_provider": str(config.get(CONFIG_KEY_SUMMARY_SYNTHESIZE_PI_PROVIDER, "") or "").strip(),
        "synthesize_model": str(config.get(CONFIG_KEY_SUMMARY_SYNTHESIZE_PI_MODEL, "") or "").strip(),
        "synthesize_thinking": str(config.get(CONFIG_KEY_SUMMARY_SYNTHESIZE_PI_THINKING, "") or "").strip(),
    }


def _legacy_summary_window_pair(config: dict[str, Any]) -> tuple[int, int] | None:
    """Parse the legacy shared window pair, or None when absent or invalid."""
    target_raw = str(
        config.get(LEGACY_CONFIG_KEY_SUMMARIZE_WINDOW_TARGET_CHARS, "") or ""
    ).strip()
    pages_raw = str(
        config.get(LEGACY_CONFIG_KEY_SUMMARIZE_WINDOW_MAX_PAGES, "") or ""
    ).strip()
    if not target_raw or not pages_raw:
        return None
    try:
        target = max(1, int(target_raw))
        pages = max(1, int(pages_raw))
    except ValueError:
        return None
    return target, pages


def save_summarize_settings(
    *,
    api_url: str,
    model_id: str,
    api_key: str,
    disable_reasoning: bool,
    minutes_target_chars: str,
    minutes_max_pages: str,
    hearings_prompt: str,
    reports_prompt: str,
    minutes_prompt: str,
    hearings_synthesis_prompt: str = "",
    reports_synthesis_prompt: str = "",
    extract_provider: str = "",
    extract_model: str = "",
    extract_thinking: str = "",
    synthesize_provider: str = "",
    synthesize_model: str = "",
    synthesize_thinking: str = "",
) -> None:
    config = _read_config()
    config[CONFIG_KEY_SUMMARIZE_API_URL] = api_url
    config[CONFIG_KEY_SUMMARIZE_MODEL_ID] = model_id
    config[CONFIG_KEY_SUMMARIZE_API_KEY] = api_key
    config[CONFIG_KEY_SUMMARIZE_DISABLE_REASONING] = bool(disable_reasoning)
    # Retired word-target keys are never written, migrated, or removed here:
    # any stored values are preserved untouched and have no effect.
    config[CONFIG_KEY_SUMMARIZE_MINUTES_WINDOW_TARGET_CHARS] = minutes_target_chars
    config[CONFIG_KEY_SUMMARIZE_MINUTES_WINDOW_MAX_PAGES] = minutes_max_pages
    # Retired per-category PI extraction window keys: PI extraction sends each
    # document's complete source pages and no longer uses windows.
    for obsolete_key in (
        CONFIG_KEY_SUMMARIZE_HEARINGS_WINDOW_TARGET_CHARS,
        CONFIG_KEY_SUMMARIZE_HEARINGS_WINDOW_MAX_PAGES,
        CONFIG_KEY_SUMMARIZE_REPORTS_WINDOW_TARGET_CHARS,
        CONFIG_KEY_SUMMARIZE_REPORTS_WINDOW_MAX_PAGES,
    ):
        config.pop(obsolete_key, None)
    config.pop(LEGACY_CONFIG_KEY_SUMMARIZE_WINDOW_TARGET_CHARS, None)
    config.pop(LEGACY_CONFIG_KEY_SUMMARIZE_WINDOW_MAX_PAGES, None)
    config.pop(LEGACY_CONFIG_KEY_SUMMARIZE_CHUNK_SIZE, None)
    # Custom PI guidance is stored byte-for-byte; an empty value means "use
    # the immutable built-in contract". The effective contract is composed at
    # run time and never persisted back into these keys.
    config[CONFIG_KEY_SUMMARIZE_HEARINGS_PROMPT] = hearings_prompt
    config[CONFIG_KEY_SUMMARIZE_REPORTS_PROMPT] = reports_prompt
    config[CONFIG_KEY_SUMMARIZE_MINUTES_PROMPT] = (
        minutes_prompt or DEFAULT_SUMMARIZE_MINUTES_PROMPT
    )
    config[CONFIG_KEY_SUMMARIZE_HEARINGS_SYNTHESIS_PROMPT] = hearings_synthesis_prompt
    config[CONFIG_KEY_SUMMARIZE_REPORTS_SYNTHESIS_PROMPT] = reports_synthesis_prompt
    # Stage overrides never mutate the project PI settings; an empty value
    # means "use the project PI model/reasoning".
    config[CONFIG_KEY_SUMMARY_EXTRACT_PI_PROVIDER] = extract_provider
    config[CONFIG_KEY_SUMMARY_EXTRACT_PI_MODEL] = extract_model
    config[CONFIG_KEY_SUMMARY_EXTRACT_PI_THINKING] = extract_thinking
    config[CONFIG_KEY_SUMMARY_SYNTHESIZE_PI_PROVIDER] = synthesize_provider
    config[CONFIG_KEY_SUMMARY_SYNTHESIZE_PI_MODEL] = synthesize_model
    config[CONFIG_KEY_SUMMARY_SYNTHESIZE_PI_THINKING] = synthesize_thinking
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
    def __init__(self, app: Adw.Application, on_saved: Callable[[], None] | None = None, on_profiles=None) -> None:
        super().__init__(application=app, title="Model settings")
        self._on_profiles = on_profiles
        self.set_default_size(900, 720)
        self.set_resizable(True)
        self._on_saved = on_saved
        self._prompt_editors: dict[str, ClassifySettingsWidgets] = {}
        self._local_ocr_widgets: LocalOcrSettingsWidgets | None = None
        self._settings_group_rows: dict[str, Adw.ActionRow] = {}
        self._settings_destination_labels: dict[str, str] = {}
        self._settings_destination_markers: dict[str, Gtk.Image] = {}
        self._active_settings_key: str | None = None
        self._text_source_row: Adw.ComboRow | None = None
        self._text_source_values: list[str] = []
        self._agent_widgets: AgentSettingsWidgets | None = None
        self._pi_model_options: list[PiModel | None] = []
        self._summary_model_rows: list[tuple[Adw.ComboRow, str]] = []
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
        header.set_title_widget(Adw.WindowTitle(title="Model settings"))
        if self._on_profiles is not None:
            profiles_button = Gtk.Button(label="Profile settings…")
            profiles_button.add_css_class("flat")
            profiles_button.set_tooltip_text("Edit practice guidance in Profile settings.")
            profiles_button.connect("clicked", lambda _button: self._on_profiles(self))
            header.pack_start(profiles_button)
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
        box.append(Gtk.Label(label="Edit processing instructions in Profile settings. Configure models and connections here.",
                             wrap=True, xalign=0))

        split = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        split.set_hexpand(True)
        split.set_vexpand(True)

        prompt_list = Gtk.ListBox()
        prompt_list.set_selection_mode(Gtk.SelectionMode.NONE)
        prompt_list.add_css_class("boxed-list")
        prompt_list.set_valign(Gtk.Align.START)
        prompt_list.set_vexpand(False)
        self._prompt_list = prompt_list

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

        self._add_settings_destination("ocr", "ocr")
        ocr_page = self._build_ocr_page(load_local_ocr_settings())
        prompt_stack.add_named(ocr_page, "ocr")

        self._add_settings_destination("classify", "classify-basic")
        classify_page = self._build_prompt_page(
            "classify-basic",
            "Classification basic",
            load_classifier_settings(),
            DEFAULT_CLASSIFIER_PROMPT,
        )
        prompt_stack.add_named(classify_page, "classify-basic")

        self._add_settings_destination("summarize", "summarize")
        summarize_page = self._build_summarize_prompt_page(load_summary_model_settings())
        prompt_stack.add_named(summarize_page, "summarize")

        self._add_settings_destination("agent", "pi")
        pi_page = self._build_pi_settings_page()
        prompt_stack.add_named(pi_page, "pi")

        self._select_settings_page("ocr")

        split.append(prompt_list_scroller)
        split.append(prompt_stack)
        box.append(split)

        view.set_content(box)
        self.set_content(view)

    def _build_text_source_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(
            title="Text extraction",
            description="Choose how text files are generated during Create files.",
        )
        group.add_css_class("list-stack")

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
        return group

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

    def _build_ocr_page(self, settings: dict[str, str]) -> Gtk.Widget:
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page_box.set_margin_top(12)
        page_box.set_margin_bottom(12)
        page_box.set_margin_start(12)
        page_box.set_margin_end(12)
        page_box.set_vexpand(True)

        title_label = Gtk.Label(label="OCR", xalign=0)
        title_label.add_css_class("title-3")
        page_box.append(title_label)
        page_box.append(self._build_text_source_group())

        info_label = Gtk.Label(
            label=(
                "The settings below apply when OCR with local model is selected. "
                "Use {slots} in the start command to insert the llama.cpp slot count."
            ),
            wrap=True,
            xalign=0,
        )
        info_label.add_css_class("dim-label")
        page_box.append(info_label)

        server_group = Adw.PreferencesGroup(title="Local OCR")
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


        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.set_hexpand(True)
        page.set_vexpand(True)
        page.set_child(page_box)

        self._prompt_editors[key] = ClassifySettingsWidgets(
            api_url_row=api_url_row,
            model_row=model_row,
            api_key_row=api_key_row,
            disable_reasoning_switch=disable_reasoning_switch,
            workers_row=workers_row,
            local_server_switch=local_server_switch,
            local_start_command_buffer=local_start_command_buffer,
            disable_reasoning_row=disable_reasoning_row,
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

        # --- PI extraction ---
        extract_group = Adw.PreferencesGroup(
            title="PI extraction + digest",
            description=(
                "Model and reasoning for stage one: one fresh PI process per "
                "hearing or report reads the complete source pages and writes "
                "concise per-category digests. Empty means use the project PI "
                "model."
            ),
        )
        extract_group.add_css_class("list-stack")
        extract_group.set_hexpand(True)
        page_box.append(extract_group)

        extract_model_row = self._build_summary_model_row(
            "Extraction model", settings.get("extract_model", "")
        )
        extract_group.add(extract_model_row)
        extract_thinking_row = self._build_summary_thinking_row(
            "Extraction reasoning level", settings.get("extract_thinking", "")
        )
        extract_group.add(extract_thinking_row)

        # --- PI synthesis ---
        synthesize_group = Adw.PreferencesGroup(
            title="PI synthesis",
            description=(
                "Independent model and reasoning for stage two: one fresh PI "
                "process per completed digest file synthesizes the final "
                "narrative from the category digests. Also used for minute-order "
                "summaries directly from source pages, one fresh process per order."
            ),
        )
        synthesize_group.add_css_class("list-stack")
        synthesize_group.set_hexpand(True)
        page_box.append(synthesize_group)

        synthesize_model_row = self._build_summary_model_row(
            "Synthesis model", settings.get("synthesize_model", "")
        )
        synthesize_group.add(synthesize_model_row)
        synthesize_thinking_row = self._build_summary_thinking_row(
            "Synthesis reasoning level", settings.get("synthesize_thinking", "")
        )
        synthesize_group.add(synthesize_thinking_row)

        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.set_hexpand(True)
        page.set_vexpand(True)
        page.set_child(page_box)

        self._summarize_widgets = SummarizeSettingsWidgets(
            extract_model_row=extract_model_row,
            extract_thinking_row=extract_thinking_row,
            synthesize_model_row=synthesize_model_row,
            synthesize_thinking_row=synthesize_thinking_row,
        )
        self._refresh_summary_model_rows()
        return page

    def _build_summary_model_row(self, title: str, configured: str) -> Adw.ComboRow:
        row = Adw.ComboRow(title=title)
        row.set_model(Gtk.StringList.new(["Use project PI model"]))
        row.set_selected(0)
        self._summary_model_rows.append((row, configured))
        return row

    def _build_summary_thinking_row(self, title: str, configured: str) -> Adw.ComboRow:
        labels = ["Use project PI reasoning"] + [
            level for level in PI_THINKING_LEVELS
        ]
        row = Adw.ComboRow(title=title)
        row.set_model(Gtk.StringList.new(labels))
        selected = 0
        if configured:
            candidate = configured.strip().lower()
            if candidate in PI_THINKING_LEVELS:
                selected = 1 + PI_THINKING_LEVELS.index(candidate)
        row.set_selected(selected)
        return row

    def _refresh_summary_model_rows(self) -> None:
        """Populate the summary model dropdowns from authenticated PI models."""
        options = getattr(self, "_pi_model_options", None)
        for row, configured in self._summary_model_rows:
            labels = ["Use project PI model"]
            selected = 0
            if options:
                models = [model for model in options if model is not None]
                labels.extend(model.label for model in models)
                if configured:
                    for index, model in enumerate(models, start=1):
                        if model.model_id == configured or (
                            f"{model.provider}/{model.model_id}" == configured
                        ):
                            selected = index
                            break
            row.set_model(Gtk.StringList.new(labels))
            row.set_selected(selected)

    def _override_row_values(
        self, model_row: Adw.ComboRow, thinking_row: Adw.ComboRow
    ) -> tuple[str, str, str]:
        options = [
            model
            for model in getattr(self, "_pi_model_options", [])
            if model is not None
        ]
        selected_index = int(model_row.get_selected())
        provider = model = ""
        if selected_index > 0 and selected_index <= len(options):
            chosen = options[selected_index - 1]
            provider, model = chosen.provider, chosen.model_id
        thinking_index = int(thinking_row.get_selected())
        thinking = (
            PI_THINKING_LEVELS[thinking_index - 1]
            if thinking_index > 0 and thinking_index <= len(PI_THINKING_LEVELS)
            else ""
        )
        return provider, model, thinking



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
            title="All five PI stages",
            description=(
                "PI runs five project-local skills sequentially in the final "
                "pipeline group (layout detection, page numbering, participant "
                "index, case overview, and source map). This model and "
                "reasoning level apply to all five stages. "
                f"Preferences: {pi_settings_path()}"
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
            title="PI model for all five stages",
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
            title="PI reasoning level for all five stages",
            subtitle=(
                "Applied to each of the five PI skill sessions; PI adjusts "
                "levels unsupported by the selected model."
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
        self._refresh_summary_model_rows()
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
    ) -> None:
        title = next(title for candidate, title, _items in SETTINGS_NAV_GROUPS if candidate == group_id)
        row = Adw.ActionRow(title=title)
        row.set_activatable(True)
        marker = Gtk.Image.new_from_icon_name("object-select-symbolic")
        marker.set_visible(False)
        row.add_suffix(marker)
        row.connect(
            "activated",
            lambda _row, destination=key: self._select_settings_page(destination),
        )
        self._settings_destination_labels[key] = title
        self._settings_destination_markers[key] = marker
        self._settings_group_rows[group_id] = row
        self._prompt_list.append(row)

    def _select_settings_page(self, key: str) -> None:
        if key not in self._settings_destination_labels:
            return
        self._active_settings_key = key
        self._prompt_stack.set_visible_child_name(key)
        for destination, marker in self._settings_destination_markers.items():
            marker.set_visible(destination == key)

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
        classify_basic_widgets = self._prompt_editors.get("classify-basic")
        local_ocr_widgets = self._local_ocr_widgets
        summarize_widgets = getattr(self, "_summarize_widgets", None)
        agent_widgets = self._agent_widgets
        if self._text_source_row:
            selected = self._text_source_row.get_selected()
            value = DEFAULT_TEXT_SOURCE
            if 0 <= selected < len(self._text_source_values):
                value = self._text_source_values[selected]
            save_text_source_setting(value)
        # Save only machine/API fields. Hidden legacy prose is byte-preserved.
        runtime_config = _read_config()
        for widgets, prefix in ((classify_basic_widgets, "classifier"),):
            if widgets is not None:
                for key, row in (("api_url", widgets.api_url_row), ("model_id", widgets.model_row), ("api_key", widgets.api_key_row)):
                    runtime_config[f"{prefix}_{key}"] = row.get_text().strip()
                reasoning = widgets.disable_reasoning_switch or widgets.disable_reasoning_row
                runtime_config[f"{prefix}_disable_reasoning"] = bool(reasoning.get_active()) if reasoning else DEFAULT_DISABLE_REASONING
        if classify_basic_widgets:
            widgets = classify_basic_widgets
            try:
                workers = int(widgets.workers_row.get_text().strip())
                if workers < 1:
                    raise ValueError
            except ValueError:
                widgets.workers_row.set_title("Classification Workers — enter a positive number")
                return
            runtime_config[CONFIG_KEY_CLASSIFIER_WORKERS] = workers
            runtime_config[CONFIG_KEY_CLASSIFIER_LOCAL_VISION_ENABLED] = bool(widgets.local_server_switch.get_active())
            runtime_config[CONFIG_KEY_CLASSIFIER_LOCAL_VISION_START_COMMAND] = self._prompt_text(widgets.local_start_command_buffer).strip()
        _write_config(runtime_config)
        if local_ocr_widgets:
            save_local_ocr_settings(
                local_ocr_widgets.server_url_row.get_text().strip(),
                local_ocr_widgets.model_row.get_text().strip(),
                self._prompt_text(local_ocr_widgets.start_command_buffer).strip(),
                local_ocr_widgets.workers_row.get_text().strip(),
                local_ocr_widgets.slots_row.get_text().strip(),
            )
        if summarize_widgets:
            extract_provider, extract_model, extract_thinking = (
                self._override_row_values(
                    summarize_widgets.extract_model_row,
                    summarize_widgets.extract_thinking_row,
                )
            )
            synthesize_provider, synthesize_model, synthesize_thinking = (
                self._override_row_values(
                    summarize_widgets.synthesize_model_row,
                    summarize_widgets.synthesize_thinking_row,
                )
            )
            runtime_config = _read_config()
            for phase, values in (("extract", (extract_provider, extract_model, extract_thinking)),
                                  ("synthesize", (synthesize_provider, synthesize_model, synthesize_thinking))):
                for field, value in zip(("provider", "model", "thinking"), values):
                    runtime_config[f"summary_{phase}_pi_{field}"] = value
            _write_config(runtime_config)
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


class RecordPrepWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title=APPLICATION_NAME)
        self.set_default_size(900, 600)

        self.selected_pdfs: list[Path] = []
        self._case_generation = 0
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

        self.case_bundle_button = self._case_header_button("folder-open-symbolic", "Choose case bundle")
        self.case_bundle_button.connect("clicked", self.on_choose_case_bundle)
        header_bar.pack_start(self.case_bundle_button)

        self.file_button = self._case_header_button("list-add-symbolic", "Choose PDF(s)")
        self.file_button.connect("clicked", self.on_choose_pdf)
        header_bar.pack_start(self.file_button)

        self.clear_case_button = self._case_header_button("user-trash-symbolic", "Clear current case")
        self.clear_case_button.set_tooltip_text("Clear current case selection; no files are deleted")
        self.clear_case_button.connect("clicked", self.on_clear_case)
        header_bar.pack_start(self.clear_case_button)

        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        status_box.set_halign(Gtk.Align.CENTER)
        self.status_spinner = Gtk.Spinner()
        self.status_label = Gtk.Label(label=APPLICATION_NAME, xalign=0)
        self.status_label.set_ellipsize(3)
        self.status_label.set_max_width_chars(52)
        status_box.append(self.status_spinner)
        self._title_widget = Adw.WindowTitle(title=APPLICATION_NAME)
        status_box.append(self._title_widget)
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
        content.append(self.status_label)

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
            subtitle="Use PI to infer the case name from the first three pages.",
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

        self.step_build_summary_editions_row = Adw.ActionRow(
            title="Build paginated summary editions",
            subtitle="Create page-matched Letter PDFs and Focus page maps.",
        )
        self.step_build_summary_editions_row.set_activatable(False)
        self._attach_step_controls(
            "build_summary_editions",
            self.step_build_summary_editions_row,
            lambda _btn: self.on_step_build_summary_editions_clicked(
                self.step_build_summary_editions_row
            ),
        )
        self._attach_step_status(self.step_build_summary_editions_row)

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
        menu.append("Model settings", "app.settings")
        from recordprep.profile_manager_ui import install_profile_menu
        from recordprep.profile_integration import open_manager
        install_profile_menu(menu, self.menu_button, lambda: open_manager(self, PI_PROJECT_DIR))

        action = Gio.SimpleAction.new("settings", None)
        action.connect("activate", self.on_settings)
        app.add_action(action)

        if app.lookup_action("save-settings") is None:
            save_action = Gio.SimpleAction.new("save-settings", None)
            save_action.connect("activate", self._on_action_save_settings)
            app.add_action(save_action)

    def on_settings(self, _action: Gio.SimpleAction, _param: object) -> None:
        if self._settings_window:
            self._settings_window.present()
            return
        settings = SettingsWindow(self.get_application(), on_saved=self._on_settings_saved, on_profiles=self._open_practice_profiles)
        settings.connect("close-request", self._on_settings_close_request)
        self._settings_window = settings
        settings.present()

    def _open_practice_profiles(self, parent=None) -> None:
        from recordprep.profile_integration import open_manager
        try:
            if parent is None:
                self.menu_button.popup()
            else:
                open_manager(self, PI_PROJECT_DIR, parent)
        except (ValueError, OSError) as exc:
            self.show_toast(f"Practice Profiles unavailable: {exc}")

    def _on_settings_saved(self) -> None:
        self.show_toast("Model settings saved.")

    def _on_settings_close_request(self, _window: SettingsWindow) -> bool:
        self._settings_window = None
        return False

    def _on_action_save_settings(self, _action: Gio.SimpleAction, _param: object) -> None:
        if not self._settings_window:
            self.show_toast("Model settings window is not open.")
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
        self.status_label.set_visible(message != APPLICATION_NAME)
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
            if (
                step_id == "build_participant_index"
                and root_dir is not None
                and is_ct_only(root_dir)
            ):
                # Preserve the explicit skip display across refreshes and
                # bundle reopening; a generic Done would misrepresent the
                # skip as a generated participant artifact.
                self._set_step_status(row, "Skipped")
                continue
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
        from recordprep.case_profiles import resolve_case_profile
        from recordprep.classification_profiles import STAGES, SUFFIXES, stage_issues
        try:
            profile = resolve_case_profile(root_dir)
            suffix = rt_path.stem.removeprefix("RT_")
            if profile is not None:
                if suffix not in SUFFIXES or stage_issues(root_dir, STAGES[SUFFIXES.index(suffix)], profile, load_classifier_settings()):
                    return False
            elif suffix in SUFFIXES and (root_dir / "classification" / f"profile-{STAGES[SUFFIXES.index(suffix)]}.json").exists():
                return False
        except (ValueError, OSError):
            return False
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
            from recordprep.case_name_stage import is_current
            return is_current(root_dir, PI_PROJECT_DIR)
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
        if step_id in {"build_toc", "correct_toc", "find_boundaries", "correct_boundaries"}:
            from recordprep.case_profiles import resolve_case_profile
            from recordprep.boundary_profiles import boundary_issues, toc_issues
            try:
                derived_profile = resolve_case_profile(root_dir)
                is_toc = step_id in {"build_toc", "correct_toc"}
                if derived_profile is not None:
                    check = toc_issues if is_toc else boundary_issues
                    if check(root_dir, derived_profile, load_classifier_settings()):
                        return False
                elif (artifacts_dir / ("profile-toc.json" if is_toc else "profile-boundaries.json")).exists():
                    return False
            except (ValueError, OSError):
                return False
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
            return _summary_agents.summary_stage_complete(root_dir, "hearings")
        if step_id == "create_report_summaries":
            return _summary_agents.summary_stage_complete(root_dir, "reports")
        if step_id == "create_minute_order_summaries":
            return _minute_summaries.stage_complete(root_dir)
        if step_id == "build_summary_editions":
            return (
                _summary_editions_complete(root_dir)
            )
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
            # Keep the action visible so clicking explains why Resume is
            # blocked, rather than nudging users toward a fresh Run instead.
            return True
        if start_index is None:
            return False
        step_id = self._pipeline_steps()[start_index][0]
        return step_id != "create_files" or bool(self.selected_pdfs)

    def _sync_pipeline_controls(self) -> None:
        from recordprep.profile_integration import update_indicator
        update_indicator(self)
        running = self._pipeline_running
        busy = running or self._pi_terminal_active
        self.case_bundle_button.set_sensitive(not busy)
        self.file_button.set_sensitive(not busy)
        self.clear_case_button.set_sensitive(not busy and bool(self.selected_pdfs or self._resolve_case_root() is not None))
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
        previous = read_resolved_layout(root_dir)
        same_layout = (previous is not None and previous.get("mode") == mode
                       and (mode != "split" or previous.get("rt_end_file_page") == rt_end))
        if same_layout:
            # Re-selecting the current layout must not rewrite its fingerprint
            # or invalidate completed classification and downstream work.
            self._rt_ct_split_mode_pending = None
            self._rt_ct_split_pending = None
            return True
        if self._has_layout_dependent_work(root_dir):
            self._rt_ct_split_mode_pending = None
            self._rt_ct_split_pending = None
            self.show_toast(
                "Layout change blocked: this bundle contains prepared work. "
                "Existing files were preserved. Use a separate folder for a changed layout.", "WARN")
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
        for directory in (root_dir / "summaries", root_dir / ".recordprep/profile-work"):
            if directory.is_dir() and any(path.is_file() for path in directory.rglob("*")):
                return True
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

    def _raise_if_stop_requested(self) -> None:
        if self._stop_event.is_set():
            raise StopRequested()

    def _validate_vision_settings(self, settings: dict[str, Any]) -> None:
        api_url = str(settings.get("api_url", "") or "").strip()
        model_id = str(settings.get("model_id", "") or "").strip()
        if not api_url or not model_id:
            raise ValueError("Configure vision API URL and model ID in Model settings.")
        local_vision_enabled = bool(settings.get("local_vision_enabled", False))
        api_key = str(settings.get("api_key", "") or "").strip()
        if not local_vision_enabled and not api_key:
            raise ValueError(
                "Configure vision API key in Model settings, or enable local llama.cpp vision server."
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
        response_error: ClassifierResponseError | None = None
        for attempt in range(1, max_attempts + 1):
            self._raise_if_stop_requested()
            try:
                entry = self._classify_image(settings, filename, image_path)
            except ClassifierResponseError as exc:
                # Profile validation must not bypass the existing bounded retry.
                # Never retry source/configuration/transport failures here, and
                # never coerce an unsupported label into a valid classification.
                response_error = exc
                continue
            page_type = _extract_entry_value(entry, "page_type", "pagetype").strip()
            if page_type:
                return entry
        if response_error is not None:
            raise RuntimeError(
                f"Classification basic returned an invalid page_type for {filename} "
                f"after {max_attempts} attempts. {response_error} "
                "Retry Classification basic; if it persists, check the classifier model and profile guidance."
            ) from response_error
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

    @staticmethod
    def _case_header_button(icon_name: str, label: str) -> Gtk.Button:
        button = Gtk.Button()
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.add_css_class("dim-label")
        button.set_child(icon)
        button.add_css_class("flat")
        button.set_valign(Gtk.Align.CENTER)
        button.set_tooltip_text(label)
        button.update_property([Gtk.AccessibleProperty.LABEL], [label])
        return button

    def on_clear_case(self, _button: Gtk.Button) -> None:
        if self._pipeline_running or self._pi_terminal_active:
            self.show_toast("Stop the pipeline before clearing the current case.")
            return
        if self._toc_editor_window is not None:
            self.show_toast("Close the TOC editor before clearing the current case.")
            return
        try:
            clear_case_context()
        except (OSError, ValueError):
            self.show_toast("Current case could not be cleared because application settings could not be saved.")
            return
        self._case_generation += 1
        self.selected_pdfs = []
        self._pending_preparation_profile = None
        self._rt_ct_split_pending = None
        self._rt_ct_split_mode_pending = None
        self._bundle_reset_required = False
        self._active_bundle_root = None
        self._bundle_identity_warning_roots.clear()
        self._active_step_id = None
        self._run_completion_message = None
        self._run_pause_message = None
        self._pi_terminal_sequence_started = False
        self._stop_event.clear()
        self.selected_label.set_text("Selected: None")
        self._load_rt_ct_split()
        self._update_source_summary()
        self._source_row.set_expanded(False)
        self._reset_step_statuses()
        self._stop_status()
        self._set_activity_status_text("No activity yet")
        if self._log_buffer is not None:
            self._log_buffer.set_text("")
        if self._activity_terminal is not None:
            self._activity_terminal.reset(True, True)
        self.show_toast("Current case cleared. No files were deleted.", level="INFO")

    def on_choose_pdf(self, _button: Gtk.Button) -> None:
        if self._pipeline_running or self._pi_terminal_active:
            self.show_toast("Stop the pipeline before choosing PDF files.")
            return
        generation = self._case_generation
        dialog = Gtk.FileDialog(title="Choose PDF files")
        file_filter = Gtk.FileFilter()
        file_filter.add_mime_type("application/pdf")
        file_filter.set_name("PDF files")
        dialog.set_default_filter(file_filter)
        dialog.open_multiple(self, None, lambda dialog, result: self._on_files_chosen(dialog, result, generation))

    def on_choose_case_bundle(self, _button: Gtk.Button) -> None:
        if self._pipeline_running or self._pi_terminal_active:
            self.show_toast("Stop the pipeline before choosing a case bundle.")
            return
        dialog = Gtk.FileDialog(title="Choose case bundle folder")
        base_dir = self._resolve_case_base()
        if base_dir is not None:
            dialog.set_initial_folder(Gio.File.new_for_path(str(base_dir)))
        generation = self._case_generation
        dialog.select_folder(self, None, lambda dialog, result: self._on_case_bundle_chosen(dialog, result, generation))

    def _on_case_bundle_chosen(
        self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, generation: int | None = None
    ) -> None:
        if self._pipeline_running or self._pi_terminal_active or (generation is not None and generation != self._case_generation):
            return
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
        self._case_generation += 1
        self._pending_preparation_profile = None
        self._rt_ct_split_pending = None
        self._rt_ct_split_mode_pending = None
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
        self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, generation: int | None = None
    ) -> None:
        if self._pipeline_running or self._pi_terminal_active or (generation is not None and generation != self._case_generation):
            return
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
        self._case_generation += 1
        pending = getattr(self, "_pending_preparation_profile", None)
        if pending is not None:
            retain_choice = root_dir is not None and not root_dir.exists() and pending[0] in (None, root_dir)
            self._pending_preparation_profile = (root_dir, pending[1]) if retain_choice else None
        self._rt_ct_split_pending = None
        self._rt_ct_split_mode_pending = None
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
                "build_summary_editions",
                self.step_build_summary_editions_row,
                self._run_step_build_summary_editions,
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
        if (getattr(self, "_bundle_reset_required", False)
                or (self.selected_pdfs and _bundle_inputs_changed(root_dir, self.selected_pdfs))):
            raise ValueError("Resume blocked: PDF selection or transcript layout needs review. "
                             "Existing files were preserved; Resume never resets a bundle.")
        steps = self._pipeline_steps()
        end_index = len(steps) - 1
        if end_step_id:
            step_ids = [step_id for step_id, _row, _handler in steps]
            if end_step_id not in step_ids:
                raise ValueError("Unknown end step.")
            end_index = step_ids.index(end_step_id)
        for index, (step_id, _row, _handler) in enumerate(steps[: end_index + 1]):
            if not self._step_artifact_complete(step_id, root_dir, self.selected_pdfs):
                if step_id == "create_files" and self._has_layout_dependent_work(root_dir):
                    raise ValueError("Resume blocked: source pages are incomplete but prepared work exists. "
                                     "Existing files were preserved; restore missing source pages before continuing.")
                # A freshness failure is not permission to silently regenerate
                # already-published work. Missing output is resumable; stale
                # existing output needs an explicit per-step rerun.
                published_paths = {
                    "detect_transcript_layout": ["artifacts/transcript_layout.json"],
                    "infer_case": ["case_name.txt"],
                    "number_transcript_pages": ["artifacts/transcript_page_numbers.json"],
                    "build_participant_index": ["artifacts/participant_index.json"],
                    "create_case_overview": ["artifacts/case_overview.md"],
                    "build_source_map": ["artifacts/source_map.json"],
                }
                stages = {"classify_basic": "basic", "classify_advanced": "advanced",
                          "correct_classify_advanced": "corrected", "classify_dates": "dates",
                          "classify_names": "names"}
                if step_id in stages:
                    # In-progress JSONL outputs can resume missing pages. A
                    # profile marker denotes an already-published stage.
                    published_paths[step_id] = [f"classification/profile-{stages[step_id]}.json"]
                if any((root_dir / path).exists() for path in published_paths.get(step_id, [])):
                    title = _row.get_title() or step_id
                    raise ValueError(f"Resume paused at {title}: existing output needs review or regeneration. "
                                     "Files were preserved. Use this step's Run or Run from here to rerun it explicitly.")
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
            new_case_profile = None
            if not root_dir.exists() and not root_dir.is_symlink():
                from recordprep.profile_integration import new_case_profile as choose_new_case_profile
                new_case_profile = choose_new_case_profile(self, root_dir)
            pending_split = self._rt_ct_split_pending
            pending_mode = self._rt_ct_split_mode_pending
            reset_required = (
                self._bundle_reset_required
                or _bundle_inputs_changed(root_dir, self.selected_pdfs)
            )
            if reset_required:
                raise ValueError(
                    "Create files blocked: PDF selection or layout differs from this bundle. "
                    "Existing files were preserved. Use the original selection or a separate folder; "
                    "RecordPrep will not clear an existing bundle automatically.")
            if self._has_layout_dependent_work(root_dir):
                if not self._step_artifact_complete("create_files", root_dir, self.selected_pdfs):
                    raise ValueError("Create files blocked: prepared work exists with incomplete source pages. "
                                     "Restore missing source pages in a recovery copy; existing files were preserved.")
                # This is already a prepared record, not a new extraction. In
                # particular, never re-merge PDFs or rewrite its manifest here.
                success = True
                return True
            root_dir, text_dir, image_pages_dir = _ensure_case_bundle_dirs(base_dir)
            if new_case_profile is not None:
                from recordprep.case_profiles import apply_case_profile
                apply_case_profile(root_dir, new_case_profile, expected_previous=None)
                self._pending_preparation_profile = None
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
            "Detected transcript layout differs from the prepared split. "
            "Existing work is preserved; review the layout and use a separate "
            "folder if the source layout must change."
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
        return self._run_pi_skill_step("infer_case", self.step_infer_case_row)

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

    def on_step_build_summary_editions_clicked(self, _row: Adw.ActionRow) -> None:
        root_dir = self._resolve_case_root()
        if root_dir is None:
            if self.selected_pdfs:
                self.show_toast("Selected PDFs must be in the same folder.")
            else:
                self.show_toast("Choose PDF files or select a saved case first.")
            return
        self._launch_single_step(
            self.step_build_summary_editions_row,
            self._run_step_build_summary_editions,
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
                    GLib.idle_add(self._finish_step, row, "Already complete")
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
                        "in Model settings."
                    )
                command_argv[0] = str(executable_path)
            elif shutil.which(executable) is None:
                raise ValueError(
                    "PI executable not found. Install PI or set the PI command in Model settings."
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

            if step_id == "infer_case":
                from recordprep.case_name_stage import is_current
                if self._resolve_case_root() != root_dir or not is_current(root_dir, PI_PROJECT_DIR):
                    raise ValueError("Case-name output changed; rerun Infer case.")
                case_name = _load_case_name_from_file(root_dir)
                save_case_context(case_name, root_dir.parent)
                GLib.idle_add(self.selected_label.set_text, f"Selected: {case_name.replace('_', ' ')}")
                self._safe_update_manifest(root_dir, {"last_completed_step": "infer_case",
                                                       "last_failed_step": None, "last_failed_at": None})
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
        root_dir = self._resolve_case_root()
        if root_dir is not None and is_ct_only(root_dir):
            # CT-only: participant indexing cannot attribute anything
            # without reporter's-transcript evidence. Skip before any VTE,
            # PI command resolution, or process launch; the step is a
            # successful no-op, not a failure, and launches no PI process.
            self._raise_if_stop_requested()
            message = ct_only_skip_message(root_dir)
            GLib.idle_add(self._append_log_message, message, "INFO")
            GLib.idle_add(
                self.show_toast,
                f"Build participant and witness index: {CT_ONLY_SKIP_LABEL}.",
                "INFO",
            )
            GLib.idle_add(
                self._finish_step,
                self.step_build_participant_index_row,
                "Skipped",
            )
            return True
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
            classification_run = ClassificationRun.begin(root_dir, "basic", shared_settings)
            classification_dir = classification_run.directory
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
                "profile_snapshot": classification_run.profile, "profile_kind": "rt",
                "disable_reasoning": bool(
                    shared_settings.get("disable_reasoning", DEFAULT_DISABLE_REASONING)
                ),
            }
            basic_ct_settings = {
                "api_url": shared_settings["api_url"],
                "model_id": shared_settings["model_id"],
                "api_key": shared_settings["api_key"],
                "prompt": shared_settings.get("ct_prompt") or shared_settings.get("prompt"),
                "profile_snapshot": classification_run.profile, "profile_kind": "ct",
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
            classification_run.publish(load_classifier_settings())
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
            settings = load_advanced_classify_settings()
            classification_run = ClassificationRun.begin(root_dir, "advanced", settings)
            classification_dir = classification_run.directory
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
                payload = classification_run.payload(payload, "first_hearing" if updated_type.startswith("RT") else
                                                       "first_minute" if "minute" in updated_type else "first_form")
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
            classification_run.publish(load_classifier_settings())
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
            classification_run = ClassificationRun.begin(root_dir, "corrected", load_classifier_settings())
            classification_dir = classification_run.directory
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
            classification_run.publish(load_classifier_settings())
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
            settings = load_classify_dates_settings()
            shared_settings = load_classifier_settings()
            classification_run = ClassificationRun.begin(root_dir, "dates", shared_settings)
            classification_dir = classification_run.directory
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
                                        "profile_snapshot": classification_run.profile, "profile_kind": "date_hearing",
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
                                        "profile_snapshot": classification_run.profile, "profile_kind": "date_minute",
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
            classification_run.publish(load_classifier_settings())
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
            settings = load_classify_names_settings()
            shared_settings = load_classifier_settings()
            classification_run = ClassificationRun.begin(root_dir, "names", shared_settings)
            classification_dir = classification_run.directory
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
                                        "profile_snapshot": classification_run.profile, "profile_kind": "report",
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
                                        "profile_snapshot": classification_run.profile, "profile_kind": "form",
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
            classification_run.publish(load_classifier_settings())
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
            from recordprep.case_profiles import resolve_case_profile
            from recordprep.boundary_profiles import boundary_inputs, publish_toc
            toc_profile = resolve_case_profile(root_dir)
            toc_expected = boundary_inputs(root_dir, toc_profile, load_classifier_settings())
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
            previous_report_page: int | None = None
            unresolved_names = 0
            for entry in basic_entries:
                self._raise_if_stop_requested()
                page_type = _extract_entry_value(entry, "page_type", "pagetype").strip().lower()
                name_value = _extract_entry_value(entry, "name", "report_name", "form_name")
                file_name = _extract_entry_value(entry, "file_name", "filename")
                page_number = _extract_page_number(file_name)
                is_report = page_type in report_types and page_number is not None and page_number > split_page
                is_report_start = is_report and (
                    previous_report_page is None or page_number != previous_report_page + 1
                )
                previous_report_page = page_number if is_report else None
                if page_number is None or page_number <= split_page:
                    continue
                if not name_value:
                    if is_report_start:
                        unresolved_names += 1
                    # Selection only: retain every source page/classification.
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
                    if toc_profile is None:
                        continue
                    date_value = "Date unresolved"
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
            publish_toc(root_dir, toc_profile, toc_expected, load_classifier_settings(), "\n".join(toc_lines).rstrip() + "\n")
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
            if unresolved_names:
                GLib.idle_add(
                    self.show_toast,
                    f"{unresolved_names} unnamed report runs omitted from navigation; source pages retained.",
                    "WARN",
                )
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
            # Keep each retained line's formatting, including CRLF and final
            # blank lines; correction removes entries, not unrelated whitespace.
            with toc_path.open(encoding="utf-8", errors="ignore", newline="") as stream:
                toc_lines = stream.read().splitlines(keepends=True)
            from recordprep.case_profiles import resolve_case_profile
            from recordprep.boundary_profiles import boundary_inputs, publish_toc
            toc_profile = resolve_case_profile(root_dir)
            toc_expected = boundary_inputs(root_dir, toc_profile, load_classifier_settings())
            corrected_lines, _removals = _correct_toc_lines(
                toc_lines, self._raise_if_stop_requested
            )
            publish_toc(root_dir, toc_profile, toc_expected, load_classifier_settings(),
                        "".join(corrected_lines))
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
            GLib.idle_add(self.show_toast, f"Correct TOC complete. {_removals} duplicate date entries removed; separate orders retained.")
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
            from recordprep.case_profiles import resolve_case_profile
            from recordprep.boundary_profiles import boundary_inputs, publish_boundaries
            boundary_profile = resolve_case_profile(root_dir)
            boundary_expected = boundary_inputs(root_dir, boundary_profile, load_classifier_settings())
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
            unnamed_report_runs = 0
            previous_report_number = None
            for file_name, page_type, page_number in entries:
                if page_number > split_page and page_type == "ct_report":
                    if previous_report_number != page_number - 1 and not report_name_by_file.get(file_name):
                        unnamed_report_runs += 1
                    previous_report_number = page_number
                else:
                    previous_report_number = None
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
            filtered_minutes: list[dict[str, str]] = []
            seen_minute_dates: set[str] = set()
            for entry in minutes_boundaries:
                if boundary_profile is not None:
                    # Date uncertainty and a shared date never erase distinct
                    # source orders in the profile-aware fidelity contract.
                    filtered_minutes.append(entry)
                    continue
                date_value = str(entry.get("date", "")).strip()
                if not date_value or date_value in seen_minute_dates:
                    continue
                seen_minute_dates.add(date_value)
                filtered_minutes.append(entry)
            publish_boundaries(root_dir, boundary_profile, boundary_expected, load_classifier_settings(), {
                "hearing_boundaries.json": hearing_boundaries, "report_boundaries.json": report_boundaries,
                "minutes_boundaries.json": filtered_minutes,
            })
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
            if unnamed_report_runs:
                GLib.idle_add(
                    self.show_toast,
                    f"{unnamed_report_runs} unnamed report runs omitted from standalone summaries; source pages retained.",
                    "WARN",
                )
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
            from recordprep.case_profiles import resolve_case_profile
            from recordprep.boundary_profiles import boundary_inputs, publish_boundaries
            boundary_profile = resolve_case_profile(root_dir)
            boundary_expected = boundary_inputs(root_dir, boundary_profile, load_classifier_settings())
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
                if not date_value and boundary_profile is None:
                    hearing_removed += 1
                    continue
                filtered_hearings.append(entry)
            report_removed = 0
            filtered_reports: list[dict[str, str]] = []
            for entry in report_entries:
                self._raise_if_stop_requested()
                report_name = _extract_entry_value(entry, "report_name", "report", "name")
                # Never infer eligibility from a historical synthetic label.
                if not report_name or entry.get("naming_status") == "unresolved":
                    report_removed += 1
                    continue
                filtered_reports.append(entry)
            if boundary_profile is not None:
                publish_boundaries(root_dir, boundary_profile, boundary_expected, load_classifier_settings(), {
                    "hearing_boundaries.json": filtered_hearings, "report_boundaries.json": filtered_reports,
                    "minutes_boundaries.json": _load_json_entries(derived_dir / "minutes_boundaries.json"),
                })
            else:
                hearing_path.write_text(json.dumps(filtered_hearings, indent=2), encoding="utf-8")
                report_path.write_text(json.dumps(filtered_reports, indent=2), encoding="utf-8")
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
                f"{report_removed} unnamed report entries omitted from standalone summaries "
                f"({removed} total); source pages retained.",
            )
        finally:
            GLib.idle_add(self.step_correct_boundaries_row.set_sensitive, True)
            GLib.idle_add(self._finish_step, self.step_correct_boundaries_row, success)
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True or success == "Skipped"







    def _run_step_create_hearing_summaries(self) -> bool:
        """Create hearing summaries through the two-stage PI pipeline."""
        return self._run_pi_skill_step(
            "create_hearing_summaries",
            self.step_hearing_summaries_row,
        )

    def _run_step_create_report_summaries(self) -> bool:
        """Create report summaries through the two-stage PI pipeline."""
        return self._run_pi_skill_step(
            "create_report_summaries",
            self.step_report_summaries_row,
        )

    def _run_step_create_minute_order_summaries(self) -> bool:
        """Direct-source Pi summaries sharing the synthesis model selection."""
        return self._run_pi_skill_step(
            "create_minute_order_summaries", self.step_minute_order_summaries_row
        )

    def _run_step_build_summary_editions(self) -> bool:
        """Build and publish page-matched Letter PDFs and Focus page maps.

        All three candidates are built and validated before any existing
        edition is replaced, so an ordinary rendering failure never leaves a
        mixed update. Messages carry only categories and page counts.
        """
        success: bool | str | None = False
        root_dir: Path | None = None
        page_counts: dict[str, int] = {}
        try:
            self._raise_if_stop_requested()
            root_dir = self._resolve_case_root()
            if root_dir is None:
                if self.selected_pdfs:
                    raise ValueError("Selected PDFs must be in the same folder.")
                raise ValueError("Choose PDF files or select a saved case first.")
            sources = _summary_edition_sources(root_dir)
            for kind in SUMMARY_EDITION_KINDS:
                if not sources[kind].exists():
                    raise FileNotFoundError(
                        "Run the summary steps to generate all three summaries first."
                    )
            editions: dict[str, SummaryEdition] = {}
            for kind in SUMMARY_EDITION_KINDS:
                self._raise_if_stop_requested()
                editions[kind] = build_summary_edition(
                    kind,
                    sources[kind],
                    root_dir,
                )
                page_counts[kind] = editions[kind].page_map["pdf"]["page_count"]
            for kind in SUMMARY_EDITION_KINDS:
                self._raise_if_stop_requested()
                publish_summary_edition(editions[kind], sources[kind])
        except StopRequested:
            success = None
        except SummaryEditionError as exc:
            GLib.idle_add(
                self.show_toast,
                f"Build paginated summary editions failed: {exc}",
            )
        except Exception as exc:
            GLib.idle_add(
                self.show_toast,
                f"Build paginated summary editions failed: {exc}",
            )
        else:
            success = True
            assert root_dir is not None
            self._safe_update_manifest(
                root_dir,
                {
                    "last_completed_step": "build_summary_editions",
                    "last_failed_step": None,
                    "last_failed_at": None,
                },
            )
            counts_text = ", ".join(
                f"{kind} {page_counts[kind]} pages"
                for kind in SUMMARY_EDITION_KINDS
            )
            GLib.idle_add(
                self.show_toast,
                f"Build paginated summary editions complete ({counts_text}).",
            )
        finally:
            GLib.idle_add(self.step_build_summary_editions_row.set_sensitive, True)
            GLib.idle_add(
                self._finish_step, self.step_build_summary_editions_row, success
            )
            GLib.idle_add(self._stop_status_if_idle)
            GLib.idle_add(self._stop_button_if_idle)
        return success is True



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
            boundary = {
                "report_name": report_name,
                "report_date": report_date,
                "report_label": _format_report_label(report_name, report_date),
                "report_id": _report_id_from_start_page(start_page),
                "start_page": start_page,
                "end_page": end_page,
            }
            report_boundaries.append(boundary)
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
        naming_contract = settings.get("naming_contract")
        if naming_contract is not None and not isinstance(naming_contract, NamingContract):
            raise ValueError("Invalid application-owned naming contract")
        profile = settings.get("profile_snapshot")
        profile_kind = settings.get("profile_kind")
        effective_prompt = naming_contract.prompt if naming_contract is not None else settings["prompt"]
        if profile is not None:
            effective_prompt, _keys = classifier_prompt(profile, profile_kind)
            if profile_kind in ("report", "form"):
                from recordprep.document_naming import compile_naming_profile
                naming_contract = compile_naming_profile(profile, profile_kind)
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
                {"role": "system", "content": effective_prompt},
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
        if naming_contract is not None:
            named = naming_contract.normalize(parsed)
            result = {"file_name": filename, "name": named.name}
            if naming_contract.kind == "report":
                result["date"] = named.date
            return result
        if profile is not None:
            from recordprep.classification_profiles import normalize_classifier
            return {"file_name": filename, **normalize_classifier(parsed, profile_kind)}
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
