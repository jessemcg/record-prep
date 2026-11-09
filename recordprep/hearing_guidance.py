"""Fixed practice-neutral hearing topics. Historical profile topics stay inert."""
from copy import deepcopy
import hashlib
import json

APPLICATION_CONTRACT = 'recordprep-hearing-topics-1'
HEARING_TOPICS = [
    # Retain the established serialized ID; its new display title and scope are neutral.
    {'id': 'parent_appearances', 'title': 'Appearances', 'guidance':
     "Which parties appeared and how (in person or remotely), and any expressly recorded absence. "
     "Distinguish a party's personal appearance from appearance by counsel or a representative; "
     "counsel appearing alone does not establish the party's personal presence. "
     "For an entity, describe its stated representation without implying personal physical presence. "
     "Use the source's party names or roles. Silence does not establish absence; if the source supplies "
     "no party-appearance information, the category is null."},
    {'id': 'evidence_considered', 'title': 'Evidence Considered', 'guidance':
     'Testimony, reports, exhibits, records, and stipulations the court\nconsidered, plus evidentiary objections and rulings on evidence. Do not\ninclude argument or orders here.'},
    {'id': 'testimony', 'title': 'Testimony', 'guidance':
     'Witnesses who were verified as sworn and the material substance of their\nsworn testimony. Q/A formatting alone does not establish testimony; unsworn\ncolloquy belongs in evidence, not here. If no sworn testimony occurred, the\ncategory is null.'},
    {'id': 'disputed_legal_issues', 'title': 'Disputed Legal Issues', 'guidance':
     'Contested legal or procedural questions argued or decided at the hearing.\nUndisputed matters and routine calendar rulings do not belong here; if\nnothing was disputed, the category is null.'},
    {'id': 'party_positions_and_reasons', 'title': 'Party Positions and Reasons', 'guidance':
     "Each party's position and the stated reasoning, with distinct attribution\nby role. A party without a stated position is omitted; if no positions were\nstated, the category is null."},
    {'id': 'court_orders_and_reasons', 'title': 'Court Orders and Reasons', 'guidance':
     "Major findings and orders the court actually made and the court's stated\nreasons, emphasizing rulings on contested matters. Never include proposed\nor recommended findings or orders as if made."},
]


def application_catalog():
    return deepcopy(HEARING_TOPICS)


def application_metadata():
    return {'application_contract': APPLICATION_CONTRACT,
            'category_catalog': [{'id': t['id'], 'title': t['title']} for t in HEARING_TOPICS]}


def application_guidance(phase):
    from .summary_profiles import summary_core
    return summary_core('hearings', phase) + '\n\nFIXED HEARING TOPICS\n' + json.dumps(HEARING_TOPICS, ensure_ascii=False)


def application_fingerprint(phase):
    return hashlib.sha256(application_guidance(phase).encode()).hexdigest()
