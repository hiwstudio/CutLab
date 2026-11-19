import type { MotionFn } from "../../../engine/assets/assetTypes";

/** Slow "I don't know" shoulder shrug (vertical lift held then released). */
export const shrug: MotionFn = (frame, fps) => {
  const t = frame / fps;
  const lift = (Math.sin(t * Math.PI * 2 * 0.6) * 0.5 + 0.5) * 6;
  return { transform: `translateY(${(-lift).toFixed(2)}px)` };
};
