"""Offline no-change reviewer for synthetic pipeline integration tests only."""
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch
import json
import tempfile
from recordprep import classification_review as review


def complete_review(root):
    project = Path(__file__).resolve().parents[1] / '.pi'
    with tempfile.TemporaryDirectory() as temp, \
         patch.object(review, 'resolve_case_profile', return_value=None), \
         patch.object(review, 'read_case_profile_ref', return_value=None), \
         patch.object(review, '_model_settings', return_value=[]), \
         patch.object(review, 'case_profile_publication', side_effect=lambda *a: nullcontext()):
        workspace = Path(temp)
        guard, ref, candidate, spec, _ = review.stage_inputs(root, project, workspace)
        access = json.loads(spec.read_text())
        Path(access['journal']).write_text('\n'.join(json.dumps(p) for p in access['reads']))
        worklist = json.loads((workspace / 'review-worklist.json').read_text())
        candidate.write_text(json.dumps({'schema_version':1, 'reviewed_blocks':[b['id'] for b in worklist['blocks']],
                                         'changes':[], 'unresolved':[]}))
        review.publish(root, project, guard, ref, candidate)
