/**
 * SRT subtitle export (V2 — Pillar 3). Pure. One cue per scene using the scene's
 * caption text and its [start, end] timing.
 */
import type { Manifest } from "../manifest/schema";

function srtTime(seconds: number): string {
  const ms = Math.max(0, Math.round(seconds * 1000));
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  const s = Math.floor((ms % 60_000) / 1000);
  const millis = ms % 1000;
  const pad = (n: number, w = 2) => String(n).padStart(w, "0");
  return `${pad(h)}:${pad(m)}:${pad(s)},${pad(millis, 3)}`;
}

export function buildSrt(manifest: Manifest): string {
  const cues: string[] = [];
  let n = 0;
  for (const scene of manifest.scenes) {
    // Captions mirror the voiceover (see Scene.tsx), so subtitles do too.
    const text = (scene.voiceover || scene.caption.text).trim();
    if (!text || scene.end <= scene.start) continue;
    n += 1;
    cues.push(`${n}\n${srtTime(scene.start)} --> ${srtTime(scene.end)}\n${text}\n`);
  }
  return cues.join("\n");
}
