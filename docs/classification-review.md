# Read-only structural review and fictional examples

## Method and confidentiality boundary

A local read-only review inspected **212 existing page images** in stratified
contact sheets. Selection covered all historical RT/CT label groups, first-page
variants, multiple bundles, rare RT-other material with its neighbors, and targeted
hearing-notice, appeal, service-proof, authentication and report distinctions.
The existing final classification JSONL and page text were used only to stratify
and target images. One malformed historical JSONL was excluded and left untouched.
Historical labels were **not** accepted as expected answers; text alone was not a
substitute for looking at the selected images.

No OCR, source extraction or RecordPrep classifier/model request was run. There
was no label correction, case write, private configuration/profile change,
OCR/model service start or other-computer access.
Temporary review sheets, their client-linked index and the disposable scanner were
removed after review. No private image, OCR excerpt, path, identifier, date,
reconstructed legal fact or page-linked annotation belongs in the repository.
Only the abstract findings below and separately authored fictional examples are
retained. No private review derivative is exported or packaged.

## Abstract findings → definition decisions

- A spoken-proceedings page can continue a long speech without a fresh speaker or
  Q/A label. RT body recognition must include that continuation, while separating
  appearance **lists** in front matter from transcribed spoken appearances.
- Index continuation/end pages may be sparse. Navigational purpose and location
  references matter more than a repeated title or a particular table layout.
- Transcript attestations are distinct from speech about a certificate. Record
  authentication is distinct from proving service, regardless of the word
  “certificate” in a title.
- Minute records can end with signatures, attestation or integral mailing blocks.
  A sparse ending does not automatically become a separate certificate/proof. A
  distinct dedicated proof page, however, retains its own service function.
- Court-directed reports can contain identifying tables, procedural information,
  recommendations or signature-only endings without narrative on every page.
  Operational records, raw results and separately reproduced exhibits need their
  own functional assessment. Report titles/agency templates alone are insufficient.
- Standardized appearance does not settle page type. Hearing-notice purpose and
  dedicated service-proof purpose govern even when a court form supplies the
  layout. Notice of Appeal/address/status forms do not announce a hearing merely
  because their titles use “notice” or “notification.”
- A party's argument or supporting declaration is not automatically a standardized
  form because it mentions a form. Requested relief/recommendations are not rulings.
- Later-page headings, running titles, codes and printed pagination are supporting
  clues, not start detectors by themselves. Unseen neighboring content must not be
  invented; adjacent and unnamed report starts still require independent checks.
- Missing expected headings, codes, signatures, footers or fresh speaker labels do
  not justify defaulting an otherwise recognizable continuation to Other.

These findings led to the neutral purpose/continuation/near-neighbor definitions
in the packaged recognition resource, not a new taxonomy, precedence cascade,
practice-specific label subset or mandatory visual checklist.

## Authored fictional examples

`tests/fixtures/recognition-fictional.json` contains **27 newly authored textual
scenarios**, covering all 15 Basic labels and positive/negative examples for all
four start tasks. They are not quotations, redacted private pages or model output.
Examples deliberately distinguish:

| Pair / variant | Expected structural distinction |
|---|---|
| Listed appearances / spoken opening / continuous speech | RT_cover / RT_body start / RT_body continuation |
| Sparse index ending / distinct reporter attestation | RT_index / RT_certificate |
| Collection title page / document index | CT_cover / CT_index |
| Fresh minute record / integral mailing-signature ending | CT_minute_order start / continuation |
| Fresh court-directed evaluation / table / signature ending | CT_report start / report continuations |
| Court-directed report / operational report exhibit | CT_report / CT_other |
| Standard hearing notice / notice with integral service block | CT_notice; both excluded from form work |
| Dedicated proof in notice packet / mailing certificate / recipient-list continuation | CT_proof_of_service; excluded from form work |
| Record authentication / certificate of mailing | CT_certificate / CT_proof_of_service |
| Notice of Appeal / address notification / standard order form | CT_form, not hearing notices |
| Standard form ending / free-form supporting declaration | CT_form continuation / CT_motion |
| Free-form motion / standalone written order not meeting form/minute definitions | CT_motion / CT_other |

The fixture tests validate coverage and eligibility expectations. Fake HTTP workers
validate actual request routing, JSON handling, first-page/naming exclusions and
Forms TOC selection, including misleading historical name fields. Neither the
fictional fixture nor a fake response proves image-model accuracy. Paid/live model
quality evaluation and private-record regeneration were not performed.
