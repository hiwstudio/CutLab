/**
 * HIW Studio asset catalog.
 *
 * Plain data only — NO React / Remotion imports. This module is the single source
 * of truth for which asset ids exist, and is safe to import from both:
 *   - the Node CLI / validator (src/engine/...)
 *   - the browser Remotion bundle (src/remotion/...)
 *
 * The visual implementations live in src/remotion/components/** and are wired to
 * these ids in src/remotion/assetRegistry.tsx. A small runtime check there asserts
 * that every catalog id has a component, so this list and the components cannot
 * drift apart silently.
 */

/** Background ids (architecture §9). */
export const BACKGROUND_IDS = [
  "cave",
  "living_room",
  "office",
  "abstract_explainer",
  "street",
  "park",
  "diner",
] as const;
export type BackgroundId = (typeof BACKGROUND_IDS)[number];

/** Character ids (architecture §8.2). */
export const CHARACTER_IDS = ["human", "ancient_brain", "dog"] as const;
export type CharacterId = (typeof CHARACTER_IDS)[number];

/** Human variants (architecture §8.3 — MVP starts with default + caveman, others stubbed). */
export const CHARACTER_VARIANTS = [
  "default",
  "caveman",
  "modern",
  "office",
  "tired",
  "excited",
  "waiter",
] as const;
export type CharacterVariant = (typeof CHARACTER_VARIANTS)[number];

/** Expressions (architecture §8.4). */
export const EXPRESSIONS = [
  "neutral",
  "happy",
  "anxious",
  "shocked",
  "confused",
  "angry",
  "tired",
  // convenience aliases used in scripts
  "worried",
  "excited",
] as const;
export type Expression = (typeof EXPRESSIONS)[number];

/** Motions (architecture §8.5 — MVP). */
export const MOTION_IDS = [
  "idle",
  "walk",
  "panic",
  "scrollPhone",
  "point",
  "shrug",
  "facepalm",
  "celebrate",
  "lookAround",
  "lightbulbIdea",
  "wave",
] as const;
export type MotionId = (typeof MOTION_IDS)[number];

/** Props (architecture §10 — MVP). */
export const PROP_IDS = [
  "phone",
  "notification_bubble",
  "money_stack",
  "brain",
  "speech_bubble",
  "club",
  "coin",
  "bill",
  "laptop",
  "warning_sign",
  "bone",
  "vending_machine",
] as const;
export type PropId = (typeof PROP_IDS)[number];

/** Camera types (architecture §11). */
export const CAMERA_TYPES = [
  "static",
  "slowZoomIn",
  "slowZoomOut",
  "quickZoom",
  "shake",
  "panLeft",
  "panRight",
] as const;
export type CameraType = (typeof CAMERA_TYPES)[number];

/** Scene effects (architecture §11). */
export const EFFECT_IDS = [
  "pop",
  "sweatDrops",
  "speedLines",
  "glow",
  "alarmFlash",
  "thoughtBubble",
  "motionLines",
  "faceDetect",
] as const;
export type EffectId = (typeof EFFECT_IDS)[number];

/** Position presets usable for characters and props. */
export const POSITION_PRESETS = [
  "center",
  "left",
  "right",
  "top",
  "bottom",
  "top-left",
  "top-right",
  "bottom-left",
  "bottom-right",
  "far-left",
  "far-right",
] as const;
export type PositionPreset = (typeof POSITION_PRESETS)[number];

/** Caption style ids (architecture §12). */
export const CAPTION_STYLES = ["hiw_default", "hiw_emphasis", "hiw_quiet"] as const;
export type CaptionStyleId = (typeof CAPTION_STYLES)[number];

/** Output/format presets (architecture §23). */
export const FORMAT_PRESETS = {
  youtube_landscape: { width: 1920, height: 1080 },
  youtube_vertical: { width: 1080, height: 1920 },
} as const;
export type FormatPreset = keyof typeof FORMAT_PRESETS;

/** Quick membership helpers (case-sensitive, ids are canonical). */
export const isKnown = <T extends readonly string[]>(
  list: T,
  value: string
): value is T[number] => (list as readonly string[]).includes(value);
