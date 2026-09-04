/**
 * RecordPrep summary-agent tools.
 *
 * Narrowly scoped custom tools for the two-stage summary pipeline. Extraction
 * children may only read the current document's complete source payload and
 * submit one extraction candidate; synthesis children may only read canonical
 * fact rows, submit sections, and finalize. There is no filesystem, shell, or
 * arbitrary-path capability here.
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

export default function recordprepSummaryTools(pi: ExtensionAPI) {
  const mode = String(process.env.RECORDPREP_SUMMARY_MODE || "");
  const specPath = String(process.env.RECORDPREP_SUMMARY_WORK_SPEC || "");
  const datasetPath = String(process.env.RECORDPREP_SUMMARY_DATASET || "");

  const requestedOrdinals = new Set<number>();
  const sections = new Map<string, Record<string, unknown>>();

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
      "Submit the completed structured extraction for the current document. " +
      "This terminates the session on success.",
    parameters: Type.Object({
      item_id: Type.String(),
      categories: Type.Array(
        Type.Object({
          id: Type.String(),
          facts: Type.Union([
            Type.Null(),
            Type.Array(
              Type.Object({
                text: Type.String(),
                evidence: Type.Array(
                  Type.Object({
                    text: Type.String(),
                    file_page: Type.Integer({ minimum: 1 }),
                  })
                ),
              })
            ),
          ]),
        })
      ),
    }),
    async execute(_id, params, _signal, _onUpdate, ctx) {
      const spec = requireSpec();
      if (params.item_id !== spec.item_id) {
        return fail(`item_id must be ${spec.item_id}`);
      }
      const expected = spec.categories.map((category) => category.id);
      const submitted = params.categories.map((category) => category.id);
      if (JSON.stringify(submitted) !== JSON.stringify(expected)) {
        return fail(
          "categories must appear exactly once each, in the configured order: " +
            expected.join(", ")
        );
      }
      for (const category of params.categories) {
        if (category.facts === null) continue;
        if (!Array.isArray(category.facts) || category.facts.length === 0) {
          return fail(
            `category ${category.id}: facts must be null or a nonempty list`
          );
        }
        for (const fact of category.facts) {
          if (!fact.evidence || fact.evidence.length === 0) {
            return fail(
              `category ${category.id}: every fact needs at least one evidence quote`
            );
          }
          for (const quote of fact.evidence) {
            const text = String(quote.text || "");
            if (/[\r\n]/.test(text) || text.includes("…") || text.includes("...")) {
              return fail(
                `category ${category.id}: quotes must be contiguous spans with no ` +
                  "ellipsis or line break"
              );
            }
            const words = text.trim().split(/\s+/).filter(Boolean).length;
            if (words < 2 || words > 12) {
              return fail(
                `category ${category.id}: quotes must be two to twelve words`
              );
            }
            const page = Number(quote.file_page);
            if (page < spec.start_page || page > spec.end_page) {
              return fail(
                `category ${category.id}: evidence page ${page} is outside this ` +
                  `document's pages ${spec.start_page}-${spec.end_page}`
              );
            }
          }
        }
      }
      try {
        writeFileSync(
          spec.candidate_path,
          JSON.stringify(
            { artifact: "recordprep-summary-extraction-candidate", item_id: spec.item_id, categories: params.categories },
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

  pi.registerTool({
    name: "recordprep_get_facts",
    label: "Get facts",
    description:
      "Return the dataset overview (omit ordinal) or one canonical fact row " +
      "by ordinal. Read every row before finalizing.",
    parameters: Type.Object({
      ordinal: Type.Optional(Type.Integer({ minimum: 1 })),
    }),
    async execute(_id, params) {
      if (!dataset) return fail("facts dataset is unavailable");
      if (params.ordinal === undefined) {
        const overview = {
          artifact: "recordprep-summary-facts-overview",
          schema_version: 1,
          total_rows: dataset.total_rows,
          items: dataset.rows.map((row) => ({
            item_id: row.item_id,
            ordinal: row.ordinal,
            label: row.label,
            non_null_category_ids: (row.categories as any[])
              .filter((category) => category.facts !== null)
              .map((category) => category.id),
            quote_ids: (row.categories as any[]).flatMap((category) =>
              category.facts === null
                ? []
                : category.facts.flatMap((fact: any) =>
                    fact.evidence.map((evidence: any) => evidence.quote_id)
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
      if (!row || row.ordinal !== params.ordinal) {
        return fail(`ordinal ${params.ordinal} does not exist`);
      }
      requestedOrdinals.add(params.ordinal);
      return {
        content: [{ type: "text" as const, text: JSON.stringify(row) }],
        details: { ordinal: params.ordinal },
      };
    },
  });

  pi.registerTool({
    name: "recordprep_submit_summary_section",
    label: "Submit summary section",
    description:
      "Submit or replace the narrative section for one document. Submit one " +
      "section per document in boundary order before finalizing.",
    parameters: Type.Object({
      item_id: Type.String(),
      paragraphs: Type.Array(Type.String()),
      covered_category_ids: Type.Array(Type.String()),
      suppressed_duplicate_category_ids: Type.Array(Type.String()),
    }),
    async execute(_id, params) {
      if (!dataset) return fail("facts dataset is unavailable");
      const row = dataset.rows.find(
        (candidate) => candidate.item_id === params.item_id
      );
      if (!row) {
        return fail(`unknown item_id ${params.item_id}`);
      }
      if (requestedOrdinals.size < dataset.total_rows) {
        return fail("read every canonical row before submitting sections");
      }
      sections.set(params.item_id, { ...params });
      return {
        content: [
          {
            type: "text" as const,
            text: `Section for ${params.item_id} recorded. Replace it by submitting ` +
              "the same item_id again; finalize when every section is complete.",
          },
        ],
        details: { item_id: params.item_id },
      };
    },
  });

  pi.registerTool({
    name: "recordprep_finish_summary",
    label: "Finish summary",
    description:
      "Finish the synthesis after every section has been submitted. This " +
      "terminates the session.",
    parameters: Type.Object({}),
    async execute(_id, _params, _signal, _onUpdate, ctx) {
      if (!dataset) return fail("facts dataset is unavailable");
      if (requestedOrdinals.size < dataset.total_rows) {
        return fail(
          `read every canonical row before finalizing (${requestedOrdinals.size} ` +
            `of ${dataset.total_rows} read)`
        );
      }
      const missing = dataset.rows
        .map((row) => String(row.item_id))
        .filter((item_id) => !sections.has(item_id));
      if (missing.length > 0) {
        return fail(`submit sections for: ${missing.join(", ")}`);
      }
      const ordered = dataset.rows.map((row) => sections.get(String(row.item_id)));
      try {
        writeFileSync(
          dataset.candidate_path,
          JSON.stringify(
            { artifact: "recordprep-summary-synthesis-candidate", sections: ordered },
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
            text: "Synthesis candidate accepted for independent validation.",
          },
        ],
        details: { accepted: true },
        terminate: true,
      };
    },
  });
}
