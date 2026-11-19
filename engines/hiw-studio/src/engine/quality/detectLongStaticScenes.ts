/**
 * Quality check: scene pacing — long/static scenes, too-short scenes, overlaps and
 * gaps (architecture §7.4 timing rules and §24 quality checks).
 */
import type { Manifest } from "../manifest/schema";
import { QUALITY_DEFAULTS, type QualityOptions, type ValidationIssue } from "./types";

export function detectLongStaticScenes(
  manifest: Manifest,
  options: Partial<QualityOptions> = {}
): ValidationIssue[] {
  const opts = { ...QUALITY_DEFAULTS, ...options };
  const issues: ValidationIssue[] = [];

  let prevEnd: number | null = null;
  let prevId: string | null = null;

  for (const scene of manifest.scenes) {
    const sid = scene.id;

    // Only assess duration when timing is structurally valid (end > start).
    if (scene.end > scene.start) {
      const dur = scene.end - scene.start;
      const hasMotionVariety =
        scene.characters.some((c) => c.motion && c.motion !== "idle") ||
        Boolean(scene.camera && scene.camera.type !== "static") ||
        scene.effects.length > 0;

      if (dur > opts.maxSceneSeconds && !hasMotionVariety) {
        issues.push({
          severity: "warning",
          code: "long-static-scene",
          scene: sid,
          message: `is ${dur.toFixed(1)}s long with little motion. Add camera/motion or split it.`,
        });
      } else if (dur > opts.maxSceneSeconds + 5) {
        issues.push({
          severity: "warning",
          code: "long-scene",
          scene: sid,
          message: `is ${dur.toFixed(1)}s long. Consider splitting it.`,
        });
      }

      if (dur < opts.minSceneSeconds) {
        issues.push({
          severity: "warning",
          code: "short-scene",
          scene: sid,
          message: `is only ${dur.toFixed(2)}s long; may be too quick to read.`,
        });
      }
    }

    if (prevEnd !== null && prevId !== null) {
      if (scene.start < prevEnd - 1e-6) {
        issues.push({
          severity: "warning",
          code: "overlap",
          scene: sid,
          message: `overlaps previous scene "${prevId}" (starts at ${scene.start}s before ${prevEnd}s ended).`,
        });
      } else if (scene.start > prevEnd + 0.05) {
        issues.push({
          severity: "warning",
          code: "gap",
          scene: sid,
          message: `has a ${(scene.start - prevEnd).toFixed(2)}s gap after "${prevId}". Intentional?`,
        });
      }
    }

    prevEnd = scene.end;
    prevId = sid;
  }

  return issues;
}
