/**
 * RecordPrep summary-agent tools.
 *
 * Narrowly scoped custom tools for the two-stage summary pipeline. Extraction
 * children may only read the current document's complete source payload and
 * submit one digest candidate; synthesis children may only read the Markdown
 * digest presentation (overview or one document's Markdown block), submit
 * sections, and finalize. There is no filesystem, shell, or arbitrary-path
 * capability here.
 *
 * Intake schemas are deliberately permissive: malformed nested model output
 * still reaches Python (which normalizes it deterministically and flags
 * sanitized warnings) and terminates the child. The desired digest shape is
 * described here and in the skills rather than enforced by rejection loops.
 */

import { Type } from "typebox";
import { readFileSync, writeFileSync } from "node:fs";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

interface WorkSpec {
  artifact: string;
  kind: string;
  item_id: string;
  ordinal: number;
  label: string;
  start_page: number;
  end_page: number;
  source: string;
  candidate_path: string;
  guidance: string;
  additional_guidance: string;
  categories: { id: string; guidance: string }[];
}

interface DatasetFile {
  artifact: string;
  total_rows: number;
  rows: Record<string, unknown>[];
  documents: string[];
  candidate_path: string;
  kind: string;
}

function readJson(path: string): any {
  return JSON.parse(readFileSync(path, "utf-8"));
}

function fail(message: string) {
  return {
    content: [{ type: "text" as const, text: `REJECTED: ${message}` }],
    details: { rejected: true },
  };
}

const PLACEHOLDER_PATTERN = /\{\{quote:([^}]+)\}\}/g;
const TYPED_QUOTE_PATTERN = /[\u201c\u201d"]/;

// The exact quote ids of one document's digest rows, in canonical order.
function rowQuoteIds(row: Record<string, unknown>): string[] {
  const ids: string[] = [];
  const categories = Array.isArray(row.categories) ? row.categories : [];
  for (const category of categories) {
    const digest = (category as { digest?: unknown })?.digest;
    const evidence =
      digest && typeof digest === "object"
        ? (digest as { evidence?: unknown }).evidence
        : undefined;
    if (!Array.isArray(evidence)) continue;
    for (const item of evidence) {
      const id = (item as { quote_id?: unknown })?.quote_id;
      if (typeof id === "string" && id) ids.push(id);
    }
  }
  return ids;
}

function placeholderIds(paragraphs: string[]): string[] {
  const ids = new Set<string>();
  for (const paragraph of paragraphs) {
    for (const match of paragraph.matchAll(PLACEHOLDER_PATTERN)) {
      ids.add(match[1].trim());
    }
  }
  return [...ids];
}

export default function recordprepSummaryTools(pi: ExtensionAPI) {
  const mode = String(process.env.RECORDPREP_SUMMARY_MODE || "");
  const specPath = String(process.env.RECORDPREP_SUMMARY_WORK_SPEC || "");
  const datasetPath = String(process.env.RECORDPREP_SUMMARY_DATASET || "");

  const requestedOrdinals = new Set<number>();
  const sections = new Map<string, Record<string, unknown>>();
  // Extension-owned synthesis scratchpad: process-local memory separate from
  // conversation history, so notes survive context compaction within this
  // child process. They are orientation aids, never evidence; they are never
  // published, logged, or persisted beyond the process.
  let scratchpadNotes = "";

  let workSpec: WorkSpec | null = null;
  let dataset: DatasetFile | null = null;
  try {
    if (mode === "extract" && specPath) workSpec = readJson(specPath);
    if (mode === "synthesize" && datasetPath) dataset = readJson(datasetPath);
  } catch (error) {
    console.error(`[recordprep-summary-tools] ${error}`);
  }

  function requireSpec(): WorkSpec {
    if (!workSpec) throw new Error("Work specification is unavailable.");
    return workSpec;
  }

  // --- Extraction tools ---

  pi.registerTool({
    name: "recordprep_get_source",
    label: "Get document source",
    description:
      "Return the current document's complete source pages, including any " +
      "scope delimiters. Read it fully before submitting.",
    parameters: Type.Object({}),
    async execute(_id) {
      const spec = requireSpec();
      return {
        content: [
          {
            type: "text" as const,
            text: spec.source,
          },
        ],
        details: { item_id: spec.item_id },
      };
    },
  });

  pi.registerTool({
    name: "recordprep_submit_extraction",
    label: "Submit extraction",
    description:
      "Submit the completed category digest for the current document. " +
      "This terminates the session on success.\n\n" +
      "Desired shape: one entry per configured category id, in the configured " +
      "order. Preferred form per entry: { \"id\": string, \"digest\": {\n" +
      "  \"text\": \"one concise synthesized digest paragraph\",\n" +
      "  \"evidence\": [{ \"text\": \"short verbatim source quote\", \"file_page\": 12 }] }\n" +
      "Set digest to exactly null when the category has no material " +
      "orientation-worthy content. Evidence quotes are continuous verbatim " +
      "two-to-five-word source phrases, preferably distinctive " +
      "three-to-five-word anchors, with no fixed count — a quotation should " +
      "help locate source language, not pad the digest. A flattened variant " +
      "(digest as a string plus a category-level evidence array) is also " +
      "accepted. Python normalizes any deviation, so always submit once and " +
      "never restate case text.",
    parameters: Type.Object({
      item_id: Type.Optional(Type.String()),
      categories: Type.Array(
        Type.Object({
          id: Type.String(),
          digest: Type.Optional(Type.Any()),
        })
      ),
    }),
    async execute(_id, params, _signal, _onUpdate, ctx) {
      const spec = requireSpec();
      // The runner-owned item id is injected here; a submitted id is ignored.
      // Nested content is passed through unmodified — Python normalizes it.
      try {
        writeFileSync(
          spec.candidate_path,
          JSON.stringify(
            {
              artifact: "recordprep-summary-extraction-candidate",
              item_id: spec.item_id,
              categories: Array.isArray(params.categories)
                ? params.categories
                : [],
            },
            null,
            2
          ) + "\n"
        );
      } catch (error) {
        return fail(`could not record the candidate: ${error}`);
      }
      ctx.shutdown();
      return {
        content: [
          {
            type: "text" as const,
            text: "Extraction candidate accepted for independent validation.",
          },
        ],
        details: { accepted: true },
        terminate: true,
      };
    },
  });

  // --- Synthesis tools ---

  // Runner-owned synthesis progress derived from actual tool activity.
  function synthesisProgress(dataset: DatasetFile) {
    const submittedIds = new Set(sections.keys());
    const submitted: number[] = [];
    const pending: number[] = [];
    for (const row of dataset.rows) {
      const ordinal = Number(row.ordinal);
      if (submittedIds.has(String(row.item_id))) {
        submitted.push(ordinal);
      } else {
        pending.push(ordinal);
      }
    }
    return {
      total_documents: dataset.total_rows,
      read_ordinals: [...requestedOrdinals].sort((a, b) => a - b),
      unread_ordinals: dataset.rows
        .map((row) => Number(row.ordinal))
        .filter((ordinal) => !requestedOrdinals.has(ordinal))
        .sort((a, b) => a - b),
      submitted_ordinals: submitted,
      pending_ordinals: pending,
    };
  }

  pi.registerTool({
    name: "recordprep_synthesis_scratchpad",
    label: "Synthesis scratchpad",
    description:
      "Your private synthesis scratchpad. It lives in extension memory " +
      "separate from the conversation, so it survives context compaction " +
      "within this process. action=\"read\" returns your notes plus " +
      "runner-owned progress (read, submitted, and pending documents). " +
      "action=\"replace\" swaps the entire notes value — replace the whole "
      + "scratchpad after completing work rather than appending forever. " +
      "Keep notes to orientation aids: what you already narrated, relevant " +
      "event dates and attribution, unresolved issues, and developments " +
      "whose change matters. Notes are never evidence and never published.",
    parameters: Type.Object({
      action: Type.Union([Type.Literal("read"), Type.Literal("replace")]),
      notes: Type.Optional(Type.String()),
    }),
    async execute(_id, params) {
      if (!dataset) return fail("digests dataset is unavailable");
      const action = String(params.action || "");
      if (action === "read") {
        return {
          content: [
            {
              type: "text" as const,
              text: JSON.stringify({
                artifact: "recordprep-synthesis-scratchpad",
                notes: scratchpadNotes,
                progress: synthesisProgress(dataset),
              }),
            },
          ],
          details: { action: "read" },
        };
      }
      if (action === "replace") {
        scratchpadNotes = String(params.notes ?? "");
        return {
          content: [
            {
              type: "text" as const,
              text: "Scratchpad replaced.",
            },
          ],
          details: { action: "replace", notes_chars: scratchpadNotes.length },
        };
      }
      return fail("action must be \"read\" or \"replace\"");
    },
  });

  pi.registerTool({
    name: "recordprep_get_facts",
    label: "Get digests",
    description:
      "Return the dataset overview (omit ordinal), one document's Markdown " +
      "digest block by ordinal (default view=\"digest\"), or that document's " +
      "already-submitted draft section (view=\"submitted_section\") after a "
      + "context compaction. Cannot read arbitrary files or other cases.",
    parameters: Type.Object({
      ordinal: Type.Optional(Type.Integer({ minimum: 1 })),
      view: Type.Optional(Type.String()),
    }),
    async execute(_id, params) {
      if (!dataset) return fail("digests dataset is unavailable");
      if (params.ordinal === undefined) {
        const overview = {
          artifact: "recordprep-summary-digest-overview",
          schema_version: 2,
          total_rows: dataset.total_rows,
          items: dataset.rows.map((row) => ({
            item_id: row.item_id,
            ordinal: row.ordinal,
            label: row.label,
            non_null_category_ids: (row.categories as any[])
              .filter((category) => category.digest !== null)
              .map((category) => category.id),
            quote_ids: (row.categories as any[]).flatMap((category) =>
              category.digest === null || category.digest === undefined
                ? []
                : ((category.digest.evidence as any[]) || []).map(
                    (evidence) => evidence.quote_id
                  )
            ),
          })),
        };
        return {
          content: [{ type: "text" as const, text: JSON.stringify(overview) }],
          details: { overview: true },
        };
      }
      const row = dataset.rows[params.ordinal - 1];
      const document = dataset.documents?.[params.ordinal - 1];
      if (!row || row.ordinal !== params.ordinal || typeof document !== "string") {
        return fail(`ordinal ${params.ordinal} does not exist`);
      }
      const view = String(params.view || "digest");
      if (view === "submitted_section") {
        const section = sections.get(String(row.item_id));
        if (section === undefined) {
          return fail(
            `ordinal ${params.ordinal} has no submitted draft section yet`
          );
        }
        return {
          content: [
            {
              type: "text" as const,
              text:
                "DRAFT SECTION (already submitted — replace it by submitting " +
                `the same item_id again):\n${JSON.stringify(section)}`,
            },
          ],
          details: { ordinal: params.ordinal, view },
        };
      }
      if (view !== "digest") {
        return fail("view must be \"digest\" or \"submitted_section\"");
      }
      requestedOrdinals.add(params.ordinal);
      return {
        content: [{ type: "text" as const, text: document }],
        details: { ordinal: params.ordinal },
      };
    },
  });

  pi.registerTool({
    name: "recordprep_submit_summary_section",
    label: "Submit summary section",
    description:
      "Submit or replace the narrative section for one document: item_id plus " +
      "flowing prose paragraphs with {{quote:<quote_id>}} placeholders for " +
      "direct quotations. Placeholders must reference this document's exact " +
      "quote ids. The tool records the section and returns nonfatal feedback " +
      "when a placeholder references an unknown quote id — fix the section " +
      "and submit the same item_id again before finalizing. Submit one " +
      "section per document in boundary order before finalizing.",
    parameters: Type.Object({
      item_id: Type.String(),
      paragraphs: Type.Array(Type.String()),
    }),
    async execute(_id, params) {
      if (!dataset) return fail("digests dataset is unavailable");
      const row = dataset.rows.find(
        (candidate) => candidate.item_id === params.item_id
      );
      if (!row) {
        return fail(`unknown item_id ${params.item_id}`);
      }
      // Validate the section against this document's exact quote ids before
      // recording. The candidate is always recorded (Python normalizes it and
      // falls back deterministically), but structured, nonfatal feedback lets
      // the model replace an invalid section before finishing. Feedback stays
      // inside this private exchange: ids and counts only, never case text.
      // Never guess an id, match by suffix, or borrow a quote from another
      // document.
      const paragraphs = Array.isArray(params.paragraphs)
        ? params.paragraphs.filter(
            (paragraph): paragraph is string => typeof paragraph === "string"
          )
        : [];
      const allowed = rowQuoteIds(row);
      const used = placeholderIds(paragraphs);
      const invalid = used.filter((id) => !allowed.includes(id));
      const advisory: string[] = [];
      if (paragraphs.some((paragraph) => TYPED_QUOTE_PATTERN.test(paragraph))) {
        advisory.push(
          "The section text contains typed quotation marks; placeholders are " +
            "rendered with quotation marks automatically, so never type " +
            "quotation marks yourself."
        );
      }
      if (allowed.length > 0 && used.length === 0) {
        advisory.push(
          "This document's digest includes direct quotes but the section has " +
            "no {{quote:...}} placeholder; quotations are optional anchors, " +
            "not a quota — use one only when the wording genuinely helps."
        );
      }
      sections.set(params.item_id, { ...params });
      if (invalid.length > 0) {
        return {
          content: [
            {
              type: "text" as const,
              text:
                `Section for ${params.item_id} recorded, but ${invalid.length} ` +
                `placeholder id(s) do not exist in this document's digest: ` +
                `${invalid.join(", ")}. Submit this item_id again with the ` +
                "section corrected before finalizing; use only this " +
                "document's quote ids exactly as provided" +
                (allowed.length > 0
                  ? `: ${allowed.join(", ")}.`
                  : ". This document has no quote ids, so remove all " +
                    "placeholders.") +
                (advisory.length > 0 ? ` ${advisory.join(" ")}` : ""),
            },
          ],
          details: {
            item_id: params.item_id,
            recorded: true,
            invalid_quote_ids: invalid,
            allowed_quote_ids: allowed,
            advisory,
          },
        };
      }
      return {
        content: [
          {
            type: "text" as const,
            text:
              `Section for ${params.item_id} recorded. Replace it by submitting ` +
              "the same item_id again; finalize when every section is complete." +
              (advisory.length > 0 ? ` ${advisory.join(" ")}` : ""),
          },
        ],
        details: {
          item_id: params.item_id,
          recorded: true,
          advisory,
        },
      };
    },
  });

  pi.registerTool({
    name: "recordprep_finish_summary",
    label: "Finish summary",
    description:
      "Finish the synthesis after submitting your sections. This terminates " +
      "the session. Always call this exactly once, even if you could not " +
      "read every row or submit every section — Python fills any gaps.",
    parameters: Type.Object({}),
    async execute(_id, _params, _signal, _onUpdate, ctx) {
      if (!dataset) return fail("digests dataset is unavailable");
      // Always emit the sections recorded so far, in boundary order; Python
      // deterministically fills missing sections and flags the gaps.
      const ordered = dataset.rows
        .map((row) => sections.get(String(row.item_id)))
        .filter((section) => section !== undefined);
      // Sanitized coverage diagnostics (counts only, never case text).
      // Python validates the types and republishes only the counts.
      const progress = synthesisProgress(dataset);
      const diagnostics = {
        unread_documents: progress.unread_ordinals.length,
        missing_sections: progress.pending_ordinals.length,
      };
      try {
        writeFileSync(
          dataset.candidate_path,
          JSON.stringify(
            {
              artifact: "recordprep-summary-synthesis-candidate",
              sections: ordered,
              diagnostics,
            },
            null,
            2
          ) + "\n"
        );
      } catch (error) {
        return fail(`could not record the candidate: ${error}`);
      }
      ctx.shutdown();
      return {
        content: [
          {
            type: "text" as const,
            text:
              "Synthesis candidate accepted for independent validation. " +
              `Coverage: ${diagnostics.unread_documents} document(s) never ` +
              `read, ${diagnostics.missing_sections} section(s) not ` +
              "submitted; Python fills gaps deterministically.",
          },
        ],
        details: { accepted: true, ...diagnostics },
        terminate: true,
      };
    },
  });
}
