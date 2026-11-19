import type { MotionFn } from "../../../engine/assets/assetTypes";

/** "Aha!" pop: a quick scale-up rise then a gentle settle. */
export const lightbulbIdea: MotionFn = (frame, fps) => {
  const t = frame / fps;
  const pop = Math.sin(t * Math.PI * 2 * 0.8) * 0.04;
  const rise = Math.sin(t * Math.PI * 2 * 0.8) * 3;
  return { transform: `translateY(${(-rise).toFixed(2)}px) scale(${(1 + Math.max(0, pop)).toFixed(3)})` };
};
