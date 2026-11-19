/**
 * Intentional on-screen text (architecture §12b). Renders ONE `scene.texts` element with
 * kind-appropriate styling + a springy entrance, so text feels like part of the animation
 * — never a subtitle. The engine ships caption-free by default; these are the deliberate,
 * contextual text beats the Director places only when they help the scene.
 *
 * Kinds:
 *  - speech   — a rounded speech bubble (with tail) containing a character's exact words.
 *  - reaction — a punchy comic/dramatic word, tilted, with a brand-accent pop.
 *  - label    — a small sign/tag/UI/notification chip that belongs in the scene.
 *  - emphasis — big headline punch text for a key visual moment / punchline.
 *
 * Rendered inside the scene's CameraRig (so it tracks the staged shot), so
 * useCurrentFrame() is scene-relative.
 */
import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { Position, SceneText } from "../../../engine/manifest/schema";
import { anchorFor } from "../../layout";
import { HIW_PALETTE as C } from "../../theme";
import { BRAND_FONT, HEADLINE_FONT, ensureFontsLoaded } from "../../fonts";

/** A chunky text outline (8-way drop) plus a soft shadow, for headline-style text. */
function outlineShadow(px: number, color: string = C.outline): string {
  const o: string[] = [];
  for (let dx = -1; dx <= 1; dx++) {
    for (let dy = -1; dy <= 1; dy++) {
      if (dx || dy) o.push(`${dx * px}px ${dy * px}px 0 ${color}`);
    }
  }
  o.push(`0 ${Math.round(px * 1.6)}px ${Math.round(px * 2.2)}px rgba(20,16,12,0.3)`);
  return o.join(",");
}

export const OnScreenText: React.FC<{
  item: SceneText;
  /** Resolved screen position (Scene fills the per-kind / per-speaker default). */
  position: Position;
  /** For speech: the speaker's screen-x (0..1), so the tail-chain leans toward them. */
  speakerX?: number;
  durationInFrames: number;
}> = ({ item, position, speakerX, durationInFrames }) => {
  const frame = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();
  ensureFontsLoaded();

  const startF = item.start != null ? Math.round(item.start * fps) : 0;
  const endF = item.end != null ? Math.round(item.end * fps) : durationInFrames;
  if (frame < startF || frame >= endF) return null;

  const local = frame - startF;
  const localDur = Math.max(1, endF - startF);
  const enter = spring({ frame: local, fps, durationInFrames: 12, config: { damping: 12, mass: 0.6 } });
  const enterClamped = Math.max(0, Math.min(1, enter));
  const fadeOut = interpolate(local, [localDur - 5, localDur], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = enterClamped * fadeOut;

  const anchor = anchorFor(position);
  const kind = item.kind ?? "reaction";
  const min = Math.min(width, height);

  const wrap: React.CSSProperties = {
    position: "absolute",
    left: anchor.x * width,
    top: anchor.y * height,
    maxWidth: width * 0.44,
    pointerEvents: "none",
    opacity,
    textAlign: "center",
  };

  if (kind === "speech") {
    // Clean oval bubble (border-radius 50% = ellipse), text sitting cleanly inside,
    // bottom-anchored just above the speaker's head (Scene set position.y clear of the
    // head) so the column grows UPWARD and never covers the face. Tail = a chain of
    // shrinking circles leading down to the speaker.
    const pop = 0.86 + 0.14 * enterClamped;
    // Thinner, more refined outline (was ~0.0072·min) so the bubbles feel lighter.
    const border = Math.max(2, min * 0.0042);
    const lean = speakerX != null ? Math.sign(speakerX - anchor.x) : 0;
    const chain = [min * 0.03, min * 0.019, min * 0.012]; // shrinking tail circles
    return (
      <div
        style={{
          position: "absolute",
          left: anchor.x * width,
          top: anchor.y * height,
          transform: `translate(-50%, -100%) scale(${pop.toFixed(3)})`,
          transformOrigin: "center bottom",
          pointerEvents: "none",
          opacity,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        {/* clean oval bubble — text sits cleanly inside */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            textAlign: "center",
            background: C.white,
            color: C.ink,
            border: `${border}px solid ${C.outline}`,
            borderRadius: "50%",
            padding: `${min * 0.036}px ${min * 0.075}px`,
            minWidth: min * 0.12,
            maxWidth: width * 0.34,
            fontFamily: `'${BRAND_FONT}', 'Segoe UI', sans-serif`,
            fontWeight: 800,
            fontSize: min * 0.044,
            lineHeight: 1.05,
            boxShadow: "0 7px 0 rgba(20,16,12,0.10)",
          }}
        >
          {item.text}
        </div>
        {/* tail: a chain of shrinking circles leading down to the speaker */}
        {chain.map((d, k) => (
          <div
            key={k}
            style={{
              width: d,
              height: d,
              marginTop: k === 0 ? min * 0.012 : min * 0.009,
              borderRadius: "50%",
              background: C.white,
              border: `${border}px solid ${C.outline}`,
              transform: `translateX(${(lean * (k + 1) * min * 0.016).toFixed(1)}px)`,
              boxShadow: "0 3px 0 rgba(20,16,12,0.08)",
            }}
          />
        ))}
      </div>
    );
  }

  if (kind === "label") {
    return (
      <div style={{ ...wrap, transform: `translate(-50%, -50%) translateY(${((1 - enterClamped) * 10).toFixed(1)}px)` }}>
        <span
          style={{
            display: "inline-block",
            background: "rgba(255,255,255,0.94)",
            color: C.ink,
            border: `${Math.max(2, min * 0.004)}px solid ${C.outline}`,
            borderRadius: min * 0.018,
            padding: `${min * 0.012}px ${min * 0.024}px`,
            fontFamily: `'${BRAND_FONT}', 'Segoe UI', sans-serif`,
            fontWeight: 700,
            fontSize: min * 0.03,
            letterSpacing: 1.2,
            textTransform: "uppercase",
            boxShadow: "0 4px 0 rgba(20,16,12,0.12)",
          }}
        >
          {item.text}
        </span>
      </div>
    );
  }

  if (kind === "emphasis") {
    return (
      <div style={{ ...wrap, transform: `translate(-50%, -50%) scale(${(0.7 + 0.3 * enterClamped).toFixed(3)})` }}>
        <span
          style={{
            fontFamily: `'${HEADLINE_FONT}', 'Segoe UI', sans-serif`,
            fontSize: min * 0.085,
            lineHeight: 1.0,
            color: C.white,
            letterSpacing: 1,
            textShadow: outlineShadow(Math.max(3, min * 0.007)),
          }}
        >
          {item.text}
        </span>
      </div>
    );
  }

  // reaction (default): tilted comic punch with a small ongoing pulse.
  const pulse = 1 + 0.035 * Math.sin((local / fps) * Math.PI * 2 * 1.4);
  const scale = (0.6 + 0.4 * enterClamped) * pulse;
  return (
    <div style={{ ...wrap, transform: `translate(-50%, -50%) rotate(-4deg) scale(${scale.toFixed(3)})` }}>
      <span
        style={{
          fontFamily: `'${HEADLINE_FONT}', 'Segoe UI', sans-serif`,
          fontSize: min * 0.072,
          lineHeight: 1.0,
          color: C.accentYellow,
          letterSpacing: 0.5,
          textShadow: outlineShadow(Math.max(3, min * 0.006)),
        }}
      >
        {item.text}
      </span>
    </div>
  );
};
