/**
 * `hiw captions <manifest>` — export an SRT subtitle file for a project
 * (V2 — Pillar 3).
 */
import fs from "fs-extra";
import path from "node:path";
import { loadManifest } from "../../engine/manifest/loadManifest";
import { validateManifest } from "../../engine/manifest/validateManifest";
import { buildSrt } from "../../engine/captions/buildSrt";
import { outputRootForManifest, srtOutputPath } from "../../engine/renderer/outputPaths";

export async function captionsCommand(
  manifestPath: string,
  opts: { out?: string }
): Promise<number> {
  let raw: unknown;
  try {
    raw = loadManifest(manifestPath).raw;
  } catch (err) {
    console.error(`  ❌ ${(err as Error).message}`);
    return 1;
  }

  const report = validateManifest(raw);
  if (!report.manifest) {
    console.error("  ❌ Manifest could not be parsed.");
    return 1;
  }

  const srt = buildSrt(report.manifest);
  const outPath = opts.out
    ? path.resolve(process.cwd(), opts.out)
    : srtOutputPath(report.manifest.projectId, outputRootForManifest(report.manifest));
  fs.ensureDirSync(path.dirname(outPath));
  fs.writeFileSync(outPath, srt, "utf8");

  const cues = srt ? srt.trim().split(/\n\n/).length : 0;
  console.log(`✅ Wrote ${cues} subtitle cue(s): ${outPath}`);
  return 0;
}
