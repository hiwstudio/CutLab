import React from "react";
import { CLEAN_PALETTE as C } from "../CleanTheme";

export interface RenCleanProps {
  pose?: "reading" | "lookup" | "tea" | "laugh" | "standing";
  expression?: "peaceful" | "smiling" | "shySelfConscious" | "warmLaugh";
  scale?: number;
  flip?: boolean;
}

export const RenClean: React.FC<RenCleanProps> = ({
  pose = "reading",
  expression = "peaceful",
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
        <radialGradient id="ren-head-glow" cx="0.4" cy="0.3" r="0.75">
          <stop offset="0%" stopColor={C.renSkinHi} />
          <stop offset="100%" stopColor={C.renSkin} />
        </radialGradient>
      </defs>

      {/* Subtle Ground Contact Shadow */}
      <ellipse cx="110" cy="365" rx="60" ry="12" fill={C.shadow} />

      {/* Seated Table & Chair Staging if seated */}
      {pose !== "standing" && (
        <g stroke={C.ink} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
          {/* Chair backrest */}
          <path d="M 52,180 L 52,340 M 64,180 L 64,340" stroke={C.inkSecondary} strokeWidth="3" />
          <path d="M 44,180 C 44,170 72,170 72,180 L 72,210 L 44,210 Z" fill="#D3A274" />

          {/* Table top edge */}
          <rect x="80" y="240" width="135" height="12" rx="3" fill="#E8C9A3" />
          {/* Table leg */}
          <line x1="145" y1="252" x2="145" y2="365" stroke={C.ink} strokeWidth="4" />
        </g>
      )}

      {/* Lower Body / Pants */}
      <g stroke={C.ink} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M 86,240 L 80,335 L 94,335 L 100,240 Z" fill="#3D405B" />
        <path d="M 112,240 L 116,335 L 130,335 L 126,240 Z" fill="#3D405B" />
        {/* Clean leather shoes */}
        <path d="M 72,344 C 72,336 82,332 96,332 L 98,344 Z" fill="#6B4B3E" />
        <path d="M 112,344 C 112,336 122,332 136,332 L 138,344 Z" fill="#6B4B3E" />
      </g>

      {/* Torso: Breton Striped Top & Mustard-Yellow Button Cardigan */}
      <g stroke={C.ink} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
        {/* Breton Striped Shirt Base */}
        <path
          d="M 72,142 C 68,170 70,220 74,242 C 96,246 124,246 146,242 C 150,220 152,170 148,142 Z"
          fill={C.renStripeLight}
        />
        {/* Navy Stripes */}
        <line x1="73" y1="165" x2="147" y2="165" stroke={C.renStripeDark} strokeWidth="4" />
        <line x1="73" y1="180" x2="147" y2="180" stroke={C.renStripeDark} strokeWidth="4" />
        <line x1="74" y1="195" x2="146" y2="195" stroke={C.renStripeDark} strokeWidth="4" />
        <line x1="74" y1="210" x2="146" y2="210" stroke={C.renStripeDark} strokeWidth="4" />
        <line x1="74" y1="225" x2="146" y2="225" stroke={C.renStripeDark} strokeWidth="4" />

        {/* Mustard Cardigan (Open front showing stripes) */}
        {/* Left Side Cardigan */}
        <path
          d="M 68,140 C 62,170 64,225 72,244 C 82,245 92,244 94,242 C 90,200 92,165 102,142 Z"
          fill={C.renCardigan}
        />
        {/* Right Side Cardigan */}
        <path
          d="M 152,140 C 158,170 156,225 148,244 C 138,245 128,244 126,242 C 130,200 128,165 118,142 Z"
          fill={C.renCardigan}
        />

        {/* Tiny Brown Buttons on Cardigan Trim */}
        <circle cx="94" cy="170" r="2.5" fill="#4A3525" />
        <circle cx="94" cy="190" r="2.5" fill="#4A3525" />
        <circle cx="94" cy="210" r="2.5" fill="#4A3525" />
        <circle cx="94" cy="230" r="2.5" fill="#4A3525" />

        {/* Poses: Arms & Hands */}
        {pose === "reading" && (
          <>
            {/* Arms bent resting on table holding open paperback novel */}
            <path d="M 68,146 C 56,170 66,215 106,236" fill="none" stroke={C.ink} strokeWidth="16" />
            <path d="M 68,146 C 56,170 66,215 106,236" fill="none" stroke={C.renCardigan} strokeWidth="10" />

            <path d="M 152,146 C 164,170 154,215 118,236" fill="none" stroke={C.ink} strokeWidth="16" />
            <path d="M 152,146 C 164,170 154,215 118,236" fill="none" stroke={C.renCardigan} strokeWidth="10" />

            {/* Open Paperback Book resting on table */}
            <path d="M 96,232 L 112,238 L 128,232 L 126,248 L 112,252 L 98,248 Z" fill="#F8F6F0" stroke={C.ink} strokeWidth="2.5" />
            {/* Sage Green Book Cover Spine */}
            <path d="M 94,233 L 112,240 L 130,233" fill="none" stroke={C.renBookCover} strokeWidth="4" />
            {/* Clean hands holding pages */}
            <circle cx="98" cy="238" r="6" fill={C.renSkin} stroke={C.ink} strokeWidth="2.5" />
            <circle cx="126" cy="238" r="6" fill={C.renSkin} stroke={C.ink} strokeWidth="2.5" />
          </>
        )}

        {(pose === "lookup" || pose === "tea") && (
          <>
            {/* Right arm resting by ceramic tea cup */}
            <path d="M 68,146 C 58,170 70,210 96,234" fill="none" stroke={C.ink} strokeWidth="16" />
            <path d="M 68,146 C 58,170 70,210 96,234" fill="none" stroke={C.renCardigan} strokeWidth="10" />
            <circle cx="98" cy="236" r="7" fill={C.renSkin} stroke={C.ink} strokeWidth="2.5" />

            <path d="M 152,146 C 164,170 156,200 138,225" fill="none" stroke={C.ink} strokeWidth="16" />
            <path d="M 152,146 C 164,170 156,200 138,225" fill="none" stroke={C.renCardigan} strokeWidth="10" />
            {/* Clean Ceramic Tea Cup */}
            <rect x="135" y="218" width="22" height="24" rx="4" fill="#FFFFFF" stroke={C.ink} strokeWidth="3" />
            <path d="M 157,224 C 163,224 163,236 157,236" fill="none" stroke={C.ink} strokeWidth="2.5" />
            <circle cx="138" cy="225" r="6" fill={C.renSkin} stroke={C.ink} strokeWidth="2" />
          </>
        )}

        {pose === "laugh" && (
          <>
            {/* Hand gently near collar / chest in warm laugh */}
            <path d="M 68,146 C 56,170 72,210 96,234" fill="none" stroke={C.ink} strokeWidth="16" />
            <path d="M 68,146 C 56,170 72,210 96,234" fill="none" stroke={C.renCardigan} strokeWidth="10" />

            <path d="M 152,146 C 166,165 150,185 120,180" fill="none" stroke={C.ink} strokeWidth="16" />
            <path d="M 152,146 C 166,165 150,185 120,180" fill="none" stroke={C.renCardigan} strokeWidth="10" />
            <circle cx="118" cy="180" r="7" fill={C.renSkin} stroke={C.ink} strokeWidth="2.5" />
          </>
        )}
      </g>

      {/* Head Group */}
      <g>
        {/* Neck */}
        <rect x="103" y="118" width="14" height="18" rx="2" fill={C.renSkin} stroke={C.ink} strokeWidth="3.5" />

        {/* Smooth Oval Head */}
        <ellipse cx="110" cy="80" rx="42" ry="46" fill="url(#ren-head-glow)" stroke={C.ink} strokeWidth="3.5" />

        {/* Chic Dark Brown Bob Haircut */}
        <path
          d="M 68,82 C 64,48 86,34 114,34 C 142,34 156,48 152,82 C 154,98 148,110 144,114 C 142,96 138,52 110,52 C 84,52 78,96 76,114 C 72,110 66,98 68,82 Z"
          fill={C.renHair}
          stroke={C.ink}
          strokeWidth="3.2"
          strokeLinejoin="round"
        />

        {/* Facial Features */}
        {expression === "peaceful" && (
          <>
            <path d="M 94,66 Q 102,63 108,66" fill="none" stroke={C.ink} strokeWidth="2.8" strokeLinecap="round" />
            <path d="M 118,66 Q 124,63 132,66" fill="none" stroke={C.ink} strokeWidth="2.8" strokeLinecap="round" />
            {/* Eyes looking gently downward at book */}
            <circle cx="102" cy="78" r="3.2" fill={C.ink} />
            <circle cx="124" cy="78" r="3.2" fill={C.ink} />
            <path d="M 106,94 Q 113,97 120,94" fill="none" stroke={C.ink} strokeWidth="2.5" strokeLinecap="round" />
          </>
        )}

        {expression === "smiling" && (
          <>
            <path d="M 94,64 Q 102,61 108,65" fill="none" stroke={C.ink} strokeWidth="2.8" strokeLinecap="round" />
            <path d="M 118,65 Q 124,61 132,64" fill="none" stroke={C.ink} strokeWidth="2.8" strokeLinecap="round" />
            {/* Bright, looking up eyes */}
            <circle cx="102" cy="74" r="3.6" fill={C.ink} />
            <circle cx="124" cy="74" r="3.6" fill={C.ink} />
            {/* Gentle smile */}
            <path d="M 104,91 Q 113,101 122,91" fill="none" stroke={C.ink} strokeWidth="3" strokeLinecap="round" />
          </>
        )}

        {expression === "shySelfConscious" && (
          <>
            {/* Slightly nervous brow */}
            <path d="M 94,64 L 108,68" fill="none" stroke={C.ink} strokeWidth="2.8" strokeLinecap="round" />
            <path d="M 118,68 L 132,64" fill="none" stroke={C.ink} strokeWidth="2.8" strokeLinecap="round" />
            <circle cx="102" cy="76" r="3.5" fill={C.ink} />
            <circle cx="124" cy="76" r="3.5" fill={C.ink} />
            {/* Shy polite smile */}
            <path d="M 106,94 Q 113,96 120,94" fill="none" stroke={C.ink} strokeWidth="2.8" strokeLinecap="round" />
            {/* Tiny pink blush dots on cheeks */}
            <circle cx="92" cy="84" r="4.5" fill="#F4A261" opacity="0.45" />
            <circle cx="134" cy="84" r="4.5" fill="#F4A261" opacity="0.45" />
          </>
        )}

        {expression === "warmLaugh" && (
          <>
            <path d="M 94,62 Q 102,59 108,63" fill="none" stroke={C.ink} strokeWidth="2.8" strokeLinecap="round" />
            <path d="M 118,63 Q 124,59 132,62" fill="none" stroke={C.ink} strokeWidth="2.8" strokeLinecap="round" />
            {/* Happy curved squint eyes */}
            <path d="M 97,76 Q 102,71 107,76" fill="none" stroke={C.ink} strokeWidth="3.2" strokeLinecap="round" />
            <path d="M 119,76 Q 124,71 129,76" fill="none" stroke={C.ink} strokeWidth="3.2" strokeLinecap="round" />
            {/* Open warm laughing mouth */}
            <path d="M 103,90 Q 113,106 123,90 Z" fill="#9E2A2B" stroke={C.ink} strokeWidth="2.8" strokeLinejoin="round" />
            {/* Cheerful blush */}
            <circle cx="90" cy="82" r="5" fill="#F4A261" opacity="0.5" />
            <circle cx="136" cy="82" r="5" fill="#F4A261" opacity="0.5" />
          </>
        )}
      </g>
    </svg>
  );
};
