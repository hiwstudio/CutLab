/**
 * Thumbnail composition (architecture §23 — output/thumbnails).
 *
 * Style modeled on the channel's reference thumbnails: a full-bleed scene (the
 * character standing in the setting) with a short, punchy YELLOW question in a heavy
 * marker font with a thick black outline, an optional RED emphasis word, and optional
 * reference devices: a big red arrow and a giant red "?".
 *
 * Rendered as a static still via renderStill.
 */
import React from "react";
import { AbsoluteFill, useVideoConfig } from "remotion";
import type { Manifest } from "../engine/manifest/schema";
import {
  resolveBackgroundId,
  resolveCharacterId,
  resolvePropId,
} from "../engine/assets/resolveAsset";
import { BACKGROUNDS, CHARACTERS, PROPS } from "./assetRegistry";
import { layerStyle } from "./layout";
import { HIW_PALETTE as C } from "./theme";
import { HEADLINE_FONT } from "./fonts";

const fontFamily = `'${HEADLINE_FONT}', 'Arial Black', sans-serif`;

const BASE_CHAR_HEIGHT_FACTOR = 0.66;
const CHAR_ASPECT = 0.625;
const PROP_HEIGHT_FACTOR = 0.2;

export type ArrowDir = "none" | "left" | "right" | "up" | "down";

export type ThumbnailProps = {
  manifest: Manifest;
  /** Which scene supplies the background + characters. */
  sceneIndex: number;
  /** Punch headline; defaults to the manifest title. Keep it short (1–4 words). */
  headline?: string;
  /** Optional word/phrase within the headline to color red for emphasis. */
  accent?: string;
  /** Headline alignment. */
  align?: "center" | "left";
  /** Multiplier on character size (1 = default, 1.4 = big/cropped). */
  charScale?: number;
  /** Optional big red arrow pointing toward the subject. */
  arrow?: ArrowDir;
  /** Optional giant red "?" graphic. */
  bigQuestion?: boolean;
  /** Crop in on the subject so head/upper-body fills the frame (legs off-frame). */
  crop?: boolean;
};

/** Where each character's head sits as a fraction of its SVG viewBox height. */
const CHARACTER_HEAD_Y: Record<string, number> = {
  human: 0.19,
  ancient_brain: 0.5,
  dog: 0.31,
};

function headlineSize(text: string): number {
  const len = text.trim().length;
  if (len <= 9) return 150;
  if (len <= 14) return 122;
  if (len <= 20) return 100;
  if (len <= 28) return 80;
  return 64;
}

const ARROW_LAYOUT: Record<Exclude<ArrowDir, "none">, { cx: number; cy: number; rot: number }> = {
  left: { cx: 0.76, cy: 0.56, rot: 180 },
  right: { cx: 0.3, cy: 0.62, rot: 0 },
  down: { cx: 0.8, cy: 0.36, rot: 90 },
  up: { cx: 0.5, cy: 0.84, rot: -90 },
};

const RedArrow: React.FC<{ dir: Exclude<ArrowDir, "none">; W: number; H: number }> = ({ dir, W, H }) => {
  const size = W * 0.17;
  const { cx, cy, rot } = ARROW_LAYOUT[dir];
  return (
    <div
      style={{
        position: "absolute",
        left: cx * W - size / 2,
        top: cy * H - (size * 0.6) / 2,
        width: size,
        height: size * 0.6,
        transform: `rotate(${rot}deg)`,
        filter: "drop-shadow(0 6px 8px rgba(0,0,0,0.4))",
      }}
    >
      <svg viewBox="0 0 100 60" width="100%" height="100%">
        <polygon
          points="0,18 55,18 55,2 98,30 55,58 55,42 0,42"
          fill={C.accentRed}
          stroke="#11131a"
          strokeWidth={5}
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
};

export const Thumbnail: React.FC<ThumbnailProps> = ({
  manifest,
  sceneIndex,
  headline,
  accent,
  align = "center",
  charScale = 1,
  arrow = "none",
  bigQuestion = false,
  crop = false,
}) => {
  const { width: W, height: H } = useVideoConfig();
  const scenes = manifest.scenes;
  const idx = Math.max(0, Math.min(sceneIndex, scenes.length - 1));
  const scene = scenes[idx];
  const text = (headline ?? manifest.title).toUpperCase();

  const BackgroundComp = BACKGROUNDS[resolveBackgroundId(scene.background) ?? "abstract_explainer"];
  const charHeightFactor = BASE_CHAR_HEIGHT_FACTOR * charScale;

  const fontSize = headlineSize(text);
  const stroke = Math.max(7, Math.round(fontSize * 0.09));

  let head: React.ReactNode = text;
  if (accent) {
    const up = accent.toUpperCase();
    const i = text.indexOf(up);
    if (i >= 0) {
      head = (
        <>
          {text.slice(0, i)}
          <span style={{ color: C.accentRed }}>{text.slice(i, i + up.length)}</span>
          {text.slice(i + up.length)}
        </>
      );
    }
  }

  return (
    <AbsoluteFill style={{ backgroundColor: C.black }}>
      {/* Full-bleed scene */}
      <BackgroundComp mood="normal" frame={0} fps={30} />

      {/* Giant red "?" sits behind the character */}
      {bigQuestion ? (
        <AbsoluteFill style={{ alignItems: "flex-end", justifyContent: "center", paddingRight: W * 0.04 }}>
          <span
            style={{
              fontFamily,
              fontSize: H * 0.7,
              lineHeight: 1,
              color: C.accentRed,
              WebkitTextStroke: `${Math.round(H * 0.018)}px #11131a`,
              paintOrder: "stroke",
              opacity: 0.95,
              transform: "rotate(8deg)",
            }}
          >
            ?
          </span>
        </AbsoluteFill>
      ) : null}

      {crop
        ? (() => {
            // Big-character crop: zoom in on the first character so head/upper-body
            // fills the frame, anchoring the head just below the headline. Props are
            // skipped for a clean subject focus.
            const ch = scene.characters[0];
            if (!ch) return null;
            const id = resolveCharacterId(ch.id);
            if (!id) return null;
            const Comp = CHARACTERS[id];
            const zoom = 1.85;
            const boxH = H * zoom;
            const boxW = boxH * CHAR_ASPECT;
            const headFrac = CHARACTER_HEAD_Y[id] ?? 0.3;
            const top = H * 0.46 - headFrac * boxH;
            return (
              <div style={{ position: "absolute", left: W / 2 - boxW / 2, top, width: boxW, height: boxH }}>
                <div style={{ width: "100%", height: "100%", transform: ch.flip ? "scaleX(-1)" : undefined }}>
                  <Comp variant={ch.variant} expression={ch.expression} motion={ch.motion} frame={0} fps={30} flip={ch.flip} />
                </div>
              </div>
            );
          })()
        : (
            <>
              {scene.characters.map((ch, i) => {
                const id = resolveCharacterId(ch.id);
                if (!id) return null;
                const Comp = CHARACTERS[id];
                return (
                  <div
                    key={`c${i}`}
                    style={layerStyle({
                      position: ch.position,
                      scale: ch.scale ?? 1,
                      width: W,
                      height: H,
                      heightFactor: charHeightFactor,
                      aspect: CHAR_ASPECT,
                    })}
                  >
                    <div style={{ width: "100%", height: "100%", transform: ch.flip ? "scaleX(-1)" : undefined }}>
                      <Comp variant={ch.variant} expression={ch.expression} motion={ch.motion} frame={0} fps={30} flip={ch.flip} />
                    </div>
                  </div>
                );
              })}

              {scene.props.map((p, i) => {
                const id = resolvePropId(p.id);
                if (!id) return null;
                const Comp = PROPS[id];
                return (
                  <div
                    key={`p${i}`}
                    style={layerStyle({
                      position: p.position,
                      scale: p.scale ?? 1,
                      width: W,
                      height: H,
                      heightFactor: PROP_HEIGHT_FACTOR,
                      aspect: 1,
                    })}
                  >
                    <Comp frame={0} fps={30} animation={p.animation} flip={p.flip} />
                  </div>
                );
              })}
            </>
          )}

      {/* Red arrow */}
      {arrow !== "none" ? <RedArrow dir={arrow} W={W} H={H} /> : null}

      {/* Top scrim for legibility */}
      <AbsoluteFill
        style={{ background: "linear-gradient(180deg, rgba(10,10,18,0.48) 0%, rgba(10,10,18,0) 36%)" }}
      />

      {/* Punch headline */}
      <AbsoluteFill
        style={{
          alignItems: align === "left" ? "flex-start" : "center",
          justifyContent: "flex-start",
          padding: `${Math.round(H * 0.04)}px ${Math.round(W * 0.04)}px 0`,
        }}
      >
        <span
          style={{
            fontFamily,
            fontSize,
            lineHeight: 0.98,
            textAlign: align,
            color: C.accentYellow,
            WebkitTextStroke: `${stroke}px #11131a`,
            paintOrder: "stroke",
            textShadow: "0 6px 0 rgba(0,0,0,0.30), 0 12px 22px rgba(0,0,0,0.45)",
            maxWidth: Math.round(W * 0.94),
            letterSpacing: 0.5,
          }}
        >
          {head}
        </span>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
