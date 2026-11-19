/**
 * Audio probing for the voiceover-first workflow (Node only — shells out to ffprobe /
 * ffmpeg, which the pipeline already requires for Shorts). NOT imported by the browser
 * bundle.
 *
 * - `probeDuration` reads the exact length of a voiceover file.
 * - `detectSilences` runs ffmpeg's silencedetect and returns the silence-START times
 *   (where speech stops = the natural end of a phrase), used as candidate scene cuts by
 *   engine/timeline/retimeToAudio.ts.
 *
 * This performs no TTS and no AI — it reads an existing audio file deterministically.
 */
import fs from "fs-extra";
import path from "node:path";
import { execFileSync, spawnSync } from "node:child_process";

/** Absolute-resolve a workspace-relative audio path. */
function resolveAudio(p: string): string {
  return path.isAbsolute(p) ? p : path.resolve(process.cwd(), p);
}

/** Voiceover length in seconds, or undefined if the file/ffprobe is unavailable. */
export function probeDuration(audioPath: string): number | undefined {
  const abs = resolveAudio(audioPath);
  if (!fs.existsSync(abs)) return undefined;
  try {
    const out = execFileSync(
      "ffprobe",
      ["-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", abs],
      { encoding: "utf8" }
    );
    const d = Number.parseFloat(out.trim());
    return Number.isFinite(d) ? d : undefined;
  } catch {
    return undefined;
  }
}

export interface SilenceOptions {
  /** Silence threshold (dB, negative). Default -30. */
  noiseDb?: number;
  /** Minimum silence duration to count, seconds. Default 0.35. */
  minSilence?: number;
}

/**
 * Silence-start times (seconds) in the audio — natural phrase boundaries. Returns an
 * empty array if ffmpeg is unavailable or no pauses are found (the caller then falls
 * back to pure proportional timing).
 */
export function detectSilences(audioPath: string, options: SilenceOptions = {}): number[] {
  const abs = resolveAudio(audioPath);
  if (!fs.existsSync(abs)) return [];
  const noise = options.noiseDb ?? -30;
  const dur = options.minSilence ?? 0.35;
  // silencedetect writes to STDERR and ffmpeg exits 0, so spawnSync (which returns both
  // streams) is the reliable way to read it — execFileSync only returns stdout.
  const res = spawnSync(
    "ffmpeg",
    ["-i", abs, "-hide_banner", "-af", `silencedetect=noise=${noise}dB:d=${dur}`, "-f", "null", "-"],
    { encoding: "utf8" }
  );
  if (res.error) return [];
  return parseSilenceStarts(`${res.stderr ?? ""}${res.stdout ?? ""}`);
}

/** Extract `silence_start: <t>` times from ffmpeg silencedetect output. */
export function parseSilenceStarts(ffmpegStderr: string): number[] {
  const out: number[] = [];
  const re = /silence_start:\s*([0-9]+(?:\.[0-9]+)?)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(ffmpegStderr)) !== null) {
    const t = Number.parseFloat(m[1]);
    if (Number.isFinite(t)) out.push(t);
  }
  return out;
}
