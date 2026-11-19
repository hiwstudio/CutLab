import React from "react";
import { C, MONO, SANS, Stage, ease, useMs } from "./lib";

/* Every timestamp below is a word start from the Timing Map (motion/src/
   timing.json), not a guess. The comment names the word it lands on. */

/* ── scene_022 · 9080ms ────────────────────────────────────────────────────
   "...three computers holding, between them, about 70 kilobytes of memory."
   three@4860  computers@5200  70@7500  kilobytes@8000
   The number IS the fact here, so this is one of only two inserts with type. */
export const Scene022: React.FC = () => {
  const ms = useMs();
  const mods = ["CCS", "FDS", "AACS"];
  // 70KB against a 12MB phone photo, to scale: the gold sliver is 0.0057% wide.
  const barW = 1420;
  const grow = ease(ms, 7500, 8600);
  const n = Math.round(ease(ms, 7500, 8000, 0, 70));
  return (
    <Stage seed={22}>
      <div style={{ position: "absolute", inset: 0, display: "flex",
        flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 74 }}>
        <div style={{ display: "flex", gap: 40 }}>
          {mods.map((m, i) => {
            const t0 = 4860 + i * 170;           // labels land across "three computers"
            const o = ease(ms, t0, t0 + 520);
            // The empty housings are on screen from the first second: the line
            // opens with "what is doing all of this", so the frame must not sit
            // black for 4.8s waiting for the anchor word.
            const shell = ease(ms, 300 + i * 220, 300 + i * 220 + 700);
            return (
              <div key={m} style={{
                width: 268, height: 158,
                border: `1px solid rgba(125,150,190,${0.16 + 0.5 * o})`,
                borderRadius: 3, opacity: 0.25 * shell + 0.75 * o + 0.25 * shell,
                transform: `translateY(${(1 - shell) * 14}px)`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontFamily: MONO, fontSize: 34, letterSpacing: 4,
                color: C.text, background: "rgba(125,150,190,0.04)" }}>
                <span style={{ opacity: o }}>{m}</span>
              </div>
            );
          })}
        </div>
        <div style={{ opacity: ease(ms, 7300, 7800) }}>
          <div style={{ width: barW, height: 15, background: "rgba(125,150,190,0.10)",
            position: "relative", overflow: "hidden" }}>
            <div style={{ position: "absolute", left: 0, top: 0, bottom: 0,
              width: Math.max(3, 3 * grow), background: C.gold,
              boxShadow: `0 0 22px ${C.gold}` }} />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between",
            width: barW, marginTop: 22, fontFamily: MONO, fontSize: 26,
            letterSpacing: 3, color: C.dim }}>
            <span style={{ color: C.gold }}>{n} KILOBYTES</span>
            <span>ONE PHONE PHOTOGRAPH</span>
          </div>
        </div>
      </div>
    </Stage>
  );
};

/* ── scene_024 · 3920ms ────────────────────────────────────────────────────
   "The code is assembly, written by hand, in the 1970s."
   assembly@680  hand@1940  1970s@2860
   A printout, not a diagram: the listing itself is the image. */
export const Scene024: React.FC = () => {
  const ms = useMs();
  const lines = [
    "CCS  LDA  #$1F", "     STA  FDSBUF", "     JSR  XMIT",
    "     BCC  *+4", "     LDX  #$00", "TLM  LDA  TABLE,X",
    "     STA  $0400,X", "     INX", "     CPX  #$40", "     BNE  TLM",
    "     RTS",
  ];
  return (
    <Stage seed={24}>
      <div style={{ position: "absolute", inset: 0, display: "flex",
        alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontFamily: MONO, fontSize: 52, lineHeight: 1.6,
          color: C.gold, letterSpacing: 2.5,
          // slow upward drift, as if the listing is being read down the page
          transform: `translateY(${ease(ms, 0, 3920, 70, -70)}px)` }}>
          {lines.map((l, i) => (
            <div key={i} style={{
              opacity: ease(ms, 250 + i * 170, 250 + i * 170 + 420),
              whiteSpace: "pre" }}>{l}</div>
          ))}
        </div>
      </div>
    </Stage>
  );
};

/* ── scene_015 · 8000ms ────────────────────────────────────────────────────
   "Ten years later, on the 14th of February 1990, six billion kilometers from
   home, the cameras were turned around one last time."
   1990@2180  kilometers@4560  cameras@5900  turned@6320
   A viewfinder reticle swings back toward a distant sun and settles. It must
   NOT show the dot — scene_017 is the photograph, and this only sets it up. */
export const Scene015: React.FC = () => {
  const ms = useMs();
  const sunX = 1440, sunY = 470;
  // the reticle starts pointed outward (away) and rotates home ON "turned"
  const swing = ease(ms, 5900, 7700);
  const rx = 470 + swing * (sunX - 470);
  const ry = 660 + swing * (sunY - 660);
  const settle = ease(ms, 7300, 8000);
  return (
    <Stage seed={15}>
      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
        {/* the sun at six billion kilometres: just another star, barely brighter */}
        <circle cx={sunX} cy={sunY} r={6} fill="#fff6e2"
          opacity={ease(ms, 600, 2200)}
          style={{ filter: "drop-shadow(0 0 22px #fff6e2)" }} />
        <circle cx={sunX} cy={sunY} r={16} fill="none" stroke="#fff6e2"
          strokeWidth={1.1} opacity={ease(ms, 600, 2200) * 0.32} />
        <g opacity={ease(ms, 4400, 5600) * (0.55 + 0.45 * settle)}>
          <circle cx={rx} cy={ry} r={92} fill="none" stroke={C.cyan}
            strokeWidth={2.2} opacity={0.9} />
          <line x1={rx - 128} y1={ry} x2={rx - 34} y2={ry} stroke={C.cyan}
            strokeWidth={2.2} opacity={0.9} />
          <line x1={rx + 34} y1={ry} x2={rx + 128} y2={ry} stroke={C.cyan}
            strokeWidth={2.2} opacity={0.9} />
          <line x1={rx} y1={ry - 128} x2={rx} y2={ry - 34} stroke={C.cyan}
            strokeWidth={2.2} opacity={0.9} />
          <line x1={rx} y1={ry + 34} x2={rx} y2={ry + 128} stroke={C.cyan}
            strokeWidth={2.2} opacity={0.9} />
        </g>
      </svg>
    </Stage>
  );
};

/* ── scene_020 · 13000ms ───────────────────────────────────────────────────
   "The edge of that bubble is called the heliopause. On the 25th of August
   2012, Voyager 1 crossed it. The first object built by human hands to leave
   the sun's atmosphere and enter interstellar space."
   heliopause@1620  2012@4420  crossed@6420  interstellar@12020
   Replaces a sourced clip whose every frame carried burned-in labels. Textless:
   the boundary is drawn, not annotated. */
export const Scene020: React.FC = () => {
  const ms = useMs();
  const boundaryX = 1080;
  const edge = ease(ms, 700, 2400);             // the membrane forms ON "heliopause"
  // the craft crosses ON "crossed" and keeps going into the cold side
  const cross = ease(ms, 4600, 6420);
  const drift = ease(ms, 6420, 13000);
  const px = 250 + cross * (boundaryX - 250) + drift * 640;
  const outside = ease(ms, 6420, 9000);         // colour turns over as it exits
  return (
    <Stage seed={20}>
      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
        <defs>
          <linearGradient id="hp" x1="0" x2="1">
            <stop offset="0%" stopColor={C.gold} stopOpacity="0" />
            <stop offset="55%" stopColor={C.gold} stopOpacity="0.30" />
            <stop offset="100%" stopColor={C.cyan} stopOpacity="0" />
          </linearGradient>
        </defs>
        {/* the sun's wind, thinning outward */}
        <rect x={0} y={0} width={boundaryX} height={1080} fill="url(#hp)"
          opacity={edge * 0.9} />
        {/* the heliopause itself: a soft membrane, no label */}
        <path d={`M ${boundaryX} 0 Q ${boundaryX + 150} 540 ${boundaryX} 1080`}
          fill="none" stroke={C.gold} strokeWidth={2.4} opacity={edge * 0.75} />
        <path d={`M ${boundaryX} 0 Q ${boundaryX + 150} 540 ${boundaryX} 1080`}
          fill="none" stroke={C.gold} strokeWidth={22} opacity={edge * 0.10} />
        {/* the craft: a single point, because that is all it is out there */}
        <circle cx={px} cy={540} r={7}
          fill={outside > 0.5 ? C.cyan : C.gold}
          opacity={ease(ms, 2600, 3800)}
          style={{ filter: `drop-shadow(0 0 18px ${outside > 0.5 ? "#7fd4e8" : "#e8b874"})` }} />
        <line x1={Math.max(250, px - 190)} y1={540} x2={px - 12} y2={540}
          stroke={outside > 0.5 ? C.cyan : C.gold} strokeWidth={1.2}
          opacity={ease(ms, 2600, 3800) * 0.4} />
      </svg>
    </Stage>
  );
};

/* Shared telemetry grid for 032 → 041. Same component, opposite direction:
   032 collapses into the locked pattern, 041 resolves out of it. `health`
   runs 1 (readable) → 0 (stuck) and the rows follow it. */
const Telemetry: React.FC<{ health: number; seed: number }> = ({ health, seed }) => {
  const rows = 12, cols = 50;
  const cells: React.ReactNode[] = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      // deterministic per-cell value; when health→0 every row collapses to the
      // SAME repeating pattern, which is what "unchanging ones and zeroes" is
      const varied = ((r * 31 + c * 17 + seed) % 7) / 7;
      const locked = c % 2;
      const v = health * varied + (1 - health) * locked;
      cells.push(
        <div key={`${r}-${c}`} style={{
          width: 22, height: 22,
          background: v > 0.5 ? C.cyan : "transparent",
          border: v > 0.5 ? "none" : `1px solid rgba(125,212,232,0.13)`,
          opacity: 0.34 + 0.66 * v }} />
      );
    }
  }
  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${cols}, 22px)`,
      gap: 9 }}>{cells}</div>
  );
};

/* ── scene_032 · 11760ms ───────────────────────────────────────────────────
   "...nothing came back that anyone could read, which meant the engineers
   were blind."   blind@3820
   Textless: the collapse is the statement. */
export const Scene032: React.FC = () => {
  const ms = useMs();
  const health = 1 - ease(ms, 2100, 3820);      // fully locked ON "blind"
  return (
    <Stage seed={32}>
      <div style={{ position: "absolute", inset: 0, display: "flex",
        alignItems: "center", justifyContent: "center" }}>
        <Telemetry health={health} seed={3} />
      </div>
    </Stage>
  );
};

/* ── scene_035 · 10280ms ───────────────────────────────────────────────────
   "...they sent what they called a poke ... in the hope that something
   readable might fall out."   poke@3040  readable@8880
   One ring goes out, and a long time later something faint comes back. */
export const Scene035: React.FC = () => {
  const ms = useMs();
  const cx = 300, cy = 540;
  const rings = [0, 1, 2].map((i) => {
    const t0 = 3040 + i * 430;                  // emitted ON "poke"
    const p = ease(ms, t0, t0 + 4200);
    return { r: 40 + p * 1500, o: (1 - p) * 0.5 };
  });
  const back = ease(ms, 8880, 10280) * 0.9;     // the faint reply, ON "readable"
  const base = ease(ms, 200, 1100);             // both endpoints exist from the start
  return (
    <Stage seed={35}>
      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
        {/* the 24-billion-km gap, drawn faintly so the frame is never empty */}
        <line x1={cx} y1={cy} x2={1640} y2={cy} stroke={C.dim}
          strokeWidth={1} strokeDasharray="3 22" opacity={base * 0.5} />
        {rings.map((g, i) => (
          <circle key={i} cx={cx} cy={cy} r={g.r} fill="none"
            stroke={C.gold} strokeWidth={3} opacity={g.o} />
        ))}
        <circle cx={cx} cy={cy} r={16} fill={C.gold}
          opacity={base * 0.95} style={{ filter: "drop-shadow(0 0 26px #e8b874)" }} />
        <circle cx={1640} cy={cy} r={9} fill={C.cyan} opacity={base * 0.6} />
        <circle cx={1640} cy={cy} r={34 + back * 46} fill="none"
          stroke={C.cyan} strokeWidth={2.4} opacity={back * 0.9} />
      </svg>
    </Stage>
  );
};

/* ── scene_041 · 10040ms ───────────────────────────────────────────────────
   "On the 20th of April, Voyager 1 reported in. Readable for the first time
   in five months. By June, all four of its surviving instruments were
   returning science again."   Readable@3400  June@6500  four@7200
   The pay-off to 032: the same grid, resolving instead of collapsing. */
export const Scene041: React.FC = () => {
  const ms = useMs();
  const health = ease(ms, 1500, 3400);          // readable ON "Readable"
  return (
    <Stage seed={41}>
      <div style={{ position: "absolute", inset: 0, display: "flex",
        flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 60 }}>
        <Telemetry health={health} seed={3} />
        <div style={{ display: "flex", gap: 30 }}>
          {[0, 1, 2, 3].map((i) => {
            const o = ease(ms, 7200 + i * 250, 7200 + i * 250 + 500);
            return (
              <div key={i} style={{ width: 172, height: 6, background: C.cyan,
                opacity: o * 0.85, boxShadow: o > 0.5 ? `0 0 16px ${C.cyan}` : "none" }} />
            );
          })}
        </div>
      </div>
    </Stage>
  );
};
