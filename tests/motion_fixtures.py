"""Synthetic schema-1 fixture builder, not a production organization path."""
import copy
from recordprep.motion_groups import ARTIFACT, singleton
from recordprep.profile_artifacts import validate_motion_groups


def historical_artifact(candidate, inventory, fingerprint, *, inputs=None):
    by_id = {p['paper_id']: p for p in inventory}
    groups, assigned = [], set()
    for proposal in candidate['groups']:
        lead = by_id[proposal['lead_paper_id']]
        members = sorted(proposal['member_paper_ids'], key=lambda m: by_id[m]['start_page'])
        group = singleton(lead)
        group.update({k: proposal[k] for k in ('filing_role', 'filing_party', 'purpose', 'date', 'date_basis', 'relationship_to', 'relationship_notes') if k in proposal})
        group.update(member_paper_ids=members, components=[dict(paper_id=m, role='lead' if m == lead['paper_id'] else 'support',
                     start_page=by_id[m]['start_page'], end_page=by_id[m]['end_page']) for m in members])
        groups.append(group); assigned.update(members)
    groups.extend(singleton(p) for p in inventory if p['paper_id'] not in assigned)
    result = dict(artifact=ARTIFACT, schema_version=1, organization_contract='recordprep-motion-organization-1',
                  inventory=copy.deepcopy(inventory), input_sha256=fingerprint, inputs=inputs or {},
                  groups=sorted(groups, key=lambda g: g['anchor_page']), findings=candidate.get('findings', []),
                  coverage_status=candidate.get('coverage_status', 'complete'))
    validate_motion_groups(result)
    return result
