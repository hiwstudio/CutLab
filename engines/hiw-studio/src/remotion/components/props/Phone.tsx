/** Phone prop (architecture §10). */
import React from "react";
import type { PropProps } from "../../../engine/assets/assetTypes";
import { HIW_PALETTE as C } from "../../theme";

export const Phone: React.FC<PropProps> = ({ animation }) => (
  <svg viewBox="0 0 100 100" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" style={{ overflow: "visible" }}>
    <g
      stroke={C.outline}
      strokeWidth={4}
      strokeLinejoin="round"
      style={animation === "glow" ? { filter: "drop-shadow(0 0 8px #7fd0ff)" } : undefined}
    >
      <rect x={30} y={8} width={40} height={84} rx={10} fill={C.outline} />
      <rect x={34} y={16} width={32} height={64} rx={4} fill="#bfe3ff" />
      <circle cx={50} cy={86} r={3.4} fill="#5b6b7a" />
      <rect x={42} y={11} width={16} height={3} rx={1.5} fill="#5b6b7a" />
    </g>
  </svg>
);
