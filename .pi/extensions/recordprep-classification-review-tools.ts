/** Classification reviewer: exact reads, private candidate writes, successful-read journal. */
import { appendFile, lstat, readFile, realpath } from "node:fs/promises";
import { dirname, isAbsolute, resolve } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function classificationReviewTools(pi: ExtensionAPI) {
  let spec: { reads: string[]; candidate: string; journal: string } | undefined;
  const ready = (async () => {
    try {
      const path = process.env.RECORDPREP_CLASSIFICATION_REVIEW_ACCESS_SPEC;
      if (!path || !isAbsolute(path)) return;
      const info = await lstat(path), parent = await lstat(dirname(path));
      if (!info.isFile() || info.isSymbolicLink() || info.nlink !== 1 || info.size > 8 * 1024 * 1024
          || info.uid !== process.getuid?.() || (info.mode & 0o077) !== 0
          || !parent.isDirectory() || parent.isSymbolicLink() || (parent.mode & 0o077) !== 0
          || await realpath(dirname(path)) !== dirname(path)) return;
      const value = JSON.parse(await readFile(path, "utf8"));
      if (!Array.isArray(value.reads) || !value.reads.length || value.reads.length > 200000
          || [value.candidate, value.journal].some(p => typeof p !== "string" || !isAbsolute(p)
            || dirname(p) !== dirname(path) || p === path)
          || value.candidate === value.journal
          || value.reads.some((p: unknown) => typeof p !== "string" || !isAbsolute(p)
            || p === path || p === value.candidate || p === value.journal)) return;
      // The journal is owned by the extension; never let a stale or linked file
      // manufacture evidence that an image was successfully read this session.
      try { await lstat(value.journal); return; } catch (e: any) { if (e?.code !== "ENOENT") return; }
      await appendFile(value.journal, "", { mode: 0o600, flag: "wx" });
      spec = value;
    } catch { /* Fail closed. */ }
  })();
  const denied = { block: true, reason: "Read only exact worklist/rule/source paths; write/edit only the private review candidate. No shell, settings, other bundles, or published output access." };
  pi.on("tool_call", async (event, ctx) => {
    await ready;
    const raw = (event.input as any).path;
    if (!spec || !["read", "write", "edit"].includes(event.toolName)
        || typeof raw !== "string" || !raw || raw.split("/").includes("..")) return denied;
    const path = resolve(ctx.cwd, raw), writing = event.toolName !== "read";
    if (writing ? path !== spec.candidate : path !== spec.candidate && !spec.reads.includes(path)) return denied;
    try {
      if (await realpath(dirname(path)) !== dirname(path)) return denied;
      const info = await lstat(path);
      if (!info.isFile() || info.isSymbolicLink() || info.nlink !== 1 || info.uid !== process.getuid?.()
          || await realpath(path) !== path) return denied;
    } catch (error: any) {
      if (!writing || error?.code !== "ENOENT" || await realpath(dirname(path)) !== dirname(path)) return denied;
    }
  });
  pi.on("tool_result", async (event, ctx) => {
    await ready;
    if (!spec || event.toolName !== "read" || event.isError) return;
    const raw = (event.input as any).path;
    if (typeof raw !== "string") return;
    const path = resolve(ctx.cwd, raw);
    if (!spec.reads.includes(path)) return;
    await appendFile(spec.journal, JSON.stringify(path) + "\n");
  });
  pi.on("user_bash", async () => ({ result: { output: "Shell is unavailable during classification review.", exitCode: 1, cancelled: false, truncated: false } }));
}
