/**
 * Diner background (story-first build for "Why Do You Say 'You Too' to the Waiter?").
 *
 * A warm, cozy restaurant interior on the shared studio base: a wide evening window,
 * two hanging pendant lamps with a soft glow, a padded booth bench along the back wall,
 * a small framed picture, and a faint checker-floor accent. Kept pale and low-contrast
 * (per StudioBase) so the characters always read as the subject. Reusable for any
 * dining / restaurant / café / small-talk scene.
 */
import React from "react";
import type { BackgroundProps } from "../../../engine/assets/assetTypes";
import { StudioBase, type StudioTint } from "./StudioBase";

const DINER_TINT: StudioTint = {
  top: "#fff4e6",
  wall: "#f6e7d2",
  floor: "#e7d3b6",
  seam: "#d8c2a2",
};

const OUTLINE = "#1f2430";

const Pendant: React.FC<{ x: number }> = ({ x }) => (
  <g>
    {/* warm pool of light */}
    <ellipse cx={x} cy={300} rx={120} ry={70} fill="#ffdf9e" opacity={0.35} />
    <g stroke={OUTLINE} strokeWidth={5} strokeLinejoin="round" strokeLinecap="round">
      <line x1={x} y1={0} x2={x} y2={196} />
      <path d={`M${x - 46},250 Q${x},196 ${x + 46},250 Z`} fill="#e7b85c" />
    </g>
    <circle cx={x} cy={258} r={11} fill="#fff0c4" stroke={OUTLINE} strokeWidth={3} />
  </g>
);

export const DinerBackground: React.FC<BackgroundProps> = () => (
  <StudioBase tint={DINER_TINT}>
    {/* Wide evening window on the back wall */}
    <g stroke={OUTLINE} strokeWidth={6} strokeLinejoin="round">
      <rect x={520} y={150} width={560} height={232} rx={10} fill="#f6d9a6" />
      {/* warm sky panes */}
      <g stroke="#caa86f" strokeWidth={3}>
        <rect x={534} y={164} width={170} height={204} rx={5} fill="#ffe7b0" />
        <rect x={715} y={164} width={170} height={204} rx={5} fill="#ffdf9e" />
        <rect x={896} y={164} width={170} height={204} rx={5} fill="#ffe7b0" />
      </g>
      {/* low sun glow */}
      <circle cx={800} cy={330} r={46} fill="#ffcf7a" opacity={0.85} />
    </g>

    {/* Framed picture (left wall) */}
    <g stroke={OUTLINE} strokeWidth={5} strokeLinejoin="round">
      <rect x={250} y={250} width={140} height={170} rx={8} fill="#e9c9a0" />
      <rect x={266} y={266} width={108} height={138} rx={4} fill="#cfe0d4" />
      <circle cx={320} cy={322} r={22} fill="#f3b98f" />
      <path d="M276,400 L312,356 L344,388 L364,366 L364,400 Z" fill="#9cc08f" />
    </g>

    {/* Pendant lamps */}
    <Pendant x={430} />
    <Pendant x={1170} />

    {/* Padded booth bench along the back wall (left of stage, center stays open) */}
    <g stroke={OUTLINE} strokeWidth={5} strokeLinejoin="round">
      {/* back cushion */}
      <rect x={90} y={470} width={520} height={92} rx={18} fill="#c98b86" />
      <g stroke="#a96f6b" strokeWidth={3}>
        <line x1={230} y1={478} x2={230} y2={554} />
        <line x1={350} y1={478} x2={350} y2={554} />
        <line x1={470} y1={478} x2={470} y2={554} />
      </g>
      {/* seat */}
      <rect x={84} y={556} width={532} height={92} rx={16} fill="#d49b95" />
    </g>

    {/* Faint diamond checker accent on the floor */}
    <g fill="#d9c4a2" opacity={0.55}>
      {Array.from({ length: 9 }).map((_, i) => {
        const cx = 120 + i * 170;
        return <path key={i} d={`M${cx},724 l40,22 l-40,22 l-40,-22 Z`} />;
      })}
    </g>
  </StudioBase>
);
