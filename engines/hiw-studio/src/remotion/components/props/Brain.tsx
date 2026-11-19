/** Brain prop (architecture §10). A small standalone brain icon. */
import React from "react";
import type { PropProps } from "../../../engine/assets/assetTypes";
import { HIW_PALETTE as C } from "../../theme";

export const Brain: React.FC<PropProps> = () => (
  <svg viewBox="0 0 100 100" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" style={{ overflow: "visible" }}>
    <path
      d="M50,16 C36,10 20,18 22,32 C10,36 12,54 24,58 C20,70 32,80 44,74 C48,84 62,84 66,72 C80,76 90,62 82,52 C92,46 90,30 78,28 C80,16 62,10 50,16 Z"
      fill={C.brain}
      stroke={C.outline}
      strokeWidth={4}
      strokeLinejoin="round"
    />
    <g fill="none" stroke={C.brainLine} strokeWidth={3} strokeLinecap="round">
      <path d="M50,20 C44,34 56,42 50,56 C46,66 54,72 50,80" />
      <path d="M30,36 C40,40 36,48 44,50" />
      <path d="M70,36 C60,40 64,48 56,50" />
    </g>
  </svg>
);
