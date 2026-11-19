/**
 * Manifest validation entry point (architecture §15 and §24).
 *
 * Pipeline:
 *   1. Zod shape/type/timing parse (schema.ts).
 *   2. Normalize (sort scenes, format preset).
 *   3. Quality checks delegated to src/engine/quality/* (single source of truth):
 *        - validateSceneCoverage  (structural: ids, timing direction, captions)
 *        - detectMissingAssets    (unknown background/character/motion/prop/...)
 *        - detectLongStaticScenes (pacing: long/short/overlap/gap)
 *   4. Optional audio file-existence checks (via injected fileExists).
 *
 * Pure (no fs / React). File checks are opt-in through `options.fileExists`.
 */
import { ManifestSchema, type Manifest } from "./schema";
import { normalizeManifest } from "./normalizeManifest";
import { detectMissingAssets } from "../quality/detectMissingAssets";
import { detectLongStaticScenes } from "../quality/detectLongStaticScenes";
import { validateSceneCoverage } from "../quality/validateSceneCoverage";
import {
  QUALITY_DEFAULTS,
  type QualityOptions,
  type ValidationIssue,
} from "../quality/types";

export type { IssueSeverity, ValidationIssue } from "../quality/types";

export interface ValidationReport {
  /** True when there are no errors (warnings are allowed). */
  ok: boolean;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
  /** Normalized manifest, present only when the shape parsed successfully. */
  manifest?: Manifest;
}

export interface ValidateOptions extends Partial<QualityOptions> {
  /**
   * Optional file-existence probe. When provided, audio paths are checked.
   * Resolve `path` relative to the workspace root (see makeFileExists in loadManifest).
   */
  fileExists?: (path: string) => boolean;
}

function split(issues: ValidationIssue[]) {
  const errors = issues.filter((i) => i.severity === "error");
  const warnings = issues.filter((i) => i.severity === "warning");
  return { errors, warnings };
}

export function validateManifest(
  raw: unknown,
  options: ValidateOptions = {}
): ValidationReport {
  const quality: QualityOptions = { ...QUALITY_DEFAULTS, ...options };

  // 1. Shape validation via Zod.
  const parsed = ManifestSchema.safeParse(raw);
  if (!parsed.success) {
    const errors: ValidationIssue[] = parsed.error.issues.map((issue) => {
      const path = issue.path.join(".");
      return {
        severity: "error" as const,
        code: "schema",
        message: `${path ? `${path}: ` : ""}${issue.message}`,
      };
    });
    return { ok: false, errors, warnings: [] };
  }

  // 2. Normalize.
  const manifest = normalizeManifest(parsed.data);

  // 3. Quality checks.
  const issues: ValidationIssue[] = [
    ...validateSceneCoverage(manifest, quality),
    ...detectMissingAssets(manifest),
    ...detectLongStaticScenes(manifest, quality),
  ];

  // 4. Audio path existence (only when a probe is provided).
  if (options.fileExists) {
    const { voiceoverPath, musicPath } = manifest.audio;
    if (voiceoverPath && !options.fileExists(voiceoverPath)) {
      issues.push({
        severity: "warning",
        code: "missing-voiceover",
        message: `voiceover not found at "${voiceoverPath}". Video will render silent until you add it.`,
      });
    }
    if (musicPath && !options.fileExists(musicPath)) {
      issues.push({
        severity: "warning",
        code: "missing-music",
        message: `music not found at "${musicPath}". It will be skipped.`,
      });
    }
  }

  const { errors, warnings } = split(issues);
  return { ok: errors.length === 0, errors, warnings, manifest };
}
