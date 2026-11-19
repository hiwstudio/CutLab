/**
 * Caption component (architecture §12).
 *
 * The caption mirrors the scene's voiceover line (see Scene.tsx) and now tracks the
 * narration word-by-word: each word eases in and the currently-spoken word pops with a
 * brand-accent highlight, so the caption feels synced to the audio instead of sitting
 * static for the whole scene. The full line stays on screen the entire time (dimmed
 * ahead of the cursor) so it's still effortless to read.
 *
 * Timing comes from `estimateWordTimings` (syllable + punctuation weighted) unless a
 * real forced-alignment `wordTimings` array is supplied, which overrides the estimate.
 *
 * Rendered inside a <Sequence>, so useCurrentFrame() is scene-relative.
 */
import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { Caption as CaptionData } from "../manifest/schema";
import { captionCss, resolveCaptionStyle } from "./captionStyles";
import { estimateWordTimings, type WordTiming } from "./wordTiming";
import { BRAND_FONT } from "../../remotion/fonts";

const ACCENT = "#ffe14d"; // brand yellow (matches hiw_emphasis)

export const Caption: React.FC<{
  caption: CaptionData;
  /** Scene length in frames; drives word timing. Falls back to ~3s when absent. */
  durationInFrames?: number;
  /** Optional forced-alignment timings; overrides the estimate when provided. */
  wordTimings?: WordTiming[];
}> = ({ caption, durationInFrames, wordTimings }) => {
  const frame = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();

  const text = (caption.text ?? "").trim();

  // Per-word timing across the scene so the caption follows the voiceover.
  // Memoized (and computed before the empty-text early return, so hook order is
  // unconditional): the timings depend on the text/span, not the current frame.
  const span = durationInFrames ?? Math.max(1, Math.round(fps * 3));
  const words = React.useMemo(
    () =>
      wordTimings && wordTimings.length > 0
        ? wordTimings
        : estimateWordTimings(text, 0, span, fps),
    [wordTimings, text, span, fps]
  );

  if (text.length === 0) return null;

  const def = resolveCaptionStyle(caption.style);
  const css = captionCss(def, width, height);
  const fontSize = (css.fontSize as number) ?? Math.round(0.055 * Math.min(width, height));

  // The base caption color may already be yellow (hiw_emphasis); in that case the active
  // word pops to white instead, so the highlight always reads against the line.
  const baseColor = (css.color as string) ?? "#ffffff";
  const baseIsAccent = baseColor.toLowerCase().startsWith("#ffe");
  const activeColor = baseIsAccent ? "#ffffff" : ACCENT;

  // Ease the whole block in/out at the scene edges so cuts aren't abrupt.
  const blockOpacity = interpolate(
    frame,
    [0, 6, Math.max(7, span - 5), span],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const position = caption.position ?? "bottom";
  const justify = position === "top" ? "flex-start" : position === "center" ? "center" : "flex-end";

  return (
    <AbsoluteFill
      style={{
        justifyContent: justify,
        alignItems: "center",
        padding: `${Math.round(height * 0.06)}px ${Math.round(width * 0.05)}px`,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          ...css,
          fontFamily: `'${BRAND_FONT}', 'Segoe UI', Arial, sans-serif`,
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          alignItems: "baseline",
          rowGap: `${Math.round(fontSize * 0.08)}px`,
          columnGap: `${Math.round(fontSize * 0.28)}px`,
          opacity: blockOpacity,
        }}
      >
        {words.map((w, i) => {
          // Reveal each word with a small lead so it lands with the syllable, not after.
          const intro = Math.max(2, Math.round(fps * 0.1));
          const t = interpolate(frame, [w.startF - 2, w.startF + intro], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const active = frame >= w.startF && frame < w.endF;

          // Upcoming words sit dimmed so the eye tracks the cursor; spoken words go bright.
          const opacity = 0.4 + 0.6 * t;
          const scale = active ? 1.07 : 0.985 + 0.015 * t;
          const lift = active ? -Math.round(fontSize * 0.05) : 0;
          const color = active || w.emphasis ? activeColor : baseColor;

          return (
            <span
              key={i}
              style={{
                display: "inline-block",
                color,
                opacity,
                transform: `translateY(${lift}px) scale(${scale.toFixed(3)})`,
                transformOrigin: "center bottom",
              }}
            >
              {w.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
