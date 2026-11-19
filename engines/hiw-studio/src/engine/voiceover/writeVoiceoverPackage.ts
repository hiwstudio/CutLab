/**
 * Voiceover-package writer (Node only — uses fs).
 *
 * Single source of truth for producing `voiceover-package.md` next to a manifest:
 * loads the channel-standard voice design (a `voice.json`), merges any per-project
 * `voice` override from the manifest, and writes the package via the pure builder in
 * `voiceoverPackage.ts`. Used by the `voiceover` / `stick:voiceover` commands AND by
 * the project scaffolders, so every project is born with a voiceover package.
 *
 * This performs NO TTS — it produces the spec/script the operator pastes into their
 * external voice tool.
 */
import fs from "fs-extra";
import path from "node:path";
import {
  buildVoiceoverPackage,
  mergeVoice,
  type VoiceConfig,
  type VoiceoverManifestLike,
} from "./voiceoverPackage";

export interface WriteVoiceoverPackageOptions {
  /**
   * Path to the channel voice design JSON (defaults to `voice.json` at the repo root).
   * The stick-hiw pipeline passes its own `stick-hiw/voice.json`.
   */
  voiceJsonPath?: string;
  /** Called with a human message when the voice.json base config is missing. */
  onMissingVoiceJson?: (resolvedPath: string) => void;
}

export interface WriteVoiceoverPackageResult {
  /** Absolute path to the written voiceover-package.md. */
  outputPath: string;
  /** True when the base voice.json was found and merged. */
  hadBaseConfig: boolean;
}

/**
 * Build and write `voiceover-package.md` next to the given manifest. Reads the manifest
 * and the base voice config from disk; safe to call at scaffold time (a placeholder
 * manifest simply yields an empty spoken-script section).
 */
export function writeVoiceoverPackage(
  manifestPath: string,
  options: WriteVoiceoverPackageOptions = {}
): WriteVoiceoverPackageResult {
  const manifestAbs = path.resolve(process.cwd(), manifestPath);
  const manifest = fs.readJsonSync(manifestAbs) as VoiceoverManifestLike;

  const voiceJsonPath =
    options.voiceJsonPath ?? path.resolve(process.cwd(), "voice.json");
  const hadBaseConfig = fs.existsSync(voiceJsonPath);
  if (!hadBaseConfig) options.onMissingVoiceJson?.(voiceJsonPath);
  const base: VoiceConfig = hadBaseConfig ? fs.readJsonSync(voiceJsonPath) : {};

  const voice = mergeVoice(base, manifest.voice);
  const outputPath = path.join(path.dirname(manifestAbs), "voiceover-package.md");
  fs.writeFileSync(outputPath, buildVoiceoverPackage(manifest, voice));

  return { outputPath, hadBaseConfig };
}
