import type { MotionFn } from "../../../engine/assets/assetTypes";

/** Despairing head-down tilt that settles into place. */
export const facepalm: MotionFn = (frame, fps) => {
  const t = frame / fps;
  const settle = Math.min(1, t / 0.6);
  const wobble = Math.sin(t * Math.PI * 2 * 0.5) * 1;
  return { transform: `rotate(${(5 * settle + wobble).toFixed(2)}deg) translateY(${(3 * settle).toFixed(2)}px)` };
};
