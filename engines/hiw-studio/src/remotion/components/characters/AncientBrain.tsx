/**
 * Ancient Brain character (V2 — Pillar 1). The channel mascot, rebuilt as a shaded,
 * breathing rig: radial-gradient pink brain body, accented folds, soft highlight,
 * blink-aware face, gently swinging stubby limbs, and a static ground shadow.
 */
import React from "react";
import type { CharacterProps } from "../../../engine/assets/assetTypes";
import { HIW_PALETTE as C } from "../../theme";
import { PuppetFace } from "./PuppetFace";
import { breathe, poseFor, safeId, talkAmount } from "./rig";

export const AncientBrain: React.FC<CharacterProps> = ({ expression, motion, frame = 0, fps = 30, speaking }) => {
  const uid = safeId(React.useId());
  const brainG = `brain-${uid}`;
  const b = breathe(frame, fps);
  const pose = poseFor(motion, frame, fps);
  const leftArmRot = (pose.leftArm * 0.7 + b.armSwing * 0.4).toFixed(2);
  const rightArmRot = (pose.rightArm * 0.7 - b.armSwing * 0.4).toFixed(2);
  const headRot = (b.headTilt * 0.7 + pose.headTilt).toFixed(2);
  const mouthOpen = speaking ? talkAmount(frame, fps) : 0;
  const shadowG = `shadow-${uid}`;

  return (
    <svg viewBox="0 0 200 300" width="100%" height="100%" preserveAspectRatio="xMidYMax meet" style={{ overflow: "visible" }}>
      <defs>
        <radialGradient id={brainG} cx="0.4" cy="0.3" r="0.85">
          <stop offset="0%" stopColor={C.brainHi} />
          <stop offset="62%" stopColor={C.brain} />
          <stop offset="100%" stopColor={C.brainShadow} />
        </radialGradient>
        <radialGradient id={shadowG} cx="0.5" cy="0.5" r="0.5">
          <stop offset="0%" stopColor="#1b1712" stopOpacity={0.32} />
          <stop offset="65%" stopColor="#1b1712" stopOpacity={0.14} />
          <stop offset="100%" stopColor="#1b1712" stopOpacity={0} />
        </radialGradient>
      </defs>

      {/* Soft contact shadow */}
      <ellipse cx={100} cy={288} rx={64} ry={14} fill={`url(#${shadowG})`} />

      <g transform={`translate(${(b.shiftX * 0.7).toFixed(2)} ${b.bobY.toFixed(2)}) rotate(${(b.sway * 0.5).toFixed(2)} 100 230)`}>
        <g stroke={C.outline} strokeWidth={4} strokeLinejoin="round" strokeLinecap="round">
          {/* Legs (behind body) */}
          <rect x={80} y={206} width={13} height={70} rx={6} fill={C.brainMid} />
          <rect x={107} y={206} width={13} height={70} rx={6} fill={C.brainMid} />
          <ellipse cx={86} cy={280} rx={14} ry={8} fill={C.outline} />
          <ellipse cx={114} cy={280} rx={14} ry={8} fill={C.outline} />
        </g>

        <g transform={`rotate(${headRot} 100 150)`}>
          {/* Brain body */}
          <path
            d="M 100,66 C 70,54 40,70 44,100 C 24,104 26,138 44,150 C 30,166 40,200 70,200 C 74,218 100,222 112,202 C 142,214 170,190 156,160 C 178,150 176,112 156,104 C 162,74 130,56 100,66 Z"
            fill={`url(#${brainG})`}
            stroke={C.outline}
            strokeWidth={4}
            strokeLinejoin="round"
          />

          {/* Soft highlight */}
          <ellipse cx={78} cy={96} rx={26} ry={18} fill={C.white} opacity={0.18} />

          {/* Folds */}
          <g fill="none" stroke={C.brainLine} strokeWidth={3.5} strokeLinecap="round" opacity={0.85}>
            <path d="M100,74 C92,96 108,112 100,132 C92,152 108,172 100,196" />
            <path d="M60,100 C74,108 68,122 82,126" />
            <path d="M140,100 C126,108 132,122 118,126" />
            <path d="M64,158 C78,166 88,156 100,166" />
            <path d="M136,158 C122,166 112,156 100,166" />
          </g>

          {/* Arms (on top of body so raised poses stay visible) */}
          <g stroke={C.outline} strokeWidth={4} strokeLinejoin="round" strokeLinecap="round">
            <g transform={`rotate(${leftArmRot} 52 156)`}>
              <rect x={20} y={150} width={32} height={13} rx={6} fill={C.brainMid} />
            </g>
            <g transform={`rotate(${rightArmRot} 148 156)`}>
              <rect x={148} y={150} width={32} height={13} rx={6} fill={C.brainMid} />
            </g>
          </g>

          {/* Face */}
          <g transform="translate(100 150)">
            <PuppetFace expression={expression} r={40} frame={frame} fps={fps} mouthOpen={mouthOpen} />
          </g>
        </g>
      </g>
    </svg>
  );
};
