/** Money stack prop (architecture §10). */
import React from "react";
import type { PropProps } from "../../../engine/assets/assetTypes";
import { HIW_PALETTE as C } from "../../theme";

export const MoneyStack: React.FC<PropProps> = () => (
  <svg viewBox="0 0 100 100" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" style={{ overflow: "visible" }}>
    <g stroke={C.outline} strokeWidth={4} strokeLinejoin="round">
      <rect x={14} y={64} width={72} height={22} rx={4} fill="#5fae74" />
      <rect x={14} y={46} width={72} height={22} rx={4} fill="#6dbd82" />
      <rect x={14} y={28} width={72} height={22} rx={4} fill="#7cc991" />
      <circle cx={50} cy={39} r={9} fill="#e9f8ee" />
      <text x={50} y={44} textAnchor="middle" fontSize={13} fontWeight={800} fill={C.outline} stroke="none" fontFamily="Arial, sans-serif">$</text>
    </g>
  </svg>
);
