/**
 * Caption styles (architecture §12).
 *
 * Plain style data keyed by caption-style id. Used by Caption.tsx. The visual goal
 * is "bold white text, dark outline/shadow, bottom-center, mobile-readable".
 */
import type { CSSProperties } from "react";

export interface CaptionStyleDef {
  /** Font size as a fraction of composition height (so it scales with resolution). */
  fontSizeFactor: number;
  color: string;
  fontWeight: number;
  /** Thick dark outline via layered text-shadow for readability over any background. */
  textShadow: string;
  fontFamily: string;
  letterSpacing: string;
  /** Max caption box width as a fraction of composition width. */
  maxWidthFactor: number;
  /** Optional semi-transparent backing plate. */
  background?: string;
  padding?: string;
  borderRadius?: number;
  uppercase?: boolean;
}

const OUTLINE = (px: number, color = "#0b0b14") =>
  [
    `-${px}px -${px}px 0 ${color}`,
    `${px}px -${px}px 0 ${color}`,
    `-${px}px ${px}px 0 ${color}`,
    `${px}px ${px}px 0 ${color}`,
    `0 ${px * 2}px ${px * 3}px rgba(0,0,0,0.45)`,
  ].join(", ");

export const CAPTION_STYLE_DEFS: Record<string, CaptionStyleDef> = {
  hiw_default: {
    fontSizeFactor: 0.055,
    color: "#ffffff",
    fontWeight: 800,
    textShadow: OUTLINE(3),
    fontFamily:
      "'Segoe UI', 'Helvetica Neue', Arial, system-ui, sans-serif",
    letterSpacing: "0.3px",
    maxWidthFactor: 0.82,
  },
  hiw_emphasis: {
    fontSizeFactor: 0.07,
    color: "#ffe14d",
    fontWeight: 900,
    textShadow: OUTLINE(4),
    fontFamily:
      "'Segoe UI', 'Helvetica Neue', Arial, system-ui, sans-serif",
    letterSpacing: "0.5px",
    maxWidthFactor: 0.86,
    uppercase: true,
  },
  hiw_quiet: {
    fontSizeFactor: 0.042,
    color: "#e8e8f0",
    fontWeight: 600,
    textShadow: OUTLINE(2),
    fontFamily:
      "'Segoe UI', 'Helvetica Neue', Arial, system-ui, sans-serif",
    letterSpacing: "0.2px",
    maxWidthFactor: 0.7,
  },
};

export function resolveCaptionStyle(styleId: string | undefined): CaptionStyleDef {
  return (styleId && CAPTION_STYLE_DEFS[styleId]) || CAPTION_STYLE_DEFS.hiw_default;
}

/** Convert a style def + composition dimensions into concrete CSS. */
export function captionCss(
  def: CaptionStyleDef,
  width: number,
  height: number
): CSSProperties {
  // Size off the shorter dimension so captions read well in both landscape (height
  // is the short side) and vertical/Shorts (width is the short side).
  const shortSide = Math.min(width, height);
  return {
    fontSize: Math.round(def.fontSizeFactor * shortSide),
    color: def.color,
    fontWeight: def.fontWeight,
    textShadow: def.textShadow,
    fontFamily: def.fontFamily,
    letterSpacing: def.letterSpacing,
    maxWidth: Math.round(def.maxWidthFactor * width),
    textAlign: "center",
    lineHeight: 1.15,
    textTransform: def.uppercase ? "uppercase" : "none",
    background: def.background,
    padding: def.padding,
    borderRadius: def.borderRadius,
    margin: 0,
  };
}
