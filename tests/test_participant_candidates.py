import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from recordprep.participant_candidates import normalize_participant_candidate, ParticipantCandidateError
from recordprep.profile_artifacts import PARTICIPANT_TEMPLATE_WARNING, participant_index_issues
from test_participant_stage import _build_record_fixture, _review_general_hearing

PROJECT = Path(__file__).resolve().parents[1]
HELPER = PROJECT / '.pi/skills/recordprep-build-participant-index/scripts/participant_index.py'


class ParticipantCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = _build_record_fixture(self.temp.name, hearings=2)
        spec = importlib.util.spec_from_file_location('candidate_helper_test', HELPER)
        self.helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.helper)
        self.path = self.helper.prepare(self.root)
        self.template = json.loads(self.path.read_text())
        self.payload = copy.deepcopy(self.template)
        self.payload['hearings'] = [_review_general_hearing(h, i) for i, h in enumerate(self.payload['hearings'], 1)]

    def test_repairs_optional_fields_keeps_useful_people_and_is_idempotent(self):
        for hearing in self.payload['hearings']:
            counsel = hearing['counsel'][0]
            for key in ('represents', 'organization', 'aliases', 'speaking_status', 'sworn_status'):
                counsel.pop(key, None)
            counsel['appearance_status'] = 'not sure'
            hearing['participants'][0]['id'] = ''
            hearing['participants'][0]['role_label'] = ''
        original = copy.deepcopy(self.payload)
        normalized, codes = normalize_participant_candidate(self.payload)
        self.assertEqual(self.payload, original)
        self.assertEqual(participant_index_issues(normalized), [])
        self.assertIn('status_unresolved', codes)
        for before, hearing in zip(self.payload['hearings'], normalized['hearings']):
            self.assertEqual(len(hearing['counsel']), len(before['counsel']))
            self.assertEqual(hearing['counsel'][0]['name'], before['counsel'][0]['name'])
            self.assertEqual(hearing['counsel'][0]['appearance_status'], 'unknown')
            self.assertEqual(hearing['counsel'][0]['sworn_status'], 'unknown')
            self.assertEqual(hearing['participants'][0]['role_label'], 'Unknown')
            self.assertTrue(any('status_unresolved' in w for w in hearing['warnings']))
        self.assertEqual(normalize_participant_candidate(normalized)[0], normalized)
        self.assertNotIn(PARTICIPANT_TEMPLATE_WARNING, normalized['warnings'])

    def test_unreviewed_template_never_becomes_a_completed_empty_index(self):
        with self.assertRaisesRegex(ParticipantCandidateError, 'not been completed|not been reviewed'):
            normalize_participant_candidate(self.template)
        partial, _ = normalize_participant_candidate(self.template, partial=True)
        self.assertIn(PARTICIPANT_TEMPLATE_WARNING, partial['hearings'][0]['warnings'])

    def test_unsupported_entries_warn_instead_of_inventing_absence(self):
        hearing = self.payload['hearings'][0]
        hearing['counsel'][0]['evidence'] = []
        hearing['witnesses'][0]['examinations'] = []
        hearing['witness_status'] = 'none'
        result, codes = normalize_participant_candidate(self.payload)
        hearing = result['hearings'][0]
        self.assertEqual(hearing['witness_status'], 'unknown')
        self.assertEqual(hearing['witnesses'], [])
        self.assertIn('unsupported_person_omitted', codes)
        self.assertIn('unsupported_witness_omitted', codes)
        self.assertEqual(participant_index_issues(result), [])

    def test_structural_and_path_errors_remain_failures(self):
        for change, expected in (
            (lambda h: h.update(end_page=0), 'invalid page range'),
            (lambda h: h['counsel'][0]['evidence'][0].update(text_path='../private.txt'), 'unsafe text_path'),
            (lambda h: h['witnesses'][0]['examinations'][0].update(start_file_page=999), 'outside its page range'),
        ):
            with self.subTest(expected=expected):
                value = copy.deepcopy(self.payload)
                change(value['hearings'][0])
                with self.assertRaisesRegex(ParticipantCandidateError, expected):
                    normalize_participant_candidate(value)

    def test_helper_normalizes_only_private_candidate_not_published_index(self):
        candidate = Path(self.temp.name) / 'private-candidate.json'
        candidate.write_text(json.dumps(self.payload))
        original = self.path.read_bytes()
        env = os.environ | {'RECORDPREP_APPLICATION_ROOT': str(PROJECT),
                            'RECORDPREP_PARTICIPANT_CANDIDATE': str(candidate)}
        result = subprocess.run([sys.executable, str(HELPER), 'validate', str(self.root), '--normalize'],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(participant_index_issues(json.loads(candidate.read_text())), [])
        self.assertEqual(self.path.read_bytes(), original)
        env['RECORDPREP_PARTICIPANT_CANDIDATE'] = str(self.path)
        refused = subprocess.run([sys.executable, str(HELPER), 'validate', str(self.root), '--normalize'],
                                 env=env, capture_output=True, text=True)
        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual(self.path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
