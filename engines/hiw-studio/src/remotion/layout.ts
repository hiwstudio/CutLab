/**
 * Stage layout helpers: turn a manifest position (preset string or {x,y}) into
 * absolute CSS for placing characters and props on the composition.
 */
import type { CSSProperties } from "react";
import type { Position } from "../engine/manifest/schema";

export interface Anchor {
  x: number;
  y: number;
}

/** Normalized anchor points (0..1) for the named presets. */
const PRESET_ANCHORS: Record<string, Anchor> = {
  center: { x: 0.5, y: 0.62 },
  left: { x: 0.3, y: 0.62 },
  right: { x: 0.7, y: 0.62 },
  "far-left": { x: 0.16, y: 0.62 },
  "far-right": { x: 0.84, y: 0.62 },
  top: { x: 0.5, y: 0.32 },
  bottom: { x: 0.5, y: 0.8 },
  "top-left": { x: 0.3, y: 0.34 },
  "top-right": { x: 0.7, y: 0.34 },
  "bottom-left": { x: 0.3, y: 0.78 },
  "bottom-right": { x: 0.7, y: 0.78 },
};

/** Resolve any manifest position into a normalized anchor. */
export function anchorFor(position: Position | undefined): Anchor {
  if (!position) return PRESET_ANCHORS.center;
  if (typeof position === "object") {
    return { x: clamp01(position.x), y: clamp01(position.y) };
  }
  return PRESET_ANCHORS[position] ?? PRESET_ANCHORS.center;
}

function clamp01(n: number): number {
  return Math.max(0, Math.min(1, n));
}

export interface LayerOptions {
  position: Position | undefined;
  scale: number;
  width: number;
  height: number;
  /** Box height as a fraction of composition height at scale 1. */
  heightFactor: number;
  /** Box aspect ratio (width / height). */
  aspect: number;
}

/** Absolute wrapper style centering the asset box on its anchor. */
export function layerStyle(opts: LayerOptions): CSSProperties {
  const anchor = anchorFor(opts.position);
  const boxHeight = opts.heightFactor * opts.height * opts.scale;
  const boxWidth = boxHeight * opts.aspect;
  return {
    position: "absolute",
    left: anchor.x * opts.width,
    top: anchor.y * opts.height,
    width: boxWidth,
    height: boxHeight,
    transform: "translate(-50%, -50%)",
    display: "flex",
    alignItems: "flex-end",
    justifyContent: "center",
  };
}
