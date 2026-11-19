/**
 * Street background (architecture §9).
 *
 * V2.1: a lively but clean city street on the studio base — soft pastel buildings with
 * windows and doors along the horizon, a road with lane dashes behind a curb, and a
 * sidewalk out front where the characters stand, dressed with a tree, a streetlamp and
 * a small sign. Bright and uncluttered, not the old dark version.
 */
import React from "react";
import type { BackgroundProps } from "../../../engine/assets/assetTypes";
import { StudioBase, type StudioTint } from "./StudioBase";

const STREET_TINT: StudioTint = {
  top: "#eaf3fb",
  wall: "#dfecf8",
  floor: "#d5dae1",
  seam: "#c3c9d2",
};

const OUTLINE = "#1f2430";

const Building: React.FC<{ x: number; w: number; h: number; fill: string }> = ({ x, w, h, fill }) => {
  const top = 648 - h;
  const cols = Math.max(2, Math.floor(w / 56));
  const rows = Math.max(2, Math.floor(h / 90));
  const gx = w / cols;
  const gy = (h - 60) / rows;
  return (
    <g stroke={OUTLINE} strokeWidth={4} strokeLinejoin="round">
      <rect x={x} y={top} width={w} height={h} rx={6} fill={fill} />
      <g fill="#eaf4ff" stroke="#b9c7d6" strokeWidth={3}>
        {Array.from({ length: rows }).flatMap((_, r) =>
          Array.from({ length: cols }).map((__, c) => (
            <rect key={`${r}-${c}`} x={x + 12 + c * gx} y={top + 22 + r * gy} width={gx - 24} height={gy - 26} rx={3} />
          ))
        )}
      </g>
    </g>
  );
};

export const StreetBackground: React.FC<BackgroundProps> = () => (
  <StudioBase tint={STREET_TINT}>
    {/* A soft cloud */}
    <ellipse cx={520} cy={150} rx={110} ry={38} fill="#ffffff" opacity={0.8} />

    {/* Buildings along the horizon */}
    <Building x={70} w={260} h={430} fill="#f3cdb0" />
    <Building x={350} w={210} h={360} fill="#bcd6ea" />
    <Building x={1060} w={230} h={400} fill="#cfe3cf" />
    <Building x={1310} w={230} h={460} fill="#e6c6d6" />

    {/* Road behind the curb, with lane dashes */}
    <rect x={0} y={648} width={1600} height={58} fill="#aeb6bf" />
    <g fill="#ffe14d">
      {Array.from({ length: 10 }).map((_, i) => (
        <rect key={i} x={40 + i * 165} y={672} width={80} height={10} rx={5} />
      ))}
    </g>
    {/* Curb */}
    <rect x={0} y={704} width={1600} height={8} fill="#b6bcc4" />

    {/* Streetlamp (right) */}
    <g stroke={OUTLINE} strokeWidth={5} strokeLinecap="round">
      <line x1={1180} y1={648} x2={1180} y2={360} />
      <path d="M1180,360 q0,-26 40,-26" fill="none" />
    </g>
    <ellipse cx={1224} cy={340} rx={16} ry={20} fill="#ffe49a" stroke={OUTLINE} strokeWidth={4} />

    {/* Tree (left, on the sidewalk edge) */}
    <g transform="translate(470 706)">
      <rect x={-16} y={-130} width={32} height={140} rx={10} fill="#b07a45" stroke={OUTLINE} strokeWidth={5} />
      <g stroke={OUTLINE} strokeWidth={5}>
        <circle cx={0} cy={-180} r={76} fill="#8fc35a" />
        <circle cx={-50} cy={-150} r={50} fill="#7cb84d" />
        <circle cx={52} cy={-150} r={50} fill="#9ccc66" />
      </g>
    </g>

    {/* Small sign (left-mid) */}
    <g stroke={OUTLINE} strokeWidth={4} strokeLinejoin="round">
      <rect x={250} y={596} width={92} height={58} rx={8} fill="#5b8def" />
      <rect x={288} y={652} width={14} height={54} fill="#9aa7b5" />
    </g>
  </StudioBase>
);
