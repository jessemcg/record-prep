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
            " Use direct quotations only from entries explicitly marked Verified in the digest. " +
            "Never use Unverified quote placeholders or copy their text as direct quotations; " +
            "paraphrase the supported digest point or choose another relevant Verified anchor. " +
            "Submit one focused paragraph per paragraphs entry. Keep original quote placeholders. " +
            "Optionally supply quote_selections: exact used id -> one continuous exact substring of its " +
            "original quote, in source case. Remove only whole words at either end; no internal deletions, " +
            "splicing, ellipses or rewriting. Keep a useful search phrase and preserve negation, conditions, " +
            "qualifications, attribution and the meaning of the whole sentence. " +
            "Supply quote_capitalizations for EVERY used quote id: the full selected text (original text " +
            "if untrimmed), case-adjusted or unchanged as an explicit retain decision. " +
            "For all-caps, sentence-case, mixed-case or lowercase quotes, adjust ordinary sentence-position " +
            "capitalization; preserve names, acronyms, first-person I and meaningful or uncertain case. " +
            "Within the selected span, change letter case only; preserve spaces and punctuation. " +
            "Do not omit decisions for unchanged quotes. Only quote-free sections may omit the map. " +
            "Address missing-decision feedback in this session. No bracket markers or announcements. " +
            "Python validates literal fidelity, not meaning, and falls back on rejected proposals.",
          async execute(...args) {
            // Keep candidate storage and existing best-effort feedback in the base tool.
            // Missing decisions are advisory, never a publication gate or auto-casing rule.
            const result = await tool.execute(...args);
            if ((result.details as { rejected?: boolean } | undefined)?.rejected) return result;
            const params = args[1] as { paragraphs?: unknown; quote_capitalizations?: unknown };
            const paragraphs = Array.isArray(params.paragraphs) ? params.paragraphs : [];
            const used = new Set<string>();
            for (const paragraph of paragraphs) {
              if (typeof paragraph !== "string") continue;
              for (const match of paragraph.matchAll(/\{\{quote:([^}]+)\}\}/g)) used.add(match[1].trim());
            }
            const map = params.quote_capitalizations;
            const decisions = map && typeof map === "object" && !Array.isArray(map)
              ? map as Record<string, unknown> : {};
            const missing = [...used].filter(id => !Object.prototype.hasOwnProperty.call(decisions, id) ||
              typeof decisions[id] !== "string" || decisions[id] === "");
            if (!missing.length) return result;
            return {
              ...result,
              content: [...result.content, {
                type: "text" as const,
                text: `Capitalization decisions missing for ${missing.length} used quote(s): ${missing.join(", ")}. ` +
                  "Resubmit this section with quote_capitalizations covering every used quote id. " +
                  "For each, supply the full selected text (complete original text if untrimmed), " +
                  "case-adjusted or unchanged to explicitly retain capitalization. Check each expanded sentence; " +
                  "retain meaningful or uncertain capitalization. Change letter case only. " +
                  "The section remains recorded; this feedback is advisory, not a publication gate.",
              }],
            };
          },
          parameters: {
            ...tool.parameters,
            properties: {
              ...tool.parameters.properties,
              quote_capitalizations: { type: "object", additionalProperties: { type: "string" } },
              quote_selections: { type: "object", additionalProperties: { type: "string" } },
            },
          },
        });
      };
    },
  });
  summaryTools(delegated);
}
