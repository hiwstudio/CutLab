import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  Sequence,
  Video,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { AUDITION_SHOTLIST_V3 } from "./auditionDataV3";

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

type ShotItem = (typeof AUDITION_SHOTLIST_V3.shots)[number];

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
          top: 64,
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
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 4,
            padding: "8px 18px",
            background: PALETTE.charcoalGlass,
            backdropFilter: "blur(8px)",
            borderRadius: 6,
            border: "1px solid rgba(255,255,255,0.08)",
            boxShadow: "0 10px 28px rgba(0,0,0,0.42)",
          }}
        >
          <span
            style={{
              fontFamily: FONTS.mono,
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: 2.2,
              color: PALETTE.gold,
              textTransform: "uppercase",
            }}
          >
            {overlay.title}
          </span>
          <span
            style={{
              fontFamily: FONTS.serif,
              fontSize: 22,
              fontWeight: 600,
              letterSpacing: 0.3,
              color: PALETTE.paper,
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
          bottom: 48,
          left: "50%",
          transform: `translateX(-50%) translateY(${translateY}px)`,
          opacity,
          display: "flex",
          alignItems: "center",
          gap: 14,
          padding: "10px 22px",
          background: "rgba(18, 16, 14, 0.92)",
          backdropFilter: "blur(10px)",
          borderRadius: 8,
          border: `1px solid ${PALETTE.goldBorder}`,
          boxShadow: "0 12px 32px rgba(0,0,0,0.55)",
          pointerEvents: "none",
          maxWidth: 960,
        }}
      >
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            backgroundColor: PALETTE.gold,
            boxShadow: `0 0 10px ${PALETTE.gold}`,
            flexShrink: 0,
          }}
        />
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
            <span
              style={{
                fontFamily: FONTS.sans,
                fontSize: 14,
                fontWeight: 700,
                color: PALETTE.paper,
                letterSpacing: 0.2,
              }}
            >
              {overlay.authors}
            </span>
            <span
              style={{
                fontFamily: FONTS.sans,
                fontSize: 12,
                fontStyle: "italic",
                color: PALETTE.gold,
              }}
            >
              {overlay.journal}
            </span>
          </div>
          <span
            style={{
              fontFamily: FONTS.serif,
              fontSize: 13,
              color: PALETTE.mutedCream,
              letterSpacing: 0.1,
            }}
          >
            {overlay.paperTitle}
          </span>
        </div>
      </div>
    );
  }

  if (overlay.type === "turn_quote") {
    return (
      <div
        style={{
          position: "absolute",
          top: 76,
          right: 90,
          opacity,
          transform: `translateY(${translateY}px)`,
          display: "flex",
          flexDirection: "column",
          gap: 8,
          maxWidth: 520,
          padding: "18px 24px",
          background: PALETTE.charcoalGlass,
          backdropFilter: "blur(10px)",
          borderRadius: 8,
          border: `1px solid ${PALETTE.goldBorder}`,
          boxShadow: "0 14px 36px rgba(0,0,0,0.52)",
          pointerEvents: "none",
        }}
      >
        {overlay.kicker && (
          <span
            style={{
              fontFamily: FONTS.mono,
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: 2.0,
              color: PALETTE.gold,
              textTransform: "uppercase",
            }}
          >
            {overlay.kicker}
          </span>
        )}
        <span
          style={{
            fontFamily: FONTS.serif,
            fontSize: 21,
            fontStyle: "italic",
            lineHeight: 1.35,
            color: PALETTE.paper,
          }}
        >
          {overlay.quote}
        </span>
      </div>
    );
  }

  return null;
};

const ShotView: React.FC<{ shot: ShotItem }> = ({ shot }) => {
  const frame = useCurrentFrame();
  const dur = shot.durationFrames;

  let scale = 1.0;
  let translateX = 0;
  let translateY = 0;

  if (shot.mediaType === "image") {
    if (shot.motion === "push-in-slow") {
      scale = interpolate(frame, [0, dur], [1.0, 1.065], {
        easing: Easing.inOut(Easing.cubic),
      });
      translateY = interpolate(frame, [0, dur], [0, -6]);
    } else if (shot.motion === "push-in-intense") {
      scale = interpolate(frame, [0, dur], [1.0, 1.12], {
        easing: Easing.in(Easing.quad),
      });
    } else if (shot.motion === "pull-out-reveal") {
      scale = interpolate(frame, [0, dur], [1.08, 1.0], {
        easing: Easing.out(Easing.cubic),
      });
    } else if (shot.motion === "pan-left-to-right") {
      scale = 1.05;
      translateX = interpolate(frame, [0, dur], [-18, 18], {
        easing: Easing.inOut(Easing.quad),
      });
    } else if (shot.motion === "pan-right-to-left") {
      scale = 1.05;
      translateX = interpolate(frame, [0, dur], [18, -18], {
        easing: Easing.inOut(Easing.quad),
      });
    } else if (shot.motion === "drift-ambient") {
      scale = 1.025;
      translateY = Math.sin((frame / Math.max(1, dur)) * Math.PI) * 4;
    }
  }

  // Final shot fade to black
  let shotOpacity = 1;
  if (shot.id === "shot_24b") {
    shotOpacity = interpolate(frame, [dur - 45, dur], [1, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.in(Easing.quad),
    });
  }

  return (
    <AbsoluteFill style={{ backgroundColor: "#11100f", overflow: "hidden", opacity: shotOpacity }}>
      {shot.mediaType === "video" ? (
        <Video
          src={staticFile(`longform/e1-talking-feels-like-an-audition/${shot.mediaSrc}`)}
          muted
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
          }}
        />
      ) : (
        <Img
          src={staticFile(`longform/e1-talking-feels-like-an-audition/${shot.mediaSrc}`)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            transform: `scale(${scale}) translate(${translateX}px, ${translateY}px)`,
          }}
        />
      )}
      <CompulsoryOverlay shot={shot} />
    </AbsoluteFill>
  );
};

export const AuditionLongformV3: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#0e0d0c" }}>
      <Audio
        src={staticFile("longform/e1-talking-feels-like-an-audition/voiceover.mp3")}
        volume={1.0}
      />
      {AUDITION_SHOTLIST_V3.shots.map((shot) => (
        <Sequence
          key={shot.id}
          from={shot.startFrame}
          durationInFrames={shot.durationFrames}
          name={`${shot.id} (${shot.mediaType})`}
        >
          <ShotView shot={shot} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
