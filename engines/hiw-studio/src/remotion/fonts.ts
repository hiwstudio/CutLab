/**
 * Brand fonts (V2 fix). Embedded as base64 data URIs (src/remotion/fontData.ts) and
 * registered via an injected CSS @font-face — NO network, NO CDN, NO public-dir.
 *
 * Deliberately does NOT call delayRender(): under Remotion's concurrent headless
 * rendering, a font-tied delayRender could hang and time out the whole render. Because
 * the fonts are inline data URIs (no I/O), they apply near-instantly at page init —
 * well before the first frame is captured — and `font-display: swap` keeps text
 * visible (in a fallback) in the worst case. So there is simply nothing to wait on.
 *
 * Regenerate fontData.ts after changing assets/fonts:  npx tsx scripts/embed-fonts.ts
 */
import { BALOO2_700, BALOO2_800, LUCKIEST_GUY_400 } from "./fontData";

export const BRAND_FONT = "Baloo 2"; // captions
export const HEADLINE_FONT = "Luckiest Guy"; // thumbnail headlines

const SPECS = [
  { family: BRAND_FONT, weight: "700", data: BALOO2_700 },
  { family: BRAND_FONT, weight: "800", data: BALOO2_800 },
  { family: HEADLINE_FONT, weight: "400", data: LUCKIEST_GUY_400 },
];

let loaded = false;
/** Idempotently register the brand fonts. Safe to call from multiple components. */
export function ensureFontsLoaded(): void {
  if (loaded) return;
  loaded = true;
  if (typeof document === "undefined" || !document.head) return;

  const css = SPECS.map(
    (s) =>
      `@font-face{font-family:'${s.family}';font-weight:${s.weight};font-style:normal;font-display:swap;src:url(${s.data}) format('woff2');}`
  ).join("\n");
  const style = document.createElement("style");
  style.setAttribute("data-hiw-fonts", "");
  style.appendChild(document.createTextNode(css));
  document.head.appendChild(style);

  // Kick off decoding early (fire-and-forget). No delayRender → can never hang.
  if (typeof document.fonts !== "undefined") {
    for (const s of SPECS) {
      try {
        void document.fonts.load(`${s.weight} 16px '${s.family}'`);
      } catch {
        /* ignore */
      }
    }
  }
}

// Register on import (modules that need the fonts import this file).
ensureFontsLoaded();
