/**
 * Office background (architecture §9).
 *
 * V2.1: a clean, furnished workplace on the studio base — a window with a soft city
 * skyline, a desk with a monitor, a chair, a houseplant, a wall shelf and a clock.
 * Light and tidy, with the centre kept clear for the character.
 */
import React from "react";
import type { BackgroundProps } from "../../../engine/assets/assetTypes";
import { StudioBase, type StudioTint } from "./StudioBase";

const OFFICE_TINT: StudioTint = {
  top: "#f5f8fc",
  wall: "#eaf0f7",
  floor: "#dde4ee",
  seam: "#cbd4e0",
};

const OUTLINE = "#1f2430";

export const OfficeBackground: React.FC<BackgroundProps> = () => (
  <StudioBase tint={OFFICE_TINT}>
    {/* Window with a soft skyline (left) */}
    <g stroke="#b9c5d4" strokeWidth={10} strokeLinejoin="round">
      <rect x={120} y={120} width={420} height={300} rx={6} fill="#d4ecff" />
    </g>
    <g fill="#b6cfe4">
      <rect x={160} y={250} width={64} height={170} />
      <rect x={240} y={200} width={64} height={220} />
      <rect x={320} y={280} width={64} height={140} />
      <rect x={400} y={220} width={64} height={200} />
      <rect x={480} y={260} width={50} height={160} />
    </g>
    <g stroke="#b9c5d4" strokeWidth={8}>
      <line x1={330} y1={120} x2={330} y2={420} />
      <line x1={120} y1={270} x2={540} y2={270} />
    </g>

    {/* Wall clock */}
    <circle cx={800} cy={210} r={42} fill="#ffffff" stroke={OUTLINE} strokeWidth={5} />
    <g stroke={OUTLINE} strokeWidth={4} strokeLinecap="round">
      <line x1={800} y1={210} x2={800} y2={184} />
      <line x1={800} y1={210} x2={820} y2={222} />
    </g>

    {/* Wall shelf with books (right) */}
    <rect x={1140} y={250} width={200} height={14} rx={4} fill="#9aa7b5" stroke={OUTLINE} strokeWidth={3} />
    <g stroke={OUTLINE} strokeWidth={3}>
      <rect x={1152} y={206} width={16} height={44} fill="#5b8def" />
      <rect x={1172} y={200} width={16} height={50} fill="#e0533a" />
      <rect x={1192} y={212} width={16} height={38} fill="#37c871" />
      <rect x={1212} y={204} width={16} height={46} fill="#ffd24d" />
    </g>

    {/* Desk with monitor (right) */}
    <g stroke={OUTLINE} strokeWidth={5} strokeLinejoin="round">
      <rect x={1120} y={604} width={440} height={22} rx={6} fill="#c79a63" />
      <rect x={1140} y={626} width={16} height={120} fill="#9c7a4e" />
      <rect x={1524} y={626} width={16} height={120} fill="#9c7a4e" />
      <rect x={1300} y={500} width={180} height={110} rx={8} fill="#2c3440" />
      <rect x={1314} y={514} width={152} height={82} rx={4} fill="#5b8def" />
      <rect x={1378} y={610} width={24} height={16} fill="#2c3440" />
    </g>

    {/* Houseplant (left of desk) */}
    <g stroke={OUTLINE} strokeWidth={5} strokeLinejoin="round">
      <path d="M980,576 L1016,576 L1008,650 L988,650 Z" fill="#5b8def" />
      <path d="M998,576 C982,524 988,496 998,480 C1010,496 1014,524 998,576 Z" fill="#5fa85f" />
      <path d="M998,576 C1024,540 1048,536 1062,550 C1048,576 1020,582 998,576 Z" fill="#6fb86f" />
    </g>
  </StudioBase>
);
