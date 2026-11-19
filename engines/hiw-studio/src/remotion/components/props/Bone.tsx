/** Bone prop (V2.1). A classic dog bone. */
import React from "react";
import type { PropProps } from "../../../engine/assets/assetTypes";
import { HIW_PALETTE as C } from "../../theme";

export const Bone: React.FC<PropProps> = () => (
  <svg viewBox="0 0 100 100" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" style={{ overflow: "visible" }}>
    <g stroke={C.outline} strokeWidth={4} strokeLinejoin="round" transform="rotate(-28 50 50)">
      <rect x={28} y={42} width={44} height={16} rx={8} fill="#f4ead2" />
      <g fill="#f4ead2">
        <circle cx={28} cy={42} r={11} />
        <circle cx={28} cy={58} r={11} />
        <circle cx={72} cy={42} r={11} />
        <circle cx={72} cy={58} r={11} />
      </g>
      <rect x={30} y={46} width={40} height={5} rx={2.5} fill="#ffffff" stroke="none" opacity={0.5} />
    </g>
  </svg>
);
