/** Application-owned native-stage boundary. Profiles cannot grant file/tool access. */
import { Type } from "typebox";
import { lstat, readFile, realpath } from "node:fs/promises";
import { basename, dirname, isAbsolute, resolve } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function nativeProfileTools(pi: ExtensionAPI) {
  let spec: { root: string; candidate: string; reads: string[]; source_ranges: number[][]; helper: string | null; python: string; stage: string } | undefined;
  let failure = "";
  const ready = (async () => {
    try {
      const path = process.env.RECORDPREP_NATIVE_ACCESS_SPEC;
      if (!path || !isAbsolute(path)) throw new Error();
      const info = await lstat(path);
      const parent = await lstat(dirname(path));
      if (!info.isFile() || info.isSymbolicLink() || info.nlink !== 1 || info.size > 65536
          || info.uid !== process.getuid?.() || (info.mode & 0o077) !== 0
          || !parent.isDirectory() || parent.isSymbolicLink() || (parent.mode & 0o077) !== 0) throw new Error();
      const value = JSON.parse(await readFile(path, "utf8"));
      if (!["participants", "overview"].includes(value.stage) || !isAbsolute(value.root) || !isAbsolute(value.candidate)
          || !isAbsolute(value.python) || !Array.isArray(value.reads) || value.reads.length > 128
          || value.reads.some((p: unknown) => typeof p !== "string" || !isAbsolute(p))
          || !Array.isArray(value.source_ranges)
          || value.source_ranges.some((range: unknown) => !Array.isArray(range) || range.length !== 2
            || !range.every(Number.isSafeInteger) || range[0] < 1 || range[1] < range[0])
          || (value.stage === "overview" && value.source_ranges.length !== 0)
          || (value.helper !== null && (typeof value.helper !== "string" || !isAbsolute(value.helper)))) throw new Error();
      if (await realpath(value.root) !== value.root || await realpath(dirname(value.candidate)) !== dirname(value.candidate)) throw new Error();
      if (dirname(value.candidate) !== dirname(path)) throw new Error();
      spec = value;
    } catch {
      failure = "Native profile access configuration is unavailable; no model file access is authorized.";
    }
  })();

  async function permitted(raw: unknown, cwd: string, writing: boolean): Promise<boolean> {
    await ready;
    if (failure || !spec || typeof raw !== "string" || !raw || raw.split("/").includes("..")) return false;
    const path = resolve(cwd, raw.replace(/^@/, ""));
    if (writing && path !== spec.candidate) return false;
    const textRoot = resolve(spec.root, "text_pages");
    const number = Number.parseInt(basename(path), 10);
    const sourcePage = spec.stage === "participants" && dirname(path) === textRoot
      && /^[0-9]{4,}\.txt$/.test(basename(path))
      && spec.source_ranges.some(([first, last]) => first <= number && number <= last);
    if (!writing && path !== spec.candidate && !spec.reads.includes(path) && !sourcePage) return false;
    try {
      // Reject linked parents and files, not just escapes from the case root.
      if (await realpath(dirname(path)) !== dirname(path)) return false;
      const info = await lstat(path);
      return info.isFile() && !info.isSymbolicLink() && info.nlink === 1 && await realpath(path) === path;
    } catch (error: any) {
      return writing && error?.code === "ENOENT" && await realpath(dirname(path)) === dirname(path);
    }
  }

  pi.on("tool_call", async (event, ctx) => {
    if (event.toolName === "recordprep_validate_candidate") {
      await ready;
      if (!failure && spec?.stage === "participants" && spec.helper) return;
    } else if (["read", "write", "edit"].includes(event.toolName)) {
      if (await permitted((event.input as any).path, ctx.cwd, event.toolName !== "read")) return;
    }
    return { block: true, reason: failure || "This stage may read only application-approved source/context files and edit only its private candidate. Shell tools and canonical publication are not authorized." };
  });

  pi.registerTool({
    name: "recordprep_validate_candidate",
    label: "Validate private participant candidate",
    defaultActive: false,
    description: "Validate the private participant candidate without publishing it. Use partial validation after each small batch and full validation before finishing.",
    parameters: Type.Object({ partial: Type.Boolean() }),
    executionMode: "sequential",
    async execute(_id, params, signal) {
      await ready;
      if (failure || !spec?.helper || spec.stage !== "participants") throw new Error(failure || "Participant validation is not applicable.");
      if (!(await permitted(spec.candidate, dirname(spec.candidate), false))) throw new Error("Private candidate is missing or unsafe.");
      const args = [spec.helper, "validate", spec.root, ...(params.partial ? ["--partial"] : [])];
      const result = await pi.exec(spec.python, args, { signal, timeout: 120000 });
      if (result.killed) throw new Error("Validation interrupted; the prior final remains unchanged.");
      const text = result.stdout.slice(0, 16000);
      return { content: [{ type: "text", text: text || (result.code === 0 ? "Candidate valid." : "Candidate validation failed; correct the private candidate.") }],
               details: { valid: result.code === 0, partial: params.partial }, isError: result.code !== 0 };
    },
  });
}
