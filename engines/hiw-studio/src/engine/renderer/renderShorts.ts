/**
 * Shorts cutdown renderer (architecture §26 Phase 5 "Shorts cutdown exporter",
 * output/shorts). Node only.
 *
 * Slices a contiguous scene range, re-times it to start at 0, trims the voiceover to
 * the matching window (ffmpeg), switches to vertical 1080x1920, and renders via the
 * normal video pipeline (renderVideo) to output/shorts/<id>_short.mp4.
 */
import fs from "fs-extra";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { loadManifest, makeFileExists } from "../manifest/loadManifest";
import { validateManifest } from "../manifest/validateManifest";
import { renderVideo } from "./renderVideo";
import { outputRootForManifest, shortsOutputPath } from "./outputPaths";
import { autoShortsRange, buildShortsManifest } from "./buildShortsManifest";
import type { Quality } from "./renderConfig";

export interface ShortsOptions {
  manifestPath: string;
  /** 0-based inclusive scene indices. If omitted, auto-pick from scene 0 within ~30s. */
  fromIndex?: number;
  toIndex?: number;
  maxSeconds?: number;
  quality?: Quality;
  onProgress?: (progress: number) => void;
}

export interface ShortsResult {
  outputPath: string;
  fromIndex: number;
  toIndex: number;
  durationInFrames: number;
  fps: number;
  width: number;
  height: number;
  voiceoverTrimmed: boolean;
}

/** Trim a workspace-relative audio file to [offset, offset+duration] using ffmpeg. */
function trimAudio(srcRel: string, destAbs: string, offset: number, duration: number): boolean {
  const srcAbs = path.resolve(process.cwd(), srcRel);
  if (!fs.existsSync(srcAbs)) return false;
  fs.ensureDirSync(path.dirname(destAbs));
  try {
    execFileSync(
      "ffmpeg",
      ["-y", "-i", srcAbs, "-ss", String(offset), "-t", String(duration), destAbs],
      { stdio: "ignore" }
    );
    return fs.existsSync(destAbs);
  } catch {
    return false;
  }
}

export async function renderShorts(options: ShortsOptions): Promise<ShortsResult> {
  const quality: Quality = options.quality ?? "final";

  const { raw } = loadManifest(options.manifestPath);
  const report = validateManifest(raw, { fileExists: makeFileExists() });
  if (!report.ok || !report.manifest) {
    const lines = report.errors.map((e) => `  ❌ ${e.scene ? `${e.scene} ` : ""}${e.message}`);
    throw new Error(`Manifest has errors:\n${lines.join("\n")}`);
  }
  const manifest = report.manifest;

  // Auto-extend the window from the requested start scene (or scene 0) when --to
  // is omitted, so `--from N` alone yields a proper N-onward cutdown.
  const [autoFrom, autoTo] = autoShortsRange(manifest, options.maxSeconds ?? 30, options.fromIndex ?? 0);
  const fromIndex = options.fromIndex ?? autoFrom;
  const toIndex = options.toIndex ?? autoTo;

  // First pass: compute the time window from the (untrimmed) selection.
  const probe = buildShortsManifest(manifest, fromIndex, toIndex);
  const { offsetSeconds, durationSeconds } = probe.window;

  // Trim the voiceover to the window, if present.
  let voiceoverTrimmed = false;
  let voShortRel: string | undefined;
  const origVo = manifest.audio.voiceoverPath;
  if (origVo) {
    voShortRel = `./.hiw/${manifest.projectId}-vo-short.wav`;
    const destAbs = path.resolve(process.cwd(), voShortRel);
    voiceoverTrimmed = trimAudio(origVo, destAbs, offsetSeconds, durationSeconds);
    if (!voiceoverTrimmed) voShortRel = undefined; // fall back to music-only
  }

  // Build the final vertical shorts manifest and write it to a temp file.
  const { manifest: shortManifest } = buildShortsManifest(manifest, fromIndex, toIndex, {
    voiceoverPath: voShortRel,
  });
  const tempManifestPath = path.resolve(process.cwd(), ".hiw", `${manifest.projectId}-short.manifest.json`);
  fs.ensureDirSync(path.dirname(tempManifestPath));
  fs.writeJsonSync(tempManifestPath, shortManifest, { spaces: 2 });

  const outputPath = shortsOutputPath(manifest.projectId, outputRootForManifest(manifest));
  const result = await renderVideo({
    manifestPath: tempManifestPath,
    quality,
    outputPath,
    // The full video's render already tallied these scenes; don't double-count.
    recordUsage: false,
    onProgress: options.onProgress,
  });

  return {
    outputPath: result.outputPath,
    fromIndex,
    toIndex,
    durationInFrames: result.durationInFrames,
    fps: result.fps,
    width: result.width,
    height: result.height,
    voiceoverTrimmed,
  };
}
