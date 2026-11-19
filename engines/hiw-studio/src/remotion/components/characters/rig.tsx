/**
 * Character rig primitives (V2 — Pillar 1).
 *
 * Pure, frame-driven helpers that give the puppets "life": periodic blinking and
 * subtle breathing/sway/head-tilt/arm-swing. Characters receive `frame`/`fps` as
 * props (from Scene), so these are deterministic functions, not hooks.
 */

/** Clamp to the 0..1 range. */
export const clamp01 = (x: number): number => Math.max(0, Math.min(1, x));

/** Overshoot ease (anticipation → past-target → settle). Used for limbs arriving at a pose. */
export function easeOutBack(x: number): number {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  const u = x - 1;
  return 1 + c3 * u * u * u + c1 * u * u;
}

/** Smooth in/out, no overshoot. */
export function easeInOutSine(x: number): number {
  return -(Math.cos(Math.PI * x) - 1) / 2;
}

/** Eyelid closed amount, 0 (open) → 1 (shut). Periodic blink with a quick close/open. */
export function blinkAmount(frame: number, fps: number, period = 3.6): number {
  const t = frame / fps;
  const closeDur = 0.14;
  const phase = t % period;
  const into = phase - (period - closeDur);
  if (into < 0) return 0;
  const x = into / closeDur; // 0..1 across the blink
  return 1 - Math.abs(2 * x - 1); // 0 → 1 → 0 triangle
}

/**
 * Subtle wandering gaze (in units of eye radius). A slow drift plus an occasional
 * quick saccade, so the eyes feel alive instead of fixed. Pure function of frame.
 */
export function gaze(frame: number, fps: number): { x: number; y: number } {
  const t = frame / fps;
  const TAU = Math.PI * 2;
  // slow ambient drift
  let x = Math.sin(t * TAU * 0.08) * 0.16 + Math.sin(t * TAU * 0.21 + 1.3) * 0.05;
  const y = Math.sin(t * TAU * 0.13 + 0.5) * 0.1;
  // occasional quick glance to the side, then back
  const sacc = t % 5.2;
  if (sacc > 4.7 && sacc < 5.0) x += 0.22 * Math.sin(((sacc - 4.7) / 0.3) * Math.PI);
  return { x, y };
}

export interface BreathePose {
  /** Vertical body bob in px. */
  bobY: number;
  /** Lateral weight shift in px. */
  shiftX: number;
  /** Body sway in degrees. */
  sway: number;
  /** Head tilt in degrees. */
  headTilt: number;
  /** Arm swing in degrees. */
  armSwing: number;
}

/**
 * Subtle always-on secondary motion so a "static" pose still feels alive. Layered
 * low-frequency sines (not a single clock) plus a slow lateral weight shift, and a
 * head tilt that lags the body sway — all of which read as "breathing/standing", not
 * "vibrating".
 */
export function breathe(frame: number, fps: number): BreathePose {
  const t = frame / fps;
  const TAU = Math.PI * 2;
  return {
    bobY: Math.sin(t * TAU * 0.22) * 2 + Math.sin(t * TAU * 0.07) * 0.8,
    shiftX: Math.sin(t * TAU * 0.09) * 2.2,
    sway: Math.sin(t * TAU * 0.16) * 1.1,
    headTilt: Math.sin(t * TAU * 0.18 - 0.6) * 1.6,
    armSwing: Math.sin(t * TAU * 0.2) * 2.4,
  };
}

/** Sanitize a React.useId() value so it is safe inside SVG url(#...) references. */
export function safeId(raw: string): string {
  return raw.replace(/[^a-zA-Z0-9_-]/g, "_");
}

export interface RigPose {
  /** Left arm rotation in degrees (positive raises the left arm up/out). */
  leftArm: number;
  /** Right arm rotation in degrees (negative raises the right arm up/out). */
  rightArm: number;
  /** Extra head tilt in degrees, added on top of breathe. */
  headTilt: number;
}

/**
 * Per-limb pose for a motion id (V2 — Pillar 2). Layered on top of breathe() so the
 * 10 catalog motions actually articulate the rig's arms/head, not just translate the
 * whole body (that whole-body transform is still applied by Scene via MotionFn).
 * `frame` is scene-relative.
 */
export function poseFor(motion: string | undefined, frame: number, fps: number): RigPose {
  const t = frame / fps;
  const TAU = Math.PI * 2;
  // Arrival envelope (0→1 with a slight overshoot) so a held pose swings in with
  // anticipation instead of teleporting to its target on frame 0. Continuous motions
  // (walk/panic) ignore it.
  const settle = easeOutBack(clamp01(t / 0.42));
  switch (motion) {
    case "walk": {
      const s = Math.sin(t * TAU * 1.6) * 22;
      return { leftArm: s, rightArm: s, headTilt: 0 };
    }
    case "panic":
      return { leftArm: 116 + Math.sin(frame * 1.3) * 16, rightArm: -116 - Math.cos(frame * 1.4) * 16, headTilt: 0 };
    case "celebrate": {
      const j = Math.abs(Math.sin(t * TAU * 1.4)) * 12;
      return { leftArm: (138 + j) * settle, rightArm: (-138 - j) * settle, headTilt: 0 };
    }
    case "point":
      return { leftArm: 0, rightArm: -82 * settle, headTilt: 0 };
    case "shrug": {
      const u = (Math.sin(t * TAU * 0.6) * 0.5 + 0.5) * 14;
      return { leftArm: (40 + u) * settle, rightArm: (-40 - u) * settle, headTilt: 0 };
    }
    case "facepalm":
      return { leftArm: 150 * settle, rightArm: 0, headTilt: 7 * settle };
    case "scrollPhone":
      return { leftArm: 34 * settle, rightArm: -34 * settle, headTilt: 5 * settle };
    case "lightbulbIdea": {
      const p = Math.sin(t * TAU * 0.8);
      return { leftArm: (124 + (p > 0 ? p * 8 : 0)) * settle, rightArm: 0, headTilt: -2 * settle };
    }
    case "wave": {
      // Right arm swings up (overshoot) then waves side to side: hello/goodbye.
      const w = Math.sin(t * TAU * 2.2) * 16;
      return { leftArm: 0, rightArm: (-132 + w) * settle, headTilt: -2 * settle };
    }
    case "lookAround":
    case "idle":
    default:
      return { leftArm: 0, rightArm: 0, headTilt: 0 };
  }
}

/** Procedural mouth-open amount (0..1) for a believable "talking" flap. */
export function talkAmount(frame: number, fps: number): number {
  const t = frame / fps;
  const TAU = Math.PI * 2;
  const a = (0.5 + 0.5 * Math.sin(t * TAU * 5.5)) * (0.6 + 0.4 * Math.sin(t * TAU * 2.3));
  return Math.max(0, Math.min(1, a));
}
