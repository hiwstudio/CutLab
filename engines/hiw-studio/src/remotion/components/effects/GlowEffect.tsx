/** Glow effect (architecture §11). Soft warm spotlight on the centre. */
import React from "react";
import { AbsoluteFill } from "remotion";
import type { EffectProps } from "../../../engine/assets/assetTypes";

export const GlowEffect: React.FC<EffectProps> = ({ frame, fps, intensity = 0.5 }) => {
  const pulse = (Math.sin((frame / fps) * Math.PI * 2 * 0.8) * 0.5 + 0.5) * 0.18 + 0.18;
  const strength = (pulse * (0.6 + intensity)).toFixed(3);
  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        background: `radial-gradient(circle at 50% 52%, rgba(255,235,160,${strength}) 0%, rgba(255,235,160,0) 45%)`,
      }}
    />
  );
};
