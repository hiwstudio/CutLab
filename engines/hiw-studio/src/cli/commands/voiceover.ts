/**
 * `hiw voiceover <manifest>` — build a production-ready voiceover package.
 *
 * Merges the channel-standard voice design (`voice.json` at the repo root) with any
 * per-project `voice` override in the manifest and the manifest's spoken lines, then
 * writes a single `voiceover-package.md` next to the manifest (config + clean spoken
 * script). This step does NOT perform TTS — it produces the spec/script you paste into
 * your own voice tool, then save the audio as voiceover.mp3 in the project folder.
 */
import fs from "fs-extra";
import path from "node:path";
import { writeVoiceoverPackage } from "../../engine/voiceover/writeVoiceoverPackage";

export async function voiceoverCommand(manifestPath: string): Promise<number> {
  const manifestAbs = path.resolve(process.cwd(), manifestPath);
  if (!fs.existsSync(manifestAbs)) {
    console.error(`  ❌ Manifest not found: ${manifestPath}`);
    return 1;
  }

  const { outputPath } = writeVoiceoverPackage(manifestPath, {
    onMissingVoiceJson: () =>
      console.warn("  ⚠️  voice.json not found at repo root — using only the manifest's `voice` block."),
  });

  console.log(`✅ Wrote voiceover package: ${path.relative(process.cwd(), outputPath)}`);
  console.log("   Paste it into your voice tool, then save the audio as voiceover.mp3 in the project folder.");
  return 0;
}
