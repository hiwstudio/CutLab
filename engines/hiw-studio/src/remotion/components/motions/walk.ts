import type { MotionFn } from "../../../engine/assets/assetTypes";

/** Walk-in-place: vertical bob with a slight body sway. */
export const walk: MotionFn = (frame, fps) => {
  const t = frame / fps;
  const step = Math.abs(Math.sin(t * Math.PI * 2 * 1.6)) * 6;
  const sway = Math.sin(t * Math.PI * 2 * 1.6) * 2;
  return { transform: `translateY(${(-step).toFixed(2)}px) rotate(${sway.toFixed(2)}deg)` };
};
