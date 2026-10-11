/** Profile-era minute tools. Exactly the legacy two capabilities, no arbitrary paths. */
import { Type } from "typebox";
import { readFileSync, writeFileSync } from "node:fs";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function minuteTools(pi: ExtensionAPI) {
  let spec: { source: string; item_id: string; candidate_path: string } | undefined;
  let read = false;
  pi.registerTool({
    name: "recordprep_get_minute_source",
    label: "Read minute order",
    description: "Read every original source page of this order. Apply only the attendance policy supplied by the application.",
    parameters: Type.Object({}),
    async execute() {
      if (!spec) {
        const path = process.env.RECORDPREP_MINUTE_WORK_SPEC;
        if (path) spec = JSON.parse(readFileSync(path, "utf-8"));
      }
      if (!spec) throw new Error("Minute-order work specification unavailable.");
      read = true;
      return { content: [{ type: "text" as const, text: spec.source }], details: undefined };
    },
  });
  pi.registerTool({
    name: "recordprep_submit_minute_summary",
    label: "Submit minute-order summary",
    description: "Submit the hearing, reporting status, source-supported appearances using declared role IDs, and concise actual orders. Follow the application attendance policy; cite the page and verbatim evidence for attendance claims. Python independently validates evidence locations and renders the paragraph. Submission ends this session.",
    parameters: Type.Object({
      hearing: Type.String(),
      reporting: Type.Union([Type.Literal("reported"), Type.Literal("not_reported"), Type.Literal("unclear")]),
      appearances: Type.Array(Type.Object({
        person: Type.String(),
        role_id: Type.String({ description: "An exact role ID from the supplied participant catalog." }),
        status: Type.Union([Type.Literal("present"), Type.Literal("not_present"), Type.Literal("unclear")]),
        evidence: Type.Array(Type.Object({ file_page: Type.Integer({ minimum: 1 }), text: Type.String() }), { maxItems: 128 }),
      }), { maxItems: 128 }),
      orders: Type.String({ description: "Concise actual orders, attributed to the court; no duplicate appearance/reporting claims." }),
    }),
    async execute(_id, params, _signal, _onUpdate, ctx) {
      if (!spec || !read) throw new Error("Read the complete minute order before submitting.");
      if (!params.hearing.trim() || !params.orders.trim()) throw new Error("Supply hearing/orders or state uncertainty.");
      writeFileSync(spec.candidate_path, JSON.stringify({
        ...params, artifact: "recordprep-minute-candidate", item_id: spec.item_id,
      }) + "\n", { mode: 0o600 });
      ctx.shutdown();
      return { content: [{ type: "text" as const, text: "Candidate accepted for independent validation." }],
        details: { accepted: true }, terminate: true };
    },
  });
}
