/**
 * Sequence planning (architecture §14): turn manifest scenes into ordered frame
 * ranges that map directly onto Remotion <Sequence> blocks.
 * Pure — safe in browser and Node.
 */
import type { Manifest } from "../manifest/schema";
import { sceneFrameRange, type SceneFrameRange } from "./calculateDurations";

export interface SequencePlan {
  fps: number;
  width: number;
  height: number;
  totalDurationInFrames: number;
  scenes: SceneFrameRange[];
}

/** Build an ordered, frame-accurate plan from a (normalized) manifest. */
export function planSequences(manifest: Manifest): SequencePlan {
  const fps = manifest.fps;
  const ranges = manifest.scenes.map((scene) => sceneFrameRange(scene, fps));
  const totalDurationInFrames = Math.max(
    1,
    ranges.reduce((max, r) => Math.max(max, r.from + r.durationInFrames), 0)
  );
  return {
    fps,
    width: manifest.resolution.width,
    height: manifest.resolution.height,
    totalDurationInFrames,
    scenes: ranges,
  };
}
