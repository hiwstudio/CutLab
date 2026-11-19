/**
 * Timeline builder (architecture §14).
 *
 * High-level entry the Remotion composition uses to turn a manifest into a render
 * plan, plus a helper to derive Remotion composition metadata (dimensions / fps /
 * duration) for <Composition calculateMetadata>.
 * Pure — safe in browser and Node.
 */
import type { Manifest } from "../manifest/schema";
import { planSequences, type SequencePlan } from "./sequencePlanner";

export type { SequencePlan } from "./sequencePlanner";

export function buildTimeline(manifest: Manifest): SequencePlan {
  return planSequences(manifest);
}

export interface CompositionMetadata {
  durationInFrames: number;
  fps: number;
  width: number;
  height: number;
}

/** Derive Remotion composition metadata from a manifest. */
export function metadataFromManifest(manifest: Manifest): CompositionMetadata {
  const plan = planSequences(manifest);
  return {
    durationInFrames: plan.totalDurationInFrames,
    fps: plan.fps,
    width: plan.width,
    height: plan.height,
  };
}
