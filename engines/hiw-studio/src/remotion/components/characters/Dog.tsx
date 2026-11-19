/**
 * Dog character (V2.1 — new character). A friendly sitting dog puppet, built in the
 * same layered, frame-driven style as Human / AncientBrain:
 *  - soft radial contact shadow
 *  - breathing body bob
 *  - a tail that wags (faster when happy/excited/celebrating)
 *  - floppy ears that perk up a little when alert/happy
 *  - blink-aware eyes, expressive brows, and a lolling tongue
 *  - a red collar with a gold tag (reads instantly as "pet")
 *
 * Receives frame/fps from Scene, so all animation is deterministic.
 */
import React from "react";
import type { CharacterProps } from "../../../engine/assets/assetTypes";
import { HIW_PALETTE as C } from "../../theme";
import { blinkAmount, breathe, safeId } from "./rig";

const COAT = "#c8893f";
const COAT_HI = "#e3ad62";
const COAT_SHADOW = "#a76d2c";
const EAR = "#a96526";
const CREAM = "#f3dcb0";
const NOSE = "#2c2622";
const TONGUE = "#ef7d8e";
const COLLAR = "#e0533a";
const TAG = "#ffd24d";

type DogMood = "neutral" | "happy" | "anxious" | "shocked" | "confused" | "tired";

function moodFor(expression: string | undefined): DogMood {
  switch (expression) {
    case "happy":
    case "excited":
      return "happy";
    case "anxious":
    case "worried":
    case "angry":
      return "anxious";
    case "shocked":
      return "shocked";
    case "confused":
      return "confused";
    case "tired":
      return "tired";
    default:
      return "neutral";
  }
}

export const Dog: React.FC<CharacterProps> = ({ expression, motion, frame = 0, fps = 30 }) => {
  const uid = safeId(React.useId());
  const coatG = `dogcoat-${uid}`;
  const shadowG = `dogshadow-${uid}`;
  const b = breathe(frame, fps);
  const mood = moodFor(expression);
  const t = frame / fps;
  const TAU = Math.PI * 2;

  // Tail wags constantly; much faster + wider when the dog is happy/celebrating.
  const excited = mood === "happy" || motion === "celebrate";
  const wagSpeed = excited ? 7.5 : motion === "panic" ? 6 : 2.4;
  const wagAmp = excited ? 26 : 14;
  const tailRot = Math.sin(t * TAU * wagSpeed) * wagAmp;

  // Ears perk up slightly when alert/happy, droop when tired/anxious.
  const earPerk = mood === "shocked" || mood === "happy" ? -10 : mood === "tired" || mood === "anxious" ? 8 : 0;

  // Head tilt: a curious tilt for "confused", plus gentle breathing.
  const headTilt = (b.headTilt * 0.6 + (mood === "confused" ? 12 : 0)).toFixed(2);

  const tongueOut = mood === "happy" || motion === "celebrate" || motion === "walk";
  const blink = blinkAmount(frame, fps);
  const baseOpen = mood === "tired" ? 0.45 : 1;
  const eyeOpen = Math.max(0.08, baseOpen * (1 - 0.9 * blink));
  const eyeR = mood === "shocked" ? 9 : 7;

  return (
    <svg viewBox="0 0 200 300" width="100%" height="100%" preserveAspectRatio="xMidYMax meet" style={{ overflow: "visible" }}>
      <defs>
        <radialGradient id={coatG} cx="0.42" cy="0.32" r="0.85">
          <stop offset="0%" stopColor={COAT_HI} />
          <stop offset="65%" stopColor={COAT} />
          <stop offset="100%" stopColor={COAT_SHADOW} />
        </radialGradient>
        <radialGradient id={shadowG} cx="0.5" cy="0.5" r="0.5">
          <stop offset="0%" stopColor="#1b1712" stopOpacity={0.32} />
          <stop offset="65%" stopColor="#1b1712" stopOpacity={0.14} />
          <stop offset="100%" stopColor="#1b1712" stopOpacity={0} />
        </radialGradient>
      </defs>

      {/* Soft contact shadow */}
      <ellipse cx={100} cy={290} rx={72} ry={15} fill={`url(#${shadowG})`} />

      <g transform={`translate(0 ${b.bobY.toFixed(2)})`}>
        {/* Tail (behind body, wagging from its base) */}
        <g transform={`rotate(${tailRot.toFixed(2)} 150 214)`}>
          <path
            d="M150,216 C176,208 190,176 184,150 C176,168 166,182 150,196 Z"
            fill={COAT}
            stroke={C.outline}
            strokeWidth={4}
            strokeLinejoin="round"
          />
        </g>

        <g stroke={C.outline} strokeWidth={4} strokeLinejoin="round" strokeLinecap="round">
          {/* Seated body / haunches */}
          <path
            d="M58,176 C44,196 40,250 56,278 L144,278 C160,250 156,196 142,176 C128,158 72,158 58,176 Z"
            fill={`url(#${coatG})`}
          />
          {/* Hind paw hint at the base sides */}
          <ellipse cx={60} cy={276} rx={22} ry={13} fill={COAT_SHADOW} />
          <ellipse cx={140} cy={276} rx={22} ry={13} fill={COAT_SHADOW} />

          {/* Front legs */}
          <rect x={80} y={206} width={17} height={74} rx={8} fill={COAT} />
          <rect x={103} y={206} width={17} height={74} rx={8} fill={COAT} />
          {/* Front paws */}
          <ellipse cx={88} cy={280} rx={15} ry={9} fill={CREAM} />
          <ellipse cx={112} cy={280} rx={15} ry={9} fill={CREAM} />
        </g>

        {/* Chest / belly cream patch (no stroke) */}
        <path d="M100,182 C84,182 76,210 80,246 C88,260 112,260 120,246 C124,210 116,182 100,182 Z" fill={CREAM} opacity={0.9} />

        {/* Collar */}
        <g stroke={C.outline} strokeWidth={4} strokeLinejoin="round">
          <path d="M64,170 C78,186 122,186 136,170 L132,156 C118,168 82,168 68,156 Z" fill={COLLAR} />
          <circle cx={100} cy={182} r={8} fill={TAG} />
        </g>

        {/* Head group */}
        <g transform={`rotate(${headTilt} 100 96)`}>
          {/* Floppy ears (behind head) */}
          <g stroke={C.outline} strokeWidth={4} strokeLinejoin="round">
            <g transform={`rotate(${earPerk} 64 60)`}>
              <path d="M64,58 C40,54 26,84 34,128 C50,132 64,112 70,84 Z" fill={EAR} />
            </g>
            <g transform={`rotate(${-earPerk} 136 60)`}>
              <path d="M136,58 C160,54 174,84 166,128 C150,132 136,112 130,84 Z" fill={EAR} />
            </g>
          </g>

          {/* Head */}
          <ellipse cx={100} cy={92} rx={54} ry={50} fill={`url(#${coatG})`} stroke={C.outline} strokeWidth={4} />
          {/* Soft highlight */}
          <ellipse cx={80} cy={72} rx={22} ry={15} fill={C.white} opacity={0.16} />

          {/* Muzzle */}
          <ellipse cx={100} cy={114} rx={32} ry={24} fill={CREAM} stroke={C.outline} strokeWidth={3.5} />

          {/* Eyes */}
          <g>
            {[-22, 22].map((ex) => (
              <g key={ex} transform={`translate(${100 + ex} 82)`}>
                <g transform={`scale(1 ${eyeOpen.toFixed(3)})`}>
                  <circle cx={0} cy={0} r={eyeR} fill={C.outline} />
                  <circle cx={-eyeR * 0.3} cy={-eyeR * 0.4} r={eyeR * 0.36} fill={C.white} />
                </g>
                {blink > 0.55 ? (
                  <line x1={-eyeR * 1.1} y1={0} x2={eyeR * 1.1} y2={0} stroke={C.outline} strokeWidth={3} strokeLinecap="round" />
                ) : null}
              </g>
            ))}
          </g>

          {/* Brows for mood */}
          {mood === "anxious" ? (
            <g stroke={C.outline} strokeWidth={3.5} strokeLinecap="round">
              <line x1={70} y1={62} x2={86} y2={68} />
              <line x1={130} y1={62} x2={114} y2={68} />
            </g>
          ) : mood === "confused" ? (
            <g stroke={C.outline} strokeWidth={3.5} strokeLinecap="round">
              <line x1={70} y1={64} x2={86} y2={60} />
              <line x1={114} y1={66} x2={130} y2={66} />
            </g>
          ) : null}

          {/* Nose */}
          <ellipse cx={100} cy={102} rx={10} ry={7.5} fill={NOSE} />
          <ellipse cx={96} cy={100} rx={3} ry={2} fill={C.white} opacity={0.5} />

          {/* Mouth + optional tongue */}
          <path d="M100,109 L100,118" stroke={C.outline} strokeWidth={3} strokeLinecap="round" />
          {tongueOut ? (
            <>
              <path d="M92,120 Q88,138 100,140 Q112,138 108,120 Z" fill={TONGUE} stroke={C.outline} strokeWidth={3} strokeLinejoin="round" />
              <line x1={100} y1={122} x2={100} y2={136} stroke="#c95f6f" strokeWidth={2} strokeLinecap="round" />
              <path d="M82,118 Q100,128 118,118" fill="none" stroke={C.outline} strokeWidth={3} strokeLinecap="round" />
            </>
          ) : mood === "anxious" || mood === "tired" ? (
            <path d="M86,124 Q100,116 114,124" fill="none" stroke={C.outline} strokeWidth={3} strokeLinecap="round" />
          ) : (
            <path d="M84,118 Q92,128 100,124 Q108,128 116,118" fill="none" stroke={C.outline} strokeWidth={3} strokeLinecap="round" />
          )}
        </g>
      </g>
    </svg>
  );
};
