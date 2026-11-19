// Approved personal-workspace direction, 2026-09-13.
// Extend D only. A/B and the original shared prototype engine remain unchanged.
// These controls edit the sample model; production work is mapped in SPINE-IMPLEMENTATION.md.
function spineTiming(id, values) {
  const c = clipById(id), t = c && trackOf(id);
  if (!c || t.locked) return { error: "Unlock the track before editing its clips." };
  const next = { ...c, ...values };
  if (![next.start, next.in, next.dur].every(Number.isSafeInteger) || next.start < 0 || next.in < 0 || next.dur < 100)
    return { error: "Use positive durations of at least 0.1s and non-negative start times." };
  if (next.src && next.in + next.dur * (next.speed || 1) > next.src)
    return { error: "That timing extends beyond the source media." };
  if (t.clips.some((o) => o.id !== id && o.start < endOf(next) && next.start < endOf(o)))
    return { error: "That timing overlaps another clip on this track." };
  if (next.start === c.start && next.in === c.in && next.dur === c.dur) return { ok: true };
  const previousStart = c.start, previousEnd = endOf(c);
  commit(`Set timing on ${nameOf(c)}`, () => {
    Object.assign(c, { start: next.start, in: next.in, dur: next.dur });
    // A timing edit means overlapping scenes need another review.
    S.p.scenes.forEach((s) => {
      if ((s.start < endOf(c) && c.start < s.start + s.dur) ||
          (s.start < previousEnd && previousStart < s.start + s.dur)) s.ok = false;
    });
  });
  return { ok: true };
}

function spineTrackGain(id, target) {
  const t = trk(id);
  if (!t || t.kind !== "audio" || t.locked || !t.clips.length) return { error: "Unlock a populated audio track first." };
  if (!Number.isFinite(target) || target < -60 || target > 12) return { error: "Use a gain between −60 and +12 dB." };
  const delta = target - t.clips[0].gain;
  if (t.clips.some((c) => c.gain + delta < -60 || c.gain + delta > 12))
    return { error: "That change would push a clip outside the gain range. Adjust it in Lens instead." };
  if (!delta) return { ok: true };
  commit(`Adjust ${t.name} by ${db(delta)}`, () => {
    t.clips.forEach((c) => { c.gain = Math.round((c.gain + delta) * 10) / 10; });
    S.p.scenes.forEach((s) => {
      if (t.clips.some((c) => s.start < endOf(c) && c.start < s.start + s.dur)) s.ok = false;
    });
  });
  return { ok: true };
}

addCss(`
.d-rh{flex-wrap:wrap;gap:8px;padding:10px 12px 8px}
.d-navtabs{display:flex;gap:3px}.d-navtabs button{height:28px;padding:0 9px;border-radius:7px;color:var(--dim);font-size:12px}
.d-navtabs button.on{background:var(--raised);color:var(--text)}
.d-rh>.mono{font-size:10px}.d-media{padding:6px 12px 16px;display:grid;gap:14px}
.d-media h4{margin:0;color:var(--dim);font-size:11px;font-weight:500;letter-spacing:.04em}
.d-media-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 8px}
.d-media-item{min-width:0;display:grid;gap:5px;text-align:left;color:var(--dim);font-size:11px}
.d-media-item>span:last-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.d-media-thumb{display:block;position:relative;aspect-ratio:16/9;background-size:cover;background-position:center;border-radius:6px;background-color:var(--raised);box-shadow:inset 0 0 0 1px var(--line)}
.d-media-thumb small{position:absolute;bottom:4px;right:4px;background:var(--bg);padding:1px 4px;border-radius:3px;font:10px "JetBrains Mono",monospace}
.d-media-item.on .d-media-thumb{box-shadow:inset 0 0 0 2px var(--accent)}
.d-media-audio{display:flex;gap:8px;align-items:center;text-align:left;min-width:0;color:var(--dim);font-size:11px;padding:5px 0}
.d-media-audio span{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.d-media-audio small{color:var(--faint)}
.d-tabs{gap:0;padding-left:10px;padding-right:10px}.d-tabs button{padding:0 8px;font-size:12px}
.d-timing{display:grid;gap:10px}.d-timing-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.d-timing label{display:grid;gap:5px;color:var(--dim);font-size:11px}
.d-timing input,.d-mixstrip input[type=number]{width:100%;min-width:0;height:30px;padding:0 8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--text);font:12px "JetBrains Mono",monospace}
.d-form-error{font-size:12px;color:var(--accent);line-height:1.4;margin:0}.d-form-error:empty{display:none}
.d-small{font-size:11px;line-height:1.5;color:var(--dim);margin:0}
.d-mixstrip{display:grid;gap:10px;padding:12px 0;border-bottom:1px solid var(--line)}
.d-mixhead{display:flex;gap:8px;align-items:center}.d-mixhead strong{font-size:13px;font-weight:500;flex:1}.d-mixhead small{color:var(--faint);font-size:11px}
.d-mixgain{display:grid;grid-template-columns:minmax(0,1fr) 76px 52px;align-items:center;gap:8px}
.d-mixgain label{color:var(--dim);font-size:11px;line-height:1.4}.d-mixgain .d-btn{font-size:11px}
.d-mixbuttons{display:flex;gap:6px}.d-mixbuttons button{flex:1;height:27px;border-radius:6px;border:1px solid var(--line);font-size:11px;color:var(--dim)}
.d-mixbuttons button.on{color:var(--accent);background:var(--raised);border-color:var(--accent)}
.d-history{display:grid;gap:0}.d-history-row{display:flex;gap:10px;padding:11px 0;border-bottom:1px solid var(--line);font-size:12px;color:var(--dim)}
.d-history-row:first-child{color:var(--text)}.d-history-row .mono{color:var(--faint);font-size:10px;padding-top:2px}.d-history-row p{margin:0;line-height:1.5;overflow-wrap:anywhere}
.d-return{margin-top:auto;padding:12px;border-top:1px solid var(--line)}.d-return button{width:100%;color:var(--dim);font-size:11px;text-align:left}
`);

const spineOriginalMount = CONCEPTS.D.mount;
CONCEPTS.D.tag = "Selected · CutLab workspace";
CONCEPTS.D.pros.push("Media browsing from A; precise clip timing and a compact audio mixer from B");
CONCEPTS.D.mount = function (root) {
  const base = spineOriginalMount(root);
  const tabButton = (group, key, label, active) => `<button class="${active === key ? "on" : ""}" data-act="tab" data-group="${group}" data-tab="${key}" aria-pressed="${active === key}">${label}</button>`;
  const chosen = (id) => S.sel?.t === "clip" && S.sel.id === id;
  function media() {
    const visual = S.p.tracks.filter((t) => t.kind === "video").flatMap((t) => t.clips).filter((c) => c.look != null);
    return `<div class="d-media"><p class="d-small">Project media · select a clip to inspect it.</p><h4>FOOTAGE & INSERTS</h4><div class="d-media-grid">${visual.map((c) => `<button class="d-media-item${chosen(c.id) ? " on" : ""}" data-act="spine-clip" data-id="${c.id}" title="${esc(nameOf(c))}"><span class="d-media-thumb" style="background-image:url(${thumbFor(c.look)})"><small>${mmss(c.dur)}</small></span><span>${esc(nameOf(c))}</span></button>`).join("")}</div>${S.p.tracks.filter((t) => t.kind === "audio").map((t) => `<h4>${esc(t.name.toUpperCase())}</h4><div>${t.clips.map((c) => `<button class="d-media-audio" data-act="spine-clip" data-id="${c.id}">${ic(t.role === "vo" ? "mic" : "music", 13)}<span>${esc(nameOf(c))}</span><small>${secs(c.dur)}</small></button>`).join("")}</div>`).join("")}</div>`;
  }
  function timing(c) {
    const locked = trackOf(c.id).locked;
    return `<form class="d-timing" data-spine-timing="${c.id}"><div class="d-k">Precise timing</div><div class="d-timing-grid">${[["start", "Timeline start", c.start], ["dur", "Duration", c.dur], ...(c.src ? [["in", "Source in", c.in]] : [])].map(([name, label, value]) => `<label>${label} (s)<input name="${name}" type="number" step="0.001" min="${name === "dur" ? "0.1" : "0"}" value="${(value / 1000).toFixed(3)}" ${locked ? "disabled" : ""} required></label>`).join("")}</div><p class="d-form-error" role="alert"></p><button type="submit" class="d-btn" ${locked ? "disabled" : ""}>Apply timing</button><p class="d-small">${locked ? "Track locked. Unlock it on the timeline to edit." : "Changes this clip only. Use scene controls to move linked layers together."}</p></form>`;
  }
  function mixer() {
    return `<div class="d-k">Audio mixer</div><p class="d-small">Adjust each track's clips together. Existing differences between clips are preserved.</p>${S.p.tracks.filter((t) => t.kind === "audio").map((t) => `<form class="d-mixstrip" data-spine-gain="${t.id}"><div class="d-mixhead"><span class="d-tid">${t.id}</span><strong>${esc(t.name)}</strong><small>${t.clips.length} clips</small></div><div class="d-mixgain"><label for="gain-${t.id}">First clip level<br>All clips shift by the same amount</label><input id="gain-${t.id}" name="gain" aria-label="${esc(t.name)} level in dB" type="number" min="-60" max="12" step="0.5" value="${t.clips[0]?.gain ?? 0}" ${t.locked || !t.clips.length ? "disabled" : ""} required><button class="d-btn" type="submit" ${t.locked || !t.clips.length ? "disabled" : ""}>Apply</button></div><div class="d-mixbuttons">${[["mute", "muted", "Mute"], ["solo", "solo", "Solo"], ["lock", "locked", "Lock"]].map(([action, key, label]) => `<button type="button" class="${t[key] ? "on" : ""}" data-act="${action}" data-id="${t.id}" aria-label="${label} ${esc(t.name)}" aria-pressed="${t[key]}">${label}</button>`).join("")}</div><p class="d-form-error" role="alert"></p></form>`).join("")}<p class="d-small">Sample controls: the prototype has no rendered audio. Live metering belongs in the production editor.</p>`;
  }
  function historyView() {
    return `<div class="d-k">Edit history</div><div class="d-btns"><button class="d-btn" data-act="undo" ${S.past.length ? "" : "disabled"}>${ic("undo", 14)} Undo</button><button class="d-btn" data-act="redo" ${S.future.length ? "" : "disabled"}>${ic("redo", 14)} Redo</button></div><div class="d-history">${S.past.length ? S.past.slice().reverse().map((h, i) => `<div class="d-history-row"><span class="mono">${pad(S.past.length - i)}</span><p>${esc(h.label)}</p></div>`).join("") : '<p class="d-small">No edits yet in this session.</p>'}</div><p class="d-small">Prototype edits last until this page is reloaded.</p>`;
  }
  return {
    ...base,
    update() {
      base.update();
      const left = S.tabs.dLeft || "scenes", right = S.tabs.d || "lens";
      setHtml(root.querySelector(".d-rh"), `<div class="d-navtabs">${tabButton("dLeft", "scenes", "Scenes", left)}${tabButton("dLeft", "media", "Media", left)}</div><span class="mono">${S.p.scenes.length} · ${mmss(duration())}</span>`);
      if (left === "media") setHtml(root.querySelector(".d-list"), media());
      setHtml(root.querySelector(".d-tabs"), [["lens", "Lens"], ["audio", "Audio"], ["log", "Director"], ["history", "History"]].map(([key, label]) => tabButton("d", key, label, right)).join(""));
      const body = root.querySelector(".d-body");
      if (right === "audio") setHtml(body, mixer());
      else if (right === "history") setHtml(body, historyView());
      else if (right === "lens" && S.sel?.t === "clip" && clipById(S.sel.id)) {
        // Replace the read-only timing summary with editable properties.
        const summary = body.querySelector(".d-grid");
        if (summary) summary.outerHTML = timing(clipById(S.sel.id));
      }
    },
    tick() { base.tick.call(this); },
  };
};

ACTS["spine-clip"] = (a) => {
  S.sel = { t: "clip", id: a.dataset.id }; S.tabs.d = "lens";
  seek(clipById(a.dataset.id).start); emit();
};
document.addEventListener("submit", (e) => {
  const f = e.target;
  if (!live_(e) || !(f.matches("[data-spine-timing]") || f.matches("[data-spine-gain]"))) return;
  e.preventDefault();
  const data = new FormData(f);
  let result;
  if (f.dataset.spineTiming) {
    const c = clipById(f.dataset.spineTiming);
    result = spineTiming(c.id, {
      start: Math.round(Number(data.get("start")) * 1000),
      dur: Math.round(Number(data.get("dur")) * 1000),
      in: data.has("in") ? Math.round(Number(data.get("in")) * 1000) : c.in,
    });
  } else result = spineTrackGain(f.dataset.spineGain, Number(data.get("gain")));
  if (result.error) f.querySelector(".d-form-error").textContent = result.error;
});
