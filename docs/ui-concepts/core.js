// Shared project model, edit ops, history and AI proposals for every concept shell.
// ponytail: in-memory stand-in for CutLab's EDL + ops engine (same semantics: split,
// ripple delete, propose -> accept/reject, undo/redo). The real app calls /apply.
const FPS = 30;

const SCENE_SRC = [
  ["Cold open", 9000, "For a hundred and twelve years, one light kept this coast alive.", "Night storm. The beam cuts through rain."],
  ["The keeper", 15000, "Elias Marr arrived in 1911 with a trunk, a logbook, and no plan to leave.", "Dusk over the cliff, wide on the tower."],
  ["The logbook", 17000, "Every night he wrote the same three lines. Wind. Weather. Ships passed.", "Lamp-lit desk, open logbook, sea through the window."],
  ["The wreck", 17000, "Until October 1923, when the entries simply stop.", "Red storm, a ship listing near the rocks."],
  ["The search", 14000, "The search took nine days. They found the lamp still burning.", "Dawn fog, search boats on flat water."],
  ["Automation", 14000, "By 1964 the keepers were gone, replaced by a timer and a switch.", "Clear daylight, the tower repainted white."],
  ["The return", 15000, "His granddaughter came back to read the last page.", "Golden hour, a figure on the cliff path."],
  ["Last light", 11000, "Some lights are not meant to go out.", "Blue hour, stars, the beam turning."],
];

let _n = 0;
const nid = () => "clp_" + (46656 + _n++).toString(36);
const slug = (s) => s.toLowerCase().replace(/[^a-z]+/g, "-").replace(/^-|-$/g, "");

function buildProject() {
  let t = 0;
  const scenes = SCENE_SRC.map(([title, dur, vo, about], i) => {
    const s = { id: "scn_" + (i + 1), look: i, title, start: t, dur, vo, about, ok: i < 2 };
    t += dur;
    return s;
  });
  const T = (id, kind, name, role) => ({ id, kind, name, role, muted: false, locked: false, solo: false, clips: [] });
  const tracks = [T("T1", "caption", "Captions", "cap"), T("V2", "video", "Overlays", "over"), T("V1", "video", "Scenes", "main"),
    T("A1", "audio", "Voiceover", "vo"), T("A2", "audio", "Music", "music"), T("A3", "audio", "SFX", "sfx")];
  const [T1, V2, V1, A1, A2, A3] = tracks;
  const clip = (o) => ({ id: nid(), in: 0, gain: 0, muted: false, speed: 1, ...o });
  scenes.forEach((s, i) => {
    const n = String(i + 1).padStart(2, "0"), vs = s.start + 600, vd = Math.round(s.dur * 0.6);
    V1.clips.push(clip({ name: `sc${n}_${slug(s.title)}.mp4`, start: s.start, dur: s.dur, look: i, in: 1200, src: s.dur + 4000 }));
    A1.clips.push(clip({ name: `vo_sc${n}.wav`, start: vs, dur: vd, src: vd, text: s.vo }));
    const w = s.vo.split(" "), h = Math.ceil(w.length / 2), cut = vs + Math.round((vd * h) / w.length);
    T1.clips.push(clip({ text: w.slice(0, h).join(" "), start: vs, dur: cut - vs }), clip({ text: w.slice(h).join(" "), start: cut, dur: vs + vd - cut }));
  });
  V2.clips.push(
    clip({ name: "Title card", overlay: "title", text: "The Last Lighthouse", start: 1200, dur: 5200 }),
    clip({ name: "Lower third", overlay: "lower", text: "Elias Marr", sub: "Keeper, 1911 – 1923", start: 10500, dur: 4500 }),
    clip({ name: "ins_logbook.mp4", overlay: "insert", look: "book", start: 31000, dur: 5000, src: 9000 }),
    clip({ name: "ins_chart.mp4", overlay: "insert", look: "map", start: 60500, dur: 5000, src: 9000 }));
  A2.clips.push(clip({ name: "Tide — score.wav", start: 0, dur: 58000, gain: -14, src: 60000 }),
    clip({ name: "Ember — score.wav", start: 58000, dur: 54000, gain: -14, src: 60000 }));
  A3.clips.push(clip({ name: "storm_rain.wav", start: 0, dur: 8000, gain: -6, src: 20000 }),
    clip({ name: "thunder.wav", start: 42000, dur: 3500, gain: -3, src: 3500 }),
    clip({ name: "gulls.wav", start: 87000, dur: 5000, gain: -10, src: 8000 }));
  return { name: "The Last Lighthouse", engine: "recap-engine", run: "run 0911-a", w: 1920, h: 1080, capStyle: "clean", scenes, tracks };
}

const S = {
  p: buildProject(), playhead: 27600, playing: false, sel: null, pps: 10.4, past: [], future: [],
  proposal: null, thinking: null, view: null, ver: 0, tool: "select",
  log: [
    { who: "sys", text: "Opened from recap-engine · run 0911-a · 8 scenes, 6 tracks" },
    { who: "user", text: "Normalize the voiceover" },
    { who: "ai", summary: "Voiceover normalized to −16 LUFS", steps: ["8 clips on A1", "Peaks held under −1 dBTP"], status: "applied" },
  ],
};

// ---- queries --------------------------------------------------------------
const endOf = (c) => c.start + c.dur;
const trk = (id) => S.p.tracks.find((t) => t.id === id);
const role = (r) => S.p.tracks.find((t) => t.role === r);
const trackOf = (id) => S.p.tracks.find((t) => t.clips.some((c) => c.id === id));
const clipById = (id) => { for (const t of S.p.tracks) { const c = t.clips.find((x) => x.id === id); if (c) return c; } };
const duration = () => Math.max(0, ...S.p.tracks.flatMap((t) => t.clips.map(endOf)));
const sceneAt = (ms) => S.p.scenes.find((s) => ms >= s.start && ms < s.start + s.dur) || S.p.scenes.at(-1);
const activeClip = (t, ms) => t.clips.find((c) => ms >= c.start && ms < endOf(c));
const audible = (t) => !t.muted && (!S.p.tracks.some((x) => x.solo) || t.solo);
const sceneNo = (s) => S.p.scenes.indexOf(s) + 1;
const nameOf = (c) => c.name || `“${c.text}”`;
const sceneClips = (s) => S.p.tracks.map((t) => ({ t, clips: t.clips.filter((c) => c.start < s.start + s.dur && endOf(c) > s.start) }));
const voEnd = (s) => Math.max(s.start, ...role("vo").clips.filter((c) => c.start >= s.start && c.start < s.start + s.dur).map(endOf));

function ctxScene() {
  if (S.sel?.t === "scene") return S.p.scenes.find((s) => s.id === S.sel.id);
  if (S.sel?.t === "clip" && clipById(S.sel.id)) return sceneAt(clipById(S.sel.id).start);
  return sceneAt(S.playhead);
}
function ctxLabel() {
  if (S.sel?.t === "scene") { const s = ctxScene(); return `Scene ${sceneNo(s)} · ${s.title}`; }
  if (S.sel?.t === "clip" && clipById(S.sel.id)) return nameOf(clipById(S.sel.id));
  return "Whole project";
}

// ---- formatting -----------------------------------------------------------
const pad = (n) => String(n).padStart(2, "0");
function tc(ms) {
  const s = Math.floor(ms / 1000), f = Math.floor(((ms % 1000) * FPS) / 1000);
  return `${pad(Math.floor(s / 3600))}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}:${pad(f)}`;
}
const mmss = (ms) => { const s = Math.floor(ms / 1000); return `${pad(Math.floor(s / 60))}:${pad(s % 60)}`; };
const secs = (ms) => (ms / 1000).toFixed(1) + "s";
const db = (g) => (g < 0 ? "−" : g > 0 ? "+" : "") + Math.abs(g).toFixed(1) + " dB";
const esc = (s) => String(s).replace(/[&<>"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[ch]);

// ---- history --------------------------------------------------------------
const snap = () => JSON.stringify(S.p);
function emit() { S.ver++; S.view && S.view.update(); }
function toast(msg) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = msg; el.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => (el.hidden = true), 2200);
}
function expireProposal() {
  if (!S.proposal) return;
  S.log.push({ who: "ai", summary: S.proposal.summary, steps: ["The project changed before you decided — ask again"], status: "expired" });
  S.proposal = null;
}
function normalize() {
  S.p.tracks.forEach((t) => t.clips.sort((a, b) => a.start - b.start));
  S.playhead = Math.min(S.playhead, duration());
  if (S.sel?.t === "clip" && !clipById(S.sel.id)) S.sel = null;
  if (S.sel?.t === "scene" && !S.p.scenes.some((s) => s.id === S.sel.id)) S.sel = null;
}
function commit(label, fn, fromAI) {
  const before = snap();
  if (fn() === false) return false;
  if (!fromAI) expireProposal();
  normalize(); S.past.push({ p: before, label }); S.future = []; emit();
  return true;
}
let live = null; // drags and sliders: one history entry per gesture
function liveEdit(label, fn) { if (!live) live = { p: snap(), label }; fn(); normalize(); emit(); }
function liveEnd() {
  if (!live) return;
  if (snap() !== live.p) { S.past.push(live); S.future = []; expireProposal(); }
  live = null; emit();
}
function travel(from, to, verb) {
  const h = from.pop();
  if (!h) return;
  to.push({ p: snap(), label: h.label }); S.p = JSON.parse(h.p);
  expireProposal(); normalize(); emit(); toast(`${verb} · ${h.label}`);
}
const undo = () => travel(S.past, S.future, "Undo");
const redo = () => travel(S.future, S.past, "Redo");

// ---- ops ------------------------------------------------------------------
function split(id, at = S.playhead) {
  id = id || (S.sel?.t === "clip" && S.sel.id) || activeClip(role("main"), at)?.id;
  const c = id && clipById(id), t = c && trackOf(id);
  if (!c) return toast("Put the playhead over a clip to split it");
  if (t.locked) return toast(`${t.name} is locked`);
  if (at <= c.start + 34 || at >= endOf(c) - 34) return toast("The playhead isn't inside that clip");
  commit(`Split ${nameOf(c)} at ${tc(at)}`, () => {
    const off = at - c.start;
    t.clips.push({ ...c, id: nid(), start: at, dur: c.dur - off, in: (c.in || 0) + off });
    c.dur = off;
  });
}
function removeSelected() {
  if (S.sel?.t !== "clip") return;
  const c = clipById(S.sel.id), t = c && trackOf(c.id);
  if (!c) return;
  if (t.locked) return toast(`${t.name} is locked`);
  commit(`Delete ${nameOf(c)}`, () => { t.clips = t.clips.filter((x) => x !== c); });
}
function cutRange(from, to) { // ripple delete across every track, like delete_range(ripple)
  const d = to - from;
  const fix = (x) => {
    const e = x.start + x.dur;
    if (e <= from) return x;
    if (x.start >= to) { x.start -= d; return x; }
    if (x.start >= from && e <= to) return null;
    if (x.start < from && e > to) { x.dur -= d; return x; }
    if (x.start < from) { x.dur = from - x.start; return x; }
    x.in = (x.in || 0) + (to - x.start); x.dur = e - to; x.start = from; return x;
  };
  S.p.tracks.forEach((t) => (t.clips = t.clips.map(fix).filter(Boolean)));
  S.p.scenes = S.p.scenes.map(fix).filter(Boolean);
}
function moveScene(a, b) { // scene + everything that starts inside it; the music bed stays put
  const sc = S.p.scenes;
  if (b < 0 || b >= sc.length || a === b) return false;
  const groups = sc.map((s) => ({ s, items: [] }));
  S.p.tracks.forEach((t) => t.role !== "music" && t.clips.forEach((c) => {
    const i = sc.findIndex((s) => c.start >= s.start && c.start < s.start + s.dur);
    if (i >= 0) groups[i].items.push(c);
  }));
  const [g] = groups.splice(a, 1);
  groups.splice(b, 0, g);
  let t = 0;
  groups.forEach(({ s, items }) => { items.forEach((c) => (c.start += t - s.start)); s.start = t; t += s.dur; });
  S.p.scenes = groups.map((x) => x.s);
}
const overlaps = (t, c) => t.clips.some((o) => o !== c && o.start < endOf(c) && c.start < endOf(o));
function toggleTrack(id, key) {
  const t = trk(id), verbs = { muted: ["Mute", "Unmute"], locked: ["Lock", "Unlock"], solo: ["Solo", "Unsolo"] };
  commit(`${verbs[key][+t[key]]} ${t.name}`, () => { t[key] = !t[key]; });
}
function toggleClipMute(id) { const c = clipById(id); commit(`${c.muted ? "Unmute" : "Mute"} ${nameOf(c)}`, () => { c.muted = !c.muted; }); }
function nudgeScene(id, dir) {
  const i = S.p.scenes.findIndex((s) => s.id === id), s = S.p.scenes[i];
  if (i + dir < 0 || i + dir >= S.p.scenes.length) return;
  commit(`Move “${s.title}” ${dir < 0 ? "earlier" : "later"}`, () => moveScene(i, i + dir));
  S.playhead = s.start; emit();
}
function toggleApprove(id) { const s = S.p.scenes.find((x) => x.id === id); commit(`${s.ok ? "Unapprove" : "Approve"} “${s.title}”`, () => { s.ok = !s.ok; }); }
function seek(ms) { S.playhead = Math.max(0, Math.min(duration(), Math.round(ms))); }
function togglePlay() { if (!S.playing && S.playhead >= duration() - 40) S.playhead = 0; S.playing = !S.playing; emit(); }

// ---- AI director: interpret -> proposal -> accept / reject -----------------
const AI_CHIPS = ["Tighten the pauses in this scene", "Lower the music under the voiceover", "Move scene 5 before scene 4", "Make scene 3 shorter", "Make the captions bolder", "Mute the sound effects"];

function interpret(text) {
  const q = text.toLowerCase(), nums = (q.match(/\d+/g) || []).map(Number);
  const named = /scene\s*(\d+)/.exec(q), sc = named ? S.p.scenes[+named[1] - 1] : null;
  const lab = (s) => `scene ${sceneNo(s)} · ${s.title}`;
  if (/(swap|move|reorder|before|after)/.test(q) && nums.length >= 2) {
    const a = nums[0] - 1; let b = nums[1] - 1;
    if (/after/.test(q) && b < a) b++; else if (/before/.test(q) && b > a) b--;
    const A = S.p.scenes[a];
    if (!A || b < 0 || b >= S.p.scenes.length || a === b) return null;
    return { summary: `Move “${A.title}” to position ${b + 1}`, ranges: [[A.start, A.start + A.dur]], run: () => moveScene(a, b),
      steps: ["Footage, voiceover, captions and overlays move together", "The music bed stays where it is", "Scenes renumber automatically"] };
  }
  if (/(pause|silence|tighten|dead air|gap)/.test(q)) {
    const list = sc ? [sc] : /this|scene/.test(q) ? [ctxScene()] : S.p.scenes;
    const cuts = list.map((s) => [voEnd(s) + 500, s.start + s.dur]).filter(([a, b]) => b - a > 300);
    const total = cuts.reduce((n, [a, b]) => n + b - a, 0);
    if (!cuts.length) return { summary: "No pauses longer than 0.3s there." };
    return { summary: `Tighten ${cuts.length} pause${cuts.length > 1 ? "s" : ""} in ${list.length > 1 ? "the project" : lab(list[0])} (−${secs(total)})`, ranges: cuts,
      run: () => cuts.slice().reverse().forEach(([a, b]) => cutRange(a, b)),
      steps: ["Keeps 0.5s of air after each voiceover line", "Ripples every track so sync holds", `Runtime becomes ${mmss(duration() - total)}`] };
  }
  if (/(shorter|shorten|trim|faster|tighter)/.test(q)) {
    const s = sc || ctxScene(), cut = Math.min(4000, s.start + s.dur - voEnd(s) - 400);
    if (cut < 300) return { summary: `${lab(s)} has no held shot left to trim.` };
    return { summary: `Shorten ${lab(s)} by ${secs(cut)}`, ranges: [[s.start + s.dur - cut, s.start + s.dur]], run: () => cutRange(s.start + s.dur - cut, s.start + s.dur),
      steps: ["Trims the held shot after the last line", "Voiceover and captions are untouched", `Scene runs ${secs(s.dur - cut)}`] };
  }
  if (/(music|duck|voice|loud|quiet|hear)/.test(q)) {
    const m = role("music"), vo = role("vo"), g = m.clips[0]?.gain ?? 0;
    return { summary: "Duck the music −10 dB under the voiceover", ranges: vo.clips.map((c) => [c.start, endOf(c)]), run: () => m.clips.forEach((c) => (c.gain = Math.max(-60, c.gain - 10))),
      steps: [`Music ${db(g)} → ${db(g - 10)} on ${m.clips.length} clips`, `Covers ${vo.clips.length} voiceover lines`, "Voiceover level unchanged"] };
  }
  if (/(caption|subtitle|text)/.test(q)) {
    return { summary: "Restyle captions: bold, high contrast", ranges: role("cap").clips.map((c) => [c.start, endOf(c)]), run: () => { S.p.capStyle = "bold"; },
      steps: ["Heavier weight with a soft backing plate", "Timing still follows the voiceover transcript"] };
  }
  if (/(mute|sfx|sound effect)/.test(q)) {
    const t = role("sfx");
    return { summary: `Mute ${t.name}`, ranges: t.clips.map((c) => [c.start, endOf(c)]), run: () => { t.muted = true; }, steps: [`Silences ${t.clips.length} clips on ${t.id}`, "Clips stay on the timeline"] };
  }
  if (/(delete|remove|drop|cut)/.test(q) && sc) {
    return { summary: `Remove ${lab(sc)}`, ranges: [[sc.start, sc.start + sc.dur]], run: () => cutRange(sc.start, sc.start + sc.dur),
      steps: ["Removes its footage, voiceover, captions and overlays", "Closes the gap on every track", `Runtime becomes ${mmss(duration() - sc.dur)}`] };
  }
  return null;
}

function ask(text) {
  text = (text || "").trim();
  if (!text || S.thinking) return;
  const where = ctxLabel();
  expireProposal();
  S.log.push({ who: "user", text, ctx: where });
  S.thinking = `Reading ${where === "Whole project" ? "the project" : where} — footage, voiceover, captions`;
  emit();
  setTimeout(() => {
    S.thinking = null;
    const p = interpret(text);
    if (!p) S.log.push({ who: "ai", text: "I can't turn that into an edit yet. Try naming a scene, a track or a clip — or pick a suggestion." });
    else if (!p.run) S.log.push({ who: "ai", text: p.summary });
    else S.proposal = { ...p, prompt: text };
    emit();
  }, 800);
}
function acceptProposal() {
  const p = S.proposal;
  if (!p) return;
  S.proposal = null;
  commit("AI · " + p.summary, () => { p.run(); }, true);
  S.log.push({ who: "ai", summary: p.summary, steps: p.steps, status: "applied" });
  emit();
}
function rejectProposal() {
  const p = S.proposal;
  if (!p) return;
  S.proposal = null;
  S.log.push({ who: "ai", summary: p.summary, steps: p.steps, status: "rejected" });
  emit();
}

function reviewNotes() {
  const notes = [];
  const m = role("music");
  if (!m.muted && m.clips.some((c) => c.gain > -20)) notes.push({ at: S.p.scenes[3]?.start ?? 0, kind: "Audio", text: "Music sits close to the voiceover level", fix: "Lower the music under the voiceover" });
  S.p.scenes.forEach((s, i) => {
    const tail = s.start + s.dur - voEnd(s);
    if (tail > 5500) notes.push({ at: voEnd(s), kind: "Pacing", text: `Scene ${i + 1} holds ${secs(tail)} after the last line`, fix: `Make scene ${i + 1} shorter` });
  });
  if (S.p.capStyle !== "bold") notes.push({ at: 48000, kind: "Captions", text: "Captions are thin over the bright shots", fix: "Make the captions bolder" });
  return notes.slice(0, 4);
}

let _last = performance.now();
function loop(now) {
  if (S.playing) {
    S.playhead += now - _last;
    if (S.playhead >= duration()) { S.playhead = duration(); S.playing = false; emit(); }
  }
  _last = now;
  S.view && S.view.tick();
  requestAnimationFrame(loop);
}
