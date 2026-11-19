/**
 * Retime scenes to a finished voiceover (voiceover-first workflow).
 *
 * Pure + dependency-free. Given per-scene weights (voiceover line length) and the real
 * audio duration, it lays out contiguous scene boundaries proportionally — then, when
 * detected silence points are supplied, SNAPS each internal cut to the nearest real
 * pause. Cutting inside a natural pause (instead of a proportional guess that can land
 * mid-word) is what makes the visuals feel synced to the narration.
 *
 * The audio probing (ffprobe duration + ffmpeg silencedetect) lives in the Node module
 * engine/audio/probeAudio.ts; this stays pure so the distribution logic is unit-tested
 * without ffmpeg.
 */

export interface RetimeOptions {
  /** Per-scene weight (use the voiceover line's trimmed length). */
  weights: number[];
  /** Real voiceover length in seconds (from ffprobe). */
  audioDuration: number;
  /** Candidate cut times (silence starts) in seconds, any order. Optional. */
  silences?: number[];
  /** Extra hold on the final scene past the last word (default 0.1s). */
  tail?: number;
  /** Max distance a cut may be snapped to a pause (default 1.2s). */
  snapWindow?: number;
  /** Minimum scene duration kept when snapping/clamping (default 0.6s). */
  minScene?: number;
}

export interface SceneTiming {
  start: number;
  end: number;
  /** True when this scene's end was snapped to a detected pause. */
  snapped: boolean;
}

const round2 = (n: number) => Math.round(n * 100) / 100;

/**
 * Nearest value in `sorted` to `target` within `window`, or undefined if none qualifies.
 * `sorted` must be ascending.
 */
function nearestWithin(sorted: number[], target: number, window: number, lo: number, hi: number): number | undefined {
  let best: number | undefined;
  let bestDist = Infinity;
  for (const s of sorted) {
    if (s < lo || s > hi) continue;
    const d = Math.abs(s - target);
    if (d <= window && d < bestDist) {
      bestDist = d;
      best = s;
    }
  }
  return best;
}

/**
 * Compute contiguous [start,end] for each scene. Internal cuts snap to the nearest
 * supplied silence within `snapWindow`, kept strictly increasing with at least
 * `minScene` between them; the last scene ends at audioDuration + tail.
 */
export function retimeToAudio(options: RetimeOptions): SceneTiming[] {
  const { weights, audioDuration } = options;
  const tail = options.tail ?? 0.1;
  const snapWindow = options.snapWindow ?? 1.2;
  const minScene = options.minScene ?? 0.6;
  const n = weights.length;
  if (n === 0) return [];

  const w = weights.map((x) => Math.max(1, x));
  const total = w.reduce((a, b) => a + b, 0);
  const silences = (options.silences ?? []).slice().sort((a, b) => a - b);

  // Proportional internal boundaries (there are n-1 of them).
  const cum: number[] = [];
  let acc = 0;
  for (let i = 0; i < n; i++) {
    acc += w[i];
    cum.push(acc);
  }
  const proportional = (i: number) => (cum[i] / total) * audioDuration; // end of scene i

  const boundaries: number[] = []; // boundary[i] = end of scene i, for i in 0..n-2
  const snappedFlags: boolean[] = [];
  let prev = 0;
  for (let i = 0; i < n - 1; i++) {
    const target = proportional(i);
    // Room limits: keep minScene behind and enough time ahead for remaining scenes.
    const lo = prev + minScene;
    const remainingAfter = n - 1 - i; // scenes still to place after this cut
    const hi = audioDuration - remainingAfter * minScene;
    const clampedTarget = Math.min(Math.max(target, lo), Math.max(lo, hi));

    const snap = nearestWithin(silences, clampedTarget, snapWindow, lo, Math.max(lo, hi));
    const value = snap ?? clampedTarget;
    boundaries.push(round2(value));
    snappedFlags.push(snap !== undefined);
    prev = value;
  }

  const timings: SceneTiming[] = [];
  for (let i = 0; i < n; i++) {
    const start = i === 0 ? 0 : boundaries[i - 1];
    const end = i === n - 1 ? round2(audioDuration + tail) : boundaries[i];
    timings.push({ start, end, snapped: i === n - 1 ? false : snappedFlags[i] });
  }
  return timings;
}
