import React from "react";
import { CLEAN_PALETTE as C } from "../CleanTheme";

export interface OggCleanProps {
  pose?: "alert" | "lever" | "peaceful";
  scale?: number;
  flip?: boolean;
}

export const OggClean: React.FC<OggCleanProps> = ({
  pose = "alert",
  scale = 1.0,
  flip = false,
}) => {
  return (
    <svg
      viewBox="0 0 220 340"
      width={220 * scale}
      height={340 * scale}
      style={{
        overflow: "visible",
        transform: flip ? "scaleX(-1)" : "none",
        filter: "drop-shadow(0 12px 24px rgba(20,20,30,0.06))",
      }}
    >
      <defs>
        <radialGradient id="ogg-head-glow" cx="0.4" cy="0.3" r="0.75">
          <stop offset="0%" stopColor="#F9E8D6" />
          <stop offset="100%" stopColor={C.oggSkin} />
        </radialGradient>
      </defs>

      {/* Subtle Ground Contact Shadow */}
      <ellipse cx="110" cy="325" rx="60" ry="12" fill={C.shadow} />

      {pose === "alert" && (
        <g stroke={C.ink} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
          {/* Crouched legs */}
          <path d="M 75,210 L 60,260 L 80,315 L 60,315" fill="none" strokeWidth="16" />
          <path d="M 75,210 L 60,260 L 80,315 L 60,315" fill="none" stroke={C.oggSkin} strokeWidth="10" />

          <path d="M 135,210 L 150,260 L 130,315 L 150,315" fill="none" strokeWidth="16" />
          <path d="M 135,210 L 150,260 L 130,315 L 150,315" fill="none" stroke={C.oggSkin} strokeWidth="10" />

          {/* Tidy Camel Fur Tunic */}
          <path
            d="M 70,140 C 65,180 70,225 76,230 L 90,218 L 105,232 L 120,218 L 134,230 C 140,225 145,180 140,140 Z"
            fill={C.oggFur}
          />
          {/* Fur texture specks */}
          <line x1="84" y1="160" x2="88" y2="170" stroke="#7A4E2D" strokeWidth="2" />
          <line x1="120" y1="170" x2="124" y2="180" stroke="#7A4E2D" strokeWidth="2" />

          {/* Left arm braced */}
          <path d="M 75,146 C 55,170 50,210 70,230" fill="none" stroke={C.ink} strokeWidth="16" />
          <path d="M 75,146 C 55,170 50,210 70,230" fill="none" stroke={C.oggSkin} strokeWidth="10" />

          {/* Right arm gripping wooden club raised defensively */}
          <path d="M 135,146 C 155,160 165,150 160,115" fill="none" stroke={C.ink} strokeWidth="16" />
          <path d="M 135,146 C 155,160 165,150 160,115" fill="none" stroke={C.oggSkin} strokeWidth="10" />
          <circle cx="160" cy="115" r="9" fill={C.oggSkin} stroke={C.ink} strokeWidth="3" />

          {/* Clean Smooth Wooden Club */}
          <path
            d="M 156,125 L 176,50 C 185,45 195,55 190,65 L 165,130 Z"
            fill={C.oggClub}
            stroke={C.ink}
            strokeWidth="3.2"
          />
        </g>
      )}

      {pose === "peaceful" && (
        <g stroke={C.ink} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
          {/* Sitting Cross-legged on floor */}
          <path d="M 55,270 C 65,300 145,300 155,270 C 140,250 70,250 55,270 Z" fill={C.oggSkin} />
          {/* Fur Tunic draped over lap */}
          <path
            d="M 70,140 C 65,180 65,260 76,270 L 134,270 C 145,260 145,180 140,140 Z"
            fill={C.oggFur}
          />
          {/* Resting arms on knees */}
          <path d="M 72,146 C 50,180 50,240 76,260" fill="none" stroke={C.ink} strokeWidth="16" />
          <path d="M 72,146 C 50,180 50,240 76,260" fill="none" stroke={C.oggSkin} strokeWidth="10" />
          <circle cx="76" cy="260" r="8" fill={C.oggSkin} stroke={C.ink} strokeWidth="3" />

          <path d="M 138,146 C 160,180 160,240 134,260" fill="none" stroke={C.ink} strokeWidth="16" />
          <path d="M 138,146 C 160,180 160,240 134,260" fill="none" stroke={C.oggSkin} strokeWidth="10" />
          <circle cx="134" cy="260" r="8" fill={C.oggSkin} stroke={C.ink} strokeWidth="3" />

          {/* Wooden Club laid flat on the floor beside him */}
          <path
            d="M 30,305 L 180,305 C 190,300 190,318 180,314 L 30,314 Z"
            fill={C.oggClub}
            stroke={C.ink}
            strokeWidth="3.2"
          />
        </g>
      )}

      {/* Head Group */}
      <g>
        {/* Wild but Clean Tidy Black Caveman Hair */}
        <path
          d="M 60,85 C 45,50 75,25 110,25 C 145,25 175,50 160,85 C 170,105 160,120 150,120 C 140,65 80,65 70,120 C 60,120 50,105 60,85 Z"
          fill="#2A2421"
          stroke={C.ink}
          strokeWidth="3.5"
          strokeLinejoin="round"
        />

        {/* Round Off-White Head */}
        <circle cx="110" cy="80" r="42" fill="url(#ogg-head-glow)" stroke={C.ink} strokeWidth="3.5" />

        {/* Big Heavy Arched Brow */}
        <path
          d="M 80,68 C 95,58 125,58 140,68"
          fill="none"
          stroke={C.ink}
          strokeWidth="6"
          strokeLinecap="round"
        />

        {/* Wide Alert Dot Eyes */}
        <circle cx="95" cy="80" r="5.5" fill={C.ink} />
        <circle cx="125" cy="80" r="5.5" fill={C.ink} />

        {/* Simple Mouth */}
        {pose === "alert" ? (
          <ellipse cx="110" cy="100" rx="6" ry="7" fill={C.ink} />
        ) : (
          <path d="M 102,98 Q 110,104 118,98" fill="none" stroke={C.ink} strokeWidth="3" strokeLinecap="round" />
        )}
      </g>
    </svg>
  );
};
