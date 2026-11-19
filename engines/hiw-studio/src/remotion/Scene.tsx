/**
 * Scene renderer (architecture §7/§8). Composes one manifest scene:
 * background -> characters (positioned + motion) -> props -> effect overlays ->
 * on-screen text -> caption. The staged visuals are wrapped in a CameraRig; the
 * caption stays fixed (outside the camera move).
 *
 * Rendered inside a <Sequence>, so useCurrentFrame() is scene-relative.
 */
import React from "react";
import { AbsoluteFill, Img, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import type { Scene as SceneData } from "../engine/manifest/schema";
import {
  resolveBackgroundId,
  resolveCharacterId,
  resolveEffectId,
  resolveMotionId,
  resolvePropId,
} from "../engine/assets/resolveAsset";
import { Caption } from "../engine/captions/Caption";
import { estimateWordTimings } from "../engine/captions/wordTiming";
import type { Position, SceneText } from "../engine/manifest/schema";
import { HIW_PALETTE as C } from "./theme";
import { anchorFor, layerStyle } from "./layout";
import { BACKGROUNDS, CHARACTERS, EFFECTS, PROPS } from "./assetRegistry";
import { getMotion } from "./components/motions";
import { CameraRig } from "./components/effects";
import { OnScreenText } from "./components/text/OnScreenText";

const DEFAULT_TEXT_POS: Record<string, Position> = {
  reaction: "top-right",
  label: "bottom-left",
  emphasis: "top",
};

const clamp = (n: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, n));

/**
 * Resolve where a text element sits, plus (for speech) the speaker's screen-x so the
 * bubble's tail can lean toward them. Speech bubbles anchor ABOVE the speaker's head: the
 * y is lifted well clear of the head and the bubble is bottom-aligned (grows upward), so
 * it can never cover the face. x is kept on-screen.
 */
function resolveText(
  item: SceneText,
  characters: { position?: Position }[]
): { position: Position; speakerX?: number } {
  const kind = item.kind ?? "reaction";
  if (kind === "speech") {
    const a = item.character != null ? anchorFor(characters[item.character]?.position) : { x: 0.5, y: 0.62 };
    // Lift the anchor (the tail-chain's end) to just above the speaker's head (~0.35h for a
    // standard character at y≈0.62); the bubble grows upward from here, clearing the face.
    const position: Position = item.position ?? { x: clamp(a.x, 0.24, 0.76), y: clamp(a.y - 0.27, 0.05, 0.45) };
    return { position, speakerX: a.x };
  }
  return { position: item.position ?? DEFAULT_TEXT_POS[kind] ?? "top" };
}

const CHARACTER_HEIGHT_FACTOR = 0.58;
const CHARACTER_ASPECT = 0.625;
const PROP_HEIGHT_FACTOR = 0.17;
const PROP_ASPECT = 1;

export const Scene: React.FC<{
  scene: SceneData;
  durationInFrames: number;
  /** When false, the on-screen caption is not rendered (clean, caption-free video). */
  showCaptions?: boolean;
}> = ({ scene, durationInFrames, showCaptions = true }) => {
  const frame = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();

  const BackgroundComp = BACKGROUNDS[resolveBackgroundId(scene.background) ?? "abstract_explainer"];

  // Soft cross-dip at the scene edges (to the studio backdrop behind) so cuts breathe
  // instead of snapping. Kept very short — a barely-there softening, not a dissolve.
  const TRANSITION = 3;
  const sceneOpacity = Math.max(
    0,
    Math.min(1, frame / TRANSITION, (durationInFrames - frame) / TRANSITION)
  );

  // Beat timing: a quick scale-"punch" on the staged frame landing on the emphasized
  // word(s) — and, on punchline (hiw_emphasis) scenes with no markup, on the final
  // kicker word — so the animation hits *with* the joke. The caption stays still.
  // Memoized: the timings depend on the scene, not the current frame.
  const beats = React.useMemo(() => {
    const beatTimings =
      scene.captionWordTimings ?? estimateWordTimings(scene.voiceover, 0, durationInFrames, fps);
    const out: number[] = [];
    for (const w of beatTimings) if (w.emphasis) out.push((w.startF + w.endF) / 2);
    if (out.length === 0 && scene.caption?.style === "hiw_emphasis" && beatTimings.length > 0) {
      const last = beatTimings[beatTimings.length - 1];
      out.push((last.startF + last.endF) / 2);
    }
    return out;
  }, [scene, durationInFrames, fps]);
  let beatScale = 1;
  for (const bf of beats) {
    const d = frame - (bf - 2); // start the pulse a touch before the word lands
    if (d >= 0 && d <= 9) beatScale = Math.max(beatScale, 1 + 0.04 * Math.sin((d / 9) * Math.PI));
  }

  return (
    <AbsoluteFill style={{ backgroundColor: C.studio, opacity: sceneOpacity }}>
      <AbsoluteFill style={{ transform: `scale(${beatScale.toFixed(4)})`, transformOrigin: "center center" }}>
      <CameraRig camera={scene.camera} frame={frame} fps={fps} durationInFrames={durationInFrames}>
        {/* Background — SVG backdrop (also the fallback under a stick-hiw image). */}
        <BackgroundComp mood="normal" frame={frame} fps={fps} />

        {/* Stick-hiw style: full-frame generated image as the scene visual. */}
        {scene.image ? (
          <AbsoluteFill>
            <Img
              src={staticFile(scene.image)}
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          </AbsoluteFill>
        ) : null}

        {/* Characters (staggered spring entrance) */}
        {scene.characters.map((ch, i) => {
          const id = resolveCharacterId(ch.id);
          if (!id) return null;
          const CharacterComp = CHARACTERS[id];
          const motion = getMotion(resolveMotionId(ch.motion))(frame, fps);
          const flip = ch.flip ? " scaleX(-1)" : "";
          const enter = spring({ frame: frame - i * 3, fps, durationInFrames: 14, config: { damping: 14, mass: 0.6 } });
          const enterClamped = Math.min(1, Math.max(0, enter));
          return (
            <div
              key={`char-${i}`}
              style={layerStyle({
                position: ch.position,
                scale: ch.scale ?? 1,
                width,
                height,
                heightFactor: CHARACTER_HEIGHT_FACTOR,
                aspect: CHARACTER_ASPECT,
              })}
            >
              <div
                style={{
                  width: "100%",
                  height: "100%",
                  transformOrigin: "center bottom",
                  opacity: enterClamped,
                  transform: `translateY(${((1 - enter) * 42).toFixed(1)}px) scale(${(0.82 + 0.18 * enterClamped).toFixed(3)})`,
                }}
              >
                <div
                  style={{
                    width: "100%",
                    height: "100%",
                    transformOrigin: "center bottom",
                    ...motion,
                    transform: `${motion.transform ?? ""}${flip}`.trim(),
                  }}
                >
                  <CharacterComp
                    variant={ch.variant}
                    expression={ch.expression}
                    motion={ch.motion}
                    frame={frame}
                    fps={fps}
                    flip={ch.flip}
                    speaking={ch.speaking}
                    extra={ch.props}
                  />
                </div>
              </div>
            </div>
          );
        })}

        {/* Props (pop in after the characters) */}
        {scene.props.map((p, i) => {
          const id = resolvePropId(p.id);
          if (!id) return null;
          const PropComp = PROPS[id];
          const flip = p.flip ? "scaleX(-1)" : "";
          const delay = scene.characters.length * 3 + 6 + i * 3;
          const enter = spring({ frame: frame - delay, fps, durationInFrames: 16, config: { damping: 10, mass: 0.7 } });
          const popScale = (0.4 + 0.6 * enter).toFixed(3);
          const opacity = Math.min(1, Math.max(0, enter * 2));
          return (
            <div
              key={`prop-${i}`}
              style={layerStyle({
                position: p.position,
                scale: p.scale ?? 1,
                width,
                height,
                heightFactor: PROP_HEIGHT_FACTOR,
                aspect: PROP_ASPECT,
              })}
            >
              <div style={{ width: "100%", height: "100%", opacity, transform: `scale(${popScale})` }}>
                <div style={{ width: "100%", height: "100%", transform: flip || undefined }}>
                  <PropComp frame={frame} fps={fps} animation={p.animation} flip={p.flip} text={p.text} />
                </div>
              </div>
            </div>
          );
        })}

        {/* Effect overlays */}
        {scene.effects.map((e, i) => {
          const id = resolveEffectId(e);
          if (!id) return null;
          const EffectComp = EFFECTS[id];
          return <EffectComp key={`fx-${i}`} frame={frame} fps={fps} intensity={0.5} />;
        })}

        {/* Intentional contextual on-screen text (speech / reaction / label / emphasis) —
            not subtitles; the Director places these only where they help the scene. */}
        {scene.texts.map((t, i) => {
          const { position, speakerX } = resolveText(t, scene.characters);
          return (
            <OnScreenText
              key={`txt-${i}`}
              item={t}
              position={position}
              speakerX={speakerX}
              durationInFrames={durationInFrames}
            />
          );
        })}
      </CameraRig>
      </AbsoluteFill>

      {/* Legacy `onscreenText` (deprecated — prefer scene.texts). Rendered through the
          same brand-styled emphasis path as texts, fixed outside the camera move. */}
      {scene.onscreenText ? (
        <OnScreenText
          item={{ kind: "emphasis", text: scene.onscreenText }}
          position="top"
          durationInFrames={durationInFrames}
        />
      ) : null}

      {/* Caption = the exact voiceover line for this scene (styled per caption.style),
          revealed word-by-word in sync with the narration. Skipped when captions are
          disabled for the project (style.captions = false). */}
      {showCaptions ? (
        <Caption
          caption={{ ...scene.caption, text: scene.voiceover }}
          durationInFrames={durationInFrames}
          wordTimings={scene.captionWordTimings}
        />
      ) : null}
    </AbsoluteFill>
  );
};
