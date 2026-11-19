/** Warning sign prop (architecture §10). */
import React from "react";
import type { PropProps } from "../../../engine/assets/assetTypes";
import { HIW_PALETTE as C } from "../../theme";

export const WarningSign: React.FC<PropProps> = ({ animation }) => (
  <svg viewBox="0 0 100 100" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" style={{ overflow: "visible" }}>
    <g
      stroke={C.outline}
      strokeWidth={4}
      strokeLinejoin="round"
      style={animation === "glow" ? { filter: "drop-shadow(0 0 8px #ffd24d)" } : undefined}
    >
      <path d="M50,12 L92,84 L8,84 Z" fill={C.accentYellow} />
      <rect x={45} y={38} width={10} height={26} rx={5} fill={C.outline} stroke="none" />
      <circle cx={50} cy={74} r={5.5} fill={C.outline} stroke="none" />
    </g>
  </svg>
);
