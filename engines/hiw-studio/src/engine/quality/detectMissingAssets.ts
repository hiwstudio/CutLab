/**
 * Quality check: detect references to assets that do not exist in the catalog
 * (architecture §15 / §24 "missing assets, missing motions, unknown ...").
 */
import {
  BACKGROUND_IDS,
  CAMERA_TYPES,
  CAPTION_STYLES,
  CHARACTER_IDS,
  CHARACTER_VARIANTS,
  EFFECT_IDS,
  EXPRESSIONS,
  MOTION_IDS,
  PROP_IDS,
  isKnown,
} from "../assets/catalog";
import type { Manifest } from "../manifest/schema";
import { suggest, type ValidationIssue } from "./types";

export function detectMissingAssets(manifest: Manifest): ValidationIssue[] {
  const issues: ValidationIssue[] = [];

  for (const scene of manifest.scenes) {
    const sid = scene.id;

    if (!isKnown(BACKGROUND_IDS, scene.background)) {
      issues.push({
        severity: "error",
        code: "unknown-background",
        scene: sid,
        message: `unknown background: "${scene.background}".${suggest(scene.background, BACKGROUND_IDS)}`,
      });
    }

    for (const ch of scene.characters) {
      if (!isKnown(CHARACTER_IDS, ch.id)) {
        issues.push({
          severity: "error",
          code: "unknown-character",
          scene: sid,
          message: `unknown character: "${ch.id}".${suggest(ch.id, CHARACTER_IDS)}`,
        });
      }
      if (ch.variant && !isKnown(CHARACTER_VARIANTS, ch.variant)) {
        issues.push({
          severity: "warning",
          code: "unknown-variant",
          scene: sid,
          message: `unknown variant "${ch.variant}" for ${ch.id}; will fall back to "default".${suggest(ch.variant, CHARACTER_VARIANTS)}`,
        });
      }
      if (ch.expression && !isKnown(EXPRESSIONS, ch.expression)) {
        issues.push({
          severity: "error",
          code: "unknown-expression",
          scene: sid,
          message: `unknown expression "${ch.expression}" for ${ch.id}.${suggest(ch.expression, EXPRESSIONS)}`,
        });
      }
      if (ch.motion && !isKnown(MOTION_IDS, ch.motion)) {
        issues.push({
          severity: "error",
          code: "unknown-motion",
          scene: sid,
          message: `uses missing motion: "${ch.motion}".${suggest(ch.motion, MOTION_IDS)}`,
        });
      }
    }

    for (const p of scene.props) {
      if (!isKnown(PROP_IDS, p.id)) {
        issues.push({
          severity: "error",
          code: "unknown-prop",
          scene: sid,
          message: `unknown prop: "${p.id}".${suggest(p.id, PROP_IDS)}`,
        });
      }
    }

    if (scene.camera && !isKnown(CAMERA_TYPES, scene.camera.type)) {
      issues.push({
        severity: "error",
        code: "unknown-camera",
        scene: sid,
        message: `unknown camera type: "${scene.camera.type}".${suggest(scene.camera.type, CAMERA_TYPES)}`,
      });
    }

    for (const e of scene.effects) {
      if (!isKnown(EFFECT_IDS, e)) {
        issues.push({
          severity: "warning",
          code: "unknown-effect",
          scene: sid,
          message: `unknown effect "${e}" (will be ignored).${suggest(e, EFFECT_IDS)}`,
        });
      }
    }

    if (!isKnown(CAPTION_STYLES, scene.caption.style)) {
      issues.push({
        severity: "warning",
        code: "unknown-caption-style",
        scene: sid,
        message: `unknown caption style "${scene.caption.style}"; using "hiw_default".${suggest(scene.caption.style, CAPTION_STYLES)}`,
      });
    }
  }

  return issues;
}
