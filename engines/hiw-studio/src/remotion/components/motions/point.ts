import type { MotionFn } from "../../../engine/assets/assetTypes";

/** Lean forward to point, with a small emphasis pulse. */
export const point: MotionFn = (frame, fps) => {
  const t = frame / fps;
  const pulse = Math.sin(t * Math.PI * 2 * 1) * 1.5;
  return { transform: `translateX(${(6 + pulse).toFixed(2)}px) rotate(-2deg)` };
};
