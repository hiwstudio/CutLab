import React from "react";
import { CLEAN_PALETTE as C } from "../CleanTheme";

export interface LogicCleanProps {
  pose?: "holdingBoard" | "pointing" | "relaxed";
  scale?: number;
  flip?: boolean;
}

export const LogicClean: React.FC<LogicCleanProps> = ({
  pose = "holdingBoard",
  scale = 1.0,
  flip = false,
}) => {
  return (
    <svg
      viewBox="0 0 220 360"
      width={220 * scale}
      height={360 * scale}
      style={{
        overflow: "visible",
        transform: flip ? "scaleX(-1)" : "none",
        filter: "drop-shadow(0 12px 24px rgba(20,20,30,0.06))",
      }}
    >
      <defs>
        <radialGradient id="logic-head-glow" cx="0.4" cy="0.3" r="0.75">
          <stop offset="0%" stopColor="#FFFFFF" />
          <stop offset="100%" stopColor="#F5F0E8" />
        </radialGradient>
      </defs>

      {/* Subtle Ground Contact Shadow */}
      <ellipse cx="110" cy="345" rx="55" ry="11" fill={C.shadow} />

      {/* Legs & Shoes */}
      <g stroke={C.ink} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M 90,225 L 86,325 L 98,325 L 102,225 Z" fill="#3D405B" />
        <path d="M 118,225 L 122,325 L 134,325 L 130,225 Z" fill="#3D405B" />
        <path d="M 76,334 C 76,326 86,323 100,323 L 102,334 Z" fill="#1E1E24" />
        <path d="M 118,334 C 118,326 128,323 142,323 L 144,334 Z" fill="#1E1E24" />
      </g>

      {/* Torso: Navy Blue Tailored Blazer over Light Blue Shirt & Tie */}
      <g stroke={C.ink} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
        {/* Shirt Base */}
        <path d="M 80,135 L 140,135 L 144,230 L 76,230 Z" fill={C.logicShirt} />
        {/* Coral-Orange Tie */}
        <path d="M 106,140 L 114,140 L 112,195 L 108,195 Z" fill={C.logicTie} />

        {/* Navy Blazer */}
        <path d="M 70,135 C 64,165 66,215 74,232 L 100,232 L 94,140 Z" fill={C.logicBlazer} />
        <path d="M 150,135 C 156,165 154,215 146,232 L 120,232 L 126,140 Z" fill={C.logicBlazer} />

        {/* Arms holding miniature whiteboard */}
        {pose === "holdingBoard" && (
          <>
            <path d="M 70,140 C 50,170 60,200 90,205" fill="none" stroke={C.ink} strokeWidth="16" />
            <path d="M 70,140 C 50,170 60,200 90,205" fill="none" stroke={C.logicBlazer} strokeWidth="10" />

            <path d="M 150,140 C 170,170 160,200 130,205" fill="none" stroke={C.ink} strokeWidth="16" />
            <path d="M 150,140 C 170,170 160,200 130,205" fill="none" stroke={C.logicBlazer} strokeWidth="10" />

            {/* Clean Mini Whiteboard */}
            <rect x="75" y="165" width="70" height="50" rx="4" fill="#FFFFFF" stroke={C.ink} strokeWidth="3" />
            <rect x="77" y="167" width="66" height="46" rx="2" fill="none" stroke={C.logicBoardFrame} strokeWidth="2" />
            {/* Sensible neat lines on whiteboard */}
            <line x1="84" y1="178" x2="110" y2="178" stroke={C.inkSecondary} strokeWidth="2.5" strokeLinecap="round" />
            <line x1="84" y1="188" x2="132" y2="188" stroke={C.inkSecondary} strokeWidth="2.5" strokeLinecap="round" />
            <line x1="84" y1="198" x2="120" y2="198" stroke={C.inkSecondary} strokeWidth="2.5" strokeLinecap="round" />

            {/* Clean hands holding board edges */}
            <circle cx="75" cy="190" r="6" fill="#F5F0E8" stroke={C.ink} strokeWidth="2.5" />
            <circle cx="145" cy="190" r="6" fill="#F5F0E8" stroke={C.ink} strokeWidth="2.5" />
          </>
        )}
      </g>

      {/* Head Group */}
      <g>
        <rect x="103" y="115" width="14" height="20" rx="2" fill="#F5F0E8" stroke={C.ink} strokeWidth="3.5" />
        <ellipse cx="110" cy="78" rx="40" ry="44" fill="url(#logic-head-glow)" stroke={C.ink} strokeWidth="3.5" />

        {/* Neat Side-Parted Hair */}
        <path
          d="M 72,72 C 70,45 88,36 112,36 C 136,36 148,46 146,72 C 142,52 126,45 110,45 C 92,45 80,55 72,72 Z"
          fill="#3B3530"
          stroke={C.ink}
          strokeWidth="3"
        />

        {/* Round Tortoiseshell Glasses */}
        <circle cx="98" cy="76" r="11" fill="rgba(255,255,255,0.6)" stroke="#6A4C3A" strokeWidth="3.2" />
        <circle cx="122" cy="76" r="11" fill="rgba(255,255,255,0.6)" stroke="#6A4C3A" strokeWidth="3.2" />
        <line x1="109" y1="76" x2="111" y2="76" stroke="#6A4C3A" strokeWidth="3.2" />

        {/* Intelligent Dot Eyes behind lenses */}
        <circle cx="98" cy="76" r="3" fill={C.ink} />
        <circle cx="122" cy="76" r="3" fill={C.ink} />

        {/* Calm Flat Line Mouth */}
        <line x1="104" y1="96" x2="118" y2="96" stroke={C.ink} strokeWidth="2.5" strokeLinecap="round" />
      </g>
    </svg>
  );
};
