/** Synthesis-only display schema; the original extraction tools stay unchanged.
 * Delegate candidate storage, feedback, metrics and termination to the base
 * extension. Python alone validates display proposals and publishes quotations.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import summaryTools from "./recordprep-summary-tools.ts";

export default function synthesisTools(pi: ExtensionAPI) {
  const delegated = new Proxy(pi, {
    get(target, property, receiver) {
      if (property !== "registerTool") return Reflect.get(target, property, receiver);
      return (tool: Parameters<ExtensionAPI["registerTool"]>[0]) => {
        if (tool.name !== "recordprep_submit_summary_section") return target.registerTool(tool);
        return target.registerTool({
          ...tool,
          description: tool.description +
            " Submit one paragraph per paragraphs array entry. For hearings, " +
            "keep each paragraph short and focused, regroup dense digest topics, " +
            "and distribute appropriate quote anchors across substantive " +
            "paragraphs. Review attribution; never force or repeat a quote " +
            "merely for formatting. For all-caps, sentence-case, mixed-case or lowercase quotes, " +
            "optionally supply quote_capitalizations when sentence position warrants adjustment: an " +
            "object mapping exact quote ids to case-only display spellings. " +
            "Preserve proper names, acronyms, initials, first-person I, legal identifiers and meaningful " +
            "capitalization; retain source spelling when uncertain. Preserve every word, character position, " +
            "space and punctuation mark. No bracketed capitalization markers or narrative announcements. " +
            "Keep the original quote placeholders in paragraphs; Python " +
            "validates each proposal and otherwise retains source capitalization.",
          parameters: {
            ...tool.parameters,
            properties: {
              ...tool.parameters.properties,
              quote_capitalizations: { type: "object", additionalProperties: { type: "string" } },
            },
          },
        });
      };
    },
  });
  summaryTools(delegated);
}
