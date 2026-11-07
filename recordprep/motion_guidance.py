"""Practice-neutral motion eligibility and default digest topics.

These defaults are also suitable for new editable profiles, but do not opt an
existing assigned profile into motion selection. No Dependency profile lookup.
"""
MOTION_ELIGIBILITY = (
    "Free-form motions, motion-like applications or requests, oppositions, replies, "
    "supplemental briefs, points and authorities, and separately titled supporting "
    "declarations, regardless of filing party. Include a combined notice-and-motion "
    "whose substantive purpose is requesting relief. Preserve each separately titled "
    "paper as its own document; do not infer a family from proximity. Standardized "
    "qualifying court request forms remain Forms. Exclude standalone hearing notices, "
    "service proofs, court rulings/minute orders and neutral court-directed reports. "
    "Agency-authored advocacy can qualify; neutral agency reports remain Reports. "
    "Separately reproduced exhibits retain their own classification. A running title "
    "or internal heading alone is not a new document; a combined filing stays one "
    "paper unless a distinct opening is established."
)
NEUTRAL_MOTION_NAMING = {"schema_version": 1, "motions": [
    {"id": "motion-papers", "name": "Motion Paper", "guidance": MOTION_ELIGIBILITY,
     "naming_mode": "source_title"},
]}
MOTION_TOPICS = [
    {"id": "requested_relief", "title": "Requested relief and position",
     "guidance": "Requested relief and the filing party's position. Attribute requests and argument; do not describe them as rulings."},
    {"id": "procedural_context", "title": "Material procedural context",
     "guidance": "Material procedural context as presented by this paper, retaining supported dates and qualifications."},
    {"id": "facts_and_evidence", "title": "Material facts and supporting evidence",
     "guidance": "Attribute factual assertions to their author. Preserve important contrary evidence and distinguish allegations from findings."},
    {"id": "legal_grounds", "title": "Legal grounds and authorities",
     "guidance": "Legal grounds and authorities only as presented in the paper. No external research or invented holdings."},
    {"id": "responses", "title": "Responses to arguments or papers",
     "guidance": "Responses to other arguments or papers, with source-supported relationships only. Do not import later responses or rulings into this paper."},
    {"id": "qualifications", "title": "Qualifications, concessions and limitations",
     "guidance": "Material qualifications, concessions and limitations needed for a balanced understanding, without routine negative checklists."},
]
