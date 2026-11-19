/**
 * Shared render/preview preparation (Node only).
 *
 * Validates a manifest, builds the audio plan, and stages ONLY the media files the
 * render references into a small per-project public dir. This keeps Remotion's bundle
 * public folder tiny (we never point Remotion at the whole workspace / node_modules).
 */
import fs from "fs-extra";
import path from "node:path";
import { loadManifest, makeFileExists } from "../manifest/loadManifest";
import { validateManifest } from "../manifest/validateManifest";
import type { Manifest } from "../manifest/schema";
import { buildAudioPlan, type AudioPlan } from "../audio/audioUtils";
import { publicStageDir } from "./outputPaths";

/** Remotion entry point (registers Root). */
export const ENTRY_POINT = path.resolve(process.cwd(), "src/remotion/index.ts");

export interface PreparedProject {
  manifest: Manifest;
  audioPlan: AudioPlan;
  /** Folder to serve as Remotion's public dir (contains only referenced media). */
  publicDir: string;
  /** Input props to hand to Remotion (selectComposition / renderMedia / studio). */
  inputProps: { manifest: Manifest; audioPlan: AudioPlan };
}

export interface PrepareOptions {
  /** Throw if the manifest has validation errors (default true). */
  strict?: boolean;
}

/** Copy a workspace-relative media file into the staging public dir, preserving path. */
function stageFile(relPath: string, publicDir: string): void {
  const src = path.resolve(process.cwd(), relPath);
  if (!fs.existsSync(src)) return;
  const dest = path.resolve(publicDir, relPath);
  fs.ensureDirSync(path.dirname(dest));
  fs.copySync(src, dest);
}


export function prepareProject(
  manifestPath: string,
  options: PrepareOptions = {}
): PreparedProject {
  const strict = options.strict ?? true;

  const { raw } = loadManifest(manifestPath);
  const report = validateManifest(raw, { fileExists: makeFileExists() });

  if (!report.ok && strict) {
    const lines = report.errors.map((e) => `  ❌ ${e.scene ? `${e.scene} ` : ""}${e.message}`);
    throw new Error(`Manifest has ${report.errors.length} error(s):\n${lines.join("\n")}`);
  }
  if (!report.manifest) {
    throw new Error("Manifest could not be parsed.");
  }

  return prepareProjectFromManifest(report.manifest);
}

/**
 * Staging half of prepareProject for callers that already hold a validated,
 * normalized manifest (e.g. the render command after printing its report) — avoids
 * loading and validating the same file twice.
 */
export function prepareProjectFromManifest(manifest: Manifest): PreparedProject {
  const audioPlan = buildAudioPlan(manifest, { fileExists: makeFileExists() });

  // Stage referenced media into a clean public dir (fonts are embedded in the bundle).
  const publicDir = publicStageDir(manifest.projectId);
  fs.emptyDirSync(publicDir);
  if (audioPlan.voiceover) stageFile(audioPlan.voiceover.src, publicDir);
  if (audioPlan.music) stageFile(audioPlan.music.src, publicDir);
  for (const sfx of audioPlan.sfx) stageFile(sfx.src, publicDir);
  // Stick-hiw style: stage any generated per-scene images the render references.
  for (const scene of manifest.scenes) {
    if (scene.image) stageFile(scene.image, publicDir);
  }

  return {
    manifest,
    audioPlan,
    publicDir,
    inputProps: { manifest, audioPlan },
  };
}
