import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { CleanScene } from "./CleanScenes";
import { CLEAN_FONTS, CLEAN_PALETTE as C } from "./CleanTheme";
import { AUDITION_CLEAN_SHOTLIST } from "./auditionCleanData";

type ShotItem = (typeof AUDITION_CLEAN_SHOTLIST.shots)[number];

const CleanOverlay: React.FC<{
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

  const enterFrame = Math.round((startSec - shot.startSec) * fps);
  const exitFrame = Math.round((endSec - shot.startSec) * fps);

  const opacity = interpolate(
    frame,
    [enterFrame, enterFrame + 18, exitFrame - 15, exitFrame],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const translateY = spring({
    frame: frame - enterFrame,
    fps,
    config: { damping: 200, mass: 1, stiffness: 100 },
  });
  const offset = (1 - translateY) * 14;

  if (overlay.type === "act_card") {
    return (
      <div
        style={{
          position: "absolute",
          top: 72,
          left: 90,
          opacity,
          transform: `translateY(${offset}px)`,
          display: "flex",
          alignItems: "stretch",
          gap: 16,
          pointerEvents: "none",
        }}
      >
        <div
          style={{
            width: 4,
            borderRadius: 2,
            backgroundColor: C.gold,
            boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
          }}
        />
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 4,
            padding: "10px 22px",
            background: "#FFFFFF",
            borderRadius: 8,
            border: `1px solid ${C.floorLine}`,
            boxShadow: "0 12px 32px rgba(20,20,30,0.08)",
          }}
        >
          <span
            style={{
              fontFamily: CLEAN_FONTS.mono,
              fontSize: 12,
              fontWeight: 800,
              letterSpacing: 2.4,
              color: C.gold,
              textTransform: "uppercase",
            }}
          >
            {overlay.title}
          </span>
          <span
            style={{
              fontFamily: CLEAN_FONTS.serif,
              fontSize: 22,
              fontWeight: 600,
              letterSpacing: 0.3,
              color: C.ink,
            }}
          >
            {overlay.subtitle}
          </span>
        </div>
      </div>
    );
  }

  if (overlay.type === "science_citation") {
    return (
      <div
        style={{
          position: "absolute",
          bottom: 56,
          left: 90,
          opacity,
          transform: `translateY(${offset}px)`,
          display: "flex",
          flexDirection: "column",
          gap: 4,
          padding: "12px 22px",
          background: "#FFFFFF",
          borderRadius: 8,
          border: `1px solid ${C.floorLine}`,
          boxShadow: "0 12px 32px rgba(20,20,30,0.08)",
          maxWidth: 720,
          pointerEvents: "none",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            style={{
              fontFamily: CLEAN_FONTS.mono,
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: 1.8,
              color: C.blue,
              textTransform: "uppercase",
            }}
          >
            RESEARCH CITATION
          </span>
          <span style={{ color: C.inkTertiary }}>·</span>
          <span
            style={{
              fontFamily: CLEAN_FONTS.sans,
              fontSize: 13,
              fontWeight: 600,
              color: C.ink,
            }}
          >
            {overlay.authors}
          </span>
        </div>
        <span
          style={{
            fontFamily: CLEAN_FONTS.serif,
            fontSize: 14,
            fontStyle: "italic",
            color: C.inkSecondary,
            letterSpacing: 0.1,
          }}
        >
          {overlay.paperTitle}
        </span>
      </div>
    );
  }

  if (overlay.type === "turn_quote") {
    return (
      <div
        style={{
          position: "absolute",
          top: 84,
          right: 96,
          opacity,
          transform: `translateY(${offset}px)`,
          display: "flex",
          flexDirection: "column",
          gap: 8,
          maxWidth: 540,
          padding: "20px 28px",
          background: "#FFFFFF",
          borderRadius: 10,
          border: `1.5px solid ${C.gold}`,
          boxShadow: "0 16px 40px rgba(20,20,30,0.09)",
          pointerEvents: "none",
        }}
      >
        {overlay.kicker && (
          <span
            style={{
              fontFamily: CLEAN_FONTS.mono,
              fontSize: 11,
              fontWeight: 800,
              letterSpacing: 2.2,
              color: C.gold,
              textTransform: "uppercase",
            }}
          >
            {overlay.kicker}
          </span>
        )}
        <span
          style={{
            fontFamily: CLEAN_FONTS.serif,
            fontSize: 22,
            fontStyle: "italic",
            lineHeight: 1.38,
            color: C.ink,
          }}
        >
          {overlay.quote}
        </span>
      </div>
    );
  }

  return null;
};

const ShotContainer: React.FC<{ shot: ShotItem }> = ({ shot }) => {
  const frame = useCurrentFrame();
  const dur = shot.durationFrames;

  let scale = 1.0;
  let translateX = 0;
  let translateY = 0;

  if (shot.cameraMotion === "push-in-slow") {
    scale = interpolate(frame, [0, dur], [1.0, 1.055], {
      easing: Easing.inOut(Easing.cubic),
    });
    translateY = interpolate(frame, [0, dur], [0, -5]);
  } else if (shot.cameraMotion === "push-in-intense") {
    scale = interpolate(frame, [0, dur], [1.0, 1.10], {
      easing: Easing.in(Easing.quad),
    });
  } else if (shot.cameraMotion === "pull-out-reveal") {
    scale = interpolate(frame, [0, dur], [1.08, 1.0], {
      easing: Easing.out(Easing.cubic),
    });
  } else if (shot.cameraMotion === "pan-left-to-right") {
    scale = 1.04;
    translateX = interpolate(frame, [0, dur], [-18, 18], {
      easing: Easing.inOut(Easing.quad),
    });
  } else if (shot.cameraMotion === "drift-ambient") {
    scale = 1.02;
    translateY = Math.sin((frame / Math.max(1, dur)) * Math.PI) * 4;
  }

  // Fade to pure white on final shot
  let shotOpacity = 1;
  if (shot.id === "shot_24") {
    shotOpacity = interpolate(frame, [dur - 50, dur], [1, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.in(Easing.quad),
    });
  }

  return (
    <AbsoluteFill style={{ backgroundColor: "#FFFFFF", overflow: "hidden" }}>
      <div
        style={{
          width: "100%",
          height: "100%",
          transform: `scale(${scale}) translate(${translateX}px, ${translateY}px)`,
          opacity: shotOpacity,
        }}
      >
        <CleanScene shotId={shot.id} scene={shot.scene} durationFrames={shot.durationFrames} />
      </div>
      <CleanOverlay shot={shot} />
    </AbsoluteFill>
  );
};

export const AuditionCleanLongform: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#FFFFFF" }}>
      <Audio
        src={staticFile("longform/e2-why-talking-feels-like-an-audition-clean/voiceover.mp3")}
        volume={1.0}
      />
      {AUDITION_CLEAN_SHOTLIST.shots.map((shot) => (
        <Sequence
          key={shot.id}
          from={shot.startFrame}
          durationInFrames={shot.durationFrames}
          name={`${shot.id}: ${shot.scene}`}
        >
          <ShotContainer shot={shot} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
