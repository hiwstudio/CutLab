/** Pop effect (architecture §11). A starburst that pops at the scene start. */
import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import type { EffectProps } from "../../../engine/assets/assetTypes";
import { HIW_PALETTE as C } from "../../theme";

export const PopEffect: React.FC<EffectProps> = ({ frame, fps }) => {
  const dur = Math.max(1, fps * 0.5);
  const scale = interpolate(frame, [0, dur], [0.2, 1.3], { extrapolateRight: "clamp" });
  const opacity = interpolate(frame, [0, dur * 0.6, dur], [1, 1, 0], { extrapolateRight: "clamp" });
  const spikes = 12;
  const points: string[] = [];
  for (let i = 0; i < spikes * 2; i++) {
    const r = i % 2 === 0 ? 90 : 44;
    const a = (Math.PI / spikes) * i;
    points.push(`${(800 + Math.cos(a) * r).toFixed(1)},${(300 + Math.sin(a) * r).toFixed(1)}`);
  }
  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity }}>
      <svg viewBox="0 0 1600 900" width="100%" height="100%" preserveAspectRatio="xMidYMid slice">
        <g transform={`translate(800 300) scale(${scale.toFixed(3)}) translate(-800 -300)`}>
          <polygon points={points.join(" ")} fill={C.accentYellow} stroke={C.outline} strokeWidth={5} />
        </g>
      </svg>
    </AbsoluteFill>
  );
};
