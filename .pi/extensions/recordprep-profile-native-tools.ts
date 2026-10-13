/** Application-owned native-stage boundary. Profiles cannot grant file/tool access. */
import { Type } from "typebox";
import { lstat, readFile, realpath, writeFile } from "node:fs/promises";
import { basename, dirname, isAbsolute, resolve } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function nativeProfileTools(pi: ExtensionAPI) {
  let spec: { root: string; candidate: string; reads: string[]; source_ranges: number[][]; helper: string | null; python: string; stage: string } | undefined;
  let failure = "";
  let validationFailures = 0;
  let lastReviewed = -1;
  let finished = false;
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
    if (finished) {
      ctx.shutdown();
      return { block: true, reason: "Participant validation is finished; no further model repair is authorized." };
    }
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
    description: "Conservatively normalize and validate the private participant candidate, without publishing. Missing optional statuses become unknown with warnings; do not refine just to remove warnings. Use partial after each newly reviewed batch and full when done. Any check that passes full validation finishes the stage. Repeated partial checks without more reviewed hearings stop the stage. Two failed validations end the stage; use the specific diagnostics, never repeatedly guess.",
    parameters: Type.Object({ partial: Type.Boolean() }),
    executionMode: "sequential",
    async execute(_id, params, signal, _onUpdate, ctx) {
      await ready;
      if (failure || !spec?.helper || spec.stage !== "participants") throw new Error(failure || "Participant validation is not applicable.");
      let result: { code: number; stdout: string; stderr?: string; killed?: boolean };
      try {
        if (!(await permitted(spec.candidate, dirname(spec.candidate), false))) throw new Error();
        const args = [spec.helper, "validate", spec.root, "--normalize", ...(params.partial ? ["--partial"] : [])];
        result = await pi.exec(spec.python, args, { signal, timeout: 120000 });
        if (result.killed) throw new Error();
      } catch {
        if (signal?.aborted) throw new Error("Validation interrupted; the prior final remains unchanged.");
        result = { code: 1, stdout: "Private candidate is missing/unsafe, or the application validator could not complete. Do not rewrite source files." };
      }
      // The helper historically emitted its actionable validation diagnostics
      // only on stderr. Discarding that stream caused blind repair loops.
      const prefix = "RECORDPREP_PARTICIPANT_PROGRESS=";
      const lines = [result.stdout, result.stderr].filter(Boolean).join("\n").split("\n");
      const text = lines.filter(line => !line.startsWith(prefix)).join("\n").slice(0, 16000);
      let progress: { reviewed: number; total: number; complete: boolean } | undefined;
      try {
        const value = JSON.parse(lines.find(line => line.startsWith(prefix))?.slice(prefix.length) || "null");
        if (value && Number.isSafeInteger(value.reviewed) && Number.isSafeInteger(value.total)
            && value.total > 0 && value.reviewed >= 0 && value.reviewed <= value.total
            && typeof value.complete === "boolean") progress = value;
      } catch { /* Missing/malformed helper progress cannot authorize partial continuation. */ }
      const valid = result.code === 0 && (!params.partial || !!progress);
      const complete = valid && (!params.partial || progress?.complete === true);
      const noProgress = valid && !complete && progress!.reviewed <= lastReviewed;
      if (valid && progress) lastReviewed = progress.reviewed;
      if (!valid) validationFailures += 1;
      finished = complete || noProgress || validationFailures >= 2;
      const status = complete ? "Full candidate validation passed; finished. Quality warnings need no repair."
        : noProgress ? "Stopped: repeated partial validation made no hearing-review progress. Prior published output is preserved."
        : valid ? `Partial candidate valid (${progress!.reviewed}/${progress!.total} hearings reviewed). Continue with unreviewed hearings only; quality warnings need no repair.`
        : validationFailures >= 2
          ? "Validation stopped after two failed attempts. Prior published output is preserved; no further repair loop is allowed."
          : "One repair attempt remains. Correct only the structural errors listed above; keep uncertainty explicit. Missing progress means the application helper failed to report review state.";
      if (noProgress || validationFailures >= 2) {
        await writeFile(resolve(dirname(spec.candidate), "participant-validation-failed"),
                        noProgress ? "partial_validation_no_progress\n" : "validation_attempts_exhausted\n", { mode: 0o600 });
      }
      if (finished) ctx.shutdown();
      return { content: [{ type: "text", text: (text ? text + "\n" : "") + status }],
               details: { valid, partial: params.partial, validationFailures, complete, noProgress }, isError: !valid || noProgress,
               ...(finished ? { terminate: true } : {}) };
    },
  });
}
