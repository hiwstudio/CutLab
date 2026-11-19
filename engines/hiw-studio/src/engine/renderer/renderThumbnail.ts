/**
 * Thumbnail renderer (architecture §23). Renders the HIWThumbnail composition to a
 * single PNG via @remotion/renderer's renderStill. Node only.
 */
import fs from "fs-extra";
import path from "node:path";
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import { loadManifest } from "../manifest/loadManifest";
import { validateManifest } from "../manifest/validateManifest";
import { ENTRY_POINT } from "./prepareRender";
import { ensureParentDir, outputRootForManifest, thumbnailOutputPath } from "./outputPaths";

export interface ThumbnailOptions {
  manifestPath: string;
  /** Scene index supplying background + characters (default 0). */
  sceneIndex?: number;
  /** Headline override; defaults to the manifest title. */
  headline?: string;
  /** Optional word within the headline to color red. */
  accent?: string;
  /** Crop in on the subject (head/upper-body fills the frame). */
  crop?: boolean;
  /** Render a vertical 1080x1920 thumbnail (for Shorts). */
  vertical?: boolean;
  outputPath?: string;
}

export interface ThumbnailResult {
  outputPath: string;
  sceneIndex: number;
}

export async function renderThumbnail(options: ThumbnailOptions): Promise<ThumbnailResult> {
  const { raw } = loadManifest(options.manifestPath);
  const report = validateManifest(raw);
  if (!report.ok || !report.manifest) {
    const lines = report.errors.map((e) => `  ❌ ${e.scene ? `${e.scene} ` : ""}${e.message}`);
    throw new Error(`Manifest has errors:\n${lines.join("\n")}`);
  }
  const manifest = report.manifest;

  const sceneIndex = Math.max(0, Math.min(options.sceneIndex ?? 0, manifest.scenes.length - 1));
  const outputPath =
    options.outputPath ??
    thumbnailOutputPath(manifest.projectId, options.vertical, outputRootForManifest(manifest));
  ensureParentDir(outputPath);

  // Thumbnails reference no external media (fonts are embedded in the bundle).
  const publicDir = path.resolve(process.cwd(), ".hiw", "public-thumbnail");
  fs.emptyDirSync(publicDir);

  const compositionId = options.vertical ? "HIWThumbnailVertical" : "HIWThumbnail";
  const inputProps = {
    manifest,
    sceneIndex,
    headline: options.headline,
    accent: options.accent,
    crop: options.crop,
  };

  const serveUrl = await bundle({ entryPoint: ENTRY_POINT, publicDir });
  const composition = await selectComposition({ serveUrl, id: compositionId, inputProps });

  await renderStill({
    composition,
    serveUrl,
    output: outputPath,
    inputProps,
    frame: 0,
    imageFormat: "png",
    overwrite: true,
  });

  return { outputPath, sceneIndex };
}
