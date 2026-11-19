/**
 * Channel art (YouTube profile picture + banner), rendered as static stills from the
 * real brand components so it matches the videos exactly — flat colors, bold navy
 * outlines, the Ancient Brain mascot, brand fonts, and the off-white studio backdrop.
 *
 * Two compositions:
 *   - ChannelAvatar  800x800   — the mascot bust on a flat yellow field (crops to a
 *                                circle on YouTube). Reads at 24px.
 *   - ChannelBanner  2048x1152 — "Ancient brain. Modern problems." wordmark in the
 *                                center safe area, mascot + modern human flanking it.
 *
 * Rendered via scripts/render-channel-art.ts (renderStill). Text uses the embedded
 * brand fonts so it's always crisp and correctly spelled (no generator garble).
 */
import React from "react";
import { AbsoluteFill, useVideoConfig } from "remotion";
import { CHARACTERS } from "./assetRegistry";
import { HIW_PALETTE as C } from "./theme";
import { HEADLINE_FONT, BRAND_FONT, ensureFontsLoaded } from "./fonts";

ensureFontsLoaded();

const CHAR_ASPECT = 0.625; // human SVG width/height
const BRAIN_ASPECT = 200 / 300; // AncientBrain viewBox width/height

const AncientBrain = CHARACTERS.ancient_brain;
const Human = CHARACTERS.human;

/* ------------------------------------------------------------------ Avatar */

export const ChannelAvatar: React.FC<{ panic?: boolean }> = ({ panic = false }) => {
  const { width: W, height: H } = useVideoConfig();

  // Full-body mascot, vertically centered so the face lands at the icon's center.
  const charH = Math.round(H * 0.86);
  const charW = Math.round(charH * BRAIN_ASPECT);
  const left = Math.round(W / 2 - charW / 2);
  const top = Math.round(H / 2 - charH / 2);

  return (
    <AbsoluteFill>
      {/* Flat brand-yellow field with a soft center glow for a touch of depth. */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at 50% 44%, #ffe98a 0%, ${C.accentYellow} 52%, #f4c400 100%)`,
        }}
      />
      {/* Light burst behind the mascot. */}
      <AbsoluteFill
        style={{
          background:
            "repeating-conic-gradient(from 0deg at 50% 46%, rgba(255,255,255,0.14) 0deg 7deg, rgba(255,255,255,0) 7deg 14deg)",
          opacity: 0.5,
        }}
      />
      <div style={{ position: "absolute", left, top, width: charW, height: charH }}>
        <AncientBrain expression={panic ? "shocked" : "happy"} motion="idle" frame={0} fps={30} />
      </div>
    </AbsoluteFill>
  );
};

/* -------------------------------------------------------------------- Logo */

/**
 * Transparent-background mascot logo, square. Used as the channel logo and, with the
 * white halo on, as the video branding watermark (so it reads over light or dark
 * footage). Render with imageFormat "png" to preserve the alpha channel.
 */
export const ChannelLogo: React.FC<{ halo?: boolean }> = ({ halo = false }) => {
  const { width: W, height: H } = useVideoConfig();

  const charH = Math.round(H * 0.9);
  const charW = Math.round(charH * BRAIN_ASPECT);
  const left = Math.round(W / 2 - charW / 2);
  const top = Math.round(H / 2 - charH / 2);

  // A soft white halo keeps the mascot legible as a small watermark on any background.
  const haloFilter = halo
    ? "drop-shadow(0 0 5px rgba(255,255,255,0.95)) drop-shadow(0 0 11px rgba(255,255,255,0.8))"
    : undefined;

  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left, top, width: charW, height: charH, filter: haloFilter }}>
        <AncientBrain expression="happy" motion="idle" frame={0} fps={30} />
      </div>
    </AbsoluteFill>
  );
};

/* ----------------------------------------------------- Subscribe watermark */

/**
 * 150x150 "Subscribe" branding watermark (rendered larger, then downscaled to a
 * transparent GIF). A bold red pill with a white play triangle + SUBSCRIBE, in the
 * brand's navy-outline style. Transparent background so it overlays any footage.
 */
export const SubscribeWatermark: React.FC = () => {
  const { width: W, height: H } = useVideoConfig();

  const btnH = Math.round(H * 0.36);
  const btnW = Math.round(W * 0.96);
  const left = Math.round((W - btnW) / 2);
  const top = Math.round((H - btnH) / 2);
  const outline = Math.max(2, Math.round(H * 0.022));
  const triH = Math.round(btnH * 0.42);
  const fontSize = Math.round(H * 0.135);

  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          left,
          top,
          width: btnW,
          height: btnH,
          boxSizing: "border-box",
          background: "#ff0000", // classic YouTube red — reads universally as "subscribe"
          borderRadius: btnH / 2,
          border: `${outline}px solid ${C.outline}`,
          boxShadow: "0 3px 0 rgba(31,36,48,0.28)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: Math.round(W * 0.04),
        }}
      >
        {/* Play triangle */}
        <svg width={triH} height={triH} viewBox="0 0 100 100" style={{ flex: "0 0 auto" }}>
          <polygon points="22,16 84,50 22,84" fill={C.white} stroke={C.outline} strokeWidth={8} strokeLinejoin="round" />
        </svg>
        <span
          style={{
            fontFamily: `'${BRAND_FONT}', 'Segoe UI', sans-serif`,
            fontWeight: 800,
            fontSize,
            color: C.white,
            letterSpacing: 0.3,
            textTransform: "uppercase",
            WebkitTextStroke: `${Math.max(1, Math.round(H * 0.006))}px ${C.outline}`,
            paintOrder: "stroke",
          }}
        >
          Subscribe
        </span>
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------ Banner */

export const ChannelBanner: React.FC = () => {
  const { width: W, height: H } = useVideoConfig();

  // Flanking characters live in the outer edges (desktop/TV); the two-line wordmark
  // sits dead center, sized to fit inside YouTube's 1546x423 all-device safe area
  // (centered in 2560x1440) so nothing clips on phones/tablets.
  const charH = Math.round(H * 0.58);
  const brainW = Math.round(charH * BRAIN_ASPECT);
  const humanW = Math.round(charH * CHAR_ASPECT);
  const feetY = Math.round(H * 0.86);
  const charTop = feetY - charH;

  const brainLeft = Math.round(W * 0.13 - brainW / 2);
  const humanLeft = Math.round(W * 0.87 - humanW / 2);

  // Whole text block (2 wordmark lines + gap + tagline) ≈ 0.25*H, inside the 0.294*H
  // tall safe strip.
  const headlineSize = Math.round(H * 0.108);
  const taglineSize = Math.round(H * 0.04);
  const taglineGap = Math.round(H * 0.022);

  return (
    <AbsoluteFill>
      {/* Studio backdrop: soft vertical wash + floor band. */}
      <AbsoluteFill style={{ background: `linear-gradient(180deg, ${C.studioTop} 0%, ${C.studio} 70%, ${C.studioFloor} 100%)` }} />
      {/* Center light glow behind the wordmark. */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(60% 75% at 50% 46%, rgba(255,225,77,0.30) 0%, rgba(255,225,77,0) 60%)`,
        }}
      />
      {/* Faint sunburst rays. */}
      <AbsoluteFill
        style={{
          background:
            "repeating-conic-gradient(from 0deg at 50% 46%, rgba(31,36,48,0.045) 0deg 6deg, rgba(31,36,48,0) 6deg 12deg)",
        }}
      />

      {/* Mascot (ancient brain) — left. */}
      <div style={{ position: "absolute", left: brainLeft, top: charTop, width: brainW, height: charH }}>
        <AncientBrain expression="happy" motion="idle" frame={0} fps={30} />
      </div>

      {/* Modern human — right, facing inward. */}
      <div style={{ position: "absolute", left: humanLeft, top: charTop, width: humanW, height: charH }}>
        <div style={{ width: "100%", height: "100%", transform: "scaleX(-1)" }}>
          <Human variant="modern" expression="happy" motion="idle" frame={0} fps={30} />
        </div>
      </div>

      {/* Wordmark + tagline, centered in the safe area. */}
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ textAlign: "center" }}>
          <div
            style={{
              fontFamily: `'${HEADLINE_FONT}', 'Arial Black', sans-serif`,
              fontSize: headlineSize,
              lineHeight: 0.9,
              color: C.ink,
              letterSpacing: 1,
              textShadow: "0 3px 0 rgba(31,36,48,0.12)",
            }}
          >
            <div>HUMAN IS</div>
            <div style={{ color: C.accentRed }}>WEIRD</div>
          </div>
          <div
            style={{
              marginTop: taglineGap,
              fontFamily: `'${BRAND_FONT}', 'Segoe UI', sans-serif`,
              fontWeight: 800,
              fontSize: taglineSize,
              color: "#5a6274",
              letterSpacing: 0.5,
            }}
          >
            Ancient brain. Modern problems.
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
