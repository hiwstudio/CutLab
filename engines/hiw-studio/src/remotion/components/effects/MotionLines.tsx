/** Motion lines effect (architecture §11). Short impact arcs around centre. */
import React from "react";
import { AbsoluteFill } from "remotion";
import type { EffectProps } from "../../../engine/assets/assetTypes";
import { HIW_PALETTE as C } from "../../theme";

export const MotionLines: React.FC<EffectProps> = ({ frame, fps }) => {
  const grow = (Math.sin((frame / fps) * Math.PI * 2 * 1.5) * 0.5 + 0.5) * 14;
  const arcs = Array.from({ length: 8 });
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <svg viewBox="0 0 1600 900" width="100%" height="100%" preserveAspectRatio="xMidYMid slice">
        <g stroke={C.outline} strokeWidth={6} strokeLinecap="round" fill="none" opacity={0.55}>
          {arcs.map((_, i) => {
            const a = (Math.PI * 2 * i) / arcs.length;
            const r1 = 120 + grow;
            const r2 = 170 + grow;
            const cx = 800;
            const cy = 360;
            return (
              <line
                key={i}
                x1={cx + Math.cos(a) * r1}
                y1={cy + Math.sin(a) * r1}
                x2={cx + Math.cos(a) * r2}
                y2={cy + Math.sin(a) * r2}
              />
            );
          })}
        </g>
      </svg>
    </AbsoluteFill>
  );
};
