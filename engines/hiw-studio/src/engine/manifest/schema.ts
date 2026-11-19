/**
 * HIW Studio manifest schema (architecture §7).
 *
 * Zod validates the *shape, types and timing* of a manifest. It intentionally keeps
 * asset ids as free strings — whether a given background / character / motion / prop
 * actually exists is checked against the asset catalog in the validation layer
 * (src/engine/manifest/validateManifest.ts) so we can emit friendly
 * "unknown motion: x" messages instead of opaque enum errors.
 *
 * Zod only. No React / Node imports — safe in browser and CLI.
 */
import { z } from "zod";

/** A position is either a named preset string or explicit normalized XY (0..1). */
export const XYPositionSchema = z.object({
  x: z.number(),
  y: z.number(),
});
export type XYPosition = z.infer<typeof XYPositionSchema>;

export const PositionSchema = z.union([z.string(), XYPositionSchema]);
export type Position = z.infer<typeof PositionSchema>;

export const SceneCharacterSchema = z.object({
  id: z.string().min(1),
  variant: z.string().optional(),
  position: PositionSchema.optional().default("center"),
  scale: z.number().positive().optional().default(1),
  expression: z.string().optional().default("neutral"),
  motion: z.string().optional().default("idle"),
  flip: z.boolean().optional().default(false),
  /** When true, the character's mouth flaps (procedural talk; default off). */
  speaking: z.boolean().optional().default(false),
  /** Free-form per-character props passed through to the component. */
  props: z.record(z.unknown()).optional(),
});
export type SceneCharacter = z.infer<typeof SceneCharacterSchema>;

export const ScenePropSchema = z.object({
  id: z.string().min(1),
  position: PositionSchema.optional().default("center"),
  scale: z.number().positive().optional().default(1),
  animation: z.string().optional(),
  flip: z.boolean().optional().default(false),
  /** Optional text shown on the prop (e.g. a label on a sign, words in a bubble). */
  text: z.string().optional(),
});
export type SceneProp = z.infer<typeof ScenePropSchema>;

/**
 * Intentional on-screen text (architecture §12b). NOT subtitles — the engine ships
 * caption-free by default; these are deliberate, contextual text beats the Director
 * places only when they help the scene:
 *  - `speech`   — a speech bubble with exactly what a character is saying right now.
 *  - `reaction` — a short comic/dramatic reaction word ("oof.", "wait, what?").
 *  - `label`    — a sign / tag / UI / notification label that belongs in the scene.
 *  - `emphasis` — big punch text reinforcing a key visual moment or punchline.
 * Keep them short. Position + timing default sensibly per kind; override when needed.
 */
export const SceneTextSchema = z.object({
  kind: z.enum(["speech", "reaction", "label", "emphasis"]).optional().default("reaction"),
  text: z.string().min(1),
  position: PositionSchema.optional(),
  /** For `speech`: 0-based index of the character saying it (positions the bubble + tail). */
  character: z.number().int().min(0).optional(),
  /** Optional appear/disappear time in seconds, relative to the scene start. */
  start: z.number().min(0).optional(),
  end: z.number().min(0).optional(),
});
export type SceneText = z.infer<typeof SceneTextSchema>;

export const CameraSchema = z.object({
  type: z.string().min(1).default("static"),
  intensity: z.number().min(0).max(1).optional().default(0.2),
});
export type Camera = z.infer<typeof CameraSchema>;

export const SfxSchema = z.object({
  id: z.string().min(1),
  at: z.number().min(0).default(0),
  volume: z.number().min(0).max(1).optional().default(0.7),
});
export type Sfx = z.infer<typeof SfxSchema>;

export const CaptionSchema = z.object({
  /**
   * DEPRECATED — the rendered caption always mirrors the scene's `voiceover` line
   * (see Scene.tsx), so this text is never displayed. Accepted for backward
   * compatibility; omit it in new manifests. Only `style` and `position` matter.
   */
  text: z.string().optional().default(""),
  style: z.string().optional().default("hiw_default"),
  position: z.enum(["top", "center", "bottom"]).optional().default("bottom"),
});
export type Caption = z.infer<typeof CaptionSchema>;

export const SceneSchema = z.object({
  id: z.string().min(1),
  voiceover: z.string(),
  start: z.number().min(0),
  end: z.number().min(0),
  background: z.string().min(1),
  /**
   * Optional generated full-frame image (stick-hiw style). When set, the scene's
   * visual is this image (workspace-relative path, forward slashes), and the engine
   * layers camera, captions, voiceover, music and effects on top of it. `background`
   * stays as a valid catalog id and acts as a fallback if the image is missing.
   */
  image: z.string().optional(),
  characters: z.array(SceneCharacterSchema).default([]),
  /**
   * Optional recurring-character ids for image-based (stick-hiw) scenes. These reference
   * the stick-hiw character library (stick-hiw/characters/characters.json); the prompt
   * generator injects each one's canonical appearance so a character looks the same across
   * videos. Authoring/metadata only — the puppet renderer ignores it (it uses `characters`).
   */
  cast: z.array(z.string()).optional(),
  /**
   * Caption styling for this scene (style + position). Optional — defaults to
   * hiw_default at the bottom. The caption TEXT is always the scene's `voiceover`
   * line; `caption.text` is deprecated and ignored (see CaptionSchema).
   */
  caption: CaptionSchema.optional().default({}),
  /**
   * Optional ElevenLabs-style delivery/performance tag for this line (e.g. "curious",
   * "deadpan", "short pause") — kept deliberately separate from `voiceover` so it never
   * reaches the caption (which always mirrors `voiceover` verbatim, see `caption` above)
   * or the image-prompt context. Only consumed by the voiceover-package builder, which
   * prefixes the spoken line with `[tag]` in the text pasted into the voice tool. Freeform
   * string, not a hard enum — see stick-hiw/docs/CONTENT_STRATEGY.md §11 for the curated
   * per-show vocabulary.
   */
  voiceTag: z.string().optional(),
  /**
   * Optional per-word caption timing (scene-relative frames). When present it overrides
   * the engine's syllable-weighted estimate — e.g. real forced alignment from Whisper/
   * ElevenLabs. Omit it and the engine estimates word timing from the voiceover line.
   */
  captionWordTimings: z
    .array(
      z.object({
        text: z.string(),
        startF: z.number(),
        endF: z.number(),
        emphasis: z.boolean().optional().default(false),
      })
    )
    .optional(),
  // optional fields (architecture §7.3)
  props: z.array(ScenePropSchema).optional().default([]),
  /** Intentional, contextual on-screen text beats (speech/reaction/label/emphasis). */
  texts: z.array(SceneTextSchema).optional().default([]),
  camera: CameraSchema.optional(),
  effects: z.array(z.string()).optional().default([]),
  sfx: z.array(SfxSchema).optional().default([]),
  onscreenText: z.string().optional(),
  notes: z.string().optional(),
  reuseTags: z.array(z.string()).optional(),
  qualityNotes: z.string().optional(),
});
export type Scene = z.infer<typeof SceneSchema>;

export const AudioConfigSchema = z.object({
  voiceoverPath: z.string().optional(),
  musicPath: z.string().optional(),
  musicVolume: z.number().min(0).max(1).optional().default(0.12),
  sfxVolume: z.number().min(0).max(1).optional().default(0.7),
});
export type AudioConfig = z.infer<typeof AudioConfigSchema>;

export const StyleConfigSchema = z.object({
  captionStyle: z.string().optional().default("hiw_default"),
  visualStyle: z.string().optional().default("simple_2d_puppet"),
  colorPalette: z.string().optional().default("hiw_default"),
  /**
   * Burn subtitle-style captions into the video. Default OFF — exports ship caption-free
   * so each platform (YouTube etc.) can generate its own captions, avoiding clutter. Use
   * intentional `scene.texts` for contextual on-screen text instead. Set true only if you
   * specifically want hard-burned subtitles.
   */
  captions: z.boolean().optional().default(false),
});
export type StyleConfig = z.infer<typeof StyleConfigSchema>;

/**
 * Optional per-project voice-design override. The channel-standard defaults live in
 * stick-hiw/voice.json; any field set here overrides them when `npm run stick:voiceover`
 * builds the voiceover package. Lets a specific episode tailor tone/pace/emotion to its
 * concept (humorous, dramatic, educational, fast-paced, conversational, …). This is a
 * spec for the operator's external voice tool — the pipeline does not perform TTS.
 */
export const VoiceConfigSchema = z.object({
  audioProfile: z.string().optional(),
  style: z.string().optional(),
  pace: z.string().optional(),
  accent: z.string().optional(),
  scene: z.string().optional(),
  sampleContext: z.string().optional(),
  /** Extra per-episode delivery direction (emotion, energy, pacing notes). */
  deliveryNotes: z.string().optional(),
});
export type VoiceConfig = z.infer<typeof VoiceConfigSchema>;

export const ResolutionSchema = z.object({
  width: z.number().int().positive(),
  height: z.number().int().positive(),
});
export type Resolution = z.infer<typeof ResolutionSchema>;

export const ManifestSchema = z.object({
  projectId: z.string().min(1),
  title: z.string().min(1),
  brand: z.string().optional().default("Human Is Weird"),
  format: z.string().optional().default("youtube_landscape"),
  fps: z.number().int().positive().optional().default(30),
  resolution: ResolutionSchema.optional().default({ width: 1920, height: 1080 }),
  audio: AudioConfigSchema.optional().default({}),
  style: StyleConfigSchema.optional().default({}),
  voice: VoiceConfigSchema.optional(),
  scenes: z.array(SceneSchema).min(1, "A manifest must contain at least one scene."),
});

/** Raw (pre-parse) input type. */
export type ManifestInput = z.input<typeof ManifestSchema>;
/** Normalized (post-parse, defaults applied) manifest type used everywhere downstream. */
export type Manifest = z.infer<typeof ManifestSchema>;
