import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { CLEAN_FONTS, CLEAN_PALETTE as C } from "./CleanTheme";
import { LogicClean } from "./characters/LogicClean";
import { MoClean } from "./characters/MoClean";
import { OggClean } from "./characters/OggClean";
import { RenClean } from "./characters/RenClean";

export interface CleanSceneProps {
  shotId: string;
  scene: string;
  durationFrames: number;
}

export const CleanScene: React.FC<CleanSceneProps> = ({ shotId, scene, durationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Subtle breathing / idle motion across the shot
  const breath = Math.sin((frame / fps) * 2.2) * 2.5;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: C.canvas,
        overflow: "hidden",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {/* Subtle floor baseline across wide shots */}
      <svg
        viewBox="0 0 1920 1080"
        width="100%"
        height="100%"
        style={{ position: "absolute", top: 0, left: 0, pointerEvents: "none" }}
      >
        <line x1="120" y1="840" x2="1800" y2="840" stroke={C.floorLine} strokeWidth="2" strokeDasharray="8 8" />
        <ellipse cx="960" cy="855" rx="720" ry="45" fill={C.floorGlow} opacity="0.6" />
      </svg>

      {/* SHOT 01: Mo at Sleek Minimalist Coffee Counter */}
      {scene === "cafe_counter" && (
        <div style={{ position: "relative", width: 1920, height: 1080 }}>
          {/* Floating Sleek Wooden Coffee Counter */}
          <svg viewBox="0 0 1920 1080" width="100%" height="100%" style={{ position: "absolute" }}>
            <rect x="340" y="660" width="560" height="24" rx="4" fill="#D3A274" stroke={C.ink} strokeWidth="3.5" />
            <rect x="360" y="684" width="520" height="156" rx="4" fill="#E8DEC8" stroke={C.ink} strokeWidth="3.5" />
            <line x1="360" y1="730" x2="880" y2="730" stroke={C.inkFaint} strokeWidth="2" />
            <line x1="360" y1="780" x2="880" y2="780" stroke={C.inkFaint} strokeWidth="2" />

            {/* Steaming Ceramic Coffee Cup on Counter */}
            <rect x="740" y="605" width="46" height="55" rx="6" fill="#FFFFFF" stroke={C.ink} strokeWidth="3.5" />
            <path d="M 786,618 C 800,618 800,644 786,644" fill="none" stroke={C.ink} strokeWidth="3" />
            {/* Animated Steam */}
            <path
              d={`M 755,${585 + breath} Q 750,${570 + breath} 758,${555 + breath}`}
              fill="none"
              stroke={C.inkTertiary}
              strokeWidth="2.5"
              strokeLinecap="round"
            />
            <path
              d={`M 770,${580 - breath} Q 776,${565 - breath} 768,${550 - breath}`}
              fill="none"
              stroke={C.inkTertiary}
              strokeWidth="2.5"
              strokeLinecap="round"
            />

            {/* Barista silhouette on left */}
            <g transform="translate(420, 480) scale(0.9)">
              <ellipse cx="60" cy="50" rx="36" ry="40" fill={C.moSkin} stroke={C.ink} strokeWidth="3.5" />
              <path d="M 30,90 L 90,90 L 96,180 L 24,180 Z" fill="#2E4057" stroke={C.ink} strokeWidth="3.5" />
              {/* Apron */}
              <rect x="34" y="96" width="52" height="84" rx="4" fill="#3D5A73" stroke={C.ink} strokeWidth="3" />
            </g>
          </svg>

          {/* Mo standing at counter with hands in hoodie pocket */}
          <div style={{ position: "absolute", left: 1040, top: 460 }}>
            <MoClean pose="pocket" expression="happy" scale={1.25} />
          </div>
        </div>
      )}

      {/* SHOT 02: Wide Split Shot — Mo turns and sees Ren */}
      {scene === "cafe_wide_split" && (
        <div style={{ position: "relative", width: 1920, height: 1080 }}>
          {/* Mo on Left, turned holding coffee cup */}
          <div style={{ position: "absolute", left: 380, top: 460 }}>
            <MoClean pose="cup" expression="anxious" scale={1.2} />
          </div>

          {/* Clean 12-foot space arrow / subtle dotted trajectory */}
          <svg viewBox="0 0 1920 1080" width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
            <line x1="620" y1="740" x2="1280" y2="740" stroke={C.gold} strokeWidth="3" strokeDasharray="12 12" />
            <text x="950" y="725" fill={C.gold} fontFamily={CLEAN_FONTS.mono} fontSize="14" fontWeight="700" textAnchor="middle" letterSpacing="2">
              12 FEET ACROSS THE HARDWOOD
            </text>
          </svg>

          {/* Ren on Right at sunny window table reading paperback */}
          <div style={{ position: "absolute", left: 1320, top: 460 }}>
            <RenClean pose="reading" expression="peaceful" scale={1.2} flip={true} />
          </div>
        </div>
      )}

      {/* SHOT 03: Mo Mannequin Freeze Beside Potted Fig */}
      {scene === "mannequin_freeze" && (
        <div style={{ position: "relative", width: 1920, height: 1080, display: "flex", alignItems: "center", justifyContent: "center" }}>
          {/* Minimalist Potted Plant on left */}
          <svg width="220" height="500" viewBox="0 0 220 500" style={{ position: "absolute", left: 620, top: 380 }}>
            <path d="M 80,340 L 65,460 L 155,460 L 140,340 Z" fill="#E8C9A3" stroke={C.ink} strokeWidth="3.5" />
            <ellipse cx="110" cy="340" rx="30" ry="8" fill="#B5835A" stroke={C.ink} strokeWidth="3" />
            {/* Minimal fiddle fig leaves */}
            <path d="M 110,340 Q 110,240 70,180" fill="none" stroke="#4D7C68" strokeWidth="4" />
            <ellipse cx="60" cy="170" rx="35" ry="48" fill="#588157" stroke={C.ink} strokeWidth="3" transform="rotate(-25 60 170)" />
            <ellipse cx="150" cy="220" rx="32" ry="44" fill="#4D7C68" stroke={C.ink} strokeWidth="3" transform="rotate(30 150 220)" />
            <ellipse cx="105" cy="110" rx="36" ry="50" fill="#7A9A85" stroke={C.ink} strokeWidth="3" />
          </svg>

          {/* Mo Stiff Mannequin Pose */}
          <div style={{ position: "absolute", left: 920, top: 440 }}>
            <MoClean pose="freeze" expression="shocked" scale={1.3} />
          </div>
        </div>
      )}

      {/* SHOT 04: Chest-Up Mo Under Theatrical Spotlight */}
      {scene === "tribunal_question" && (
        <div style={{ position: "relative", width: 1920, height: 1080, display: "flex", alignItems: "center", justifyContent: "center" }}>
          {/* Conical Graphic Spotlight Beam cutting down */}
          <svg viewBox="0 0 1920 1080" width="100%" height="100%" style={{ position: "absolute" }}>
            <polygon points="960,0 680,1080 1240,1080" fill={C.spotlightBeam} />
            <ellipse cx="960" cy="850" rx="280" ry="70" fill={C.spotlightFloor} />
          </svg>

          {/* Mo in center */}
          <div style={{ position: "absolute", top: 440 }}>
            <MoClean pose="pocket" expression="anxious" scale={1.35} />
          </div>
        </div>
      )}

      {/* SHOT 05: Theatrical Split: Actor Mo on X vs Director Mo behind Desk */}
      {scene === "split_director" && (
        <div style={{ position: "relative", width: 1920, height: 1080 }}>
          {/* Actor Mo on stage left on X mark under spotlight */}
          <svg viewBox="0 0 1920 1080" width="100%" height="100%" style={{ position: "absolute" }}>
            <polygon points="560,0 360,1080 760,1080" fill={C.spotlightBeam} />
            <ellipse cx="560" cy="840" rx="190" ry="45" fill={C.spotlightFloor} />
            {/* Taped X Mark on Floor */}
            <line x1="535" y1="830" x2="585" y2="850" stroke={C.red} strokeWidth="6" strokeLinecap="round" />
            <line x1="585" y1="830" x2="535" y2="850" stroke={C.red} strokeWidth="6" strokeLinecap="round" />

            {/* Casting Desk on stage right */}
            <rect x="1160" y="660" width="460" height="18" rx="4" fill="#2E4057" stroke={C.ink} strokeWidth="3.5" />
            <line x1="1200" y1="678" x2="1200" y2="840" stroke={C.ink} strokeWidth="4" />
            <line x1="1580" y1="678" x2="1580" y2="840" stroke={C.ink} strokeWidth="4" />

            {/* Director Desk Lamp & Evaluation Clipboard */}
            <path d="M 1220,660 L 1220,580 L 1250,580" fill="none" stroke={C.ink} strokeWidth="3.5" />
            <path d="M 1240,570 L 1265,595 L 1235,595 Z" fill="#F4A261" stroke={C.ink} strokeWidth="2.5" />
            {/* Clipboard */}
            <rect x="1360" y="600" width="70" height="90" rx="4" fill="#F4F1EA" stroke={C.ink} strokeWidth="3" />
            <rect x="1380" y="594" width="30" height="10" rx="2" fill="#8D99AE" stroke={C.ink} strokeWidth="2" />
            <line x1="1372" y1="620" x2="1418" y2="620" stroke={C.red} strokeWidth="2.5" />
            <line x1="1372" y1="635" x2="1418" y2="635" stroke={C.inkTertiary} strokeWidth="2" />
            <line x1="1372" y1="650" x2="1405" y2="650" stroke={C.inkTertiary} strokeWidth="2" />
          </svg>

          {/* Actor Mo */}
          <div style={{ position: "absolute", left: 450, top: 450 }}>
            <MoClean pose="pocket" expression="anxious" scale={1.2} />
          </div>

          {/* Director Mo behind desk */}
          <div style={{ position: "absolute", left: 1300, top: 430 }}>
            <MoClean pose="pocket" expression="sternDirector" scale={1.2} />
          </div>
        </div>
      )}

      {/* SHOT 06: Customs Inspection Mailroom Desk View */}
      {scene === "customs_mailroom" && (
        <div style={{ position: "relative", width: 1920, height: 1080, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <svg viewBox="0 0 1920 1080" width="100%" height="100%" style={{ position: "absolute" }}>
            {/* Customs Wooden Counter Top */}
            <rect x="360" y="680" width="1200" height="28" rx="4" fill="#D3A274" stroke={C.ink} strokeWidth="4" />
            <rect x="380" y="708" width="1160" height="150" fill="#E8DEC8" stroke={C.ink} strokeWidth="4" />

            {/* Three Paper Slips labeled "HEY", "HI THERE", "HELLO" */}
            {/* Envelope 1: HEY */}
            <g transform="translate(560, 560)">
              <rect x="0" y="0" width="220" height="110" rx="6" fill="#FFFFFF" stroke={C.ink} strokeWidth="3.5" />
              <text x="110" y="65" fill={C.ink} fontFamily={CLEAN_FONTS.mono} fontSize="26" fontWeight="700" textAnchor="middle" letterSpacing="4">
                "HEY"
              </text>
              <rect x="30" y="80" width="160" height="6" rx="2" fill={C.inkFaint} />
            </g>

            {/* Envelope 2: HI THERE */}
            <g transform="translate(850, 560)">
              <rect x="0" y="0" width="220" height="110" rx="6" fill="#FFFFFF" stroke={C.ink} strokeWidth="3.5" />
              <text x="110" y="65" fill={C.ink} fontFamily={CLEAN_FONTS.mono} fontSize="24" fontWeight="700" textAnchor="middle" letterSpacing="3">
                "HI THERE"
              </text>
              <rect x="30" y="80" width="160" height="6" rx="2" fill={C.inkFaint} />
            </g>

            {/* Envelope 3: HELLO */}
            <g transform="translate(1140, 560)">
              <rect x="0" y="0" width="220" height="110" rx="6" fill="#FFFFFF" stroke={C.ink} strokeWidth="3.5" />
              <text x="110" y="65" fill={C.ink} fontFamily={CLEAN_FONTS.mono} fontSize="26" fontWeight="700" textAnchor="middle" letterSpacing="4">
                "HELLO"
              </text>
              <rect x="30" y="80" width="160" height="6" rx="2" fill={C.inkFaint} />
            </g>

            {/* Giant Red Rubber Stamp poised overhead */}
            <g transform="translate(900, 320)">
              {/* Handle */}
              <ellipse cx="60" cy="30" rx="35" ry="24" fill="#9E2A2B" stroke={C.ink} strokeWidth="3.5" />
              <rect x="48" y="45" width="24" height="75" rx="6" fill="#B23A48" stroke={C.ink} strokeWidth="3.5" />
              {/* Base */}
              <rect x="0" y="120" width="120" height="26" rx="6" fill="#C83E4D" stroke={C.ink} strokeWidth="3.5" />
              <rect x="6" y="146" width="108" height="14" rx="3" fill="#E63946" stroke={C.ink} strokeWidth="2.5" />
              {/* Red Stamp Ink mark: REJECTED */}
              <g transform="translate(-160, 160) rotate(-12)">
                <rect x="0" y="0" width="180" height="48" rx="6" fill="none" stroke={C.red} strokeWidth="4" />
                <text x="90" y="34" fill={C.red} fontFamily={CLEAN_FONTS.mono} fontSize="20" fontWeight="800" textAnchor="middle" letterSpacing="4">
                  REJECTED
                </text>
              </g>
            </g>
          </svg>
        </div>
      )}

      {/* SHOT 07: Walking with Press Kit Portfolio */}
      {scene === "press_kit_walk" && (
        <div style={{ position: "relative", width: 1920, height: 1080 }}>
          {/* Dashed trajectory line across clean floor */}
          <svg viewBox="0 0 1920 1080" width="100%" height="100%" style={{ position: "absolute" }}>
            <line x1="320" y1="840" x2="1600" y2="840" stroke={C.inkSecondary} strokeWidth="3.5" strokeDasharray="14 14" />
            {/* Footstep markers */}
            <circle cx="580" cy="840" r="6" fill={C.gold} />
            <circle cx="780" cy="840" r="6" fill={C.gold} />
            <circle cx="980" cy="840" r="6" fill={C.gold} />
          </svg>

          <div style={{ position: "absolute", left: 820, top: 450 }}>
            <MoClean pose="pocket" expression="anxious" scale={1.25} />
            {/* Portfolio Binder tucked under arm */}
            <svg style={{ position: "absolute", left: 130, top: 155, width: 80, height: 95 }} viewBox="0 0 80 95">
              <rect x="0" y="0" width="75" height="92" rx="5" fill="#2E4057" stroke={C.ink} strokeWidth="3.5" />
              <rect x="8" y="15" width="58" height="28" rx="3" fill="#FFFFFF" stroke={C.ink} strokeWidth="2" />
              <text x="37" y="32" fill={C.ink} fontFamily={CLEAN_FONTS.mono} fontSize="8" fontWeight="800" textAnchor="middle">
                PRESS KIT
              </text>
            </svg>
          </div>
        </div>
      )}

      {/* SHOT 08: Ren at Table Drinking Tea — The Actual Threat */}
      {scene === "actual_threat_ren" && (
        <div style={{ position: "relative", width: 1920, height: 1080, display: "flex", alignItems: "center", justifyContent: "center" }}>
          {/* Gavel & Bench floating metaphor in background negative space */}
          <svg viewBox="0 0 1920 1080" width="100%" height="100%" style={{ position: "absolute" }}>
            {/* Subtle judicial outline in light grey */}
            <g transform="translate(1360, 420)" opacity="0.25">
              <rect x="0" y="120" width="240" height="24" rx="4" fill="#2E4057" stroke={C.ink} strokeWidth="3" />
              {/* Wooden gavel */}
              <rect x="90" y="40" width="60" height="34" rx="4" fill="#8D5B4C" stroke={C.ink} strokeWidth="3" />
              <line x1="120" y1="74" x2="120" y2="120" stroke={C.ink} strokeWidth="4" />
            </g>
          </svg>

          <div style={{ position: "absolute", left: 880, top: 440 }}>
            <RenClean pose="tea" expression="peaceful" scale={1.3} />
          </div>
        </div>
      )}

      {/* SHOT 09: Split-Level Brain: Logic Upstairs vs Ogg Downstairs */}
      {scene === "control_room" && (
        <div style={{ position: "relative", width: 1920, height: 1080 }}>
          <svg viewBox="0 0 1920 1080" width="100%" height="100%" style={{ position: "absolute" }}>
            {/* Split Level Platform Line */}
            <line x1="300" y1="520" x2="1620" y2="520" stroke={C.ink} strokeWidth="5" />
            {/* Floor Labels */}
            <text x="360" y="360" fill={C.blue} fontFamily={CLEAN_FONTS.mono} fontSize="14" fontWeight="800" letterSpacing="3">
              PREFRONTAL CORTEX (LOGIC)
            </text>
            <text x="360" y="660" fill={C.red} fontFamily={CLEAN_FONTS.mono} fontSize="14" fontWeight="800" letterSpacing="3">
              LIMBIC MIDBRAIN (OGG)
            </text>

            {/* Red Panic Siren in basement */}
            <g transform="translate(1260, 680)">
              <rect x="0" y="40" width="60" height="30" rx="4" fill="#333333" stroke={C.ink} strokeWidth="3" />
              <path d="M 10,40 C 10,15 50,15 50,40 Z" fill={C.red} stroke={C.ink} strokeWidth="3" />
              {/* Red glow pulse */}
              <circle cx="30" cy="28" r="45" fill={C.red} opacity={0.25 + 0.15 * Math.sin(frame * 0.3)} />
            </g>
          </svg>

          {/* Logic upstairs */}
          <div style={{ position: "absolute", left: 880, top: 160 }}>
            <LogicClean pose="holdingBoard" scale={1.05} />
          </div>

          {/* Ogg downstairs */}
          <div style={{ position: "absolute", left: 880, top: 530 }}>
            <OggClean pose="alert" scale={1.05} />
          </div>
        </div>
      )}

      {/* SHOT 10: Prehistoric African Savanna Campfire */}
      {scene === "savanna_campfire" && (
        <div style={{ position: "relative", width: 1920, height: 1080, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <svg viewBox="0 0 1920 1080" width="100%" height="100%" style={{ position: "absolute" }}>
            {/* Acacia Tree Silhouette */}
            <path
              d="M 1420,840 L 1435,680 Q 1480,620 1560,580 Q 1460,570 1435,530 Q 1380,570 1340,620 L 1420,840 Z"
              fill="#22222A"
            />
            <ellipse cx="1560" cy="560" rx="140" ry="24" fill="#22222A" />
            <ellipse cx="1360" cy="580" rx="120" ry="20" fill="#22222A" />
            <ellipse cx="1450" cy="520" rx="160" ry="28" fill="#22222A" />

            {/* Glowing Stone Campfire Pit in center */}
            <g transform="translate(920, 800)">
              <ellipse cx="40" cy="40" rx="90" ry="22" fill="#E76F51" opacity="0.3" />
              {/* Stones */}
              <circle cx="-10" cy="35" r="14" fill="#6C757D" stroke={C.ink} strokeWidth="3" />
              <circle cx="20" cy="42" r="15" fill="#495057" stroke={C.ink} strokeWidth="3" />
              <circle cx="55" cy="40" r="14" fill="#6C757D" stroke={C.ink} strokeWidth="3" />
              <circle cx="85" cy="36" r="13" fill="#495057" stroke={C.ink} strokeWidth="3" />
              {/* Animated Flames */}
              <path
                d={`M 15,35 Q 40,${-15 + breath * 3} 65,35 Q 40,${-5 - breath * 3} 15,35 Z`}
                fill="#F4A261"
                stroke={C.ink}
                strokeWidth="3"
              />
              <path
                d={`M 25,35 Q 40,${5 + breath * 2} 55,35 Q 40,${15 - breath * 2} 25,35 Z`}
                fill="#E76F51"
              />
            </g>

            {/* 3 Huddled Stick Figures in background */}
            <g transform="translate(1080, 740)">
              <circle cx="0" cy="0" r="12" fill={C.ink} />
              <line x1="0" y1="12" x2="0" y2="60" stroke={C.ink} strokeWidth="5" />
              <circle cx="45" cy="10" r="11" fill={C.ink} />
              <line x1="45" y1="21" x2="45" y2="60" stroke={C.ink} strokeWidth="5" />
              <circle cx="85" cy="5" r="11" fill={C.ink} />
              <line x1="85" y1="16" x2="85" y2="60" stroke={C.ink} strokeWidth="5" />
            </g>
          </svg>

          {/* Ogg in Foreground with Club */}
          <div style={{ position: "absolute", left: 600, top: 520 }}>
            <OggClean pose="alert" scale={1.25} />
          </div>
        </div>
      )}

      {/* SHOT 11: Symmetrical Diptych: Ogg at Fire vs Mo at Ren */}
      {scene === "tribal_diptych" && (
        <div style={{ position: "relative", width: 1920, height: 1080 }}>
          {/* Vertical Dividing Line */}
          <svg viewBox="0 0 1920 1080" width="100%" height="100%" style={{ position: "absolute" }}>
            <line x1="960" y1="180" x2="960" y2="900" stroke={C.inkFaint} strokeWidth="3" strokeDasharray="10 10" />
            <text x="480" y="240" fill={C.inkSecondary} fontFamily={CLEAN_FONTS.mono} fontSize="14" fontWeight="700" letterSpacing="3" textAnchor="middle">
              100,000 BCE · FORAGING CLAN
            </text>
            <text x="1440" y="240" fill={C.inkSecondary} fontFamily={CLEAN_FONTS.mono} fontSize="14" fontWeight="700" letterSpacing="3" textAnchor="middle">
              TODAY · TUESDAY AFTERNOON
            </text>
          </svg>

          {/* Ogg on left */}
          <div style={{ position: "absolute", left: 380, top: 460 }}>
            <OggClean pose="alert" scale={1.2} />
          </div>

          {/* Mo on right with identical eyebrow tilt */}
          <div style={{ position: "absolute", left: 1340, top: 460 }}>
            <MoClean pose="pocket" expression="anxious" scale={1.2} />
          </div>
        </div>
      )}

      {/* SHOT 12: Logic with Apartment Chart vs Ogg Pulling Giant PANIC Lever */}
      {scene === "panic_lever" && (
        <div style={{ position: "relative", width: 1920, height: 1080 }}>
          {/* Apartment Chart on left */}
          <svg viewBox="0 0 1920 1080" width="100%" height="100%" style={{ position: "absolute" }}>
            <g transform="translate(420, 380)">
              {/* Architectural Chart on Easel */}
              <rect x="0" y="0" width="220" height="160" rx="4" fill="#FFFFFF" stroke={C.ink} strokeWidth="3.5" />
              {/* Apartment Building drawing */}
              <rect x="50" y="30" width="120" height="110" fill="#E0FBFC" stroke={C.ink} strokeWidth="2.5" />
              <rect x="70" y="45" width="20" height="20" fill="#FFFFFF" stroke={C.ink} strokeWidth="2" />
              <rect x="110" y="45" width="20" height="20" fill="#FFFFFF" stroke={C.ink} strokeWidth="2" />
              <text x="110" y="20" fill={C.blue} fontFamily={CLEAN_FONTS.mono} fontSize="11" fontWeight="800" textAnchor="middle">
                APARTMENT / TV BED
              </text>
            </g>

            {/* Giant Brass PANIC Lever on right */}
            <g transform="translate(1360, 580)">
              <rect x="0" y="160" width="160" height="60" rx="6" fill="#3D405B" stroke={C.ink} strokeWidth="4" />
              <text x="80" y="200" fill="#E63946" fontFamily={CLEAN_FONTS.mono} fontSize="22" fontWeight="900" textAnchor="middle" letterSpacing="4">
                PANIC
              </text>
              {/* Lever arm angled down in full pull */}
              <line x1="80" y1="160" x2="30" y2="40" stroke="#E09F2B" strokeWidth="16" strokeLinecap="round" />
              <line x1="80" y1="160" x2="30" y2="40" stroke={C.ink} strokeWidth="4" strokeLinecap="round" />
              <circle cx="25" cy="35" r="24" fill="#E63946" stroke={C.ink} strokeWidth="4" />
            </g>
          </svg>

          {/* Logic pointing */}
          <div style={{ position: "absolute", left: 660, top: 420 }}>
            <LogicClean pose="holdingBoard" scale={1.2} />
          </div>

          {/* Ogg throwing weight onto lever */}
          <div style={{ position: "absolute", left: 1180, top: 480 }}>
            <OggClean pose="alert" scale={1.2} flip={true} />
          </div>
        </div>
      )}

      {/* SHOT 13: 4 Working Memory Battery Slot Gauges */}
      {scene === "working_memory_gauges" && (
        <div style={{ position: "relative", width: 1920, height: 1080, display: "flex", alignItems: "center", justifyContent: "center" }}>
          {/* Cognitive Load Battery Slots floating above Mo */}
          <svg viewBox="0 0 1920 1080" width="100%" height="100%" style={{ position: "absolute" }}>
            <g transform="translate(560, 240)">
              <text x="400" y="30" fill={C.inkSecondary} fontFamily={CLEAN_FONTS.mono} fontSize="16" fontWeight="800" letterSpacing="3" textAnchor="middle">
                WORKING MEMORY CAPACITY (4 SLOTS)
              </text>

              {/* Slot 1: SELF-SURVEILLANCE (AMBER) */}
              <g transform="translate(0, 60)">
                <rect x="0" y="0" width="180" height="50" rx="6" fill="#F4A261" stroke={C.ink} strokeWidth="3" />
                <text x="90" y="32" fill="#FFFFFF" fontFamily={CLEAN_FONTS.mono} fontSize="11" fontWeight="800" textAnchor="middle">
                  SELF-POSTURE
                </text>
              </g>

              {/* Slot 2: SELF-SURVEILLANCE (AMBER) */}
              <g transform="translate(200, 60)">
                <rect x="0" y="0" width="180" height="50" rx="6" fill="#E76F51" stroke={C.ink} strokeWidth="3" />
                <text x="90" y="32" fill="#FFFFFF" fontFamily={CLEAN_FONTS.mono} fontSize="11" fontWeight="800" textAnchor="middle">
                  VOICE TELEMETRY
                </text>
              </g>

              {/* Slot 3: SELF-SURVEILLANCE (AMBER) */}
              <g transform="translate(400, 60)">
                <rect x="0" y="0" width="180" height="50" rx="6" fill="#D62828" stroke={C.ink} strokeWidth="3" />
                <text x="90" y="32" fill="#FFFFFF" fontFamily={CLEAN_FONTS.mono} fontSize="11" fontWeight="800" textAnchor="middle">
                  ARM PLACEMENT
                </text>
              </g>

              {/* Slot 4: ACTUAL SPEECH (FLICKERING GREEN) */}
              <g transform="translate(600, 60)">
                <rect x="0" y="0" width="180" height="50" rx="6" fill="#2A9D8F" stroke={C.ink} strokeWidth="3" opacity={0.65 + 0.35 * Math.sin(frame * 0.4)} />
                <text x="90" y="32" fill="#FFFFFF" fontFamily={CLEAN_FONTS.mono} fontSize="11" fontWeight="800" textAnchor="middle">
                  ACTUAL TALK
                </text>
              </g>
            </g>
          </svg>

          {/* Mo centered */}
          <div style={{ position: "absolute", top: 480 }}>
            <MoClean pose="pocket" expression="anxious" scale={1.3} />
          </div>
        </div>
      )}

      {/* SHOT 14: Spotlight Effect (Gilovich 2000) */}
      {scene === "spotlight_effect" && (
        <div style={{ position: "relative", width: 1920, height: 1080 }}>
          {/* Blinding conical spotlight over Mo */}
          <svg viewBox="0 0 1920 1080" width="100%" height="100%" style={{ position: "absolute" }}>
            <polygon points="560,0 280,1080 840,1080" fill={C.spotlightBeam} />
            <ellipse cx="560" cy="840" rx="280" ry="70" fill={C.spotlightFloor} />
          </svg>

          {/* Mo inside beam */}
          <div style={{ position: "absolute", left: 450, top: 440 }}>
            <MoClean pose="pocket" expression="shocked" scale={1.25} />
          </div>

          {/* Ren reading calmly in natural soft light */}
          <div style={{ position: "absolute", left: 1320, top: 440 }}>
            <RenClean pose="reading" expression="peaceful" scale={1.25} flip={true} />
          </div>
        </div>
      )}

      {/* SHOT 15: High Self-Monitoring CCTV Security Cameras */}
      {scene === "cctv_self_monitoring" && (
        <div style={{ position: "relative", width: 1920, height: 1080, display: "flex", alignItems: "center", justifyContent: "center" }}>
          {/* Three Articulated CCTV Camera Lenses pointing right at Mo's face */}
          <svg viewBox="0 0 1920 1080" width="100%" height="100%" style={{ position: "absolute" }}>
            {/* Camera 1 (Top Left) */}
            <g transform="translate(680, 360)">
              <rect x="0" y="0" width="110" height="60" rx="8" fill="#2E4057" stroke={C.ink} strokeWidth="3.5" />
              <circle cx="110" cy="30" r="22" fill="#1E1E24" stroke={C.ink} strokeWidth="3" />
              <circle cx="110" cy="30" r="12" fill="#E63946" />
              <line x1="-30" y1="-20" x2="10" y2="20" stroke={C.ink} strokeWidth="6" />
            </g>

            {/* Camera 2 (Top Right) */}
            <g transform="translate(1120, 360)">
              <rect x="0" y="0" width="110" height="60" rx="8" fill="#2E4057" stroke={C.ink} strokeWidth="3.5" />
              <circle cx="0" cy="30" r="22" fill="#1E1E24" stroke={C.ink} strokeWidth="3" />
              <circle cx="0" cy="30" r="12" fill="#E63946" />
              <line x1="140" y1="-20" x2="100" y2="20" stroke={C.ink} strokeWidth="6" />
            </g>

            {/* Camera 3 (Center High) */}
            <g transform="translate(900, 220)">
              <rect x="0" y="0" width="120" height="65" rx="8" fill="#2E4057" stroke={C.ink} strokeWidth="3.5" />
              <circle cx="60" cy="65" r="24" fill="#1E1E24" stroke={C.ink} strokeWidth="3" />
              <circle cx="60" cy="65" r="14" fill="#E63946" />
            </g>
          </svg>

          {/* Mo wincing in center */}
          <div style={{ position: "absolute", top: 450 }}>
            <MoClean pose="pocket" expression="anxious" scale={1.3} />
          </div>
        </div>
      )}

      {/* SHOT 16: Mo Hiding Behind Smiling Cardboard Cutout */}
      {scene === "cardboard_cutout" && (
        <div style={{ position: "relative", width: 1920, height: 1080 }}>
          {/* Mo behind flat cardboard cutout of suit figure */}
          <div style={{ position: "absolute", left: 560, top: 440 }}>
            <MoClean pose="pocket" expression="anxious" scale={1.2} />

            {/* Cardboard Cutout Mannequin positioned in front */}
            <svg style={{ position: "absolute", left: -30, top: 20, width: 280, height: 360 }} viewBox="0 0 280 360">
              {/* Stand bracket */}
              <line x1="140" y1="310" x2="140" y2="350" stroke="#B08968" strokeWidth="10" />
              <polygon points="110,350 170,350 140,310" fill="#DDB892" stroke={C.ink} strokeWidth="3" />

              {/* Smiling Corporate Suit Silhouette */}
              <ellipse cx="140" cy="80" rx="42" ry="46" fill="#F8F9FA" stroke={C.ink} strokeWidth="3.5" />
              <circle cx="128" cy="76" r="3.5" fill={C.ink} />
              <circle cx="152" cy="76" r="3.5" fill={C.ink} />
              {/* Frozen plastic smile */}
              <path d="M 125,92 Q 140,108 155,92" fill="none" stroke={C.ink} strokeWidth="3.5" />

              {/* Business Suit & Red Tie */}
              <path d="M 95,135 L 185,135 L 195,310 L 85,310 Z" fill="#2B2D42" stroke={C.ink} strokeWidth="3.5" />
              <path d="M 134,140 L 146,140 L 143,230 L 137,230 Z" fill="#E63946" stroke={C.ink} strokeWidth="2" />
            </svg>
          </div>

          {/* Ren looking gently curious across table */}
          <div style={{ position: "absolute", left: 1220, top: 440 }}>
            <RenClean pose="tea" expression="smiling" scale={1.2} flip={true} />
          </div>
        </div>
      )}

      {/* SHOT 17: The Liking Gap — Tangled Thought Clouds */}
      {scene === "liking_gap_scribbles" && (
        <div style={{ position: "relative", width: 1920, height: 1080 }}>
          {/* Mo on Left */}
          <div style={{ position: "absolute", left: 540, top: 450 }}>
            <MoClean pose="pocket" expression="anxious" scale={1.2} />
            {/* Mo's Thought Cloud: "DID I SOUND STUPID?" */}
            <svg style={{ position: "absolute", left: -40, top: -140, width: 280, height: 130 }} viewBox="0 0 280 130">
              <path
                d="M 50,40 C 30,30 20,60 30,80 C 15,95 40,115 65,110 C 80,125 125,125 140,110 C 160,120 190,110 195,90 C 215,85 210,50 190,40 C 185,20 150,15 135,30 C 115,10 70,15 50,40 Z"
                fill="#FFFFFF"
                stroke={C.ink}
                strokeWidth="3.5"
              />
              <text x="115" y="72" fill={C.ink} fontFamily={CLEAN_FONTS.mono} fontSize="13" fontWeight="800" textAnchor="middle">
                "DID I SOUND DUMB?"
              </text>
            </svg>
          </div>

          {/* Ren on Right */}
          <div style={{ position: "absolute", left: 1180, top: 450 }}>
            <RenClean pose="tea" expression="shySelfConscious" scale={1.2} flip={true} />
            {/* Ren's Thought Cloud: "IS MY BREATH OKAY?" */}
            <svg style={{ position: "absolute", left: -40, top: -140, width: 280, height: 130 }} viewBox="0 0 280 130">
              <path
                d="M 50,40 C 30,30 20,60 30,80 C 15,95 40,115 65,110 C 80,125 125,125 140,110 C 160,120 190,110 195,90 C 215,85 210,50 190,40 C 185,20 150,15 135,30 C 115,10 70,15 50,40 Z"
                fill="#FFFFFF"
                stroke={C.ink}
                strokeWidth="3.5"
              />
              <text x="115" y="72" fill={C.ink} fontFamily={CLEAN_FONTS.mono} fontSize="13" fontWeight="800" textAnchor="middle">
                "IS MY VOICE SQUEAKY?"
              </text>
            </svg>
          </div>
        </div>
      )}

      {/* SHOT 18: Inside Ren's Head — Reverse Camera */}
      {scene === "reverse_camera_ren" && (
        <div style={{ position: "relative", width: 1920, height: 1080, display: "flex", alignItems: "center", justifyContent: "center" }}>
          {/* Ren Close-Up with Shy Smile */}
          <div style={{ position: "absolute", top: 420 }}>
            <RenClean pose="tea" expression="shySelfConscious" scale={1.35} />

            {/* Minimalist thought bubble: tiny spilled coffee cup */}
            <svg style={{ position: "absolute", left: 180, top: -90, width: 140, height: 110 }} viewBox="0 0 140 110">
              <ellipse cx="70" cy="55" rx="55" ry="38" fill="#FFFFFF" stroke={C.ink} strokeWidth="3" />
              {/* Spilled cup icon */}
              <g transform="translate(50, 40) rotate(35)">
                <rect x="0" y="0" width="22" height="24" rx="3" fill="#FFFFFF" stroke={C.ink} strokeWidth="2.5" />
                <path d="M 22,6 C 28,6 28,18 22,18" fill="none" stroke={C.ink} strokeWidth="2" />
                <ellipse cx="28" cy="24" rx="8" ry="4" fill="#6F4E37" />
              </g>
              {/* Question mark */}
              <text x="96" y="65" fill={C.red} fontFamily={CLEAN_FONTS.mono} fontSize="24" fontWeight="900">
                ?
              </text>
            </svg>
          </div>
        </div>
      )}

      {/* SHOT 19: The Crooked Laugh — Two Humans Relaxing */}
      {scene === "crooked_laugh" && (
        <div style={{ position: "relative", width: 1920, height: 1080 }}>
          {/* Mo with crooked honest grin */}
          <div style={{ position: "absolute", left: 560, top: 450 }}>
            <MoClean pose="pocket" expression="crookedSmile" scale={1.25} />
          </div>

          {/* Ren laughing warmly */}
          <div style={{ position: "absolute", left: 1180, top: 450 }}>
            <RenClean pose="laugh" expression="warmLaugh" scale={1.25} flip={true} />
          </div>
        </div>
      )}

      {/* SHOT 20: The Turn — Stepping Off the Wooden Platform */}
      {scene === "cancel_the_show" && (
        <div style={{ position: "relative", width: 1920, height: 1080 }}>
          <svg viewBox="0 0 1920 1080" width="100%" height="100%" style={{ position: "absolute" }}>
            {/* Raised Wooden Audition Stage on left (abandoned) */}
            <rect x="220" y="780" width="480" height="30" rx="4" fill="#3D405B" stroke={C.ink} strokeWidth="3.5" />
            <polygon points="220,780 700,780 660,720 180,720" fill="#D3A274" stroke={C.ink} strokeWidth="3.5" />

            {/* Director folding chair collapsed flat */}
            <g transform="translate(360, 660)">
              <line x1="20" y1="20" x2="80" y2="70" stroke={C.ink} strokeWidth="4" />
              <line x1="80" y1="20" x2="20" y2="70" stroke={C.ink} strokeWidth="4" />
              <rect x="24" y="25" width="52" height="10" rx="2" fill="#E63946" stroke={C.ink} strokeWidth="2.5" />
            </g>

            {/* Stepped down arrow */}
            <path d="M 680,740 Q 740,730 780,780" fill="none" stroke={C.green} strokeWidth="4" strokeDasharray="6 6" />
          </svg>

          {/* Mo stepping forward onto normal floorboards */}
          <div style={{ position: "absolute", left: 880, top: 440 }}>
            <MoClean pose="pocket" expression="happy" scale={1.25} />
          </div>
        </div>
      )}

      {/* SHOT 21: The Golden Lantern — Reclaiming Working Memory */}
      {scene === "curiosity_lantern" && (
        <div style={{ position: "relative", width: 1920, height: 1080 }}>
          {/* Warm Golden Lantern Beam radiating from Mo toward Ren */}
          <svg viewBox="0 0 1920 1080" width="100%" height="100%" style={{ position: "absolute" }}>
            <defs>
              <linearGradient id="lantern-gradient" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#F4A261" stopOpacity="0.6" />
                <stop offset="100%" stopColor="#F4A261" stopOpacity="0.05" />
              </linearGradient>
            </defs>
            <polygon points="620,540 1480,440 1480,820 620,640" fill="url(#lantern-gradient)" />
          </svg>

          {/* Mo on Left */}
          <div style={{ position: "absolute", left: 450, top: 450 }}>
            <MoClean pose="pocket" expression="happy" scale={1.25} />
          </div>

          {/* Ren on Right bathed in warm golden light */}
          <div style={{ position: "absolute", left: 1300, top: 450 }}>
            <RenClean pose="reading" expression="smiling" scale={1.25} flip={true} />
          </div>
        </div>
      )}

      {/* SHOT 22: Freedom — Ogg by Hearth & Logic Relaxing */}
      {scene === "hearth_peace" && (
        <div style={{ position: "relative", width: 1920, height: 1080 }}>
          <svg viewBox="0 0 1920 1080" width="100%" height="100%" style={{ position: "absolute" }}>
            {/* Warm Glowing Hearth / Fireplace on left */}
            <g transform="translate(420, 620)">
              <rect x="0" y="0" width="240" height="220" rx="8" fill="#F4F1EA" stroke={C.ink} strokeWidth="4" />
              <path d="M 40,220 L 40,90 Q 120,50 200,90 L 200,220 Z" fill="#2B2D42" />
              {/* Embers */}
              <ellipse cx="120" cy="205" rx="60" ry="16" fill="#E76F51" />
              <ellipse cx="120" cy="200" rx="40" ry="10" fill="#F4A261" />
            </g>
          </svg>

          {/* Ogg peaceful cross-legged by hearth */}
          <div style={{ position: "absolute", left: 740, top: 510 }}>
            <OggClean pose="peaceful" scale={1.2} />
          </div>

          {/* Logic relaxed clipping marker */}
          <div style={{ position: "absolute", left: 1140, top: 440 }}>
            <LogicClean pose="holdingBoard" scale={1.2} />
          </div>
        </div>
      )}

      {/* SHOT 23: Mo Approaches Ren's Table and Speaks */}
      {scene === "honest_greeting" && (
        <div style={{ position: "relative", width: 1920, height: 1080 }}>
          {/* Mo standing beside Ren's table with warm natural smile */}
          <div style={{ position: "absolute", left: 620, top: 430 }}>
            <MoClean pose="pocket" expression="crookedSmile" scale={1.25} />
          </div>

          {/* Ren closing novel with welcoming bright smile */}
          <div style={{ position: "absolute", left: 1120, top: 450 }}>
            <RenClean pose="lookup" expression="smiling" scale={1.25} flip={true} />
          </div>
        </div>
      )}

      {/* SHOT 24: Coda — Two Slightly Awkward Primates at Table */}
      {scene === "coda_two_primates" && (
        <div style={{ position: "relative", width: 1920, height: 1080 }}>
          {/* Warm Amber Pendant Lamp overhead */}
          <svg viewBox="0 0 1920 1080" width="100%" height="100%" style={{ position: "absolute" }}>
            <line x1="960" y1="0" x2="960" y2="280" stroke={C.ink} strokeWidth="3" />
            <path d="M 910,320 C 910,280 1010,280 1010,320 Z" fill="#2E4057" stroke={C.ink} strokeWidth="3.5" />
            <ellipse cx="960" cy="320" rx="50" ry="14" fill="#F4A261" />
            {/* Soft Warm Cone */}
            <polygon points="960,320 620,860 1300,860" fill="rgba(244,162,97,0.14)" />
          </svg>

          {/* Mo on Left, seated talking */}
          <div style={{ position: "absolute", left: 680, top: 460 }}>
            <MoClean pose="cup" expression="happy" scale={1.2} />
          </div>

          {/* Ren on Right, seated listening */}
          <div style={{ position: "absolute", left: 1080, top: 460 }}>
            <RenClean pose="tea" expression="smiling" scale={1.2} flip={true} />
          </div>
        </div>
      )}
    </AbsoluteFill>
  );
};
