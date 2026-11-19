/** Sweat drops effect (architecture §11). Anxiety drops near the top-centre. */
import React from "react";
import { AbsoluteFill } from "remotion";
import type { EffectProps } from "../../../engine/assets/assetTypes";
import { HIW_PALETTE as C } from "../../theme";

export const SweatDrops: React.FC<EffectProps> = ({ frame, fps }) => {
  const t = frame / fps;
  const drops = [
    { x: 720, baseY: 250, phase: 0 },
    { x: 880, baseY: 230, phase: 0.6 },
    { x: 800, baseY: 290, phase: 1.2 },
  ];
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <svg viewBox="0 0 1600 900" width="100%" height="100%" preserveAspectRatio="xMidYMid slice">
        {drops.map((d, i) => {
          const cycle = (t + d.phase) % 1.4;
          const y = d.baseY + cycle * 90;
          const opacity = cycle < 1.1 ? 1 : Math.max(0, 1 - (cycle - 1.1) * 5);
          return (
            <path
              key={i}
              d={`M${d.x},${y} C${d.x - 12},${y + 18} ${d.x + 12},${y + 18} ${d.x},${y} Z`}
              fill={C.sweat}
              stroke={C.outline}
              strokeWidth={3}
              opacity={opacity}
            />
          );
        })}
      </svg>
    </AbsoluteFill>
  );
};
