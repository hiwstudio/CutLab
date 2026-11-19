/** Notification bubble prop (architecture §10). Red alert badge. */
import React from "react";
import type { PropProps } from "../../../engine/assets/assetTypes";
import { HIW_PALETTE as C } from "../../theme";

export const NotificationBubble: React.FC<PropProps> = ({ animation }) => (
  <svg viewBox="0 0 100 100" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" style={{ overflow: "visible" }}>
    <g
      stroke={C.outline}
      strokeWidth={4}
      style={animation === "glow" ? { filter: "drop-shadow(0 0 10px #ff7a7a)" } : undefined}
    >
      <circle cx={50} cy={46} r={34} fill={C.accentRed} />
      <path d="M50,26 C40,26 34,33 34,44 L34,54 L30,62 L70,62 L66,54 L66,44 C66,33 60,26 50,26 Z" fill={C.white} stroke="none" />
      <circle cx={50} cy={68} r={6} fill={C.white} stroke="none" />
    </g>
  </svg>
);
