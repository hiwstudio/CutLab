import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  Sequence,
   interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { AUDITION_SHOTLIST } from "./auditionData";

const PALETTE = {
  paper: "#f5f2eb",
  cream: "#efece6",
  ink: "#1a1917",
  charcoalGlass: "rgba(24, 22, 19, 0.88)",
  gold: "#f5b041",
  goldBorder: "rgba(245, 176, 65, 0.55)",
  mutedCream: "#cfc8b8",
};

const FONTS = {
  serif: "'Georgia', 'Newsreader', 'Times New Roman', serif",
  sans: "'Inter', 'Segoe UI', system-ui, sans-serif",
  mono: "'JetBrains Mono', 'Consolas', monospace",
};

type ShotItem = (typeof AUDITION_SHOTLIST.shots)[number];

/**
 * Restrained, compulsory-only editorial overlay.
 * Appears ONLY on the 5 designated shots in the entire 7m36s video:
 * - shot_05: Act I title in open dark upper-left stage space
 * - shot_09: Act II title in open dark upper-left blackboard space
 * - shot_14: Gilovich et al. (2000) humble source citation centered at bottom floor space
 * - shot_17: Boothby et al. (2018) humble source citation centered at bottom table apron
 * - shot_20: The Turn quote in open dark upper-right stage space
 */
const CompulsoryOverlay: React.FC<{
  shot: ShotItem;
}> = ({ shot }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const overlay = shot.overlay;
  if (!overlay) return null;

  const absTimeSec = shot.startSec + frame / fps;
  const startSec = overlay.startSec;
  const endSec = overlay.endSec;

  if (absTimeSec < startSec - 0.1 || absTimeSec > endSec + 0.35) {
    return null;
  }

  const localFrame = Math.max(0, Math.round((absTimeSec - startSec) * fps));
  const totalOverlayFrames = Math.max(1, Math.round((endSec - startSec) * fps));

  // Editorial high-damping enter (14f settle, no bounce) and fast clean exit (9f)
  const enterProgress = spring({
    frame: localFrame,
    fps,
    config: { damping: 200, stiffness: 130, mass: 0.9, overshootClamping: true },
  });

  const exitProgress = interpolate(
    localFrame,
    [totalOverlayFrames - 9, totalOverlayFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.in(Easing.quad) }
  );

  const opacity = enterProgress * exitProgress;
  const translateY = interpolate(enterProgress, [0, 1], [10, 0]);

  if (overlay.type === "act_card") {
    return (
      <div
        style={{
          position: "absolute",
          top: shot.id === "shot_09" ? 44 : 64,
          left: 84,
          opacity,
          transform: `translateY(${translateY}px)`,
          display: "flex",
          alignItems: "stretch",
          gap: 16,
          pointerEvents: "none",
        }}
      >
        <div
          style={{
            width: 3,
            borderRadius: 2,
            backgroundColor: PALETTE.gold,
            boxShadow: "0 2px 8px rgba(0,0,0,0.45)",
          }}
        />
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <div
            style={{
              fontFamily: FONTS.mono,
              fontSize: 13,
              fontWeight: 700,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: PALETTE.gold,
              textShadow: "0 2px 8px rgba(0,0,0,0.75)",
            }}
          >
            {overlay.overline}
          </div>
          <div
            style={{
              fontFamily: FONTS.serif,
              fontSize: shot.id === "shot_09" ? 28 : 34,
              fontWeight: 700,
              color: PALETTE.paper,
              letterSpacing: "-0.01em",
              lineHeight: 1.15,
              textShadow: "0 3px 12px rgba(0,0,0,0.85)",
            }}
          >
            {overlay.title}
          </div>
        </div>
      </div>
    );
  }

  if (overlay.type === "science_citation") {
    return (
      <div
        style={{
          position: "absolute",
          bottom: 44,
          left: "50%",
          opacity,
          transform: `translate(-50%, ${translateY}px)`,
          backgroundColor: PALETTE.charcoalGlass,
          border: `1.5px solid ${PALETTE.goldBorder}`,
          borderRadius: 10,
          padding: "12px 24px",
          display: "flex",
          alignItems: "center",
          gap: 16,
          boxShadow: "0 8px 24px rgba(0,0,0,0.28)",
          pointerEvents: "none",
          maxWidth: 920,
        }}
      >
        <div
          style={{
            width: 3,
            height: 36,
            borderRadius: 2,
            backgroundColor: PALETTE.gold,
            flexShrink: 0,
          }}
        />
        <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span
              style={{
                fontFamily: FONTS.mono,
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.14em",
                color: PALETTE.gold,
                textTransform: "uppercase",
              }}
            >
              RESEARCH CITATION
            </span>
            <span style={{ color: PALETTE.mutedCream, fontSize: 12 }}>·</span>
            <span
              style={{
                fontFamily: FONTS.sans,
                fontSize: 15,
                fontWeight: 700,
                color: PALETTE.paper,
              }}
            >
              {overlay.authors}
            </span>
          </div>
          <div
            style={{
              fontFamily: FONTS.serif,
              fontStyle: "italic",
              fontSize: 14,
              color: PALETTE.mutedCream,
            }}
          >
            {overlay.work}
          </div>
        </div>
      </div>
    );
  }

  if (overlay.type === "turn_quote") {
    // Stagger second clause by 10 frames so each sentence lands with weight
    const secondLineEnter = spring({
      frame: Math.max(0, localFrame - 10),
      fps,
      config: { damping: 200, stiffness: 130, mass: 0.9, overshootClamping: true },
    });

    return (
      <div
        style={{
          position: "absolute",
          top: 116,
          right: 110,
          width: 680,
          opacity: exitProgress,
          display: "flex",
          flexDirection: "column",
          gap: 12,
          pointerEvents: "none",
        }}
      >
        <div
          style={{
            fontFamily: FONTS.mono,
            fontSize: 12,
            fontWeight: 700,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: PALETTE.gold,
            opacity: enterProgress,
            transform: `translateY(${interpolate(enterProgress, [0, 1], [8, 0])}px)`,
          }}
        >
          THE TURN
        </div>
        <div
          style={{
            fontFamily: FONTS.serif,
            fontSize: 34,
            fontWeight: 600,
            color: PALETTE.mutedCream,
            lineHeight: 1.22,
            opacity: enterProgress,
            transform: `translateY(${interpolate(enterProgress, [0, 1], [10, 0])}px)`,
            textShadow: "0 3px 12px rgba(0,0,0,0.8)",
          }}
        >
          “An audition tries to get cast.
        </div>
        <div
          style={{
            fontFamily: FONTS.serif,
            fontSize: 38,
            fontWeight: 700,
            fontStyle: "italic",
            color: PALETTE.gold,
            lineHeight: 1.22,
            opacity: secondLineEnter,
            transform: `translateY(${interpolate(secondLineEnter, [0, 1], [10, 0])}px)`,
            textShadow: "0 3px 14px rgba(0,0,0,0.85)",
          }}
        >
          A conversation tries to get curious.”
        </div>
      </div>
    );
  }

  return null;
};

const ScenePlate: React.FC<{
  shot: ShotItem;
  isFirst: boolean;
  isLast: boolean;
}> = ({ shot, isFirst, isLast }) => {
  const frame = useCurrentFrame();
  const dur = Math.max(1, shot.durationFrames);

  const progress = interpolate(frame, [0, dur], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.sin),
  });

  // Ensure scale always covers edge-to-edge when panning
  const minSafeScale =
    1 +
    (Math.max(Math.abs(shot.camera.panXFrom), Math.abs(shot.camera.panXTo)) * 2.2) / 1920 +
    (Math.max(Math.abs(shot.camera.panYFrom), Math.abs(shot.camera.panYTo)) * 2.2) / 1080;

  const zoomFrom = Math.max(shot.camera.zoomFrom, minSafeScale);
  const zoomTo = Math.max(shot.camera.zoomTo, minSafeScale);

  const scale = interpolate(progress, [0, 1], [zoomFrom, zoomTo]);
  const panX = interpolate(progress, [0, 1], [shot.camera.panXFrom, shot.camera.panXTo]);
  const panY = interpolate(progress, [0, 1], [shot.camera.panYFrom, shot.camera.panYTo]);

  const fadeIn = isFirst
    ? interpolate(frame, [0, 15], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
    : interpolate(frame, [0, 5], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const fadeOut = isLast
    ? interpolate(frame, [dur - 24, dur], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
    : 1;

  const imgPath = `longform/e1-talking-feels-like-an-audition/${shot.image}`;

  return (
    <AbsoluteFill style={{ backgroundColor: "#181613", opacity: fadeIn * fadeOut }}>
      <AbsoluteFill style={{ overflow: "hidden" }}>
        <Img
          src={staticFile(imgPath)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            transform: `scale(${scale.toFixed(4)}) translate(${panX.toFixed(2)}px, ${panY.toFixed(2)}px)`,
            transformOrigin: "center center",
          }}
        />
      </AbsoluteFill>
      <CompulsoryOverlay shot={shot} />
    </AbsoluteFill>
  );
};

export const AuditionLongform: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#181613" }}>
      <Audio src={staticFile("longform/e1-talking-feels-like-an-audition/voiceover.mp3")} volume={1} />
      {AUDITION_SHOTLIST.shots.map((shot, idx) => {
        const startFrame = shot.startFrame;
        const durationFrames = Math.max(1, shot.durationFrames);
        return (
          <Sequence
            key={shot.id}
            from={startFrame}
            durationInFrames={durationFrames}
            name={`${shot.id} (${shot.act})`}
          >
            <ScenePlate
              shot={shot}
              isFirst={idx === 0}
              isLast={idx === AUDITION_SHOTLIST.shots.length - 1}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

export const AuditionThumbnail: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#181613" }}>
      <Img
        src={staticFile("longform/e1-talking-feels-like-an-audition/images/shot_05.jpg")}
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
      />
      <div
        style={{
          position: "absolute",
          top: 52,
          left: 68,
          display: "flex",
          flexDirection: "column",
          gap: 6,
        }}
      >
        <div
          style={{
            fontFamily: FONTS.mono,
            fontSize: 22,
            fontWeight: 800,
            letterSpacing: "0.16em",
            color: PALETTE.gold,
            textTransform: "uppercase",
            textShadow: "0 3px 10px rgba(0,0,0,0.85)",
          }}
        >
          HUMAN IS WEIRD
        </div>
        <div
          style={{
            fontFamily: FONTS.serif,
            fontSize: 64,
            fontWeight: 800,
            color: PALETTE.paper,
            lineHeight: 1.05,
            textShadow: "0 4px 16px rgba(0,0,0,0.9)",
          }}
        >
          THE INTERNAL AUDITION
        </div>
      </div>
    </AbsoluteFill>
  );
};
