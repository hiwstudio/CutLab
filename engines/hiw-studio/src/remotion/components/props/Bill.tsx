/** Bill prop (architecture §10). A single banknote. */
import React from "react";
import type { PropProps } from "../../../engine/assets/assetTypes";
import { HIW_PALETTE as C } from "../../theme";

export const Bill: React.FC<PropProps> = () => (
  <svg viewBox="0 0 100 100" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" style={{ overflow: "visible" }}>
    <g stroke={C.outline} strokeWidth={4} strokeLinejoin="round">
      <rect x={10} y={32} width={80} height={40} rx={5} fill="#6dbd82" />
      <circle cx={50} cy={52} r={12} fill="#bfe6cb" />
      <text x={50} y={57} textAnchor="middle" fontSize={14} fontWeight={800} fill={C.outline} stroke="none" fontFamily="Arial, sans-serif">$</text>
      <circle cx={22} cy={42} r={3} fill="#bfe6cb" stroke="none" />
      <circle cx={78} cy={62} r={3} fill="#bfe6cb" stroke="none" />
    </g>
  </svg>
);
