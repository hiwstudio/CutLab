/**
 * Quality check: structural scene coverage (architecture §15).
 *
 * Validates the things every scene needs regardless of which assets it references:
 * unique ids, valid timing direction, presence of characters, and sensible captions.
 * The rendered caption mirrors `scene.voiceover` (caption.text is deprecated), so
 * length checks target the voiceover — and only when burned captions are enabled.
 */
import type { Manifest } from "../manifest/schema";
import { QUALITY_DEFAULTS, type QualityOptions, type ValidationIssue } from "./types";

export function validateSceneCoverage(
  manifest: Manifest,
  options: Partial<QualityOptions> = {}
): ValidationIssue[] {
  const opts = { ...QUALITY_DEFAULTS, ...options };
  const issues: ValidationIssue[] = [];
  const seen = new Set<string>();
  const burnedCaptions = manifest.style?.captions ?? false;

  for (const scene of manifest.scenes) {
    const sid = scene.id;

    if (seen.has(sid)) {
      issues.push({
        severity: "error",
        code: "duplicate-scene-id",
        scene: sid,
        message: `duplicate scene id "${sid}".`,
      });
    }
    seen.add(sid);

    if (scene.end <= scene.start) {
      issues.push({
        severity: "error",
        code: "bad-timing",
        scene: sid,
        message: `end (${scene.end}s) must be greater than start (${scene.start}s).`,
      });
    }

    // Stick-hiw image scenes bake characters into the generated image, so an
    // empty `characters` array is expected and not worth warning about.
    if (scene.characters.length === 0 && !scene.image) {
      issues.push({
        severity: "warning",
        code: "no-characters",
        scene: sid,
        message: "has no characters on screen.",
      });
    }

    // The burned caption renders the voiceover line, so check that text's length —
    // and only when captions are actually burned in (style.captions: true).
    const spoken = scene.voiceover.trim();
    if (burnedCaptions && spoken.length > opts.maxCaptionChars) {
      issues.push({
        severity: "warning",
        code: "caption-overflow",
        scene: sid,
        message: `voiceover renders as a ${spoken.length}-char caption; may overflow 2 lines on mobile (max ~${opts.maxCaptionChars}). Split the scene.`,
      });
    }
  }

  return issues;
}
