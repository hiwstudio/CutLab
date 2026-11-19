/** Thought bubble effect (architecture §11). Drifting thought cloud, top area. */
import React from "react";
import { AbsoluteFill } from "remotion";
import type { EffectProps } from "../../../engine/assets/assetTypes";
import { HIW_PALETTE as C } from "../../theme";

export const ThoughtBubble: React.FC<EffectProps> = ({ frame, fps }) => {
  const bob = Math.sin((frame / fps) * Math.PI * 2 * 0.5) * 10;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <svg viewBox="0 0 1600 900" width="100%" height="100%" preserveAspectRatio="xMidYMid slice">
        <g transform={`translate(1040 ${160 + bob})`} stroke={C.outline} strokeWidth={4}>
          <circle cx={20} cy={120} r={10} fill={C.white} />
          <circle cx={48} cy={92} r={16} fill={C.white} />
          <ellipse cx={140} cy={40} rx={120} ry={62} fill={C.white} />
          <circle cx={80} cy={70} r={34} fill={C.white} />
          <circle cx={210} cy={66} r={36} fill={C.white} />
        </g>
      </svg>
    </AbsoluteFill>
  );
};
