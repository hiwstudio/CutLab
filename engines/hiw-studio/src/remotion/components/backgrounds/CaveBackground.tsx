/**
 * Cave background (architecture §9).
 *
 * V2.1: a warm, clean "stone age" cave on the studio base — a rock arch, a few
 * stalactites and boulders, simple cave paintings on the wall, and a small crackling
 * fire with a soft glow. Lighter and tidier than the old dark cave, centre kept clear.
 */
import React from "react";
import { useCurrentFrame } from "remotion";
import type { BackgroundProps } from "../../../engine/assets/assetTypes";
import { StudioBase, type StudioTint } from "./StudioBase";

const CAVE_TINT: StudioTint = {
  top: "#f6ecdd",
  wall: "#ecdcc6",
  floor: "#dcc6a3",
  seam: "#c7aa7c",
};

const OUTLINE = "#1f2430";

export const CaveBackground: React.FC<BackgroundProps> = () => {
  const frame = useCurrentFrame();
  const flicker = 1 + Math.sin(frame * 0.5) * 0.08;
  return (
    <StudioBase tint={CAVE_TINT}>
      {/* Rock arch framing the scene */}
      <path
        d="M 180 900 Q 170 230 800 220 Q 1430 230 1420 900"
        fill="none"
        stroke="#c2a679"
        strokeWidth={16}
        opacity={0.7}
      />

      {/* Stalactites hanging from the arch */}
      <g fill="#d2b88c" stroke={OUTLINE} strokeWidth={4} strokeLinejoin="round">
        <path d="M430,236 L478,236 L454,330 Z" />
        <path d="M720,222 L772,222 L746,338 Z" />
        <path d="M1080,236 L1128,236 L1104,322 Z" />
      </g>

      {/* Cave paintings on the back wall */}
      <g stroke="#a6603a" strokeWidth={6} fill="none" strokeLinecap="round" opacity={0.7}>
        <path d="M610,430 q20,-40 44,0 l16,40 m-16,-40 l4,46" />
        <circle cx={700} cy={446} r={4} fill="#a6603a" />
        <path d="M880,440 l40,-10 l34,18 l-12,30 l-44,6 Z" />
        <path d="M860,470 l-18,24 m96,-18 l20,22" />
      </g>

      {/* Boulders on the floor */}
      <g stroke={OUTLINE} strokeWidth={4} strokeLinejoin="round">
        <ellipse cx={250} cy={730} rx={120} ry={58} fill="#cdb086" />
        <ellipse cx={1380} cy={742} rx={150} ry={64} fill="#c6a87d" />
      </g>

      {/* Small campfire with glow (right) */}
      <ellipse cx={1120} cy={760} rx={150} ry={70} fill="#ff9a4d" opacity={0.16} />
      <g stroke={OUTLINE} strokeWidth={4} strokeLinejoin="round">
        <ellipse cx={1120} cy={760} rx={56} ry={16} fill="#8a5a30" />
        <rect x={1078} y={748} width={84} height={14} rx={6} fill="#9c6b3f" transform="rotate(-12 1120 755)" />
      </g>
      <g transform={`translate(1120 742) scale(${flicker.toFixed(3)})`} style={{ transformOrigin: "center bottom" }}>
        <path d="M0,4 C-22,-18 -14,-44 0,-58 C14,-44 22,-18 0,4 Z" fill="#ff8a3c" />
        <path d="M0,-2 C-12,-16 -8,-34 0,-44 C8,-34 12,-16 0,-2 Z" fill="#ffd24d" />
      </g>
    </StudioBase>
  );
};
