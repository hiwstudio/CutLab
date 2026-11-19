/** Coin prop (architecture §10). */
import React from "react";
import type { PropProps } from "../../../engine/assets/assetTypes";
import { HIW_PALETTE as C } from "../../theme";

export const Coin: React.FC<PropProps> = ({ animation }) => (
  <svg viewBox="0 0 100 100" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" style={{ overflow: "visible" }}>
    <g
      stroke={C.outline}
      strokeWidth={4}
      style={animation === "glow" ? { filter: "drop-shadow(0 0 8px #ffe14d)" } : undefined}
    >
      <circle cx={50} cy={50} r={36} fill="#ffcf4d" />
      <circle cx={50} cy={50} r={27} fill="none" stroke="#e0a92e" strokeWidth={3} />
      <text x={50} y={62} textAnchor="middle" fontSize={34} fontWeight={800} fill="#b9831f" stroke="none" fontFamily="Arial, sans-serif">$</text>
    </g>
  </svg>
);
