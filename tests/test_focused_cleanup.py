"""Focused cleanup contracts; fictional inputs and offline delivery only."""
import ast
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from recordprep import summary_agents as sa, motion_guidance as guidance
from recordprep.ui import main_window as ui
from test_minute_summaries import fixture
from test_structured_classification import bundle

ROOT = Path(__file__).resolve().parents[1]


class FocusedCleanupTests(unittest.TestCase):
    def test_pipeline_subtitles_match_current_operations(self):
        tree = ast.parse((ROOT / 'recordprep/ui/main_window.py').read_text())
        subtitles = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'ActionRow':
                values = {kw.arg: kw.value.value for kw in node.keywords if isinstance(kw.value, ast.Constant)}
                if 'title' in values and 'subtitle' in values:
                    subtitles[values['title']] = values['subtitle']
        for title, phrase in (
            ('Classification names', 'motion-paper names'), ('Build TOC', 'motions'),
            ('Find boundaries', 'motion papers'), ('Filter boundary entries', 'keep named single-page reports'),
            ('Create hearing summaries', 'proceedings, arguments, and rulings'),
            ('Create minute-order summaries', 'compact appearances, orders, and next-hearing entries'),
        ):
            self.assertIn(phrase, subtitles[title])
        self.assertNotIn('Correct boundaries', subtitles)
        self.assertNotIn('single-page report boundaries unless', subtitles['Filter boundary entries'])
        self.assertNotIn('paragraphs', subtitles['Create minute-order summaries'])

    def test_missing_edition_summary_error_has_no_fixed_category_count(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            worker = SimpleNamespace(_raise_if_stop_requested=Mock(), _resolve_case_root=lambda: root,
                selected_pdfs=[], show_toast=Mock(), step_build_summary_editions_row=Mock(),
                _finish_step=Mock(), _stop_status_if_idle=Mock(), _stop_button_if_idle=Mock(),
                _safe_update_manifest=Mock())
            with patch.object(ui.GLib, 'idle_add', side_effect=lambda fn, *args: fn(*args)):
                self.assertFalse(ui.RecordPrepWindow._run_step_build_summary_editions(worker))
            text = str(worker.show_toast.call_args_list)
            self.assertIn('required summaries', text)
            self.assertNotIn('three summaries', text)
            self.assertNotIn('four summaries', text)

    def test_motion_request_reasons_selection_applies_to_both_phases_and_is_inspectable(self):
        # The later motion follow-up deliberately supersedes synthesis-only selection:
        # fallback final prose comes from the digest, so selection must start there.
        for phase in ('extract', 'synthesize'):
            from recordprep.summary_profiles import compile_summary
            text = guidance.application_guidance(phase)
            for phrase in ('same narrow purpose', 'Exclude hearing dates/times/departments',
                           'street or mailing addresses', 'case/court', 'incident/tracking identifiers',
                           'not a prose checklist', 'Separate opposition example', 'Separate reply example',
                           'excluding privileged advice'):
                self.assertIn(phrase, text)
            self.assertNotIn('only when needed to distinguish', text)
            self.assertNotIn('Keep any omitted detail if material', text)
            self.assertIn(text, compile_summary(bundle(), 'motions', phase).prompt)

    def test_phase_specific_synthesis_skill_and_fixed_guidance_fingerprints(self):
        with tempfile.TemporaryDirectory() as td:
            _root, project = fixture(Path(td), 1)
            profiles = (None, bundle())
            def configs():
                return {(kind, assigned): (sa.effective_extraction_config(project, kind, profile=profile).fingerprint,
                    sa.effective_synthesis_config(project, kind, profile=profile))
                    for assigned, profile in enumerate(profiles) for kind in ('hearings', 'reports', 'motions')}
            before = configs()
            skill = project / 'skills/recordprep-synthesize-motions/SKILL.md'
            skill.write_text(skill.read_text() + '\nFictional synthesis-only refinement.\n')
            after = configs()
            for key in before:
                self.assertEqual(before[key][0], after[key][0])
                if key[0] == 'motions':
                    self.assertNotEqual(before[key][1], after[key][1])
                else:
                    self.assertEqual(before[key], after[key])
            original = guidance.application_guidance
            with patch.object(guidance, 'application_guidance', side_effect=lambda phase:
                    original(phase) + ('\nFictional synthesis-only change.' if phase == 'synthesize' else '')):
                changed = configs()
                for key in after:
                    self.assertEqual(after[key][0], changed[key][0])
                    if key[0] == 'motions':
                        self.assertNotEqual(after[key][1], changed[key][1])
                    else:
                        self.assertEqual(after[key], changed[key])

    def test_protected_explainer_presentation_is_explanation_plus_progression(self):
        # The task's independent whole-file before/after check supplies byte preservation;
        # this contract also guards the existing composition, wrapping and expansion.
        import inspect
        from recordprep.profile_editor_ui import ProfileEditorWindow
        source = inspect.getsource(ProfileEditorWindow._explanation)
        self.assertIn('explanation += "\\n\\n" + (CLASSIFICATION_PROGRESSION if classification else SUMMARY_PROGRESSION)', source)
        self.assertIn('label = wrapped(explanation, margin_top=6, margin_bottom=6)', source)
        self.assertNotIn('ScrolledWindow', source)
        self.assertNotIn('set_max_content_height', source)
