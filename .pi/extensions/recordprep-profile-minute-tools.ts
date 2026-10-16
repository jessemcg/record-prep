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
    description: "Submit normally one or two headline outcomes, not a miniature order or field-by-field narrative. Python renders Date — Hearing type, then Appearances / Orders / Next labeled lines without bullets; Focus makes the labels bold. State the result in plain English, not form legalese. Omit administrative/report-filing mechanics and conditional late-filing sanctions warnings; if administrative-only, say 'No substantive orders recorded.' Keep only essential qualifications and the next substantive hearing type/date. Exclude future report dates and report-only hearings. No separate party-position narrative or calendar inventory. Attendance evidence may come from any page; counsel alone proves neither presence nor absence. Python verifies locations; submission ends this session.",
    parameters: Type.Object({
      hearing: Type.String({ description: "Short hearing type only; no date, case caption, birth date, courthouse or department. Python puts this beside the date." }),
      appearances: Type.Array(Type.Object({
        person: Type.String(),
        role_label: Type.String({ maxLength: 512, description: "Short role or relationship of a person relevant under the profile, not a roster of every named attorney or court employee; Unknown if unresolved. Use only this order, not a participant index or predefined role catalog." }),
        status: Type.Union([Type.Literal("present"), Type.Literal("not_present"), Type.Literal("unclear")]),
        evidence: Type.Array(Type.Object({ file_page: Type.Integer({ minimum: 1 }), text: Type.String() }), { maxItems: 128 }),
      }), { maxItems: 128 }),
      orders: Type.String({ description: "Normally one or two decisive outcomes in simple, plain English: who must do what, what was allowed/denied, or what changed. Translate legal/form language faithfully; retain necessary terms and essential conditions or substantive deadlines. No statutory/standard/unchanged-order recitals, routine report receipt/preparation, filing/e-filing/portal deadlines, calendar/clerical and service-of-paperwork logistics or conditional late-filing sanctions warnings. For administrative-only orders say 'No substantive orders recorded.' An actually imposed consequential sanction is different. Another outcome only if omission would mislead about disposition. Setting a motion for hearing does not grant relief. Include an objection only if essential; no separate positions narrative or repetition of hearing/next date." }),
      next_hearing: Type.String({ description: "Only the next substantive hearing type/date. Exclude report-only hearings and report filing/due dates, even if earlier. Do not move that report calendar into orders. Omit later settings, times and notice/return directions. Use 'Not stated.' or 'Unclear.' as appropriate; do not invent settings or list a vacated hearing as next." }),
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
