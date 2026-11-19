/**
 * `hiw add-scene <manifest> --template <id>` (V2 — reuse engine).
 * Appends a template's scene to a manifest (preserving the file's existing content),
 * assigns the next scene id + timing, validates, and bumps the template usage count.
 */
import fs from "fs-extra";
import { loadManifest } from "../../engine/manifest/loadManifest";
import { validateManifest } from "../../engine/manifest/validateManifest";
import {
  buildSceneFromTemplate,
  bumpTemplateUsage,
  getTemplate,
  nextSceneId,
} from "../../engine/templates/templateStore";
import { printReport } from "./validate";

interface RawScene {
  id?: string;
  end?: number;
}

export async function addSceneCommand(
  manifestPath: string,
  opts: { template?: string; start?: string; duration?: string; voiceover?: string; caption?: string }
): Promise<number> {
  if (!opts.template) {
    console.error("  ❌ --template is required (see `npm run templates`).");
    return 1;
  }
  const tpl = getTemplate(opts.template);
  if (!tpl) {
    console.error(`  ❌ Template "${opts.template}" not found. List with: npm run templates`);
    return 1;
  }

  let loaded;
  try {
    loaded = loadManifest(manifestPath);
  } catch (err) {
    console.error(`  ❌ ${(err as Error).message}`);
    return 1;
  }
  const data = loaded.raw as { scenes?: RawScene[] };
  if (!Array.isArray(data.scenes)) {
    console.error("  ❌ Manifest has no scenes array.");
    return 1;
  }

  const existingIds = data.scenes.map((s) => s.id ?? "");
  const lastEnd = data.scenes.reduce((m, s) => Math.max(m, s.end ?? 0), 0);
  const start = opts.start !== undefined ? Number.parseFloat(opts.start) : lastEnd;
  const duration = opts.duration !== undefined ? Number.parseFloat(opts.duration) : 4;
  const id = nextSceneId(existingIds);

  const scene = buildSceneFromTemplate(tpl, {
    id,
    start,
    end: start + duration,
    voiceover: opts.voiceover,
    captionText: opts.caption,
  });
  data.scenes.push(scene);

  fs.writeJsonSync(loaded.manifestPath, data, { spaces: 2 });

  console.log(`✅ Added ${id} from template "${tpl.id}" at ${start}s–${(start + duration).toFixed(2)}s.\n`);
  const report = validateManifest(data);
  printReport(report);
  bumpTemplateUsage(tpl.id);

  if (!opts.voiceover || !opts.caption) {
    console.log("\n   Tip: fill in the new scene's voiceover/caption and re-time it, then validate again.");
  }
  return report.ok ? 0 : 1;
}
