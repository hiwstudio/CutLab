import type { MotionFn } from "../../../engine/assets/assetTypes";

/** Gentle breathing bob. */
export const idle: MotionFn = (frame, fps) => {
  const t = frame / fps;
  const y = Math.sin(t * Math.PI * 2 * 0.5) * 4;
  return { transform: `translateY(${y.toFixed(2)}px)` };
};
