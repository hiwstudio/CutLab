/** Laptop prop (architecture §10). */
import React from "react";
import type { PropProps } from "../../../engine/assets/assetTypes";
import { HIW_PALETTE as C } from "../../theme";

export const Laptop: React.FC<PropProps> = () => (
  <svg viewBox="0 0 100 100" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" style={{ overflow: "visible" }}>
    <g stroke={C.outline} strokeWidth={4} strokeLinejoin="round">
      <rect x={22} y={24} width={56} height={40} rx={4} fill={C.outline} />
      <rect x={26} y={28} width={48} height={32} rx={2} fill="#7fc8ff" stroke="none" />
      <path d="M14,64 L86,64 L92,76 L8,76 Z" fill="#c7ced6" />
      <rect x={8} y={76} width={84} height={5} rx={2.5} fill="#9aa7b5" stroke="none" />
    </g>
  </svg>
);
