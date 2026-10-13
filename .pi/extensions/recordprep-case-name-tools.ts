/** Caption-only native stage: staged pages in, private candidate out. */
import { lstat, readFile, realpath } from "node:fs/promises";
import { dirname, isAbsolute, resolve } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function caseNameTools(pi: ExtensionAPI) {
  let spec: { reads: string[]; candidate: string } | undefined;
  const ready = (async () => {
    try {
      const path = process.env.RECORDPREP_CASE_NAME_ACCESS_SPEC;
      if (!path || !isAbsolute(path)) return;
      const info = await lstat(path), parent = await lstat(dirname(path));
      if (!info.isFile() || info.isSymbolicLink() || info.nlink !== 1 || info.size > 65536
          || info.uid !== process.getuid?.() || (info.mode & 0o077) !== 0
          || !parent.isDirectory() || parent.isSymbolicLink() || (parent.mode & 0o077) !== 0
          || await realpath(dirname(path)) !== dirname(path)) return;
      const value = JSON.parse(await readFile(path, "utf8"));
      if (!Array.isArray(value.reads) || value.reads.length < 1 || value.reads.length > 3
          || typeof value.candidate !== "string" || !isAbsolute(value.candidate)
          || dirname(value.candidate) !== dirname(path) || value.candidate === path
          || value.reads.some((p: unknown) => typeof p !== "string" || !isAbsolute(p)
            || dirname(p) !== dirname(path) || p === path || p === value.candidate)) return;
      spec = value;
    } catch { /* Fail closed. */ }
  })();
  pi.on("tool_call", async (event, ctx) => {
    await ready;
    const raw = (event.input as any).path;
    const blocked = { block: true, reason: "Read only the supplied staged pages and edit only the private caption candidate. No shell, other files, or canonical publication is authorized." };
    if (!spec || !["read", "write", "edit"].includes(event.toolName)
        || typeof raw !== "string" || !raw || raw.split("/").includes("..")) return blocked;
    const path = resolve(ctx.cwd, raw);
    const writing = event.toolName !== "read";
    if (writing ? path !== spec.candidate : path !== spec.candidate && !spec.reads.includes(path)) return blocked;
    try {
      if (await realpath(dirname(path)) !== dirname(path)) return blocked;
      const info = await lstat(path);
      if (!info.isFile() || info.isSymbolicLink() || info.nlink !== 1 || await realpath(path) !== path) return blocked;
    } catch (error: any) {
      if (!writing || error?.code !== "ENOENT" || await realpath(dirname(path)) !== dirname(path)) return blocked;
    }
  });
}
