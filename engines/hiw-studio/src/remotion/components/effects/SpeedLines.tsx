/** Speed lines effect (architecture §11). Comic urgency streaks on the sides. */
import React from "react";
import { AbsoluteFill } from "remotion";
import type { EffectProps } from "../../../engine/assets/assetTypes";
import { HIW_PALETTE as C } from "../../theme";

export const SpeedLines: React.FC<EffectProps> = ({ frame }) => {
  const offset = (frame * 14) % 120;
  const rows = Array.from({ length: 7 });
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <svg viewBox="0 0 1600 900" width="100%" height="100%" preserveAspectRatio="xMidYMid slice">
        {rows.map((_, i) => {
          const y = 120 + i * 110;
          const len = 70 + ((i * 37) % 60);
          return (
            <g key={i} stroke={C.outline} strokeWidth={6} strokeLinecap="round" opacity={0.5}>
              <line x1={-offset} y1={y} x2={-offset + len} y2={y} />
              <line x1={1600 + offset - len} y1={y + 50} x2={1600 + offset} y2={y + 50} />
            </g>
          );
        })}
      </svg>
    </AbsoluteFill>
  );
};
