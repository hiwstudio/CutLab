/**
 * Shared component contracts for HIW Studio visual assets.
 * Type-only module (no runtime imports beyond React types).
 */
import type { CSSProperties } from "react";
import type { Position } from "../manifest/schema";

export type { Position };

/** A motion is a pure function of the current frame returning CSS to apply. */
export type MotionStyle = CSSProperties;
export type MotionFn = (frame: number, fps: number) => MotionStyle;

/** Props passed to every character component. Layout (position/scale) is applied by Scene. */
export interface CharacterProps {
  variant?: string;
  expression?: string;
  motion?: string;
  frame: number;
  fps: number;
  flip?: boolean;
  /** When true, the mouth flaps with a procedural talk cycle. */
  speaking?: boolean;
  /** Free-form pass-through props from the manifest. */
  extra?: Record<string, unknown>;
}

/** Props passed to every background component. */
export interface BackgroundProps {
  mood?: string;
  frame: number;
  fps: number;
}

/** Props passed to every prop component. */
export interface PropProps {
  frame: number;
  fps: number;
  animation?: string;
  flip?: boolean;
  /** Optional text to render on the prop (label on a sign, words in a bubble). */
  text?: string;
}

/** Props passed to every effect overlay component. */
export interface EffectProps {
  frame: number;
  fps: number;
  intensity?: number;
}

export type AssetKind =
  | "character"
  | "background"
  | "prop"
  | "motion"
  | "effect";
