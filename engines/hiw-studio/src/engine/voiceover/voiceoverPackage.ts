/**
 * Voiceover package builder (shared by the classic `hiw voiceover` command and the
 * stick-hiw `stick:voiceover` tool). Pure + dependency-free — the fs / config-loading
 * lives in each caller.
 *
 * Combines a channel-standard voice design (a `voice.json`) with any per-project `voice`
 * override and the manifest's spoken lines into a single `voiceover-package.md`:
 *   1. the complete voice-generation configuration, and
 *   2. the final voiceover script to be spoken (one paragraph per scene).
 *
 * This produces a SPEC you paste into your own voice tool. The pipeline performs no TTS
 * (same standalone philosophy as the image prompts).
 */

export interface VoiceConfig {
  voiceProfileName?: string;
  model?: string;
  audioProfile?: string;
  style?: string;
  pace?: string;
  accent?: string;
  scene?: string;
  sampleContext?: string;
  deliveryNotes?: string;
}

interface SceneLike {
  id: string;
  voiceover?: string;
  /** Optional ElevenLabs-style delivery tag (e.g. "curious", "deadpan") — see SceneSchema. */
  voiceTag?: string;
  start?: number;
  end?: number;
}

export interface VoiceoverManifestLike {
  title?: string;
  projectId?: string;
  voice?: VoiceConfig;
  scenes?: SceneLike[];
}

/** Per-project `voice` fields override the global defaults; empty strings are ignored. */
export function mergeVoice(base: VoiceConfig, override?: VoiceConfig): VoiceConfig {
  const out: VoiceConfig = { ...base };
  if (override) {
    for (const [k, v] of Object.entries(override)) {
      if (typeof v === "string" && v.trim() !== "") (out as Record<string, string>)[k] = v;
    }
  }
  return out;
}

function field(label: string, value?: string): string {
  return `**${label}**\n${(value && value.trim()) || "_(not set)_"}\n`;
}

/** Build the full voiceover-package markdown for a manifest + resolved voice config. */
export function buildVoiceoverPackage(manifest: VoiceoverManifestLike, voice: VoiceConfig): string {
  const title = manifest.title ?? manifest.projectId ?? "Untitled";
  const scenes = manifest.scenes ?? [];
  const spokenScenes = scenes.filter((s) => {
    const t = (s.voiceover ?? "").trim();
    return t && !/^(replace this|add as many)/i.test(t);
  });

  // Clean, spoken-only script: one paragraph per scene. A `voiceTag` (ElevenLabs-style
  // delivery cue, e.g. "curious", "deadpan") is prefixed in brackets right on the line
  // being spoken — this is the one place tags reach the voice tool. `voiceover` itself
  // (used for captions/image prompts elsewhere) never carries the tag.
  const spoken = spokenScenes
    .map((s) => {
      const t = (s.voiceover ?? "").trim();
      const tag = (s.voiceTag ?? "").trim();
      return tag ? `[${tag}] ${t}` : t;
    })
    .join("\n\n");

  const perScene = scenes
    .map((s, i) => {
      const t = (s.voiceover ?? "").trim();
      const tag = (s.voiceTag ?? "").trim();
      const window =
        typeof s.start === "number" && typeof s.end === "number" ? ` _(scene ${i + 1}: ${s.start}s–${s.end}s)_` : "";
      const tagNote = tag ? ` — tag: \`${tag}\`` : "";
      return `- **${s.id}**${window}${tagNote}\n  ${t || "_(no line)_"}`;
    })
    .join("\n");

  return `# Voiceover Package — ${title}

> Paste the **Voice Generation Configuration** and **Voiceover Script** below into your
> voice tool (${voice.model || "your voice model"}), generate the narration, then save it
> as \`voiceover.mp3\` (or \`.wav\`) in this project folder. The pipeline performs no TTS.

## Voice Generation Configuration

${field("Audio Profile", voice.audioProfile)}
${field("Style", voice.style)}
${field("Pace", voice.pace)}
${field("Accent", voice.accent)}
${field("Scene", voice.scene)}
${field("Sample Context", voice.sampleContext)}${
    voice.deliveryNotes && voice.deliveryNotes.trim()
      ? `\n${field("Delivery Notes (this episode)", voice.deliveryNotes)}`
      : ""
  }
## Voiceover Script

_Speak exactly this — read nothing above this line aloud._

${spoken || "_(no spoken lines in manifest yet)_"}

---

### Per-scene reference (operator only — do not read aloud)

${perScene || "_(no scenes)_"}
`;
}
