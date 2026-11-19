/**
 * Human character (V2 — Pillar 1). Layered, articulated puppet:
 *  - static ground shadow
 *  - body group with breathing bob + sway
 *  - arms that gently swing from the shoulders
 *  - head group with a subtle tilt + blink-aware face
 *  - soft shading (radial skin gradient, torso highlight/shadow), rounder linework
 *  - visibly distinct variants (caveman / modern / office / tired / excited)
 */
import React from "react";
import type { CharacterProps } from "../../../engine/assets/assetTypes";
import { HIW_PALETTE as C } from "../../theme";
import { PuppetFace } from "./PuppetFace";
import { breathe, poseFor, safeId, talkAmount } from "./rig";

interface VariantStyle {
  skin: string;
  skinHi: string;
  torso: string;
  bareArms: boolean;
  hair: "neat" | "messy" | "none";
  beard: boolean;
  collar: boolean;
  tie: boolean;
  apron: boolean;
  bowtie: boolean;
}

function variantStyle(variant: string): VariantStyle {
  const base = { apron: false, bowtie: false };
  switch (variant) {
    case "caveman":
      return { skin: C.caveSkin, skinHi: C.caveSkinHi, torso: C.fur, bareArms: true, hair: "messy", beard: true, collar: false, tie: false, ...base };
    case "modern":
      return { skin: C.skin, skinHi: C.skinHi, torso: C.shirtModern, bareArms: false, hair: "neat", beard: false, collar: false, tie: false, ...base };
    case "office":
      return { skin: C.skin, skinHi: C.skinHi, torso: C.shirtOffice, bareArms: false, hair: "neat", beard: false, collar: true, tie: true, ...base };
    case "tired":
      return { skin: C.skin, skinHi: C.skinHi, torso: C.shirtTired, bareArms: false, hair: "neat", beard: false, collar: false, tie: false, ...base };
    case "excited":
      return { skin: C.skin, skinHi: C.skinHi, torso: C.shirtExcited, bareArms: false, hair: "neat", beard: false, collar: false, tie: false, ...base };
    case "waiter":
      return { skin: C.skin, skinHi: C.skinHi, torso: C.shirtWaiter, bareArms: false, hair: "neat", beard: false, collar: true, tie: false, apron: true, bowtie: true };
    default:
      return { skin: C.skin, skinHi: C.skinHi, torso: C.shirt, bareArms: false, hair: "neat", beard: false, collar: false, tie: false, ...base };
  }
}

export const Human: React.FC<CharacterProps> = ({ variant = "default", expression, motion, frame = 0, fps = 30, speaking }) => {
  const v = variantStyle(variant);
  const uid = safeId(React.useId());
  const skinG = `skin-${uid}`;
  const b = breathe(frame, fps);
  const pose = poseFor(motion, frame, fps);
  const leftArmRot = (pose.leftArm + b.armSwing * 0.4).toFixed(2);
  const rightArmRot = (pose.rightArm - b.armSwing * 0.4).toFixed(2);
  const headRot = (b.headTilt + pose.headTilt).toFixed(2);
  const mouthOpen = speaking ? talkAmount(frame, fps) : 0;

  const sleeve = v.bareArms ? v.skin : v.torso;
  const shadowG = `shadow-${uid}`;

  return (
    <svg viewBox="0 0 200 344" width="100%" height="100%" preserveAspectRatio="xMidYMax meet" style={{ overflow: "visible" }}>
      <defs>
        <radialGradient id={skinG} cx="0.4" cy="0.32" r="0.8">
          <stop offset="0%" stopColor={v.skinHi} />
          <stop offset="100%" stopColor={v.skin} />
        </radialGradient>
        <radialGradient id={shadowG} cx="0.5" cy="0.5" r="0.5">
          <stop offset="0%" stopColor="#1b1712" stopOpacity={0.32} />
          <stop offset="65%" stopColor="#1b1712" stopOpacity={0.14} />
          <stop offset="100%" stopColor="#1b1712" stopOpacity={0} />
        </radialGradient>
      </defs>

      {/* Soft contact shadow (static, stays put while the body breathes) */}
      <ellipse cx={100} cy={324} rx={70} ry={15} fill={`url(#${shadowG})`} />

      <g transform={`translate(${b.shiftX.toFixed(2)} ${b.bobY.toFixed(2)}) rotate(${(b.sway * 0.5).toFixed(2)} 100 250)`}>
        <g stroke={C.outline} strokeWidth={4} strokeLinejoin="round" strokeLinecap="round">
          {/* Legs */}
          <rect x={79} y={206} width={18} height={92} rx={9} fill={C.pants} />
          <rect x={103} y={206} width={18} height={92} rx={9} fill={C.pants} />
          <ellipse cx={86} cy={302} rx={16} ry={9} fill={C.outline} />
          <ellipse cx={114} cy={302} rx={16} ry={9} fill={C.outline} />

          {/* Arms (pose + breathe swing from shoulders) */}
          <g transform={`rotate(${leftArmRot} 56 134)`}>
            <rect x={46} y={128} width={20} height={74} rx={10} fill={sleeve} />
            <circle cx={56} cy={206} r={12} fill={v.skin} />
          </g>
          <g transform={`rotate(${rightArmRot} 144 134)`}>
            <rect x={134} y={128} width={20} height={74} rx={10} fill={sleeve} />
            <circle cx={144} cy={206} r={12} fill={v.skin} />
          </g>

          {/* Torso */}
          <rect x={62} y={120} width={76} height={98} rx={24} fill={v.torso} />
        </g>

        {/* Torso shading (no stroke) */}
        <rect x={70} y={126} width={60} height={26} rx={16} fill={C.white} opacity={0.1} />
        <ellipse cx={100} cy={210} rx={42} ry={16} fill="#000" opacity={0.08} />

        {/* Waiter waist apron (over the torso bottom + upper legs) */}
        {v.apron ? (
          <g stroke={C.outline} strokeWidth={4} strokeLinejoin="round">
            <rect x={74} y={158} width={52} height={116} rx={8} fill={C.apron} />
            <rect x={70} y={148} width={60} height={12} rx={4} fill={C.apron} />
            <rect x={88} y={212} width={24} height={22} rx={3} fill="none" stroke="#222a33" strokeWidth={3} />
          </g>
        ) : null}

        {/* Office collar + tie */}
        {v.collar ? (
          <g stroke={C.outline} strokeWidth={3} strokeLinejoin="round">
            <path d="M88,124 L100,140 L88,150 Z" fill={C.white} />
            <path d="M112,124 L100,140 L112,150 Z" fill={C.white} />
          </g>
        ) : null}
        {v.tie ? <path d="M100,140 L94,150 L100,196 L106,150 Z" fill={C.accentRed} stroke={C.outline} strokeWidth={3} strokeLinejoin="round" /> : null}

        {/* Waiter bow tie (at the collar) */}
        {v.bowtie ? (
          <g stroke={C.outline} strokeWidth={2.5} strokeLinejoin="round">
            <path d="M100,132 L84,124 L84,140 Z" fill={C.black} />
            <path d="M100,132 L116,124 L116,140 Z" fill={C.black} />
            <rect x={96} y={127} width={8} height={10} rx={2} fill={C.black} />
          </g>
        ) : null}

        {/* Neck */}
        <rect x={90} y={104} width={20} height={24} fill={v.skin} stroke={C.outline} strokeWidth={4} strokeLinejoin="round" />

        {/* Head group (tilt) */}
        <g transform={`rotate(${headRot} 100 66)`}>
          <g stroke={C.outline} strokeWidth={4} strokeLinejoin="round">
            <circle cx={56} cy={70} r={9} fill={v.skin} />
            <circle cx={144} cy={70} r={9} fill={v.skin} />
            <circle cx={100} cy={66} r={46} fill={`url(#${skinG})`} />
          </g>

          {/* Beard (caveman) */}
          {v.beard ? (
            <path
              d="M58,72 C60,118 84,140 100,140 C116,140 140,118 142,72 C132,96 116,104 100,104 C84,104 68,96 58,72 Z"
              fill={C.hair}
              opacity={0.95}
            />
          ) : null}

          {/* Hair */}
          {v.hair === "messy" ? (
            <path d="M52,64 Q46,12 100,6 Q154,12 148,64 Q138,28 120,40 Q112,18 100,36 Q88,18 80,40 Q62,28 52,64 Z" fill={C.hair} stroke={C.outline} strokeWidth={4} strokeLinejoin="round" />
          ) : v.hair === "neat" ? (
            <path d="M56,62 Q58,16 100,12 Q142,16 144,62 Q120,36 100,40 Q80,36 56,62 Z" fill={C.hair} stroke={C.outline} strokeWidth={4} strokeLinejoin="round" />
          ) : null}

          {/* Face */}
          <g transform="translate(100 66)">
            <PuppetFace expression={expression} r={40} frame={frame} fps={fps} mouthOpen={mouthOpen} />
          </g>
        </g>
      </g>
    </svg>
  );
};
