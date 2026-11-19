/**
 * Programmatic video renderer (architecture §6 renderer / §23 output).
 *
 * Bundles the Remotion entry, selects the HIW composition (which derives its size /
 * fps / duration from the manifest via calculateMetadata), and renders an MP4.
 * Node only — uses @remotion/bundler and @remotion/renderer.
 */
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import { ENTRY_POINT, prepareProject, type PreparedProject } from "./prepareRender";
import { RENDER_PRESETS, type Quality } from "./renderConfig";
import { ensureParentDir, outputRootForManifest, videoOutputPath } from "./outputPaths";
import { recordManifestUsage } from "../assets/usageStore";

const COMPOSITION_ID = "HIWVideo";

export interface RenderOptions {
  manifestPath: string;
  quality: Quality;
  /** Optional explicit output path; defaults to output/{drafts|finals}/{id}_{quality}.mp4 */
  outputPath?: string;
  /**
   * Already-validated + staged project (from prepareProject / prepareProjectFromManifest).
   * When provided, the manifest is not loaded or validated again.
   */
  prepared?: PreparedProject;
  /**
   * Tally this manifest's assets into assets/usage.json (default true). Derived
   * renders (e.g. Shorts cutdowns) pass false so the same scenes aren't counted twice.
   */
  recordUsage?: boolean;
  onProgress?: (progress: number) => void;
}

export interface RenderResult {
  outputPath: string;
  durationInFrames: number;
  fps: number;
  width: number;
  height: number;
}

export async function renderVideo(options: RenderOptions): Promise<RenderResult> {
  const { manifestPath, quality } = options;
  const preset = RENDER_PRESETS[quality];

  const prepared = options.prepared ?? prepareProject(manifestPath);
  const outputPath =
    options.outputPath ??
    videoOutputPath(prepared.manifest.projectId, quality, outputRootForManifest(prepared.manifest));
  ensureParentDir(outputPath);

  // 1. Bundle the Remotion project. Public dir holds only referenced media.
  const serveUrl = await bundle({
    entryPoint: ENTRY_POINT,
    publicDir: prepared.publicDir,
  });

  // 2. Select the composition (runs calculateMetadata with our manifest).
  const composition = await selectComposition({
    serveUrl,
    id: COMPOSITION_ID,
    inputProps: prepared.inputProps,
  });

  // 3. Render to MP4.
  await renderMedia({
    composition,
    serveUrl,
    codec: "h264",
    outputLocation: outputPath,
    inputProps: prepared.inputProps,
    imageFormat: "jpeg",
    jpegQuality: preset.jpegQuality,
    crf: preset.crf,
    scale: preset.scale,
    onProgress: ({ progress }) => options.onProgress?.(progress),
  });

  // Record asset usage (best-effort; never fail a render over this).
  if (options.recordUsage ?? true) {
    try {
      recordManifestUsage(prepared.manifest);
    } catch {
      /* ignore usage-tracking errors */
    }
  }

  return {
    outputPath,
    durationInFrames: composition.durationInFrames,
    fps: composition.fps,
    width: composition.width,
    height: composition.height,
  };
}
