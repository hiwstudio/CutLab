/**
 * `hiw retime <manifest>` — voiceover-first timing (architecture: audio is the master
 * clock). Reads the project's finished voiceover, distributes the scenes across its real
 * duration proportionally to each line's length, and snaps every cut to the nearest
 * detected pause so scene changes land in natural breaks in the narration.
 *
 * Requires the voiceover file (manifest.audio.voiceoverPath) to exist — that is the
 * whole point of the voiceover-first workflow. Edits the manifest's scene start/end in
 * place (preserving all other fields).
 */
import fs from "fs-extra";
import { loadManifest } from "../../engine/manifest/loadManifest";
import { validateManifest } from "../../engine/manifest/validateManifest";
import { probeDuration, detectSilences } from "../../engine/audio/probeAudio";
import { retimeToAudio } from "../../engine/timeline/retimeToAudio";

interface RawScene {
  id?: string;
  voiceover?: string;
  start?: number;
  end?: number;
}

export interface RetimeOptions {
  snap?: boolean; // default true
  noise?: string; // dB
  minSilence?: string; // seconds
  window?: string; // seconds
  tail?: string; // seconds
}

export async function retimeCommand(manifestPath: string, opts: RetimeOptions): Promise<number> {
  let loaded;
  try {
    loaded = loadManifest(manifestPath);
  } catch (err) {
    console.error(`  ❌ ${(err as Error).message}`);
    return 1;
  }

  // Validate first so we're timing a well-formed manifest.
  const report = validateManifest(loaded.raw);
  if (!report.manifest) {
    console.error("  ❌ Manifest could not be parsed.");
    return 1;
  }
  const voPath = report.manifest.audio.voiceoverPath;
  if (!voPath) {
    console.error("  ❌ No audio.voiceoverPath set. Add the finished voiceover first (voiceover-first workflow).");
    return 1;
  }

  const duration = probeDuration(voPath);
  if (duration === undefined) {
    console.error(`  ❌ Voiceover not found or unreadable at "${voPath}".`);
    console.error("     Generate/record the final voiceover before retiming — it is the timing reference.");
    return 1;
  }

  const raw = loaded.raw as { scenes?: RawScene[] };
  const scenes = raw.scenes ?? [];
  if (scenes.length === 0) {
    console.error("  ❌ Manifest has no scenes.");
    return 1;
  }

  const useSnap = opts.snap !== false;
  const silences = useSnap
    ? detectSilences(voPath, {
        noiseDb: opts.noise ? Number.parseFloat(opts.noise) : undefined,
        minSilence: opts.minSilence ? Number.parseFloat(opts.minSilence) : undefined,
      })
    : [];

  const weights = scenes.map((s) => (s.voiceover ?? "").trim().length);
  const timings = retimeToAudio({
    weights,
    audioDuration: duration,
    silences,
    tail: opts.tail ? Number.parseFloat(opts.tail) : undefined,
    snapWindow: opts.window ? Number.parseFloat(opts.window) : undefined,
  });

  scenes.forEach((s, i) => {
    s.start = timings[i].start;
    s.end = timings[i].end;
  });
  fs.writeJsonSync(loaded.manifestPath, raw, { spaces: 2 });

  const snappedCount = timings.filter((t) => t.snapped).length;
  console.log(`✅ Retimed ${scenes.length} scene(s) to the voiceover (${duration.toFixed(2)}s).`);
  console.log(
    useSnap
      ? `   ${silences.length} pause(s) detected; ${snappedCount} of ${scenes.length - 1} cuts snapped to a natural pause.`
      : "   Proportional timing (snap-to-silence disabled)."
  );
  for (let i = 0; i < scenes.length; i++) {
    const t = timings[i];
    const dur = (t.end - t.start).toFixed(2);
    const mark = t.snapped ? "⟵ pause" : "";
    console.log(`   ${scenes[i].id ?? `scene ${i + 1}`}: ${t.start}s – ${t.end}s  (${dur}s) ${mark}`);
  }
  console.log("\n   Re-validate and render:  npm run validate -- " + manifestPath);
  return 0;
}
