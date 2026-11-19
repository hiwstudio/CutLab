// Shared editor widgets + one delegated input layer. Concept shells only arrange and skin these.
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
S.tabs = {};
S.scale = 1;
const CONCEPTS = {};
const addCss = (t) => document.head.insertAdjacentHTML("beforeend", `<style>${t}</style>`);
const ACTS = { // concept files may add more
  soon: () => toast("Layout only in this prototype — this control isn't wired up"),
  capstyle: (a) => commit(`Caption style · ${a.dataset.v}`, () => { S.p.capStyle = a.dataset.v; }),
};

// ---- icons (one set, stroke 1.75) -------------------------------------------
const I = {
  play: '<path d="M7 4.5v15l12.5-7.5z" fill="currentColor"/>', pause: '<rect x="6" y="4.5" width="4" height="15" rx="1" fill="currentColor"/><rect x="14" y="4.5" width="4" height="15" rx="1" fill="currentColor"/>',
  split: '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4 8.1 15.9M14.5 14.5 20 20M8.1 8.1 12 12"/>',
  trash: '<path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
  undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>', redo: '<path d="m15 14 5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/>',
  plus: '<path d="M5 12h14M12 5v14"/>', minus: '<path d="M5 12h14"/>', x: '<path d="M18 6 6 18M6 6l12 12"/>', check: '<path d="M20 6 9 17l-5-5"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  vol: '<path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14"/>', volx: '<path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="m22 9-6 6M16 9l6 6"/>',
  lock: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>', unlock: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.9-1"/>',
  chl: '<path d="m15 18-6-6 6-6"/>', chr: '<path d="m9 18 6-6-6-6"/>', chu: '<path d="m18 15-6-6-6 6"/>', chd: '<path d="m6 9 6 6 6-6"/>',
  prev: '<path d="M19 20 9 12l10-8zM5 19V5"/>', next: '<path d="m5 4 10 8-10 8zM19 5v14"/>', send: '<path d="M12 19V5M5 12l7-7 7 7"/>',
  film: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M17 3v18M3 7.5h4M3 12h18M3 16.5h4M17 7.5h4M17 16.5h4"/>',
  music: '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>', mic: '<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M19 10v1a7 7 0 0 1-14 0v-1M12 18v4"/>',
  type: '<path d="M4 7V4h16v3M9 20h6M12 4v16"/>', cc: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M10.5 10a2.5 2.5 0 1 0 0 4M17.5 10a2.5 2.5 0 1 0 0 4"/>',
  wand: '<path d="M15 4V2M15 16v-2M8 9h2M20 9h2M17.8 11.8 19 13M17.8 6.2 19 5M3 21l9-9M12.2 6.2 11 5"/>',
  layers: '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5M2 12l10 5 10-5"/>', pointer: '<path d="m4 4 7 17 2.5-7.5L21 11z"/>',
  ripple: '<path d="M3 5v14M21 5v14M7 12h10M13 8l4 4-4 4"/>', slip: '<path d="M8 3 4 7l4 4M16 13l4 4-4 4M4 7h16M20 17H4"/>', pen: '<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  hand: '<path d="M18 11V6a2 2 0 0 0-4 0M14 10V4a2 2 0 0 0-4 0v2M10 10.5V6a2 2 0 0 0-4 0v8M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.9-6-2.3l-3.6-3.6a2 2 0 0 1 2.8-2.8L7 15"/>',
  magnet: '<path d="m6 15-4-4 6.8-6.8a7.8 7.8 0 0 1 11 11L13 22l-4-4 6.4-6.4a2.1 2.1 0 0 0-3-3zM5 8l4 4M12 15l4 4"/>',
  export: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>', image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/>',
  sliders: '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>', max: '<path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3"/>',
  fx: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  trans: '<rect x="2" y="6" width="9" height="12" rx="1.5"/><rect x="13" y="6" width="9" height="12" rx="1.5"/><path d="M9 12h6"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>', flag: '<path d="M4 22V4a1 1 0 0 1 1-1h13l-3 5 3 5H5"/>',
  history: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l4 2"/>', head: '<path d="M3 14h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a9 9 0 0 1 18 0v7a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3"/>',
};
const ic = (n, s = 16) => `<svg class="ic" width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${I[n]}</svg>`;
const playIc = (s) => ic(S.playing ? "pause" : "play", s);

// ---- render helpers ----------------------------------------------------------
function setHtml(el, html) {
  if (!el || el._h === html) return;
  const a = document.activeElement;
  if (a && a.type === "range" && el.contains(a)) return; // never yank a slider mid-drag
  el._h = html; el.innerHTML = html;
  if (el.hasAttribute("data-stick")) el.scrollTop = el.scrollHeight;
}
const X = (ms) => (ms / 1000) * S.pps;

// ---- preview compositor ------------------------------------------------------
const previewHtml = (extra = "") => `<div class="pv"><canvas width="960" height="540"></canvas><div class="pv-cap" hidden></div>${extra}</div>`;
function drawPreviews(root, force) {
  root.querySelectorAll(".pv").forEach((pv) => {
    const key = S.playhead + "|" + S.ver;
    if (!force && pv._key === key) return;
    pv._key = key;
    const cv = pv.querySelector("canvas"), ctx = cv.getContext("2d"), W = cv.width, H = cv.height, ms = S.playhead;
    ctx.fillStyle = "#000"; ctx.fillRect(0, 0, W, H);
    const main = role("main"), v = !main.muted && activeClip(main, ms);
    if (v) paintScene(ctx, W, H, v.look, (ms - v.start + v.in) / 1000);
    const ov = role("over"), o = !ov.muted && activeClip(ov, ms);
    if (o) drawOverlay(ctx, W, H, o, (ms - o.start) / 1000);
    const cap = role("cap"), cc = !cap.muted && activeClip(cap, ms), el = pv.querySelector(".pv-cap");
    el.className = "pv-cap cap-" + S.p.capStyle; el.textContent = cc ? cc.text : ""; el.hidden = !cc;
  });
}
function drawOverlay(ctx, W, H, o, t) {
  const a = Math.max(0, Math.min(1, t / 0.5, (o.dur / 1000 - t) / 0.5));
  ctx.save(); ctx.globalAlpha = a;
  if (o.overlay === "insert") paintInsert(ctx, W, H, o.look, t + o.in / 1000);
  else if (o.overlay === "title") {
    ctx.fillStyle = "#f4efe4"; ctx.textAlign = "center"; ctx.font = "400 46px Georgia, serif"; ctx.letterSpacing = "14px";
    ctx.fillText(o.text.toUpperCase(), W / 2, H * 0.48);
    ctx.font = "400 15px Georgia, serif"; ctx.letterSpacing = "6px"; ctx.fillStyle = "rgba(244,239,228,.65)";
    ctx.fillText("A STORY OF MARR POINT", W / 2, H * 0.48 + 42);
  } else {
    const x = W * 0.06, y = H * 0.7;
    ctx.fillStyle = "rgba(8,8,8,.55)"; ctx.fillRect(x, y, 310, 66); ctx.fillStyle = "#f4efe4"; ctx.fillRect(x, y, 3, 66);
    ctx.textAlign = "left"; ctx.font = "600 24px system-ui, sans-serif"; ctx.fillText(o.text, x + 20, y + 31);
    ctx.font = "400 15px system-ui, sans-serif"; ctx.fillStyle = "rgba(244,239,228,.7)"; ctx.fillText(o.sub, x + 20, y + 53);
  }
  ctx.restore();
}

// ---- waveforms: loudness is a pure function of (source, source-time) so splits stay continuous
const hash = (s) => { let x = 2166136261; for (const ch of s) x = Math.imul(x ^ ch.charCodeAt(0), 16777619); return ((x >>> 0) % 1000) / 1000; };
function amp(c, ms, r) {
  const h = hash(c.name + Math.floor(ms / 60));
  if (r === "vo") return Math.max(0.04, Math.abs(Math.sin(ms / 170) * Math.sin(ms / 1300 + 1)) * (0.55 + 0.45 * h));
  if (r === "music") return 0.35 + 0.22 * Math.sin(ms / 2400) + 0.22 * h;
  return (0.2 + 0.6 * h) * Math.abs(Math.sin(ms / 400));
}
function drawWave(cv) {
  const c = clipById(cv.dataset.id), t = c && trackOf(c.id);
  if (!c) return;
  const ctx = cv.getContext("2d"), W = cv.width, H = cv.height, g = Math.min(1.6, 2.2 * Math.pow(10, c.gain / 20));
  ctx.clearRect(0, 0, W, H); ctx.fillStyle = getComputedStyle(cv).color;
  const k = c.dur / W;
  for (let x = 0; x < W; x += 2) {
    const h = Math.max(1, Math.min(1, amp(c, c.in + x * k, t.role) * g) * (H - 6));
    ctx.fillRect(x, (H - h) / 2, 1.3, h);
  }
}
function level(r) { // for meters
  if (r === "master") return Math.min(1, Math.max(level("vo"), level("music"), level("sfx")));
  const t = role(r), c = audible(t) && activeClip(t, S.playhead);
  return c && !c.muted ? Math.min(1, amp(c, c.in + S.playhead - c.start, r) * Math.pow(10, c.gain / 20) * 1.4) : 0;
}

// ---- timeline -----------------------------------------------------------------
const timelineHtml = (corner = "") => `<div class="tl" data-tl><div class="tl-side"><div class="tl-corner">${corner}</div><div class="tl-heads"></div></div><div class="tl-scroll"><div class="tl-inner"></div></div></div>`;

function clipHtml(t, c, o) {
  const sel = S.sel?.t === "clip" && S.sel.id === c.id, w = Math.max(2, X(c.dur));
  let body = "";
  if (t.kind === "audio") body = `<canvas class="wv" data-id="${c.id}" width="${Math.min(4000, Math.round(w))}" height="56"></canvas>`;
  else if (c.look != null) body = `<div class="fs" style="background-image:url(${thumbFor(c.look)})"></div>`;
  const meta = t.kind === "audio" && c.gain ? ` <em>${db(c.gain)}</em>` : "";
  const label = o.label ? o.label(t, c) : esc(t.kind === "caption" ? c.text : c.name) + meta;
  return `<div class="cl k-${t.kind} r-${t.role}${c.overlay ? " ov-" + c.overlay : ""}${sel ? " sel" : ""}${c.muted ? " is-muted" : ""}" data-clip="${c.id}" style="left:${X(c.start)}px;width:${w}px">${body}<span class="cn">${label}</span><i class="h h-l" data-edge="l"></i><i class="h h-r" data-edge="r"></i></div>`;
}

function renderTimeline(root, o) {
  const tl = root.querySelector("[data-tl]");
  if (!tl) return;
  const tail = duration() + 20000, stepS = [1, 2, 5, 10, 15, 30, 60].find((s) => s * S.pps >= (o.tickPx || 80)) || 120;
  const state = (t) => `k-${t.kind} r-${t.role}${t.muted ? " is-muted" : ""}${t.locked ? " is-locked" : ""}${t.solo ? " is-solo" : ""}`;
  setHtml(tl.querySelector(".tl-heads"), S.p.tracks.map((t) => `<div class="th ${state(t)}">${o.head(t)}</div>`).join(""));
  let ticks = "";
  for (let s = 0; s * 1000 <= tail; s += stepS) {
    ticks += `<span class="tk" style="left:${X(s * 1000)}px">${(o.fmt || mmss)(s * 1000)}</span>`;
    for (let k = 1; k < 5; k++) ticks += `<i class="tkm" style="left:${X((s + (stepS * k) / 5) * 1000)}px"></i>`;
  }
  const selScene = S.sel?.t === "scene" && ctxScene();
  const band = o.band ? `<div class="tl-band">${S.p.scenes.map((s, i) => `<div class="sb${selScene === s ? " sel" : ""}${s.ok ? " ok" : ""}" data-scene="${s.id}" data-now="${s.id}" style="left:${X(s.start)}px;width:${X(s.dur)}px;--i:${s.look}">${(o.bandLabel || ((s, i) => `<b>${pad(i + 1)}</b><span>${esc(s.title)}</span>`))(s, i)}</div>`).join("")}</div>` : "";
  const markers = o.markers ? S.p.scenes.map((s, i) => `<i class="mk" style="left:${X(s.start)}px;--i:${s.look}" title="Scene ${i + 1} · ${esc(s.title)}"></i>`).join("") : "";
  const notes = o.notes ? reviewNotes().map((n) => `<button class="nt" data-act="ask" data-q="${esc(n.fix)}" style="left:${X(n.at)}px" title="${esc(n.kind + ": " + n.text)}"></button>`).join("") : "";
  const ranges = S.proposal ? S.proposal.ranges.map(([a, b]) => `<div class="pr" style="left:${X(a)}px;width:${Math.max(3, X(b - a))}px"></div>`).join("") : "";
  const scope = selScene ? `<div class="scope" style="left:${X(selScene.start)}px;width:${X(selScene.dur)}px"></div>` : "";
  const lanes = S.p.tracks.map((t) => `<div class="ln ${state(t)}" data-track="${t.id}">${t.clips.map((c) => clipHtml(t, c, o)).join("")}</div>`).join("");
  const inner = tl.querySelector(".tl-inner");
  inner.style.width = X(tail) + "px";
  inner.innerHTML = `${band}<div class="tl-ruler" data-ruler>${ticks}${markers}${notes}</div><div class="tl-lanes">${lanes}${scope}${ranges}</div><div class="ph" data-ph><i></i></div>`;
  $$("canvas.wv", inner).forEach(drawWave);
}
function placePlayhead(root) {
  root.querySelectorAll("[data-ph]").forEach((el) => {
    const x = X(S.playhead);
    if (el._x === x) return; // write styles only on change, or the page never goes idle
    el._x = x;
    el.style.transform = `translateX(${x}px)`;
    const sc = el.closest(".tl-scroll");
    if (S.playing && sc && (x > sc.scrollLeft + sc.clientWidth * 0.9 || x < sc.scrollLeft)) sc.scrollLeft = x - sc.clientWidth * 0.1;
  });
}
function tickCommon(root) {
  root.querySelectorAll("[data-tc]").forEach((el) => {
    const v = el.dataset.tc === "dur" ? duration() : S.playhead, txt = (el.dataset.fmt === "mmss" ? mmss : tc)(v);
    if (el.textContent !== txt) el.textContent = txt;
  });
  const cur = sceneAt(S.playhead)?.id;
  if (root._cur !== cur) { root._cur = cur; root.querySelectorAll("[data-now]").forEach((el) => el.classList.toggle("now", el.dataset.now === cur)); }
  if (root._playing !== S.playing) { root._playing = S.playing; root.querySelectorAll("[data-act=play]").forEach((b) => { b.innerHTML = playIc(+b.dataset.s || 16); b.setAttribute("aria-label", S.playing ? "Pause" : "Play"); }); }
  root.querySelectorAll("[data-meter]").forEach((el) => { const lv = level(el.dataset.meter); if (el._lv !== lv) { el._lv = lv; el.style.setProperty("--lv", lv); } });
  placePlayhead(root); drawPreviews(root);
}
function refreshCommon(root) {
  root._cur = root._playing = null;
  root.querySelectorAll("[data-ctx]").forEach((el) => (el.textContent = ctxLabel()));
  tickCommon(root);
}

// ---- AI blocks ----------------------------------------------------------------------------
const STATUS = { applied: "Applied", rejected: "Dismissed", expired: "Expired" };
function aiFeedHtml(max = 20) {
  const items = S.log.slice(-max).map((m) => {
    if (m.who === "sys") return `<div class="ai-sys">${esc(m.text)}</div>`;
    if (m.who === "user") return `<div class="ai-user"><p>${esc(m.text)}</p>${m.ctx ? `<small>${esc(m.ctx)}</small>` : ""}</div>`;
    if (m.summary) return `<div class="ai-card st-${m.status}"><div class="ai-card-h"><span>${esc(m.summary)}</span><em>${STATUS[m.status]}</em></div>${m.steps?.length ? `<ul>${m.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ul>` : ""}</div>`;
    return `<div class="ai-msg">${esc(m.text)}</div>`;
  }).join("");
  const thinking = S.thinking ? `<div class="ai-thinking"><i></i><i></i><i></i><span>${esc(S.thinking)}…</span></div>` : "";
  return items + thinking + (S.proposal ? proposalHtml() : "");
}
function proposalHtml() {
  const p = S.proposal;
  return `<div class="ai-prop"><div class="ai-prop-k">Proposed · not applied</div><div class="ai-prop-t">${esc(p.summary)}</div><ul>${p.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ul><div class="ai-prop-a"><button class="b-apply" data-act="accept">Apply edit</button><button class="b-dismiss" data-act="reject">Dismiss</button><small>Marked on the timeline</small></div></div>`;
}
const composerHtml = (ph = "Describe an edit…", rows = 1) => `<form class="ai-compose" data-ask><span class="ai-ctx" data-ctx></span><textarea rows="${rows}" placeholder="${esc(ph)}" aria-label="Describe an edit"></textarea><button type="submit" aria-label="Send">${ic("send", 15)}</button></form>`;
const chipsHtml = (n = 4, from = 0) => AI_CHIPS.slice(from, from + n).map((q) => `<button class="chip" data-act="ask" data-q="${esc(q)}">${esc(q)}</button>`).join("");

// ---- actions ---------------------------------------------------------------------------------
function selectScene(id) { const s = S.p.scenes.find((x) => x.id === id); if (!s) return; S.sel = { t: "scene", id }; seek(s.start); emit(); }
function stepScene(dir) {
  const i = S.p.scenes.indexOf(sceneAt(S.playhead)), cur = S.p.scenes[i];
  const j = dir < 0 && S.playhead > cur.start + 600 ? i : Math.max(0, Math.min(S.p.scenes.length - 1, i + dir));
  selectScene(S.p.scenes[j].id);
}
function zoom(f, to) {
  const sc = S.view?.root.querySelector(".tl-scroll");
  const off = sc ? X(S.playhead) - sc.scrollLeft : 0;
  S.pps = Math.max(2, Math.min(160, to ?? S.pps * f)); emit();
  if (sc) sc.scrollLeft = X(S.playhead) - off;
}
function fitZoom() { const sc = S.view?.root.querySelector(".tl-scroll"); if (sc) { zoom(0, (sc.clientWidth - 40) / (duration() / 1000)); sc.scrollLeft = 0; } }
const xToMs = (e, inner) => ((e.clientX - inner.getBoundingClientRect().left) / S.scale / S.pps) * 1000;
function snapMs(ms, self) {
  let best = ms, bd = (8 / S.pps) * 1000;
  const cand = [S.playhead, ...S.p.scenes.map((s) => s.start)];
  S.p.tracks.forEach((t) => t.clips.forEach((c) => c !== self && cand.push(c.start, endOf(c))));
  for (const v of cand) { const d = Math.abs(v - ms); if (d < bd) { bd = d; best = v; } }
  return best;
}

// ---- input layer -------------------------------------------------------------------------------
let drag = null;
const live_ = (e) => e.target.closest("[data-concept]") && !e.target.closest(".mini");
document.addEventListener("pointerdown", (e) => {
  if (!live_(e) || e.button !== 0) return;
  const inner = e.target.closest(".tl-inner"), clipEl = e.target.closest("[data-clip]");
  if (clipEl && inner) {
    const c = clipById(clipEl.dataset.clip), t = trackOf(c.id);
    e.preventDefault();
    if (S.tool === "razor") return split(c.id, snapMs(xToMs(e, inner), c));
    S.sel = { t: "clip", id: c.id };
    if (!t.locked) drag = { kind: e.target.dataset.edge ? "trim" : "move", edge: e.target.dataset.edge, id: c.id, x0: e.clientX, o: { start: c.start, dur: c.dur, in: c.in } };
    emit();
    if (t.locked) toast(`${t.name} is locked`);
    return;
  }
  const band = e.target.closest(".tl-band [data-scene]");
  if (band) return selectScene(band.dataset.scene);
  if (inner && e.target.closest("[data-ruler]") && !e.target.closest("[data-act]")) { drag = { kind: "scrub", inner }; seek(xToMs(e, inner)); e.preventDefault(); return; }
  if (inner && e.target.closest(".tl-lanes")) { S.sel = null; seek(xToMs(e, inner)); emit(); }
});
document.addEventListener("pointermove", (e) => {
  if (!drag) return;
  if (drag.kind === "scrub") return seek(xToMs(e, drag.inner));
  if (!drag.moved && Math.abs(e.clientX - drag.x0) < 3) return;
  drag.moved = true;
  const d = drag, c = clipById(d.id), t = trackOf(d.id), o = d.o, dms = ((e.clientX - d.x0) / S.scale / S.pps) * 1000;
  liveEdit(`${d.kind === "move" ? "Move" : "Trim"} ${nameOf(c)}`, () => {
    if (d.kind === "move") {
      const raw = Math.max(0, o.start + dms), a = snapMs(raw, c), b = snapMs(raw + o.dur, c) - o.dur;
      c.start = Math.round(Math.max(0, a !== raw ? a : b));
    } else if (d.edge === "l") {
      const lim = Math.max(-o.start, c.src ? -o.in : -Infinity), k = Math.max(lim, Math.min(o.dur - 100, snapMs(o.start + dms, c) - o.start));
      c.start = Math.round(o.start + k); c.dur = Math.round(o.dur - k); c.in = Math.round(o.in + k);
    } else {
      c.dur = Math.round(Math.max(100, Math.min(c.src ? c.src - o.in : Infinity, snapMs(o.start + o.dur + dms, c) - o.start)));
    }
  });
});
document.addEventListener("pointerup", () => {
  const d = drag;
  drag = null;
  if (!d || d.kind === "scrub" || !d.moved) return d && emit();
  const c = clipById(d.id), t = trackOf(d.id);
  if (overlaps(t, c)) { Object.assign(c, d.o); normalize(); toast(`Clips can't overlap on ${t.id} — moved back`); }
  liveEnd();
});
document.addEventListener("click", (e) => {
  const a = e.target.closest("[data-act]");
  if (!a || !live_(e)) return;
  const id = a.dataset.id;
  ({
    play: togglePlay, split: () => split(), del: removeSelected, undo, redo, fit: fitZoom,
    "zoom-in": () => zoom(1.4), "zoom-out": () => zoom(1 / 1.4), "scene-prev": () => stepScene(-1), "scene-next": () => stepScene(1),
    scene: () => selectScene(id), clip: () => { S.sel = { t: "clip", id }; seek(clipById(id).start); emit(); }, deselect: () => { S.sel = null; emit(); },
    mute: () => toggleTrack(id, "muted"), lock: () => toggleTrack(id, "locked"), solo: () => toggleTrack(id, "solo"),
    "clip-mute": () => toggleClipMute(id), approve: () => toggleApprove(id), up: () => nudgeScene(id, -1), down: () => nudgeScene(id, 1),
    ask: () => ask(a.dataset.q), accept: acceptProposal, reject: rejectProposal,
    tool: () => { S.tool = a.dataset.tool; emit(); }, tab: () => { S.tabs[a.dataset.group] = a.dataset.tab; emit(); },
    seek: () => { seek(+a.dataset.ms); emit(); }, step: () => { seek(S.playhead + +a.dataset.ms); emit(); }, ...ACTS,
  })[a.dataset.act]?.(a);
});
document.addEventListener("input", (e) => {
  const a = e.target.closest("[data-live]");
  if (!a || !live_(e)) return;
  const v = +a.value, out = a.parentElement.querySelector("output");
  if (a.dataset.live === "gain") { liveEdit(`Set volume on ${nameOf(clipById(a.dataset.id))}`, () => { clipById(a.dataset.id).gain = v; }); if (out) out.textContent = db(v); }
  if (a.dataset.live === "zoom") zoom(0, v);
});
document.addEventListener("change", (e) => e.target.closest("[data-live=gain]") && liveEnd());
document.addEventListener("submit", (e) => {
  const f = e.target.closest("[data-ask]");
  if (!f) return;
  e.preventDefault();
  const i = f.querySelector("textarea");
  ask(i.value); i.value = "";
});
document.addEventListener("wheel", (e) => {
  if (!e.target.closest(".tl-scroll") || !(e.ctrlKey || e.altKey) || !live_(e)) return;
  e.preventDefault(); zoom(e.deltaY < 0 ? 1.15 : 1 / 1.15);
}, { passive: false });
document.addEventListener("keydown", (e) => {
  const tag = e.target.tagName;
  if (tag === "TEXTAREA" && e.key === "Enter" && !e.shiftKey) { e.preventDefault(); e.target.form?.requestSubmit(); return; }
  if (tag === "INPUT" || tag === "TEXTAREA") { if (e.key === "Escape") e.target.blur(); return; }
  if (/^[0-4]$/.test(e.key) && !e.ctrlKey && !e.metaKey) return showConcept(e.key === "0" ? "overview" : "ABCD"[+e.key - 1]);
  if (!S.view || S.view.id === "overview") return;
  const k = e.key.toLowerCase(), mod = e.ctrlKey || e.metaKey;
  if (mod && k === "z") { e.preventDefault(); e.shiftKey ? redo() : undo(); }
  else if (mod && k === "y") { e.preventDefault(); redo(); }
  else if (mod || e.altKey) return;
  else if (e.key === " ") { e.preventDefault(); togglePlay(); }
  else if (k === "s") split();
  else if (e.key === "Delete" || e.key === "Backspace") removeSelected();
  else if (e.key === "ArrowLeft" || e.key === "ArrowRight") { e.preventDefault(); seek(S.playhead + (e.key === "ArrowLeft" ? -1 : 1) * (e.shiftKey ? 1000 : 1000 / FPS)); }
  else if (e.key === "ArrowUp" || e.key === "ArrowDown") { e.preventDefault(); stepScene(e.key === "ArrowUp" ? -1 : 1); }
  else if (k === "m" && S.sel?.t === "clip") toggleClipMute(S.sel.id);
  else if (e.key === "=" || e.key === "+") zoom(1.4);
  else if (e.key === "-") zoom(1 / 1.4);
  else if (e.key === "/") { const i = S.view.root.querySelector("[data-ask] textarea"); if (i) { e.preventDefault(); i.focus(); } }
  else if (e.key === "Escape") { S.sel = null; emit(); }
  else if (k === "v" || k === "c") { S.tool = k === "c" ? "razor" : "select"; emit(); }
});

// ---- concept switching + stage fit --------------------------------------------------------------
function showConcept(id) {
  if (!CONCEPTS[id]) id = "overview";
  S.playing = false;
  const stage = document.getElementById("stage");
  stage.className = "stage " + (id === "overview" ? "is-overview" : "is-app");
  S.view = { id, ...CONCEPTS[id].mount(stage) };
  stage.dataset.concept = id;
  document.querySelectorAll("[data-show]").forEach((b) => b.setAttribute("aria-current", b.dataset.show === id));
  history.replaceState(null, "", "#" + id);
  fitStage(); S.view.update();
  if (id !== "overview") requestAnimationFrame(fitZoom);
}
function fitStage() {
  const stage = document.getElementById("stage"), vp = stage.parentElement;
  if (stage.classList.contains("is-overview")) { stage.style.transform = ""; S.scale = 1; return; }
  S.scale = Math.min(vp.clientWidth / 1440, vp.clientHeight / 860, 1.5);
  stage.style.transform = `translate(-50%, -50%) scale(${S.scale})`;
}
addEventListener("resize", () => { fitStage(); });
