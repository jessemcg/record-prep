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
    description: "Read every original source page of this complete minute order, including appearance entries and future hearing settings.",
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
    description: "Submit source-supported appearances, attributed party positions, main findings and orders, and the next hearing scheduled. Attendance evidence can come from any page; counsel alone proves neither presence nor absence. Cite the page and verbatim evidence for attendance claims. Use complete sentences for positions, orders and next_hearing. Python validates evidence locations and renders one concise paragraph. Submission ends this session.",
    parameters: Type.Object({
      hearing: Type.String(),
      appearances: Type.Array(Type.Object({
        person: Type.String(),
        role_id: Type.String({ description: "An exact role ID from the supplied participant catalog." }),
        status: Type.Union([Type.Literal("present"), Type.Literal("not_present"), Type.Literal("unclear")]),
        evidence: Type.Array(Type.Object({ file_page: Type.Integer({ minimum: 1 }), text: Type.String() }), { maxItems: 128 }),
      }), { maxItems: 128 }),
      positions: Type.String({ description: "Material requests, objections, agreements or positions actually recorded, attributed to each party; empty if none recorded. Do not infer agreement from silence or from a ruling." }),
      orders: Type.String({ description: "Main findings and orders actually made by the court, distinguished from requested relief; no duplicate appearances or party positions." }),
      next_hearing: Type.String({ description: "Next hearing type, date and time as recorded; distinguish other material settings if several were scheduled. Say 'Next hearing not stated.' if none is recorded, or 'Next hearing unclear.' if illegible/ambiguous. Never invent missing details." }),
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
