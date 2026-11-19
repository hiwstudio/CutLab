/**
 * HIW Studio visual theme (architecture §25 Style Guide).
 * Simple, funny, clean, bold outlines, flat colors.
 */
export const HIW_PALETTE = {
  outline: "#1f2430",
  white: "#ffffff",
  black: "#1f2430",

  skin: "#f4c79b",
  skinShadow: "#e0a877",
  caveSkin: "#d9a06b",
  hair: "#3a2a1a",

  shirt: "#3b82f6",
  shirtModern: "#5b8def",
  shirtOffice: "#9aa7b5",
  shirtTired: "#7d8597",
  shirtExcited: "#ff7a59",
  shirtWaiter: "#f2f4f7",
  apron: "#36404a",
  fur: "#8b5a2b",
  pants: "#2c3e50",

  brain: "#ff8fa3",
  brainMid: "#f3708a",
  brainShadow: "#e0607a",
  brainLine: "#c84f66",

  accentYellow: "#ffe14d",
  accentRed: "#ff5a5a",
  accentGreen: "#37c871",

  sweat: "#6cc6ff",

  // V2 shading
  mouthFill: "#6e2f33",
  skinHi: "#ffe0bd",
  caveSkinHi: "#e9bd8f",
  brainHi: "#ffb3c2",
  groundShadow: "rgba(15,15,25,0.28)",

  // V2.1 — clean "studio" backdrop (plain off-white, professional, character-first)
  studioTop: "#fbf9f4",
  studio: "#f4f1e9",
  studioFloor: "#e8e2d5",
  studioSeam: "#ded7c8",
  /** Brand ink for headlines/on-screen text on a light background. */
  ink: "#222838",
} as const;

/** Per-color palette for backgrounds keyed by "mood". */
export const MOOD_TINT: Record<string, number> = {
  normal: 1,
  warm: 1.06,
  cool: 0.94,
  dark: 0.8,
};
