// Procedural "footage" for the concept prototypes — no real media ships with the page.
// ponytail: canvas painter stands in for proxy video; the real app plays proxies.
const LOOKS = [
  { sky: ["#070d18", "#1b2838"], far: "#0b121c", sea: ["#0b1520", "#05080d"], cliff: "#06090e", tower: "#0d131b", house: 0.72, beam: 1, rain: 1 },
  { sky: ["#232447", "#e08a5a"], far: "#3a2c45", sea: ["#3a3552", "#141626"], cliff: "#14111c", tower: "#1d1826", house: 0.3, sun: [0.62, 0.58, 0.02, "#ffcf8a"], lamp: "#ffd690" },
  { interior: 1 },
  { sky: ["#14080a", "#5a1e1a"], far: "#200c0e", sea: ["#1e1012", "#070304"], cliff: "#0b0506", tower: "#140a0b", house: 0.82, rain: 1, flash: 1, ship: 1 },
  { sky: ["#6b7b87", "#c9cfcf"], far: "#8b989d", sea: ["#5b6a71", "#34403f"], fog: 0.55, boats: 1 },
  { sky: ["#3677b3", "#bfe0f0"], far: "#5b8fa8", sea: ["#2e6a8a", "#173a4f"], cliff: "#2d3a2a", tower: "#e9e6de", house: 0.64, sun: [0.2, 0.18, 0.02, "#fff6d8"], lamp: "#c8d3d6" },
  { sky: ["#f09c52", "#f6d8a0"], far: "#c27a4e", sea: ["#b8733f", "#5a3320"], cliff: "#3b2318", tower: "#4a2c1f", house: 0.36, sun: [0.7, 0.6, 0.03, "#fff0c0"], figure: 1 },
  { sky: ["#0b1633", "#3a4e7a"], far: "#141f3a", sea: ["#18264a", "#070b18"], cliff: "#070a14", tower: "#0e1424", house: 0.58, beam: 1, stars: 1 },
];

function rng(seed) { let s = seed >>> 0 || 1; return () => (s = (s * 1664525 + 1013904223) >>> 0) / 4294967296; }

function paintScene(ctx, W, H, look, t) {
  const L = LOOKS[look] || LOOKS[0];
  ctx.save();
  const z = 1.05 + 0.04 * Math.sin(t * 0.11);
  ctx.translate(W / 2, H / 2); ctx.scale(z, z); ctx.translate(-W / 2 + Math.sin(t * 0.07) * W * 0.012, -H / 2);
  if (L.interior) paintInterior(ctx, W, H, t); else paintCoast(ctx, W, H, L, look, t);
  if (L.rain) {
    const r = rng(3); ctx.strokeStyle = "rgba(200,215,230,.16)"; ctx.lineWidth = 1; ctx.beginPath();
    for (let i = 0; i < 170; i++) {
      const x = ((r() * W * 1.3 + t * 240) % (W * 1.3)) - W * 0.15, y = (r() * H + t * 900 * (0.7 + r() * 0.3)) % H;
      ctx.moveTo(x, y); ctx.lineTo(x - 7, y + 20);
    }
    ctx.stroke();
  }
  if (L.flash && t % 4.2 < 0.1) { ctx.fillStyle = "rgba(255,235,235,.3)"; ctx.fillRect(-W, -H, W * 3, H * 3); }
  if (L.fog) {
    const g = ctx.createLinearGradient(0, H * 0.25, 0, H);
    g.addColorStop(0, "rgba(222,227,228,0)"); g.addColorStop(0.5, `rgba(222,227,228,${L.fog})`); g.addColorStop(1, `rgba(222,227,228,${L.fog * 0.5})`);
    ctx.fillStyle = g; ctx.fillRect(-W, -H, W * 3, H * 3);
  }
  ctx.restore();
  const v = ctx.createRadialGradient(W / 2, H / 2, H * 0.3, W / 2, H / 2, H * 0.95);
  v.addColorStop(0, "rgba(0,0,0,0)"); v.addColorStop(1, "rgba(0,0,0,.55)");
  ctx.fillStyle = v; ctx.fillRect(0, 0, W, H);
}

function paintCoast(ctx, W, H, L, look, t) {
  let g = ctx.createLinearGradient(0, 0, 0, H * 0.62);
  g.addColorStop(0, L.sky[0]); g.addColorStop(1, L.sky[1]);
  ctx.fillStyle = g; ctx.fillRect(-W * 0.2, -H * 0.2, W * 1.4, H * 0.85);
  if (L.stars) { const r = rng(7); ctx.fillStyle = "rgba(255,255,255,.75)"; for (let i = 0; i < 90; i++) ctx.fillRect(r() * W, r() * H * 0.5, 1.5, 1.5); }
  if (L.sun) {
    const [sx, sy, sr, sc] = L.sun, rg = ctx.createRadialGradient(sx * W, sy * H, 0, sx * W, sy * H, sr * W * 9);
    rg.addColorStop(0, sc); rg.addColorStop(0.11, sc); rg.addColorStop(0.13, sc + "88"); rg.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = rg; ctx.fillRect(-W * 0.2, -H * 0.2, W * 1.4, H * 0.85);
  }
  const hy = H * 0.62;
  ctx.fillStyle = L.far; ctx.beginPath(); ctx.moveTo(-W * 0.2, hy);
  for (let x = -W * 0.2; x <= W * 1.2; x += W / 50) ctx.lineTo(x, hy - H * (0.03 + 0.025 * Math.sin(x * 0.011 + look) + 0.012 * Math.sin(x * 0.041)));
  ctx.lineTo(W * 1.2, hy); ctx.fill();
  g = ctx.createLinearGradient(0, hy, 0, H);
  g.addColorStop(0, L.sea[0]); g.addColorStop(1, L.sea[1]);
  ctx.fillStyle = g; ctx.fillRect(-W * 0.2, hy, W * 1.4, H * 0.6);
  ctx.strokeStyle = "rgba(255,255,255,.07)"; ctx.lineWidth = 1.2;
  for (let i = 0; i < 14; i++) {
    const y = hy + i * i * H * 0.0021 + 4; ctx.beginPath();
    for (let x = -W * 0.2; x <= W * 1.2; x += W / 60) ctx.lineTo(x, y + Math.sin(x * 0.02 + t * 1.3 + i) * (1 + i * 0.35));
    ctx.stroke();
  }
  if (L.boats) { ctx.fillStyle = "rgba(40,48,52,.55)"; [0.22, 0.47, 0.71].forEach((bx, i) => { const x = W * bx + Math.sin(t * 0.3 + i) * 6, y = hy + H * (0.03 + i * 0.02); ctx.fillRect(x - 18, y, 36, 5); ctx.fillRect(x - 1, y - 22, 2, 22); }); }
  if (L.ship) {
    ctx.save(); ctx.translate(W * 0.28, hy + H * 0.05); ctx.rotate(-0.22 + Math.sin(t * 0.8) * 0.04);
    ctx.fillStyle = "#050203"; ctx.beginPath(); ctx.moveTo(-70, 0); ctx.lineTo(70, -8); ctx.lineTo(52, 18); ctx.lineTo(-58, 18); ctx.fill();
    ctx.fillRect(-6, -70, 4, 70); ctx.fillRect(24, -52, 3, 46); ctx.restore();
  }
  if (!L.house) return;
  const cx = W * L.house;
  ctx.fillStyle = L.cliff; ctx.beginPath();
  ctx.moveTo(cx - W * 0.22, H * 1.2); ctx.lineTo(cx - W * 0.12, hy + H * 0.02); ctx.lineTo(cx - W * 0.03, hy - H * 0.08);
  ctx.lineTo(cx + W * 0.08, hy - H * 0.09); ctx.lineTo(cx + W * 0.3, hy + H * 0.05); ctx.lineTo(cx + W * 0.36, H * 1.2); ctx.fill();
  const by = hy - H * 0.085, th = H * 0.26, bw = W * 0.028, tw = W * 0.018;
  ctx.fillStyle = L.tower; ctx.beginPath();
  ctx.moveTo(cx - bw, by); ctx.lineTo(cx - tw, by - th); ctx.lineTo(cx + tw, by - th); ctx.lineTo(cx + bw, by); ctx.fill();
  ctx.fillRect(cx - tw * 1.45, by - th - H * 0.012, tw * 2.9, H * 0.012);
  ctx.fillStyle = L.lamp || "#ffe6a0"; ctx.fillRect(cx - tw * 0.8, by - th - H * 0.05, tw * 1.6, H * 0.038);
  ctx.fillStyle = L.tower; ctx.beginPath();
  ctx.moveTo(cx - tw * 1.15, by - th - H * 0.05); ctx.lineTo(cx, by - th - H * 0.085); ctx.lineTo(cx + tw * 1.15, by - th - H * 0.05); ctx.fill();
  if (L.figure) { ctx.fillStyle = "#2a170f"; ctx.fillRect(cx + W * 0.1, hy - H * 0.14, 7, 34); ctx.beginPath(); ctx.arc(cx + W * 0.1 + 3.5, hy - H * 0.15, 6, 0, 7); ctx.fill(); }
  if (L.beam) {
    const lx = cx, ly = by - th - H * 0.031, d = Math.cos(t * 0.9), len = W * 1.2;
    ctx.save(); ctx.globalCompositeOperation = "lighter";
    const bg = ctx.createLinearGradient(lx, ly, lx + d * len, ly);
    bg.addColorStop(0, "rgba(255,236,170,.5)"); bg.addColorStop(1, "rgba(255,236,170,0)");
    ctx.fillStyle = bg; ctx.beginPath(); ctx.moveTo(lx, ly);
    ctx.lineTo(lx + d * len, ly - H * (0.02 + 0.09 * Math.abs(d))); ctx.lineTo(lx + d * len, ly + H * (0.02 + 0.07 * Math.abs(d))); ctx.fill();
    ctx.restore();
  }
}

function paintInterior(ctx, W, H, t) {
  let g = ctx.createLinearGradient(0, 0, W, H);
  g.addColorStop(0, "#2a1c12"); g.addColorStop(1, "#140d08");
  ctx.fillStyle = g; ctx.fillRect(-W * 0.2, -H * 0.2, W * 1.4, H * 1.4);
  const wx = W * 0.56, wy = H * 0.14, ww = W * 0.3, wh = H * 0.42;
  g = ctx.createLinearGradient(0, wy, 0, wy + wh); g.addColorStop(0, "#0c1630"); g.addColorStop(0.65, "#24345a"); g.addColorStop(0.66, "#0d1628"); g.addColorStop(1, "#060a14");
  ctx.fillStyle = g; ctx.fillRect(wx, wy, ww, wh);
  ctx.fillStyle = "rgba(255,236,170,.6)"; ctx.fillRect(wx + ww * (0.5 + 0.35 * Math.sin(t * 0.9)), wy + wh * 0.6, 3, 3);
  ctx.strokeStyle = "#1a110a"; ctx.lineWidth = 10; ctx.strokeRect(wx, wy, ww, wh);
  ctx.beginPath(); ctx.moveTo(wx + ww / 2, wy); ctx.lineTo(wx + ww / 2, wy + wh); ctx.moveTo(wx, wy + wh / 2); ctx.lineTo(wx + ww, wy + wh / 2); ctx.stroke();
  const lamp = ctx.createRadialGradient(W * 0.25, H * 0.52, 0, W * 0.25, H * 0.52, W * 0.42);
  const f = 0.9 + 0.06 * Math.sin(t * 7) * Math.sin(t * 3.1);
  lamp.addColorStop(0, `rgba(255,178,90,${0.55 * f})`); lamp.addColorStop(1, "rgba(255,178,90,0)");
  ctx.fillStyle = lamp; ctx.fillRect(-W * 0.2, -H * 0.2, W * 1.4, H * 1.4);
  ctx.fillStyle = "#1b120b"; ctx.fillRect(-W * 0.2, H * 0.72, W * 1.4, H * 0.5);
  ctx.fillStyle = "#ffcf8a"; ctx.beginPath(); ctx.ellipse(W * 0.25, H * 0.56, 22, 30, 0, 0, 7); ctx.fill();
  ctx.fillStyle = "#3a2817"; ctx.fillRect(W * 0.25 - 26, H * 0.6, 52, 8); ctx.fillRect(W * 0.25 - 16, H * 0.62, 32, H * 0.1);
  ctx.fillStyle = "#d9cba8"; ctx.beginPath();
  ctx.moveTo(W * 0.4, H * 0.77); ctx.lineTo(W * 0.53, H * 0.74); ctx.lineTo(W * 0.66, H * 0.77); ctx.lineTo(W * 0.66, H * 0.84); ctx.lineTo(W * 0.53, H * 0.81); ctx.lineTo(W * 0.4, H * 0.84); ctx.fill();
  ctx.strokeStyle = "rgba(60,40,20,.45)"; ctx.lineWidth = 1;
  for (let i = 0; i < 4; i++) { ctx.beginPath(); ctx.moveTo(W * 0.42, H * (0.785 + i * 0.013)); ctx.lineTo(W * 0.51, H * (0.765 + i * 0.013)); ctx.stroke(); }
}

// Overlay inserts (b-roll close-ups on V2)
function paintInsert(ctx, W, H, kind, t) {
  const g = ctx.createLinearGradient(0, 0, W, H);
  g.addColorStop(0, "#e2d5b4"); g.addColorStop(1, "#b9a57c");
  ctx.save(); const z = 1.02 + t * 0.012; ctx.translate(W / 2, H / 2); ctx.scale(z, z); ctx.translate(-W / 2, -H / 2);
  ctx.fillStyle = g; ctx.fillRect(-20, -20, W + 40, H + 40);
  ctx.strokeStyle = "rgba(70,50,30,.55)"; ctx.lineWidth = 2;
  if (kind === "map") {
    ctx.beginPath(); const r = rng(11); let y = H * 0.1;
    for (let x = W * 0.55; y < H * 0.95; y += H * 0.03) ctx.lineTo(x + (r() - 0.5) * 40 + Math.sin(y * 0.01) * 60, y);
    ctx.stroke(); ctx.setLineDash([6, 8]); ctx.beginPath(); ctx.moveTo(W * 0.18, H * 0.8); ctx.quadraticCurveTo(W * 0.35, H * 0.3, W * 0.56, H * 0.42); ctx.stroke(); ctx.setLineDash([]);
    ctx.font = "italic 34px Georgia, serif"; ctx.fillStyle = "rgba(90,40,20,.8)"; ctx.fillText("Marr Point", W * 0.6, H * 0.4);
    ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(W * 0.54, H * 0.4); ctx.lineTo(W * 0.58, H * 0.44); ctx.moveTo(W * 0.58, H * 0.4); ctx.lineTo(W * 0.54, H * 0.44); ctx.stroke();
  } else {
    for (let i = 0; i < 9; i++) {
      const y = H * (0.18 + i * 0.085); ctx.beginPath();
      for (let x = W * 0.12; x < W * (0.8 - (i === 8 ? 0.35 : 0)); x += 6) ctx.lineTo(x, y + Math.sin(x * 0.19 + i * 2) * 4 * Math.sin(x * 0.03));
      ctx.stroke();
    }
    ctx.font = "italic 38px Georgia, serif"; ctx.fillStyle = "rgba(60,30,15,.85)"; ctx.fillText("14 Oct. 1923 —", W * 0.12, H * 0.12);
  }
  ctx.restore();
}

const _thumbs = {};
function thumbFor(key) {
  if (_thumbs[key]) return _thumbs[key];
  const c = document.createElement("canvas"); c.width = 192; c.height = 108;
  const x = c.getContext("2d");
  if (typeof key === "number") paintScene(x, 192, 108, key, 2); else paintInsert(x, 192, 108, key, 0);
  return (_thumbs[key] = c.toDataURL("image/jpeg", 0.8));
}
