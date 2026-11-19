/**
 * Output path resolution (architecture §6/§23). Node only.
 */
import fs from "fs-extra";
import path from "node:path";
import type { Quality } from "./renderConfig";

const OUTPUT_ROOT = "output";
/** stick-hiw projects keep their outputs self-contained under the stick-hiw/ folder. */
const STICK_OUTPUT_ROOT = "stick-hiw/output";

/**
 * Output root for a given manifest. stick-hiw (image-based) projects render into
 * stick-hiw/output/; classic 2D/3D puppet projects render into the shared output/.
 */
export function outputRootForManifest(manifest: { style?: { visualStyle?: string } }): string {
  return manifest.style?.visualStyle === "stick_image" ? STICK_OUTPUT_ROOT : OUTPUT_ROOT;
}

/** Absolute output file path for a project render, e.g. output/drafts/foo_draft.mp4. */
export function videoOutputPath(projectId: string, quality: Quality, outputRoot: string = OUTPUT_ROOT): string {
  const folder = quality === "draft" ? "drafts" : "finals";
  return path.resolve(process.cwd(), outputRoot, folder, `${projectId}_${quality}.mp4`);
}

/** Ensure the directory for a given file path exists. */
export function ensureParentDir(filePath: string): void {
  fs.ensureDirSync(path.dirname(filePath));
}

/** Staging dir used for serving only the media a render references (keeps the bundle small). */
export function publicStageDir(projectId: string): string {
  return path.resolve(process.cwd(), ".hiw", `public-${projectId}`);
}

/** Absolute output path for a project thumbnail, e.g. output/thumbnails/foo.png. */
export function thumbnailOutputPath(projectId: string, vertical = false, outputRoot: string = OUTPUT_ROOT): string {
  const name = vertical ? `${projectId}_vertical.png` : `${projectId}.png`;
  return path.resolve(process.cwd(), outputRoot, "thumbnails", name);
}

/** Absolute output path for a Shorts cutdown, e.g. output/shorts/foo_short.mp4. */
export function shortsOutputPath(projectId: string, outputRoot: string = OUTPUT_ROOT): string {
  return path.resolve(process.cwd(), outputRoot, "shorts", `${projectId}_short.mp4`);
}

/** Absolute output path for an SRT subtitle file, e.g. output/captions/foo.srt. */
export function srtOutputPath(projectId: string, outputRoot: string = OUTPUT_ROOT): string {
  return path.resolve(process.cwd(), outputRoot, "captions", `${projectId}.srt`);
}
