# Summary category resources

Tracked, editable Markdown guidance for the hearing and report extraction
categories. These files replace the former hard-coded per-category guidance
strings in `recordprep/summary_agents.py`.

## File contract

Each resource file starts with a machine-readable header comment:

```
<!-- recordprep:summary-categories v1 kind:hearings -->
```

followed by optional prose and exactly one level-two heading per category
id, in the code-owned order:

```
## parent_appearances

Editable guidance prose for this category.
```

The loader (`recordprep/summary_categories.py`) enforces the contract
strictly using only the standard library:

- The file must exist and its header must declare the supported version and
  the matching kind.
- Every code-owned category id must appear exactly once as a level-two
  heading, in the code-owned order.
- No unknown or duplicated category headings are allowed.
- Each section must contain non-empty guidance text.
- A missing or malformed resource is an actionable error raised before any
  paid work; embedded fallback guidance is never silently substituted.

Category **ids, display titles, ordering, and null semantics are code-owned**
(`recordprep/summary_agents.py`) and must not be changed in these files. Only
the guidance prose beneath each heading is editable. Digest Markdown heading
titles keep using the code-owned display titles, so previously published
digest stores remain parseable.

## Customization for forks

Edit the prose beneath a heading to retrain extraction emphasis for a fork.
Descriptions are loaded once per summary stage and frozen for that stage;
edits take effect the next time a summary stage runs. Changing one kind's
descriptions changes only that kind's extraction fingerprints, so published
rows for that kind become regeneration-pending and re-extract on the next
stage run — inspection never triggers regeneration by itself.

These files are generated-resource inputs, not generated artifacts: never
point Settings or the application at them for writing. The digest Markdown
under a case bundle's `summaries/` directory is a different, generated,
inspection-only artifact and must never be hand-edited.
