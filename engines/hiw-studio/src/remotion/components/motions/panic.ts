import type { MotionFn } from "../../../engine/assets/assetTypes";

/** Frantic shake + bounce (architecture §8.6 reference motion). */
export const panic: MotionFn = (frame) => {
  const shake = Math.sin(frame * 1.2) * 8;
  const bounce = Math.sin(frame * 0.5) * 10;
  return {
    transform: `translate(${shake.toFixed(2)}px, ${bounce.toFixed(2)}px) rotate(${(shake * 0.3).toFixed(2)}deg)`,
  };
};
