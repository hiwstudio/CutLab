/** Club prop (architecture §10). Caveman club. */
import React from "react";
import type { PropProps } from "../../../engine/assets/assetTypes";
import { HIW_PALETTE as C } from "../../theme";

export const Club: React.FC<PropProps> = () => (
  <svg viewBox="0 0 100 100" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" style={{ overflow: "visible" }}>
    <g stroke={C.outline} strokeWidth={4} strokeLinejoin="round">
      <rect x={20} y={66} width={40} height={14} rx={7} fill="#9c6b3f" transform="rotate(-38 40 73)" />
      <path d="M58,46 C70,34 84,34 88,46 C92,56 86,66 74,66 C80,54 70,48 58,46 Z" fill="#8a5a30" />
      <circle cx={70} cy={40} r={9} fill="#7a4e28" />
      <circle cx={82} cy={52} r={7} fill="#7a4e28" />
    </g>
  </svg>
);
