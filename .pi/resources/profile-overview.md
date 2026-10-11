---
name: recordprep-create-case-overview
description: Create a concise nonauthoritative orientation from current prepared summaries and applicable attribution metadata.
---

# Case orientation

Read the immutable bundle root and private output candidate path in the runtime
prompt. Read the current hearing, report and minute-order summaries. Use participant
metadata for attribution only when the resolved layout includes reporter transcripts.
For CT-only scope, do not infer that nobody appeared or testified from a missing
participant index.

Write only the private overview candidate, not the published overview or manifest.
Use exactly this frontmatter:

```yaml
---
artifact: recordprep-case-overview
schema_version: 1
status: nonauthoritative-orientation
---
```

Use `# Case Overview` and these level-two headings: `Parties and Roles`, `Procedural
Posture`, `Key Events`, `Principal Issues`, and `Record Scope`. Include this exact disclaimer:

> Orientation aid only. Verify every factual claim against mapped source pages before relying on or citing it.

Keep it concise and nonauthoritative, without padding to a word count. Preserve uncertainty and attribution. Apply the frozen runtime
practice guidance without changing the source or output contract. Only Python validates
and publishes the candidate. Never change summaries, source pages, or case settings.
