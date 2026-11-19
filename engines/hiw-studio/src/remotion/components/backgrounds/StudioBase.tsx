/**
 * Shared studio backdrop (V2.1 visual upgrade).
 *
 * A clean, plain, off-white "studio" stage that every background builds on:
 *  - a soft vertical wall gradient (a touch lighter up top)
 *  - a grounded floor band with a gentle floor glow and a soft wall/floor seam
 *  - a faint vignette to keep focus center-stage
 *
 * Scene-specific detail is passed as `children` (SVG, viewBox 0 0 1600 900) and should
 * stay pale / low-contrast so the characters always read as the subject. The floor
 * seam sits at y≈648 (~0.72 of frame height); characters' feet land around y≈810, so
 * they stand naturally on the floor.
 */
import React from "react";
import { AbsoluteFill } from "remotion";
import { HIW_PALETTE as C } from "../../theme";
import { safeId } from "../characters/rig";

export interface StudioTint {
  /** Wall colour near the top of frame. */
  top?: string;
  /** Main wall colour. */
  wall?: string;
  /** Floor band colour. */
  floor?: string;
  /** Wall/floor seam shadow colour. */
  seam?: string;
}

export const StudioBase: React.FC<{ tint?: StudioTint; children?: React.ReactNode }> = ({
  tint,
  children,
}) => {
  const top = tint?.top ?? C.studioTop;
  const wall = tint?.wall ?? C.studio;
  const floor = tint?.floor ?? C.studioFloor;
  const seam = tint?.seam ?? C.studioSeam;
  const id = safeId(React.useId());

  return (
    <AbsoluteFill style={{ backgroundColor: wall }}>
      <svg
        viewBox="0 0 1600 900"
        width="100%"
        height="100%"
        preserveAspectRatio="xMidYMid slice"
        style={{ display: "block" }}
      >
        <defs>
          <linearGradient id={`wall-${id}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={top} />
            <stop offset="62%" stopColor={wall} />
            <stop offset="100%" stopColor={wall} />
          </linearGradient>
          {/* Studio softbox: a broad warm key light washing the upper-centre wall. */}
          <radialGradient id={`key-${id}`} cx="0.5" cy="0.22" r="0.75">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.5" />
            <stop offset="55%" stopColor="#fff7ea" stopOpacity="0.16" />
            <stop offset="100%" stopColor="#fff7ea" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={`floorglow-${id}`} cx="0.5" cy="1.05" r="0.7">
            <stop offset="0%" stopColor={floor} />
            <stop offset="100%" stopColor={floor} stopOpacity="0" />
          </radialGradient>
          {/* Center-stage floor spotlight pool — grounds + frames the characters. */}
          <radialGradient id={`spot-${id}`} cx="0.5" cy="0.5" r="0.5">
            <stop offset="0%" stopColor="#fffaf0" stopOpacity="0.55" />
            <stop offset="60%" stopColor="#fffaf0" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#fffaf0" stopOpacity="0" />
          </radialGradient>
          {/* Warm glow along the wall/floor seam (horizon light). */}
          <linearGradient id={`seamglow-${id}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fff2dc" stopOpacity="0" />
            <stop offset="100%" stopColor="#fff2dc" stopOpacity="0.5" />
          </linearGradient>
          <radialGradient id={`vign-${id}`} cx="0.5" cy="0.4" r="0.9">
            <stop offset="48%" stopColor="#201a12" stopOpacity="0" />
            <stop offset="100%" stopColor="#201a12" stopOpacity="0.12" />
          </radialGradient>
        </defs>

        {/* Wall + studio key light */}
        <rect x="0" y="0" width="1600" height="900" fill={`url(#wall-${id})`} />
        <rect x="0" y="0" width="1600" height="720" fill={`url(#key-${id})`} />

        {/* Floor band + soft wall/floor seam + warm horizon glow */}
        <rect x="0" y="648" width="1600" height="252" fill={floor} />
        <rect x="0" y="600" width="1600" height="60" fill={`url(#seamglow-${id})`} />
        <rect x="0" y="640" width="1600" height="14" fill={seam} opacity="0.55" />
        <ellipse cx="800" cy="930" rx="1000" ry="240" fill={`url(#floorglow-${id})`} />

        {/* Center-stage floor spotlight (under the scene dressing + characters) */}
        <ellipse cx="800" cy="772" rx="560" ry="150" fill={`url(#spot-${id})`} />

        {/* Scene-specific pale hints */}
        {children}

        {/* Vignette to focus center stage */}
        <rect x="0" y="0" width="1600" height="900" fill={`url(#vign-${id})`} />
      </svg>
    </AbsoluteFill>
  );
};
