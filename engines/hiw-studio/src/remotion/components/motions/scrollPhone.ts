import type { MotionFn } from "../../../engine/assets/assetTypes";

/** Hunched-over phone scroll: slight forward lean with a small rhythmic jitter. */
export const scrollPhone: MotionFn = (frame, fps) => {
  const t = frame / fps;
  const jitter = Math.sin(t * Math.PI * 2 * 2) * 1.5;
  return { transform: `translateY(${jitter.toFixed(2)}px) rotate(2deg)` };
};
