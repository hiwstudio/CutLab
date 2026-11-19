/**
 * Build a vertical Shorts manifest from a contiguous slice of a full manifest.
 * Pure (no fs). The selected scenes are shifted to start at 0 and the format is
 * switched to vertical 1080x1920. Audio trimming is handled by the caller
 * (renderShorts.ts) which sets the trimmed voiceover path here.
 */
import type { Manifest } from "../manifest/schema";

export interface ShortsWindow {
  /** Start offset (seconds) into the original voiceover. */
  offsetSeconds: number;
  /** Length (seconds) of the short. */
  durationSeconds: number;
}

export interface BuildShortsResult {
  manifest: Manifest;
  window: ShortsWindow;
}

const round2 = (n: number) => Math.round(n * 100) / 100;

export interface BuildShortsOptions {
  /** Workspace-relative path to the trimmed voiceover (if any). */
  voiceoverPath?: string;
}

/**
 * @param fromIdx 0-based inclusive start scene index
 * @param toIdx   0-based inclusive end scene index
 */
export function buildShortsManifest(
  manifest: Manifest,
  fromIdx: number,
  toIdx: number,
  options: BuildShortsOptions = {}
): BuildShortsResult {
  const last = manifest.scenes.length - 1;
  const from = Math.max(0, Math.min(fromIdx, last));
  const to = Math.max(from, Math.min(toIdx, last));

  const selected = manifest.scenes.slice(from, to + 1);
  const offset = selected[0].start;
  const lastEnd = selected[selected.length - 1].end;

  const scenes = selected.map((s) => ({
    ...s,
    start: round2(s.start - offset),
    end: round2(s.end - offset),
  }));

  const shortManifest: Manifest = {
    ...manifest,
    projectId: `${manifest.projectId}-short`,
    format: "youtube_vertical",
    resolution: { width: 1080, height: 1920 },
    audio: {
      ...manifest.audio,
      voiceoverPath: options.voiceoverPath ?? manifest.audio.voiceoverPath,
    },
    scenes,
  };

  return {
    manifest: shortManifest,
    window: { offsetSeconds: round2(offset), durationSeconds: round2(lastEnd - offset) },
  };
}

/**
 * Auto-pick a 0-based [from, to] range starting at `fromIdx` (default scene 0) that
 * stays within `maxSeconds` (always at least one scene). Lets `--from N` without
 * `--to` extend forward from N instead of colliding with a scene-0 window.
 */
export function autoShortsRange(manifest: Manifest, maxSeconds = 30, fromIdx = 0): [number, number] {
  const last = manifest.scenes.length - 1;
  const from = Math.max(0, Math.min(fromIdx, last));
  const start = manifest.scenes[from]?.start ?? 0;
  let to = from;
  for (let i = from; i < manifest.scenes.length; i++) {
    if (manifest.scenes[i].end - start <= maxSeconds) to = i;
    else break;
  }
  return [from, to];
}
