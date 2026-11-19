/**
 * Manifest loading from disk (Node only — uses fs).
 *
 * IMPORTANT: never import this from the Remotion browser bundle (src/remotion/**).
 * The browser receives the manifest through Remotion inputProps, not the filesystem.
 */
import fs from "fs-extra";
import path from "node:path";

export interface LoadedManifest {
  /** Raw parsed JSON (not yet schema-validated). */
  raw: unknown;
  /** Absolute path to the manifest file. */
  manifestPath: string;
  /** Absolute directory containing the manifest (the project folder). */
  projectDir: string;
}

/** Read and JSON-parse a manifest file. Throws a friendly Error on failure. */
export function loadManifest(manifestPath: string): LoadedManifest {
  const abs = path.resolve(process.cwd(), manifestPath);
  if (!fs.existsSync(abs)) {
    throw new Error(`Manifest not found: ${manifestPath} (looked at ${abs})`);
  }
  let text: string;
  try {
    text = fs.readFileSync(abs, "utf8");
  } catch (err) {
    throw new Error(`Could not read manifest ${manifestPath}: ${(err as Error).message}`);
  }
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch (err) {
    throw new Error(`Manifest ${manifestPath} is not valid JSON: ${(err as Error).message}`);
  }
  return { raw, manifestPath: abs, projectDir: path.dirname(abs) };
}

/**
 * Build a fileExists probe that resolves manifest-relative paths.
 *
 * Manifest audio paths are written relative to the workspace root (e.g.
 * "./assets/audio/music/x.mp3" or "./projects/foo/voiceover.mp3"), so we resolve
 * against the current working directory, which is the HIW Studio root.
 */
export function makeFileExists(baseDir: string = process.cwd()) {
  return (p: string): boolean => {
    if (!p) return false;
    const abs = path.isAbsolute(p) ? p : path.resolve(baseDir, p);
    return fs.existsSync(abs);
  };
}
