import type { MotionFn } from "../../../engine/assets/assetTypes";

/** Happy celebration jump with a little rotation. */
export const celebrate: MotionFn = (frame, fps) => {
  const t = frame / fps;
  const jump = Math.abs(Math.sin(t * Math.PI * 2 * 1.4)) * 22;
  const tilt = Math.sin(t * Math.PI * 2 * 1.4) * 4;
  return { transform: `translateY(${(-jump).toFixed(2)}px) rotate(${tilt.toFixed(2)}deg)` };
};
