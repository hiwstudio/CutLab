/** Alarm flash effect (architecture §11). Pulsing red alert tint. */
import React from "react";
import { AbsoluteFill } from "remotion";
import type { EffectProps } from "../../../engine/assets/assetTypes";

export const AlarmFlash: React.FC<EffectProps> = ({ frame, fps, intensity = 0.5 }) => {
  const pulse = (Math.sin((frame / fps) * Math.PI * 2 * 2) * 0.5 + 0.5) * 0.28 * (0.5 + intensity);
  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        background: `radial-gradient(circle at center, rgba(255,40,40,0) 40%, rgba(255,30,30,${pulse.toFixed(3)}) 100%)`,
      }}
    />
  );
};
