/**
 * Manifest normalization (architecture §7).
 *
 * Pure functions, no Node/React imports. Applied after Zod parsing to put a manifest
 * into a canonical form the timeline/renderer can rely on:
 *   - scenes sorted by start time
 *   - resolution backfilled from a known format preset when applicable
 */
import { FORMAT_PRESETS } from "../assets/catalog";
import { ManifestSchema, type Manifest } from "./schema";

/** Sort scenes ascending by start time (stable for equal starts). */
export function sortScenes(manifest: Manifest): Manifest {
  const scenes = [...manifest.scenes].sort((a, b) => a.start - b.start);
  return { ...manifest, scenes };
}

/**
 * If the manifest references a known format preset, make sure the resolution
 * matches it. Explicit resolutions that differ are left untouched (the format is
 * treated as advisory once an explicit resolution is present and non-default).
 */
export function applyFormatPreset(manifest: Manifest): Manifest {
  const preset = FORMAT_PRESETS[manifest.format as keyof typeof FORMAT_PRESETS];
  if (!preset) return manifest;
  const isDefaultRes =
    manifest.resolution.width === 1920 && manifest.resolution.height === 1080;
  // Only auto-apply a vertical/other preset when the user left the default landscape.
  if (isDefaultRes && manifest.format !== "youtube_landscape") {
    return { ...manifest, resolution: { ...preset } };
  }
  return manifest;
}

/** Full normalization pipeline for an already-parsed manifest. */
export function normalizeManifest(manifest: Manifest): Manifest {
  return sortScenes(applyFormatPreset(manifest));
}

/**
 * Parse + normalize raw input in one step. Throws a ZodError on invalid input;
 * prefer validateManifest() in the CLI for friendly, collected error reporting.
 */
export function parseAndNormalize(raw: unknown): Manifest {
  return normalizeManifest(ManifestSchema.parse(raw));
}
