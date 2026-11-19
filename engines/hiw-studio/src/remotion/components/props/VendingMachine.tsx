/**
 * Vending machine prop (architecture §10).
 *
 * A front-facing snack machine — a classic inanimate object we irrationally personify
 * ("thank the machine"). Reusable for consumerism / modern-object / temptation beats.
 * `animation === "glow"` lights up the selection panel.
 */
import React from "react";
import type { PropProps } from "../../../engine/assets/assetTypes";
import { HIW_PALETTE as C } from "../../theme";

export const VendingMachine: React.FC<PropProps> = ({ animation }) => {
  const glow = animation === "glow";
  return (
    <svg viewBox="0 0 100 100" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" style={{ overflow: "visible" }}>
      <g stroke={C.outline} strokeWidth={4} strokeLinejoin="round">
        {/* cabinet */}
        <rect x={22} y={8} width={56} height={86} rx={5} fill="#ef5f6b" />
        {/* glass display */}
        <rect
          x={28}
          y={14}
          width={34}
          height={58}
          rx={3}
          fill="#bfe6ff"
          style={glow ? { filter: "drop-shadow(0 0 6px #7fc8ff)" } : undefined}
        />
        {/* shelves + snacks */}
        <g stroke={C.outline} strokeWidth={2}>
          <line x1={28} y1={28} x2={62} y2={28} />
          <line x1={28} y1={42} x2={62} y2={42} />
          <line x1={28} y1={56} x2={62} y2={56} />
          <rect x={31} y={18} width={9} height={7} rx={1.5} fill={C.accentYellow} stroke="none" />
          <rect x={44} y={18} width={9} height={7} rx={1.5} fill={C.accentGreen} stroke="none" />
          <rect x={31} y={32} width={9} height={7} rx={1.5} fill="#ff9f43" stroke="none" />
          <rect x={49} y={32} width={9} height={7} rx={1.5} fill={C.shirt} stroke="none" />
          <rect x={31} y={46} width={9} height={7} rx={1.5} fill={C.brain} stroke="none" />
          <rect x={44} y={46} width={9} height={7} rx={1.5} fill={C.accentYellow} stroke="none" />
        </g>
        {/* keypad + selection panel */}
        <rect
          x={66}
          y={14}
          width={9}
          height={20}
          rx={2}
          fill={glow ? C.accentGreen : "#2c3e50"}
          stroke={C.outline}
          strokeWidth={3}
          style={glow ? { filter: "drop-shadow(0 0 5px #37c871)" } : undefined}
        />
        <g fill={C.white} stroke="none">
          <circle cx={70.5} cy={19} r={1.6} />
          <circle cx={70.5} cy={24} r={1.6} />
          <circle cx={70.5} cy={29} r={1.6} />
        </g>
        {/* dispenser tray */}
        <rect x={28} y={78} width={44} height={11} rx={2} fill="#2c3e50" />
        {/* legs */}
        <rect x={26} y={92} width={7} height={5} fill={C.outline} stroke="none" />
        <rect x={67} y={92} width={7} height={5} fill={C.outline} stroke="none" />
      </g>
    </svg>
  );
};
