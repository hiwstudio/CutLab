/**
 * Face-detection reticle effect (architecture §11).
 *
 * The visual thesis of "your brain is a mind-detector": a camera-style reticle snaps
 * onto a centered subject, sweeps a scan line ("SCANNING…", yellow), then locks green
 * with a "MIND DETECTED" label. Reusable for any anthropomorphism / agency-detection /
 * "your brain labels X as a person" beat.
 *
 * The subject should be centered in the scene so the reticle frames it. `intensity`
 * (0..1) nudges how fast the lock happens (higher = snappier).
 */
import React from "react";
import { AbsoluteFill } from "remotion";
import type { EffectProps } from "../../../engine/assets/assetTypes";
import { HIW_PALETTE as C } from "../../theme";
import { BRAND_FONT } from "../../fonts";

const clamp01 = (n: number) => Math.max(0, Math.min(1, n));
/** easeOutBack for a satisfying little overshoot on the lock. */
const easeOutBack = (t: number) => {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
};

export const FaceDetect: React.FC<EffectProps> = ({ frame, fps, intensity = 0.5 }) => {
  const t = frame / fps;
  // Reticle box (frames a centered head + shoulders in a 1600x900 field).
  const L = 610;
  const R = 990;
  const T = 170;
  const B = 610;
  const cx = (L + R) / 2;

  // Timeline (seconds). A higher intensity locks a touch sooner.
  const lockAt = 0.62 - intensity * 0.18;
  const appear = clamp01(t / 0.22);
  const snap = clamp01((t - 0.05) / 0.32);
  const locked = t >= lockAt;

  // Corners start slightly expanded and snap inward.
  const expand = (1 - easeOutBack(snap)) * 46;
  // Gentle breathing once locked.
  const pulse = locked ? Math.sin((t - lockAt) * Math.PI * 2 * 0.8) * 3 : 0;

  const stroke = locked ? C.accentGreen : C.accentYellow;
  const armLen = 62;
  const sw = 8;

  // Scan line sweeps top→bottom while scanning.
  const scanP = clamp01((t - 0.12) / (lockAt - 0.12));
  const scanY = T + scanP * (B - T);

  // Label pop.
  const labelP = clamp01((t - lockAt) / 0.2);
  const labelScale = locked ? 0.6 + easeOutBack(labelP) * 0.4 : 1;

  // Corner bracket path (an L opening toward the box interior).
  const corner = (x: number, y: number, sx: number, sy: number) =>
    `M ${x + sx * armLen} ${y} L ${x} ${y} L ${x} ${y + sy * armLen}`;

  const oL = L - expand - pulse;
  const oR = R + expand + pulse;
  const oT = T - expand - pulse;
  const oB = B + expand + pulse;

  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity: appear }}>
      <svg viewBox="0 0 1600 900" width="100%" height="100%" preserveAspectRatio="xMidYMid slice">
        {/* faint targeting frame */}
        <rect
          x={oL}
          y={oT}
          width={oR - oL}
          height={oB - oT}
          fill="none"
          stroke={stroke}
          strokeOpacity={0.28}
          strokeWidth={2.5}
          strokeDasharray="10 12"
          rx={10}
        />

        {/* corner brackets */}
        <g stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" fill="none">
          <path d={corner(oL, oT, +1, +1)} />
          <path d={corner(oR, oT, -1, +1)} />
          <path d={corner(oL, oB, +1, -1)} />
          <path d={corner(oR, oB, -1, -1)} />
        </g>

        {/* scan line (only while scanning) */}
        {!locked && (
          <g>
            <line x1={oL} y1={scanY} x2={oR} y2={scanY} stroke={C.accentYellow} strokeWidth={4} strokeOpacity={0.9} />
            <line x1={oL} y1={scanY} x2={oR} y2={scanY} stroke={C.accentYellow} strokeWidth={16} strokeOpacity={0.15} />
          </g>
        )}

        {/* status label */}
        <g transform={`translate(${cx} ${B + 66}) scale(${labelScale})`}>
          <rect
            x={-190}
            y={-34}
            width={380}
            height={68}
            rx={34}
            fill={locked ? C.accentGreen : C.accentYellow}
            stroke={C.outline}
            strokeWidth={5}
          />
          {locked && (
            <g transform="translate(-150 0)">
              <circle r={17} fill={C.white} stroke={C.outline} strokeWidth={4} />
              <path d="M -8 0 L -2 7 L 9 -8" fill="none" stroke={C.accentGreen} strokeWidth={5} strokeLinecap="round" strokeLinejoin="round" />
            </g>
          )}
          <text
            x={locked ? 18 : 0}
            y={11}
            textAnchor="middle"
            fontFamily={`'${BRAND_FONT}', 'Segoe UI', sans-serif`}
            fontSize={34}
            fontWeight={800}
            letterSpacing={1.5}
            fill={locked ? C.white : C.outline}
          >
            {locked ? "MIND DETECTED" : "SCANNING…"}
          </text>
        </g>
      </svg>
    </AbsoluteFill>
  );
};
