import type { MotionFn } from "../../../engine/assets/assetTypes";

/** Friendly hello/goodbye: a gentle body lean while the arm waves (arm is in poseFor). */
export const wave: MotionFn = (frame, fps) => {
  const t = frame / fps;
  const lean = Math.sin(t * Math.PI * 2 * 0.5) * 1.2;
  return { transform: `rotate(${lean.toFixed(2)}deg)` };
};
