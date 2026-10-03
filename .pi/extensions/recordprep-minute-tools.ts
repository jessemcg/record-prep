/** Direct-source minute-order tools. No arbitrary paths or canonical writes. */
import { Type } from "typebox";
import { readFileSync, writeFileSync } from "node:fs";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function minuteTools(pi: ExtensionAPI) {
  let spec: { source: string; item_id: string; candidate_path: string } | undefined;
  let read = false;
  function requireSpec() {
    if (!spec) {
      const path = process.env.RECORDPREP_MINUTE_WORK_SPEC;
      if (path) spec = JSON.parse(readFileSync(path, "utf-8"));
    }
    if (!spec) throw new Error("Minute-order work specification unavailable.");
    return spec;
  }
  pi.registerTool({
    name: "recordprep_get_minute_source",
    label: "Read minute order",
    description: "Read all source pages of the current minute order. The first page is explicitly marked; only that page supports affirmative parent appearances.",
    parameters: Type.Object({}),
    async execute() {
      const current = requireSpec();
      read = true;
      return { content: [{ type: "text" as const, text: current.source }], details: undefined };
    },
  });
  pi.registerTool({
    name: "recordprep_submit_minute_summary",
    label: "Submit minute-order summary",
    description: "Submit this order's hearing name, reporting status, each parent's personal appearance, and concise actual orders. A present parent requires a verbatim first-page passage showing personal presence, not just counsel. Attorney-only listings mean not_present; ambiguous evidence means unclear. Python validates and renders the final paragraph. Submission ends this session.",
    parameters: Type.Object({
      hearing: Type.String(),
      reporting: Type.Union([Type.Literal("reported"), Type.Literal("not_reported"), Type.Literal("unclear")]),
      parents: Type.Array(Type.Object({
        parent: Type.String({ description: "Mother, Father, or a source-supported parent identifier when multiple parents share a role." }),
        status: Type.Union([Type.Literal("present"), Type.Literal("not_present"), Type.Literal("unclear")]),
        first_page_evidence: Type.String({ description: "Verbatim first-page evidence; required for present, otherwise may be empty." }),
      })),
      orders: Type.String({ description: "Brief actual court orders only; do not duplicate hearing/reporting/appearance fields." }),
    }),
    async execute(_id, params, _signal, _onUpdate, ctx) {
      if (!spec || !read) throw new Error("Read the complete minute order before submitting.");
      if (!params.hearing.trim() || !params.orders.trim()) throw new Error("Supply the hearing name and concise orders, or explicitly state uncertainty.");
      writeFileSync(spec.candidate_path, JSON.stringify({
        ...params, artifact: "recordprep-minute-candidate", item_id: spec.item_id,
      }) + "\n", { mode: 0o600 });
      ctx.shutdown();
      return {
        content: [{ type: "text" as const, text: "Candidate accepted for independent validation." }],
        details: { accepted: true }, terminate: true,
      };
    },
  });
}
