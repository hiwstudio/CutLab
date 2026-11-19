/**
 * Living room background (architecture §9).
 *
 * V2.1: a cozy, furnished home interior on the studio base — a window with a view, a
 * couch, a coffee table, a rug, a houseplant, framed wall art and a floor lamp. Warm
 * and lived-in, but soft and clean, with the centre rug kept clear for the characters.
 */
import React from "react";
import type { BackgroundProps } from "../../../engine/assets/assetTypes";
import { StudioBase, type StudioTint } from "./StudioBase";

const LIVING_ROOM_TINT: StudioTint = {
  top: "#faf3e7",
  wall: "#f3ead9",
  floor: "#e3cba6",
  seam: "#caa777",
};

const OUTLINE = "#1f2430";

export const LivingRoomBackground: React.FC<BackgroundProps> = () => (
  <StudioBase tint={LIVING_ROOM_TINT}>
    {/* Window with a sky + tree view (left) */}
    <g stroke="#b79a6e" strokeWidth={10} strokeLinejoin="round">
      <rect x={120} y={120} width={300} height={240} rx={6} fill="#cdeaff" />
    </g>
    <circle cx={360} cy={185} r={34} fill="#ffe49a" />
    <ellipse cx={205} cy={300} rx={70} ry={44} fill="#8fc35a" />
    <g stroke="#b79a6e" strokeWidth={8}>
      <line x1={270} y1={120} x2={270} y2={360} />
      <line x1={120} y1={240} x2={420} y2={240} />
    </g>

    {/* Framed wall art (right) */}
    <g stroke="#b79a6e" strokeWidth={10} strokeLinejoin="round">
      <rect x={1140} y={150} width={170} height={130} rx={6} fill="#ffd98a" />
    </g>
    <path d="M1150,270 L1200,210 L1240,250 L1280,200 L1300,270 Z" fill="#e08a5b" opacity={0.8} />

    {/* Shelf with books (right, above couch) */}
    <rect x={1360} y={300} width={170} height={14} rx={4} fill="#b79a6e" stroke={OUTLINE} strokeWidth={3} />
    <g stroke={OUTLINE} strokeWidth={3}>
      <rect x={1372} y={258} width={16} height={42} fill="#5b8def" />
      <rect x={1392} y={250} width={16} height={50} fill="#e0533a" />
      <rect x={1412} y={262} width={16} height={38} fill="#37c871" />
      <rect x={1432} y={256} width={16} height={44} fill="#ffd24d" />
    </g>

    {/* Rug under center stage */}
    <ellipse cx={800} cy={772} rx={420} ry={86} fill="#e7b9a3" opacity={0.8} />
    <ellipse cx={800} cy={772} rx={360} ry={66} fill="none" stroke="#d59a80" strokeWidth={6} opacity={0.7} />

    {/* Couch (right) */}
    <g stroke="#7a8aa6" strokeWidth={6} strokeLinejoin="round">
      <rect x={1120} y={560} width={420} height={140} rx={26} fill="#8aa1c4" />
      <rect x={1120} y={506} width={420} height={84} rx={22} fill="#9bb0cf" />
      <rect x={1104} y={528} width={56} height={172} rx={20} fill="#8aa1c4" />
      <rect x={1500} y={528} width={56} height={172} rx={20} fill="#8aa1c4" />
    </g>

    {/* Coffee table (center-right, low so it doesn't crowd the stage) */}
    <g stroke="#9c7a4e" strokeWidth={5} strokeLinejoin="round">
      <rect x={1010} y={712} width={190} height={20} rx={6} fill="#c79a63" />
      <rect x={1024} y={732} width={14} height={40} fill="#9c7a4e" />
      <rect x={1172} y={732} width={14} height={40} fill="#9c7a4e" />
    </g>

    {/* Houseplant (left) */}
    <g stroke={OUTLINE} strokeWidth={5} strokeLinejoin="round">
      <path d="M300,560 L336,560 L328,640 L308,640 Z" fill="#d98a5b" />
      <path d="M318,560 C300,500 306,470 318,452 C330,470 336,500 318,560 Z" fill="#5fa85f" />
      <path d="M318,560 C346,520 372,516 388,532 C372,560 342,566 318,560 Z" fill="#6fb86f" />
      <path d="M318,560 C290,520 264,516 248,532 C264,560 294,566 318,560 Z" fill="#69b069" />
    </g>

    {/* Floor lamp (far left) */}
    <g stroke="#9c8763" strokeWidth={7}>
      <line x1={70} y1={648} x2={70} y2={460} />
    </g>
    <path d="M30,460 L110,460 L92,400 L48,400 Z" fill="#ffe9a8" stroke={OUTLINE} strokeWidth={4} strokeLinejoin="round" />
  </StudioBase>
);
