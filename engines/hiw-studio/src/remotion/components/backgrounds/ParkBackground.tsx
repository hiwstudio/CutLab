/**
 * Park background (V2.1 — new outdoor scene).
 *
 * Clean, sunny park on the studio base: soft sky, sun and clouds up top, a green grass
 * floor with a path, framed by trees and bushes with a bench and a little park sign.
 * Detailed enough to feel alive, but the centre + path are kept clear so the
 * characters read as the subject.
 */
import React from "react";
import type { BackgroundProps } from "../../../engine/assets/assetTypes";
import { StudioBase, type StudioTint } from "./StudioBase";

const PARK_TINT: StudioTint = {
  top: "#eaf7ff",
  wall: "#dceffb",
  floor: "#cfe6a6",
  seam: "#b6d585",
};

const Tree: React.FC<{ x: number; scale?: number }> = ({ x, scale = 1 }) => (
  <g transform={`translate(${x} 648) scale(${scale})`}>
    {/* trunk */}
    <rect x={-18} y={-150} width={36} height={170} rx={12} fill="#b07a45" stroke="#1f2430" strokeWidth={5} />
    {/* foliage */}
    <g stroke="#1f2430" strokeWidth={5}>
      <circle cx={0} cy={-210} r={92} fill="#8fc35a" />
      <circle cx={-62} cy={-170} r={62} fill="#7cb84d" />
      <circle cx={64} cy={-172} r={64} fill="#9ccc66" />
    </g>
    <ellipse cx={-26} cy={-238} rx={36} ry={22} fill="#ffffff" opacity={0.14} />
  </g>
);

export const ParkBackground: React.FC<BackgroundProps> = () => (
  <StudioBase tint={PARK_TINT}>
    {/* Sun */}
    <circle cx={1340} cy={170} r={86} fill="#ffe49a" opacity={0.85} />
    <circle cx={1340} cy={170} r={62} fill="#ffd24d" opacity={0.9} />
    {/* Clouds */}
    <g fill="#ffffff" opacity={0.92}>
      <ellipse cx={360} cy={170} rx={120} ry={44} />
      <ellipse cx={300} cy={196} rx={80} ry={36} />
      <ellipse cx={900} cy={120} rx={96} ry={36} />
    </g>

    {/* Path running up the middle to the horizon */}
    <path d="M640,900 L740,648 L860,648 L960,900 Z" fill="#e7d9b4" />
    <path d="M640,900 L740,648 L860,648 L960,900 Z" fill="none" stroke="#d6c79a" strokeWidth={5} opacity={0.6} />

    {/* Distant bushes along the horizon */}
    <g stroke="#1f2430" strokeWidth={4}>
      <ellipse cx={140} cy={648} rx={120} ry={48} fill="#84bd54" />
      <ellipse cx={1480} cy={648} rx={140} ry={52} fill="#84bd54" />
      <ellipse cx={1120} cy={650} rx={90} ry={40} fill="#92c75f" />
    </g>

    {/* Framing trees (kept to the sides) */}
    <Tree x={210} scale={1.05} />
    <Tree x={1380} scale={0.9} />

    {/* Park bench (left) */}
    <g stroke="#1f2430" strokeWidth={4} strokeLinejoin="round">
      <rect x={300} y={600} width={210} height={20} rx={6} fill="#caa06a" />
      <rect x={300} y={636} width={210} height={20} rx={6} fill="#caa06a" />
      <rect x={316} y={620} width={16} height={56} fill="#9c7a4e" />
      <rect x={478} y={620} width={16} height={56} fill="#9c7a4e" />
    </g>

    {/* Little park sign (right) */}
    <g stroke="#1f2430" strokeWidth={4} strokeLinejoin="round">
      <rect x={1140} y={560} width={120} height={70} rx={10} fill="#7cb84d" />
      <rect x={1192} y={628} width={16} height={48} fill="#9c7a4e" />
    </g>
    <g fill="#ffffff" opacity={0.9}>
      <rect x={1158} y={582} width={84} height={9} rx={4} />
      <rect x={1158} y={600} width={64} height={9} rx={4} />
    </g>
  </StudioBase>
);
