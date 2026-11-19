/**
 * Puppet face (V2 — Pillar 1). Blink-aware, shaded eyes with highlights, expressive
 * brows, and open/closed mouths. Drawn in an SVG coordinate system whose origin (0,0)
 * is the centre of the head, with head radius R. Shared by Human and AncientBrain.
 */
import React from "react";
import { HIW_PALETTE } from "../../theme";
import { blinkAmount, gaze } from "./rig";

type Expr =
  | "neutral"
  | "happy"
  | "anxious"
  | "shocked"
  | "confused"
  | "angry"
  | "tired";

function normalizeExpression(expression: string | undefined): Expr {
  switch (expression) {
    case "worried":
      return "anxious";
    case "excited":
      return "happy";
    case "happy":
    case "anxious":
    case "shocked":
    case "confused":
    case "angry":
    case "tired":
    case "neutral":
      return expression;
    default:
      return "neutral";
  }
}

export const PuppetFace: React.FC<{
  expression?: string;
  /** Head radius in the parent SVG's units. */
  r: number;
  frame?: number;
  fps?: number;
  eyeColor?: string;
  /** 0..1 talking mouth open amount; overrides the expression mouth when > 0. */
  mouthOpen?: number;
}> = ({ expression, r, frame = 0, fps = 30, eyeColor = HIW_PALETTE.outline, mouthOpen = 0 }) => {
  const e = normalizeExpression(expression);
  const stroke = HIW_PALETTE.outline;
  const sw = r * 0.09;
  const eyeX = r * 0.4;
  const eyeY = -r * 0.08;
  const browY = -r * 0.4;
  const mY = r * 0.34;
  const hw = r * 0.3;

  const blink = blinkAmount(frame, fps);
  const bigEyes = e === "shocked";
  const baseOpen = e === "tired" ? 0.5 : 1;
  const open = Math.max(0.07, baseOpen * (1 - 0.92 * blink));
  const eyeR = (bigEyes ? 0.17 : 0.13) * r;
  // Wandering gaze: shift the dark eye + catchlight a touch within the eye area.
  const g = gaze(frame, fps);
  const gx = g.x * eyeR;
  const gy = g.y * eyeR;

  const Eye: React.FC<{ x: number }> = ({ x }) => (
    <g transform={`translate(${x} ${eyeY})`}>
      <g transform={`scale(1 ${open.toFixed(3)})`}>
        <ellipse cx={gx} cy={gy} rx={eyeR} ry={eyeR * 1.18} fill={eyeColor} />
        <circle cx={gx - eyeR * 0.32} cy={gy - eyeR * 0.45} r={eyeR * 0.34} fill={HIW_PALETTE.white} />
      </g>
      {blink > 0.55 ? (
        <line x1={-eyeR * 1.1} y1={0} x2={eyeR * 1.1} y2={0} stroke={stroke} strokeWidth={sw * 0.8} strokeLinecap="round" />
      ) : null}
    </g>
  );

  const brow = (x: number, innerDown: number, raise: number) => {
    const inner = x > 0 ? x - r * 0.18 : x + r * 0.18;
    const outer = x > 0 ? x + r * 0.18 : x - r * 0.18;
    const y = browY - raise;
    return (
      <line
        x1={inner}
        y1={y + innerDown}
        x2={outer}
        y2={y - innerDown}
        stroke={stroke}
        strokeWidth={sw}
        strokeLinecap="round"
      />
    );
  };

  const brows = () => {
    switch (e) {
      case "angry":
        return (<>{brow(-eyeX, r * 0.12, 0)}{brow(eyeX, r * 0.12, 0)}</>);
      case "anxious":
        return (<>{brow(-eyeX, -r * 0.1, r * 0.06)}{brow(eyeX, -r * 0.1, r * 0.06)}</>);
      case "confused":
        return (<>{brow(-eyeX, 0, r * 0.14)}{brow(eyeX, r * 0.06, 0)}</>);
      case "happy":
      case "shocked":
        return (<>{brow(-eyeX, 0, r * 0.12)}{brow(eyeX, 0, r * 0.12)}</>);
      case "tired":
        return (<>{brow(-eyeX, -r * 0.05, -r * 0.05)}{brow(eyeX, -r * 0.05, -r * 0.05)}</>);
      default:
        return null;
    }
  };

  const mouth = () => {
    const common = { fill: "none", stroke, strokeWidth: sw, strokeLinecap: "round" as const };
    // Talking flap overrides the expression mouth.
    if (mouthOpen > 0.12) {
      return (
        <ellipse
          cx={0}
          cy={mY + r * 0.04}
          rx={r * 0.18}
          ry={r * (0.05 + 0.2 * Math.min(1, mouthOpen))}
          fill={HIW_PALETTE.mouthFill}
          stroke={stroke}
          strokeWidth={sw}
        />
      );
    }
    switch (e) {
      case "happy":
        return (
          <path
            d={`M ${-hw} ${mY - r * 0.04} Q 0 ${mY + r * 0.34} ${hw} ${mY - r * 0.04} Q 0 ${mY + r * 0.16} ${-hw} ${mY - r * 0.04} Z`}
            fill={HIW_PALETTE.mouthFill}
            stroke={stroke}
            strokeWidth={sw}
            strokeLinejoin="round"
          />
        );
      case "angry":
        return <path d={`M ${-hw} ${mY + r * 0.16} Q 0 ${mY - r * 0.14} ${hw} ${mY + r * 0.16}`} {...common} />;
      case "shocked":
        return (
          <ellipse cx={0} cy={mY + r * 0.04} rx={r * 0.17} ry={r * 0.22} fill={HIW_PALETTE.mouthFill} stroke={stroke} strokeWidth={sw} />
        );
      case "anxious":
        return <path d={`M ${-hw * 0.7} ${mY + r * 0.06} Q 0 ${mY - r * 0.06} ${hw * 0.7} ${mY + r * 0.06}`} {...common} />;
      case "confused":
        return <path d={`M ${-hw} ${mY} Q ${-hw / 2} ${mY - r * 0.12} 0 ${mY} Q ${hw / 2} ${mY + r * 0.12} ${hw} ${mY}`} {...common} />;
      case "tired":
        return <line x1={-hw * 0.7} y1={mY + r * 0.05} x2={hw * 0.7} y2={mY + r * 0.05} stroke={stroke} strokeWidth={sw} strokeLinecap="round" />;
      default:
        return <line x1={-hw * 0.7} y1={mY} x2={hw * 0.7} y2={mY} stroke={stroke} strokeWidth={sw} strokeLinecap="round" />;
    }
  };

  return (
    <g>
      <Eye x={-eyeX} />
      <Eye x={eyeX} />
      {brows()}
      {mouth()}
    </g>
  );
};
