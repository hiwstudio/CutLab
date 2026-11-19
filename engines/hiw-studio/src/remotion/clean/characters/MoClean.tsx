import React from "react";
import { CLEAN_PALETTE as C } from "../CleanTheme";

export interface MoCleanProps {
  pose?: "pocket" | "freeze" | "cup" | "walk" | "splitDirector";
  expression?: "neutral" | "happy" | "anxious" | "shocked" | "crookedSmile" | "sternDirector";
  scale?: number;
  flip?: boolean;
}

export const MoClean: React.FC<MoCleanProps> = ({
  pose = "pocket",
  expression = "neutral",
  scale = 1.0,
  flip = false,
}) => {
  return (
    <svg
      viewBox="0 0 220 380"
      width={220 * scale}
      height={380 * scale}
      style={{
        overflow: "visible",
        transform: flip ? "scaleX(-1)" : "none",
        filter: "drop-shadow(0 12px 24px rgba(20,20,30,0.06))",
      }}
    >
      <defs>
        <radialGradient id="mo-head-glow" cx="0.4" cy="0.3" r="0.75">
          <stop offset="0%" stopColor={C.moSkinHi} />
          <stop offset="100%" stopColor={C.moSkin} />
        </radialGradient>
      </defs>

      {/* Subtle Ground Contact Shadow */}
      <ellipse cx="110" cy="365" rx="65" ry="12" fill={C.shadow} />

      {/* Legs & Shoes */}
      <g stroke={C.ink} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
        {/* Dark Tailored Joggers */}
        <path d="M 88,230 L 84,330 L 98,330 L 102,230 Z" fill={C.moPants} />
        <path d="M 118,230 L 122,330 L 136,330 L 132,230 Z" fill={C.moPants} />

        {/* Crisp Minimalist Sneakers */}
        <path d="M 72,342 C 72,332 84,328 100,328 L 104,342 Z" fill={C.moSneakers} />
        <line x1="72" y1="342" x2="104" y2="342" stroke={C.ink} strokeWidth="3" />
        <path d="M 116,342 C 116,332 128,328 144,328 L 148,342 Z" fill={C.moSneakers} />
        <line x1="116" y1="342" x2="148" y2="342" stroke={C.ink} strokeWidth="3" />
      </g>

      {/* Torso & Slate-Blue Hoodie */}
      <g stroke={C.ink} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
        {/* Main Hoodie Body */}
        <path
          d="M 68,140 C 64,170 66,215 72,238 C 95,244 125,244 148,238 C 154,215 156,170 152,140 C 140,126 80,126 68,140 Z"
          fill={C.moHoodie}
        />

        {/* Kangaroo Pocket */}
        <path
          d="M 80,188 L 140,188 L 144,226 L 76,226 Z"
          fill={C.moHoodiePocket}
          stroke={C.ink}
          strokeWidth="3"
        />

        {/* Poses: Hands */}
        {pose === "pocket" && (
          <>
            {/* Left Arm entering pocket */}
            <path
              d="M 70,146 C 54,170 52,195 86,206"
              fill="none"
              stroke={C.ink}
              strokeWidth="18"
            />
            <path
              d="M 70,146 C 54,170 52,195 86,206"
              fill="none"
              stroke={C.moHoodie}
              strokeWidth="12"
            />

            {/* Right Arm entering pocket */}
            <path
              d="M 150,146 C 166,170 168,195 134,206"
              fill="none"
              stroke={C.ink}
              strokeWidth="18"
            />
            <path
              d="M 150,146 C 166,170 168,195 134,206"
              fill="none"
              stroke={C.moHoodie}
              strokeWidth="12"
            />
          </>
        )}

        {pose === "freeze" && (
          <>
            {/* Stiff Mannequin Arms straight down */}
            <path d="M 66,146 L 56,235" fill="none" stroke={C.ink} strokeWidth="16" />
            <path d="M 66,146 L 56,235" fill="none" stroke={C.moHoodie} strokeWidth="10" />
            <circle cx="56" cy="242" r="8" fill={C.moSkin} stroke={C.ink} strokeWidth="3" />

            <path d="M 154,146 L 164,235" fill="none" stroke={C.ink} strokeWidth="16" />
            <path d="M 154,146 L 164,235" fill="none" stroke={C.moHoodie} strokeWidth="10" />
            <circle cx="164" cy="242" r="8" fill={C.moSkin} stroke={C.ink} strokeWidth="3" />
          </>
        )}

        {pose === "cup" && (
          <>
            {/* Left arm in pocket */}
            <path d="M 70,146 C 54,170 52,195 86,206" fill="none" stroke={C.ink} strokeWidth="18" />
            <path d="M 70,146 C 54,170 52,195 86,206" fill="none" stroke={C.moHoodie} strokeWidth="12" />

            {/* Right arm bent holding white ceramic cup */}
            <path d="M 150,146 C 166,165 174,180 156,198" fill="none" stroke={C.ink} strokeWidth="18" />
            <path d="M 150,146 C 166,165 174,180 156,198" fill="none" stroke={C.moHoodie} strokeWidth="12" />
            {/* Clean Ceramic Coffee Cup */}
            <rect x="148" y="184" width="22" height="26" rx="4" fill="#FFFFFF" stroke={C.ink} strokeWidth="3" />
            <path d="M 170,190 C 176,190 176,204 170,204" fill="none" stroke={C.ink} strokeWidth="2.5" />
            {/* Steam curl */}
            <path d="M 154,178 C 152,172 156,168 154,162" fill="none" stroke={C.inkTertiary} strokeWidth="2" strokeLinecap="round" />
            <path d="M 162,178 C 160,170 164,166 162,160" fill="none" stroke={C.inkTertiary} strokeWidth="2" strokeLinecap="round" />
          </>
        )}

        {/* Clean White Collar Notch */}
        <path d="M 102,130 L 110,144 L 118,130 Z" fill="#FFFFFF" stroke={C.ink} strokeWidth="3" />
      </g>

      {/* Head Group */}
      <g>
        {/* Neck */}
        <rect x="102" y="116" width="16" height="20" rx="3" fill={C.moSkin} stroke={C.ink} strokeWidth="3.5" />

        {/* Smooth Oval Head */}
        <ellipse
          cx="110"
          cy="80"
          rx="44"
          ry="48"
          fill="url(#mo-head-glow)"
          stroke={C.ink}
          strokeWidth="3.5"
          strokeLinejoin="round"
        />

        {/* Clean Side-Swept Dark Hair */}
        <path
          d="M 68,78 C 66,48 90,34 118,34 C 142,34 156,48 152,74 C 146,54 130,46 112,46 C 92,46 76,58 70,78 Z"
          fill={C.moHair}
          stroke={C.ink}
          strokeWidth="3"
        />

        {/* Facial Features */}
        {/* Eyebrows */}
        {expression === "neutral" && (
          <>
            <path d="M 94,66 Q 102,64 108,67" fill="none" stroke={C.ink} strokeWidth="3" strokeLinecap="round" />
            <path d="M 118,67 Q 124,64 132,66" fill="none" stroke={C.ink} strokeWidth="3" strokeLinecap="round" />
            <circle cx="102" cy="76" r="3.5" fill={C.ink} />
            <circle cx="124" cy="76" r="3.5" fill={C.ink} />
            <path d="M 106,94 Q 113,97 120,94" fill="none" stroke={C.ink} strokeWidth="2.5" strokeLinecap="round" />
          </>
        )}

        {expression === "happy" && (
          <>
            <path d="M 94,64 Q 102,61 108,65" fill="none" stroke={C.ink} strokeWidth="3" strokeLinecap="round" />
            <path d="M 118,65 Q 124,61 132,64" fill="none" stroke={C.ink} strokeWidth="3" strokeLinecap="round" />
            <circle cx="102" cy="74" r="3.5" fill={C.ink} />
            <circle cx="124" cy="74" r="3.5" fill={C.ink} />
            <path d="M 104,90 Q 113,102 122,90" fill="none" stroke={C.ink} strokeWidth="3" strokeLinecap="round" />
          </>
        )}

        {expression === "anxious" && (
          <>
            {/* Worried tilted brows */}
            <path d="M 94,64 L 108,70" fill="none" stroke={C.ink} strokeWidth="3.2" strokeLinecap="round" />
            <path d="M 118,70 L 132,64" fill="none" stroke={C.ink} strokeWidth="3.2" strokeLinecap="round" />
            <circle cx="102" cy="78" r="4.2" fill={C.ink} />
            <circle cx="124" cy="78" r="4.2" fill={C.ink} />
            {/* Tight flat mouth */}
            <line x1="104" y1="96" x2="122" y2="96" stroke={C.ink} strokeWidth="3" strokeLinecap="round" />
            {/* Tiny elegant sweat drop */}
            <path d="M 148,68 C 150,64 153,60 153,58 C 153,55 150,54 148,56 C 146,58 146,64 148,68 Z" fill="#6CC6FF" stroke={C.ink} strokeWidth="1.5" />
          </>
        )}

        {expression === "shocked" && (
          <>
            <path d="M 92,60 Q 102,56 108,60" fill="none" stroke={C.ink} strokeWidth="3.2" strokeLinecap="round" />
            <path d="M 118,60 Q 124,56 134,60" fill="none" stroke={C.ink} strokeWidth="3.2" strokeLinecap="round" />
            <circle cx="102" cy="74" r="5.5" fill={C.ink} />
            <circle cx="124" cy="74" r="5.5" fill={C.ink} />
            <ellipse cx="113" cy="95" rx="6" ry="8" fill={C.ink} />
            {/* Sweat drop */}
            <path d="M 148,64 C 151,60 154,56 154,54 C 154,51 150,50 148,52 C 146,54 146,60 148,64 Z" fill="#6CC6FF" stroke={C.ink} strokeWidth="1.5" />
          </>
        )}

        {expression === "crookedSmile" && (
          <>
            <path d="M 94,65 Q 102,62 108,66" fill="none" stroke={C.ink} strokeWidth="3" strokeLinecap="round" />
            <path d="M 118,66 Q 124,62 132,65" fill="none" stroke={C.ink} strokeWidth="3" strokeLinecap="round" />
            <circle cx="102" cy="75" r="3.5" fill={C.ink} />
            <circle cx="124" cy="75" r="3.5" fill={C.ink} />
            {/* Warm crooked smile */}
            <path d="M 103,94 Q 112,96 123,89" fill="none" stroke={C.ink} strokeWidth="3.2" strokeLinecap="round" />
          </>
        )}

        {expression === "sternDirector" && (
          <>
            {/* Severe glasses & stern mouth */}
            <circle cx="100" cy="76" r="12" fill="rgba(255,255,255,0.7)" stroke={C.ink} strokeWidth="3" />
            <circle cx="126" cy="76" r="12" fill="rgba(255,255,255,0.7)" stroke={C.ink} strokeWidth="3" />
            <line x1="112" y1="76" x2="114" y2="76" stroke={C.ink} strokeWidth="3" />
            <circle cx="100" cy="76" r="3" fill={C.ink} />
            <circle cx="126" cy="76" r="3" fill={C.ink} />
            <path d="M 90,62 L 108,67" fill="none" stroke={C.ink} strokeWidth="3.5" strokeLinecap="round" />
            <path d="M 118,67 L 136,62" fill="none" stroke={C.ink} strokeWidth="3.5" strokeLinecap="round" />
            <line x1="102" y1="98" x2="124" y2="98" stroke={C.ink} strokeWidth="3.5" strokeLinecap="round" />
          </>
        )}
      </g>
    </svg>
  );
};
