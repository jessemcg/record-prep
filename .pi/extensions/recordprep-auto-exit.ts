import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function recordPrepAutoExit(pi: ExtensionAPI) {
  pi.on("agent_end", (_event, ctx) => {
    ctx.shutdown();
  });
}
