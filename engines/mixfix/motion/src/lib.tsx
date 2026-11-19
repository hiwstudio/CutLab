import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";

// One palette for every insert so the graphics read as a set, not as five
// unrelated cards. Gold is lifted from the Golden Record plate that closes the
// film; cyan is the telemetry colour and is used ONLY for signal.
export const C = {
  bg: "#0a1119",
  gold: "#e8b874",
  cyan: "#7fd4e8",
  dim: "#3d4757",
  text: "#dfe6f0",
};

export const MONO = "'Consolas','SF Mono','DejaVu Sans Mono',monospace";
export const SANS = "'Inter','Segoe UI',system-ui,sans-serif";

/** Current time in ms — every animation is keyed off the Timing Map in ms,
 *  never off frame counts, so the graphics stay locked to the narration. */
export const useMs = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (frame / fps) * 1000;
};

/** Deterministic PRNG. Remotion compositions must not use Math.random(): the
 *  render is chunked and a random starfield would flicker between chunks. */
const rand = (seed: number) => {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
};

/** Slow, no overshoot. A spring's bounce reads as UI motion, not film. */
export const ease = (ms: number, a: number, b: number, from = 0, to = 1) =>
  interpolate(ms, [a, b], [from, to], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: (t) => 1 - Math.pow(1 - t, 3),
  });

export const Starfield: React.FC<{ seed?: number; count?: number }> = ({
  seed = 7,
  count = 140,
}) => {
  const ms = useMs();
  const r = rand(seed);
  const stars = Array.from({ length: count }, () => ({
    x: r() * 1920,
    y: r() * 1080,
    s: 0.4 + r() * 1.4,
    o: 0.15 + r() * 0.5,
    ph: r() * 6.28,
  }));
  return (
    <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
      {stars.map((st, i) => (
        <circle
          key={i}
          cx={st.x}
          cy={st.y}
          r={st.s}
          fill="#cfe2ff"
          opacity={st.o * (0.75 + 0.25 * Math.sin(ms / 900 + st.ph))}
        />
      ))}
    </svg>
  );
};

export const Stage: React.FC<{ children: React.ReactNode; seed?: number }> = ({
  children,
  seed,
}) => {
  const ms = useMs();
  const { durationInFrames, fps } = useVideoConfig();
  const total = (durationInFrames / fps) * 1000;
  // Every insert fades from and to black so it cuts cleanly against footage.
  const fade =
    Math.min(ease(ms, 0, 320), 1 - ease(ms, total - 380, total)) ;
  return (
    <div style={{ width: 1920, height: 1080, background: C.bg, position: "relative", opacity: fade }}>
      {/* A soft nebular wash. Without it these inserts are >98% of pixels below
          0.10 luminance, which the render-QA black-frame detector flags — and
          it is right to: an 11-second near-black stretch reads as dead air on a
          phone, not as style. This lifts the field without washing it out. */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(ellipse 70% 60% at 42% 45%, rgba(58,86,130,0.42) 0%, rgba(30,46,74,0.26) 42%, rgba(10,16,26,0) 78%)",
        }}
      />
      <Starfield seed={seed} count={260} />
      {children}
      {/* subtle vignette keeps the eye centred at pane width */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(ellipse at center, rgba(0,0,0,0) 58%, rgba(0,0,0,0.38) 100%)",
        }}
      />
    </div>
  );
};
