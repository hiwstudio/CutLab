import type { MotionFn } from "../../../engine/assets/assetTypes";

/** Cautious looking left and right. */
export const lookAround: MotionFn = (frame, fps) => {
  const t = frame / fps;
  const sweep = Math.sin(t * Math.PI * 2 * 0.4);
  return { transform: `translateX(${(sweep * 5).toFixed(2)}px) rotate(${(sweep * 4).toFixed(2)}deg)` };
};
