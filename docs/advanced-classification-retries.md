# Advanced classification response retries

Advanced classification retries invalid model answers for all five first-page
checks (hearings, minute orders, forms, reports and motions), with at most three
classification attempts per page. Accepted values remain yes/no and true/false;
missing fields, malformed JSON and unsupported values are not guessed or coerced.
The response validator raises `ClassifierResponseError` for unresolved answers.

After exhaustion, the stage stops with the source filename, check type, attempt
count and a suggestion to retry Advanced or check the classifier model. Diagnostics
do not include model prose. Source/configuration/transport failures and Stop are
not caught by this response retry; existing HTTP transport handling is unchanged.
Stop is checked before each attempt. Failed stages preserve published output;
existing checkpoint and publication behavior is unchanged. In particular, CT
results are still checkpointed as a batch, not after each successful page.

## Validation (2026-11-09, work computer)

Offline synthetic tests in a disposable tracked-source checkout with an isolated
machine-local environment and temporary HOME/XDG state; metrics disabled:

- Full suite: 1,023 tests, 1,015 passed, 8 skipped.
- Classification profile tests: 17 passed, including all five first-page tasks,
  malformed/missing/unsupported responses, recovery on attempt three, sanitized
  exhaustion diagnostics, operational failures and Stop between attempts.
- Report first-page tests: 14 passed after adding explicit assertions that a
  failed Advanced stage makes three attempts, identifies the page/check and
  preserves prior output bytes and modification time.
- Resource validation, compileall and git diff whitespace check passed.

Logs: `/tmp/recordprep-advanced-validation/` (machine-local).
No real case processing, provider calls, private settings changes, application
restart, deployment or visual acceptance was performed. This changes backend
retry/error handling only, not widgets or classification instructions.
