/**
 * Timeline duration math (architecture §14).
 * Pure functions — safe in browser and Node.
 */
import type { Manifest, Scene } from "../manifest/schema";

/** Convert seconds to whole frames at a given fps (rounded). */
export function secondsToFrames(seconds: number, fps: number): number {
  return Math.round(seconds * fps);
}

/** Convert frames back to seconds. */
export function framesToSeconds(frames: number, fps: number): number {
  return frames / fps;
}

/** End time (seconds) of the last scene — i.e. the manifest's content length. */
export function manifestEndSeconds(manifest: Manifest): number {
  return manifest.scenes.reduce((max, s) => Math.max(max, s.end), 0);
}

/**
 * Total composition length in frames. Always at least 1 frame so Remotion can mount
 * even for an (invalid) empty manifest.
 */
export function totalDurationFrames(manifest: Manifest): number {
  const endSeconds = manifestEndSeconds(manifest);
  return Math.max(1, secondsToFrames(endSeconds, manifest.fps));
}

/** Per-scene frame placement. */
export interface SceneFrameRange {
  scene: Scene;
  from: number;
  durationInFrames: number;
}

export function sceneFrameRange(scene: Scene, fps: number): SceneFrameRange {
  const from = secondsToFrames(scene.start, fps);
  const end = secondsToFrames(scene.end, fps);
  return {
    scene,
    from,
    durationInFrames: Math.max(1, end - from),
  };
}
