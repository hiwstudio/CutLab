/**
 * Asset id resolution with graceful fallbacks (architecture §16).
 *
 * Pure (catalog only, no React). The validator rejects unknown ids up front, but the
 * renderer also degrades safely so a slightly-off manifest still produces a video
 * instead of crashing.
 */
import {
  BACKGROUND_IDS,
  CAMERA_TYPES,
  CHARACTER_IDS,
  CHARACTER_VARIANTS,
  EFFECT_IDS,
  EXPRESSIONS,
  MOTION_IDS,
  PROP_IDS,
  isKnown,
  type BackgroundId,
  type CameraType,
  type CharacterId,
  type CharacterVariant,
  type EffectId,
  type Expression,
  type MotionId,
  type PropId,
} from "./catalog";

export function resolveCharacterId(id: string): CharacterId | undefined {
  return isKnown(CHARACTER_IDS, id) ? id : undefined;
}

export function resolveVariant(variant: string | undefined): CharacterVariant {
  return variant && isKnown(CHARACTER_VARIANTS, variant) ? variant : "default";
}

export function resolveExpression(expression: string | undefined): Expression {
  return expression && isKnown(EXPRESSIONS, expression) ? expression : "neutral";
}

export function resolveMotionId(motion: string | undefined): MotionId {
  return motion && isKnown(MOTION_IDS, motion) ? motion : "idle";
}

export function resolveBackgroundId(id: string): BackgroundId | undefined {
  return isKnown(BACKGROUND_IDS, id) ? id : undefined;
}

export function resolvePropId(id: string): PropId | undefined {
  return isKnown(PROP_IDS, id) ? id : undefined;
}

export function resolveCameraType(type: string | undefined): CameraType {
  return type && isKnown(CAMERA_TYPES, type) ? type : "static";
}

export function resolveEffectId(id: string): EffectId | undefined {
  return isKnown(EFFECT_IDS, id) ? id : undefined;
}
