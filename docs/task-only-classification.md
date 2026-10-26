# Task-only classification

Classification settings starts with Reporter transcript pages, followed by the
RT and CT task editors. Common guidance is removed: no editor, default text file,
shared prompt composition, or component dependency remains. The application-owned
contract continues to enforce source evidence, uncertainty, taxonomy and response
keys. Each task supplies its own specialty instructions. Naming remains separate.

Dependency's former shared sentence duplicated recognition clues already present
in its RT and CT tasks; no replacement shared instruction or mass-copy into every
task was needed. Existing task-specific personal wording is not rewritten.

## Storage

RecordPrep content schema 6 rejects the common `classification` resource.
Both the public Dependency resources and the compatibility-only General resource
directory omit the file. Profile settings upgrades its draft to schema 6; Save
publishes only declared resources, so the new revision contains neither the field
nor its old text/file. There is no backup field or automatic redistribution of
old common text into task prompts.

Private configuration and already accepted immutable snapshots are not rewritten,
deleted or migrated by agent scripts or startup. The narrow old-schema validator
still reads schemas 1–5 for existing data. Their common text is immediately inert:
it is absent from classifier prompts and stage fingerprints, even before Save.
Schema-1 profiles, which lack task guidance, use the fixed classifier contract;
explicit editing supplies the existing supported task defaults.

Focus's vendored `profile_contract.py` is updated byte-identically for schema-6
validation only; Focus's neutral research method and UI are unchanged. Keep the
RecordPrep and Focus changes in separate commits.

## Freshness and reviewed native compatibility

Classifier contract 2 and removal of the common component honestly invalidate old
classifier checkpoints for explicit classification work. Existing outputs, badges,
Resume and private case metadata are not rewritten or reset. Naming and summary
component definitions are unchanged.

Native stage identity includes the entire shared profile-contract file. Review of
this change found only the schema-6 resource omission and classification component
selection changes: participant/overview resources, evidence validators, prompts,
source hashing, model checks and publication guards are unchanged. Recomputing
stage digests with the HEAD profile-contract hash substituted reproduces the exact
prior guarded baselines:

- Participants: `675abd27aec9aba67b9f7b9c49a3ebf176769bcfdba6ff3c4adba21e1e3dd426`
  → `8a89f981f32ce6c8c4b01eac1e6b37b2a6c441953a178ec276ab44859902d558`.
- Overview: `60ca803cf2d915411a4cac0fed419a787d8c43caf2fc26ab65eb446cb54c92b0`
  → `e70c1a22603136ea2492aa9620db53febf842c004d98b808eea3572bb7a942f1`.

The compatibility registry adds only those exact prior code identities under the
new guarded baselines. Actual source/model/component checks remain mandatory;
future code changes disable the exception. No private metadata is repaired.

## Validation

- `test_task_only_classification.py`: schema-6 resource rejection, removal on
  explicit edit/save, old common-text prompt/fingerprint isolation for schemas 1–5,
  and unchanged unrelated stage components.
- Profile, native/pipeline, summary/overview and unified GTK settings suites.
- Real GTK create-profile and delete-profile acceptance with isolated stores.
- Native desktop observation of the task-only Classification outline and editor
  using temporary settings; the user's running application was not restarted.
- Focus profile contract/artifact/map-reader tests, including schema 6.
- PI resource validation and byte-identical vendored contract check.

No live model calls, private profile cleanup or case regeneration was performed.
