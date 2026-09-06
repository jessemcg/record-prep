<!-- recordprep:summary-categories v1 kind:hearings -->
# Hearing Category Guidance

Editable per-category extraction guidance for hearing documents. Category
ids, display titles, ordering, and null semantics are code-owned and must
not change here; edit only the prose beneath each heading. The loader
rejects missing, duplicated, unknown, reordered, or empty sections before
any paid work.

## parent_appearances

Which parents personally appeared and how (in person or remotely). An
appearance by counsel only is not a parent appearance; if no parent
personally appeared, the category is null.

## evidence_considered

Testimony, reports, exhibits, records, and stipulations the court
considered, plus evidentiary objections and rulings on evidence. Do not
include argument or orders here.

## testimony

Witnesses who were verified as sworn and the material substance of their
sworn testimony. Q/A formatting alone does not establish testimony; unsworn
colloquy belongs in evidence, not here. If no sworn testimony occurred, the
category is null.

## disputed_legal_issues

Contested legal or procedural questions argued or decided at the hearing.
Undisputed matters and routine calendar rulings do not belong here; if
nothing was disputed, the category is null.

## party_positions_and_reasons

Each party's position and the stated reasoning, with distinct attribution
by role. A party without a stated position is omitted; if no positions were
stated, the category is null.

## court_orders_and_reasons

Major findings and orders the court actually made and the court's stated
reasons, emphasizing rulings on contested matters. Never include proposed
or recommended findings or orders as if made.
