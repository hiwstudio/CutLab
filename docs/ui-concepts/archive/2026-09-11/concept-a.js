// Concept A — Studio (CapCut-inspired): tool rail + one drawer, dominant player, thumbnail-first timeline.
addCss(`
.cA{--bg:#0d0e11;--panel:#16171b;--raised:#1f2026;--hover:#282a31;--line:rgba(255,255,255,.06);--text:#f1f2f4;--dim:#9b9ea8;--faint:#62656e;--accent:#2fd9c9;--accent-ink:#04201d;
  --head-w:60px;--ruler-h:24px;--band-h:18px;--h-cap:26px;--h-over:30px;--h-main:62px;--h-audio:34px;--clip-inset:3px;
  --tl-bg:#111216;--tl-head-bg:#111216;--tick:rgba(255,255,255,.07);--tick-text:#6c6f78;--tick-font:500 10px/1 Figtree,sans-serif;--ph:#fff;
  --pr-a:rgba(47,217,201,.22);--pr-line:#2fd9c9;--scope-dim:rgba(0,0,0,.4);--scope-line:rgba(255,255,255,.55);--range-bg:#2c2e35;--range-thumb:#fff;
  width:1440px;height:860px;display:grid;grid-template-rows:52px 1fr 44px 262px;background:var(--bg);color:var(--text);font:13px/1.4 Figtree,system-ui,sans-serif}
.cA kbd{font:600 10.5px Figtree,sans-serif;padding:1px 5px;border-radius:4px;background:var(--raised);border:1px solid var(--line)}
.a-top{display:flex;align-items:center;gap:14px;padding:0 14px 0 16px}
.a-brand{display:flex;align-items:center;gap:8px;font-weight:700;font-size:15px;letter-spacing:-.01em}
.a-logo{width:24px;height:24px;border-radius:7px;background:var(--accent);color:var(--accent-ink);display:grid;place-items:center}
.a-sep{width:1px;height:18px;background:var(--line)}
.a-proj{display:flex;align-items:baseline;gap:10px}.a-proj b{font-weight:600}.a-proj small{color:var(--faint);font-size:12px}
.a-top-r{margin-left:auto;display:flex;gap:10px;align-items:center}
.a-pill{padding:6px 10px;border-radius:8px;background:var(--panel);color:var(--dim);font-size:12px}
.a-export{display:flex;align-items:center;gap:7px;height:32px;padding:0 16px;border-radius:9px;background:var(--accent);color:var(--accent-ink);font-weight:650}
.a-export:hover{filter:brightness(1.08)}
.a-main{display:grid;grid-template-columns:72px 296px 1fr 288px;gap:8px;padding-right:8px;min-height:0}
.a-rail{display:flex;flex-direction:column;gap:2px;padding:2px 6px}
.a-rb{display:flex;flex-direction:column;align-items:center;gap:5px;padding:9px 0 8px;border-radius:10px;color:var(--dim);font-size:10.5px;font-weight:500}
.a-rb:hover{background:var(--panel);color:var(--text)}.a-rb.on{color:var(--accent);background:var(--panel)}
.a-drawer,.a-player,.a-props{background:var(--panel);border-radius:12px;min-height:0;display:flex;flex-direction:column;overflow:hidden}
.a-dh,.a-ph{padding:14px 16px 10px;display:flex;flex-direction:column;gap:2px;flex:none}
.a-dh h3,.a-ph h3{margin:0;font-size:14px;font-weight:650}.a-dh span,.a-ph span{color:var(--faint);font-size:12px}
.a-db,.a-pb{padding:0 16px 16px;overflow:auto;display:flex;flex-direction:column;gap:10px;min-height:0;scrollbar-width:thin}
.a-seg{display:flex;background:var(--bg);border-radius:8px;padding:3px;gap:2px}
.a-seg span{flex:1;text-align:center;padding:5px;border-radius:6px;font-size:12px;color:var(--dim)}.a-seg .on{background:var(--raised);color:var(--text)}
.a-sub{margin:6px 0 -2px;font-size:11.5px;color:var(--dim);font-weight:600;display:flex;justify-content:space-between}.a-sub span{color:var(--faint);font-weight:500}
.a-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.a-tile{display:flex;flex-direction:column;gap:6px;text-align:left;min-width:0}
.a-th{position:relative;aspect-ratio:16/9;border-radius:8px;background-size:cover;background-position:center;background-color:var(--raised);box-shadow:inset 0 0 0 1px var(--line);overflow:hidden}
.a-th em{position:absolute;right:5px;bottom:5px;font:600 10px/1 Figtree,sans-serif;font-style:normal;padding:3px 5px;border-radius:4px;background:rgba(0,0,0,.62);color:#fff}
.a-tile:hover .a-th{box-shadow:inset 0 0 0 1px rgba(255,255,255,.3)}.a-tile.sel .a-th{box-shadow:inset 0 0 0 2px var(--accent)}
.a-tn{font-size:12px;color:var(--dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.a-tile.now .a-tn{color:var(--text)}
.a-txt{display:grid;place-items:center;color:#f4efe4;font-size:13px;background:linear-gradient(135deg,#262830,#17181c)}
.t-title{font-family:Georgia,serif;letter-spacing:.16em;text-transform:uppercase;font-size:9.5px}.t-lower{place-items:end start;padding:10px;font-weight:700}
.t-chapter{font-weight:800;font-size:18px;letter-spacing:-.02em}.t-quote{font-family:Georgia,serif;font-style:italic}
.a-capd{container-type:inline-size}.a-capd .pv-cap{font-size:10.5px;bottom:10%}
.a-tr i{position:absolute;inset:0;background-size:cover;background-position:center}
.a-tr i+i{-webkit-mask-image:linear-gradient(90deg,transparent 35%,#000 65%);mask-image:linear-gradient(90deg,transparent 35%,#000 65%)}
.a-tr.v1 i+i{-webkit-mask-image:linear-gradient(90deg,transparent 50%,#000 50%);mask-image:linear-gradient(90deg,transparent 50%,#000 50%)}
.a-tr.v2::after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,transparent 25%,#000 50%,transparent 75%)}
.a-row{display:flex;align-items:center;gap:10px;padding:6px 8px;border-radius:8px;text-align:left;min-width:0}
.a-row:hover{background:var(--raised)}.a-row.sel{background:var(--raised);box-shadow:inset 0 0 0 1px var(--accent)}
.a-ri{width:26px;height:26px;border-radius:7px;display:grid;place-items:center;flex:none;background:var(--raised)}
.a-ri.r-vo,.cA .cl.r-vo{color:#7cc4ff}.a-ri.r-music,.cA .cl.r-music{color:#6ee7b7}.a-ri.r-sfx,.cA .cl.r-sfx{color:#ff9f7a}.a-ri.r-over,.cA .cl.r-over{color:#c9b8ff}.a-ri.r-cap,.cA .cl.r-cap{color:#f6d47a}.a-ri.r-main{color:#e5e7eb}
.a-rn{flex:1;font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.a-rd{color:var(--faint);font-size:11.5px;font-variant-numeric:tabular-nums;flex:none}
.a-feed{flex:1;overflow:auto;padding:0 16px 8px;display:flex;flex-direction:column;gap:10px;scrollbar-width:thin}
.a-chips{display:flex;flex-wrap:wrap;gap:6px;padding:8px 16px 10px}
.cA .chip{padding:6px 10px;border-radius:999px;background:var(--raised);color:var(--dim);font-size:11.5px}.cA .chip:hover{color:var(--text);background:var(--hover)}
.cA .ai-compose{margin:0 12px 12px;padding:10px 10px 10px 12px;border-radius:12px;background:var(--bg);box-shadow:inset 0 0 0 1px var(--line);flex-wrap:wrap}
.cA .ai-compose:focus-within{box-shadow:inset 0 0 0 1px var(--accent)}
.cA .ai-ctx{width:100%;font-size:11px;color:var(--accent)}
.cA .ai-compose button{width:30px;height:30px;border-radius:9px;background:var(--accent);color:var(--accent-ink);display:grid;place-items:center}
.cA .ai-user{align-self:flex-end;max-width:88%;display:flex;flex-direction:column;align-items:flex-end;gap:3px}
.cA .ai-user p{margin:0;padding:8px 12px;border-radius:12px 12px 4px 12px;background:var(--raised);font-size:12.5px}.cA .ai-user small{color:var(--faint);font-size:10.5px}
.cA .ai-sys{font-size:11px;color:var(--faint);text-align:center}.cA .ai-msg{font-size:12.5px;color:var(--dim)}
.cA .ai-card{padding:10px 12px;border-radius:10px;background:var(--bg);font-size:12.5px}
.cA .ai-card-h{display:flex;justify-content:space-between;gap:8px}.cA .ai-card-h em{font-style:normal;font-size:11px;color:var(--accent);flex:none}
.cA .st-rejected .ai-card-h em,.cA .st-expired .ai-card-h em{color:var(--faint)}
.cA .ai-card ul,.cA .ai-prop ul{margin:6px 0 0;padding-left:16px;color:var(--dim);font-size:12px}
.cA .ai-thinking{font-size:12px;color:var(--dim)}.cA .ai-thinking span{margin-left:5px}
.cA .ai-prop{padding:12px;border-radius:12px;background:var(--raised);box-shadow:inset 0 0 0 1px var(--accent)}
.cA .ai-prop-k{font-size:10.5px;font-weight:650;color:var(--accent);text-transform:uppercase;letter-spacing:.06em}
.cA .ai-prop-t{font-size:13.5px;font-weight:600;margin-top:4px}
.cA .ai-prop-a{display:flex;align-items:center;gap:8px;margin-top:12px}.cA .ai-prop-a small{margin-left:auto;color:var(--faint);font-size:11px}
.cA .b-apply{height:30px;padding:0 14px;border-radius:8px;background:var(--accent);color:var(--accent-ink);font-weight:650}
.cA .b-dismiss{height:30px;padding:0 12px;border-radius:8px;background:var(--hover)}
.a-pl-h{display:flex;justify-content:space-between;padding:11px 14px 8px;font-size:12px;color:var(--dim)}.a-now{color:var(--faint)}
.a-pl-v{flex:1;display:grid;place-items:center;padding:0 14px;min-height:0}
.a-pl-v .pv{width:100%;max-width:600px;border-radius:6px}
.a-pl-t{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;padding:8px 12px 10px 14px}
.a-tc{font-variant-numeric:tabular-nums;color:var(--dim);font-size:12px}.a-tc b{color:var(--text);font-weight:600}
.a-play{width:38px;height:38px;border-radius:50%;background:var(--text);color:var(--bg);display:grid;place-items:center}.a-play:hover{background:#fff}
.a-pl-r{display:flex;justify-content:flex-end;gap:2px}
.a-ib{width:30px;height:30px;border-radius:8px;display:grid;place-items:center;color:var(--dim)}
.a-ib:hover:not(:disabled){background:var(--raised);color:var(--text)}.a-ib.on{color:var(--accent)}
.a-pthumb{aspect-ratio:16/9;border-radius:8px;background-size:cover;background-position:center;flex:none}
.a-f{display:flex;flex-direction:column;gap:3px;min-width:0}.a-f label{font-size:11px;color:var(--faint)}.a-f div{font-size:13px;overflow:hidden;text-overflow:ellipsis;font-variant-numeric:tabular-nums}
.a-f2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.a-sec{border-top:1px solid var(--line);padding-top:12px;display:flex;flex-direction:column;gap:9px}
.a-sec h4{margin:0;font-size:12px;font-weight:600;color:var(--dim)}
.a-slider{display:flex;align-items:center;gap:10px}.a-slider input{flex:1}.a-slider output{font-size:12px;font-variant-numeric:tabular-nums;min-width:58px;text-align:right}
.a-toggle{display:flex;align-items:center;gap:6px;align-self:flex-start;padding:6px 10px;border-radius:8px;background:var(--raised);font-size:12px}.a-toggle.on{background:var(--accent);color:var(--accent-ink)}
.a-chips2{display:flex;gap:6px}.a-chip{flex:1;padding:6px 0;border-radius:8px;background:var(--raised);font-size:12px;color:var(--dim)}.a-chip.on{background:var(--text);color:var(--bg);font-weight:600}
.a-about{margin:0;color:var(--dim);font-size:12.5px;line-height:1.5}
.a-inrow{display:flex;align-items:center;gap:10px;font-size:12.5px}.a-inrow em{margin-left:auto;font-style:normal;color:var(--faint)}
.a-btns{display:flex;gap:8px}.a-btn{flex:1;display:flex;align-items:center;justify-content:center;gap:6px;height:32px;border-radius:8px;background:var(--raised);font-size:12.5px}.a-btn:hover{background:var(--hover)}
.a-hint{color:var(--faint);font-size:12px;line-height:1.7;margin:4px 0 0}
.a-tools{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:0 12px 0 16px}
.a-tg{display:flex;align-items:center;gap:2px}.a-vr{width:1px;height:16px;background:var(--line);margin:0 6px}
.a-hist{color:var(--faint);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.a-tools input[type=range]{width:110px;margin:0 4px}
.a-fit{padding:5px 9px;border-radius:7px;font-size:12px;color:var(--dim)}.a-fit:hover{background:var(--raised);color:var(--text)}
.a-tl{margin:0 8px 8px;border-radius:12px;overflow:hidden}
.cA .th{display:flex;align-items:center;justify-content:center}
.a-tbtn{width:24px;height:24px;border-radius:6px;display:grid;place-items:center;color:var(--faint)}.a-tbtn:hover{color:var(--text);background:var(--raised)}
.cA .th.is-muted .a-tbtn:first-child,.cA .th.is-locked .a-tbtn:last-child{color:var(--accent)}
.cA .sb{border-right:2px solid var(--tl-bg);border-radius:5px;background:rgba(255,255,255,.04);color:var(--faint);font-size:10.5px;padding:0 6px}
.cA .sb b{color:var(--dim);font-weight:600}.cA .sb.now{color:var(--dim)}.cA .sb.now b{color:var(--text)}.cA .sb.sel{background:var(--accent);color:var(--accent-ink)}.cA .sb.sel b{color:var(--accent-ink)}
.cA .cl{border-radius:6px;font-size:11px;background:var(--raised)}
.cA .cl .cn{padding:3px 7px;font-weight:500}
.cA .cl.r-main{background:#222}.cA .cl.r-main .cn{margin:4px;padding:1px 5px;border-radius:4px;background:rgba(0,0,0,.6);color:#fff;font-size:10px;font-weight:600}
.cA .cl.r-over{background:#342a52}.cA .cl.ov-insert .cn{margin:3px;padding:0 5px;border-radius:4px;background:rgba(0,0,0,.6)}
.cA .cl.r-cap{background:#42360f}.cA .cl.r-vo{background:#11293d}.cA .cl.r-music{background:#12322a}.cA .cl.r-sfx{background:#3a2218}
.cA .cl .wv{opacity:.8}
.cA .cl.sel{box-shadow:inset 0 0 0 2px #fff;z-index:2}
.cA .cl.sel .h{background:#fff}.cA .cl.sel .h-l{border-radius:6px 0 0 6px}.cA .cl.sel .h-r{border-radius:0 6px 6px 0}
.cA .cl.sel .h::after{content:"";position:absolute;left:3px;top:50%;height:10px;margin-top:-5px;width:1px;background:#111}
`);

CONCEPTS.A = {
  name: "Studio",
  tag: "CapCut-inspired",
  thesis: "Approachable and visual. A tool rail opens one drawer at a time, the player dominates, and the timeline stays simple: thumbnails on the main track, colour-coded audio below, scenes as a light strip on top.",
  pros: ["Fastest to learn — you can edit within a minute", "Big player and thumbnail-first timeline", "Media, text, effects and AI share one drawer pattern"],
  cons: ["Scenes are secondary — you edit clips more than story", "Few pro controls: no meters, mixer or timecode entry"],
  mount(root) {
    const q = (s) => root.querySelector(s);
    const TABS = [["media", "film", "Media"], ["audio", "music", "Audio"], ["text", "type", "Text"], ["captions", "cc", "Captions"], ["effects", "fx", "Effects"], ["transitions", "trans", "Transitions"], ["ai", "wand", "AI edit"]];
    const tab = () => S.tabs.a || "media";
    const sel = (c) => (S.sel?.t === "clip" && S.sel.id === c.id ? " sel" : "");
    const roleIc = (t) => (t.kind === "audio" ? (t.role === "vo" ? "mic" : "music") : t.kind === "caption" ? "cc" : "film");
    root.innerHTML = `<div class="cA">
      <header class="a-top"><div class="a-brand"><span class="a-logo">${ic("split", 14)}</span>CutLab</div><span class="a-sep"></span>
        <div class="a-proj"><b>${esc(S.p.name)}</b><small>Saved · from ${S.p.engine}</small></div>
        <div class="a-top-r"><span class="a-pill">16:9 · 1080p · 30 fps</span><button class="a-export" data-act="soon">${ic("export", 15)} Export</button></div></header>
      <div class="a-main"><nav class="a-rail" aria-label="Tools"></nav><section class="a-drawer"></section>
        <section class="a-player"><div class="a-pl-h"><span>Player</span><span class="a-now" data-ctx></span></div><div class="a-pl-v">${previewHtml()}</div>
          <div class="a-pl-t"><span class="a-tc"><b data-tc data-fmt="mmss"></b> / <span data-tc="dur" data-fmt="mmss"></span></span><button class="a-play" data-act="play" data-s="18" aria-label="Play"></button>
          <div class="a-pl-r"><button class="a-ib" data-act="scene-prev" aria-label="Previous scene">${ic("prev", 15)}</button><button class="a-ib" data-act="scene-next" aria-label="Next scene">${ic("next", 15)}</button><button class="a-ib" data-act="soon" aria-label="Full screen">${ic("max", 15)}</button></div></div></section>
        <aside class="a-props"></aside></div>
      <div class="a-tools"><div class="a-tg"><button class="a-ib" data-act="undo" aria-label="Undo">${ic("undo")}</button><button class="a-ib" data-act="redo" aria-label="Redo">${ic("redo")}</button><span class="a-vr"></span>
        <button class="a-ib" data-act="split" aria-label="Split at playhead (S)" title="Split (S)">${ic("split")}</button><button class="a-ib" data-act="del" aria-label="Delete selected (Del)" title="Delete (Del)">${ic("trash")}</button></div>
        <div class="a-hist"></div>
        <div class="a-tg"><button class="a-ib on" data-act="soon" aria-pressed="true" aria-label="Main track magnet" title="Main track magnet">${ic("magnet", 15)}</button><span class="a-vr"></span>
        <button class="a-ib" data-act="zoom-out" aria-label="Zoom out">${ic("minus", 15)}</button><input type="range" min="2" max="80" step="0.1" data-live="zoom" aria-label="Timeline zoom"><button class="a-ib" data-act="zoom-in" aria-label="Zoom in">${ic("plus", 15)}</button><button class="a-fit" data-act="fit">Fit</button></div></div>
      <div class="a-tl">${timelineHtml()}</div></div>`;

    const tlo = {
      band: true, tickPx: 70,
      bandLabel: (s, i) => `<b>${i + 1}</b><span>${esc(s.title)}</span>`,
      head: (t) => `<button class="a-tbtn" data-act="mute" data-id="${t.id}" aria-label="${t.muted ? "Show" : "Hide"} ${t.name}" title="${t.name}">${ic(t.kind === "audio" ? (t.muted ? "volx" : "vol") : t.muted ? "x" : "eye", 14)}</button><button class="a-tbtn" data-act="lock" data-id="${t.id}" aria-label="${t.locked ? "Unlock" : "Lock"} ${t.name}">${ic(t.locked ? "lock" : "unlock", 13)}</button>`,
      label: (t, c) => (t.role === "main" ? secs(c.dur) : esc(t.kind === "caption" ? c.text : c.name) + (t.kind === "audio" && c.gain ? ` <em>${db(c.gain)}</em>` : "")),
    };
    const tiles = (list) => `<div class="a-grid">${list.join("")}</div>`;
    const tile = (act, id, img, label, extra = "", cls = "") => `<button class="a-tile${cls}" data-act="${act}"${id ? ` data-id="${id}"` : ""}><span class="a-th${extra}" ${img ? `style="background-image:url(${img})"` : ""}>`;

    function fill(k) {
      if (k === "media") {
        return `<div class="a-seg"><span class="on">Project</span><span>Library</span></div><p class="a-sub">Scenes <span>from ${S.p.engine}</span></p>` +
          tiles(S.p.scenes.map((s, i) => `${tile("scene", s.id, thumbFor(s.look), "", "", S.sel?.t === "scene" && S.sel.id === s.id ? " sel" : "").replace('class="a-tile', `data-now="${s.id}" class="a-tile`)}<em>${mmss(s.dur)}</em></span><span class="a-tn">${i + 1}. ${esc(s.title)}</span></button>`)) +
          `<p class="a-sub">Inserts</p>` + tiles(role("over").clips.filter((c) => c.overlay === "insert").map((c) => `${tile("clip", c.id, thumbFor(c.look), "", "", sel(c))}<em>${mmss(c.dur)}</em></span><span class="a-tn">${esc(c.name)}</span></button>`));
      }
      if (k === "audio") return ["vo", "music", "sfx"].map((r) => { const t = role(r); return `<p class="a-sub">${t.name} <span>${t.id}</span></p>${t.clips.map((c) => `<button class="a-row${sel(c)}" data-act="clip" data-id="${c.id}"><span class="a-ri r-${r}">${ic(roleIc(t), 14)}</span><span class="a-rn">${esc(c.name)}</span><span class="a-rd">${mmss(c.dur)}</span></button>`).join("")}`; }).join("");
      if (k === "text") return `<p class="a-sub">Templates</p>` + tiles([["Title", "The Last Lighthouse", "title"], ["Lower third", "Elias Marr", "lower"], ["Chapter", "Part II", "chapter"], ["Quote", "“Wind. Weather.”", "quote"]].map(([n, s, c]) => `<button class="a-tile" data-act="soon"><span class="a-th a-txt t-${c}">${s}</span><span class="a-tn">${n}</span></button>`));
      if (k === "captions") return `<p class="a-sub">Style</p>` + tiles([["clean", "Clean"], ["bold", "Bold"]].map(([v, n]) => `<button class="a-tile${S.p.capStyle === v ? " sel" : ""}" data-act="capstyle" data-v="${v}"><span class="a-th a-capd" style="background-image:url(${thumbFor(6)})"><i class="pv-cap cap-${v}">Wind. Weather.</i></span><span class="a-tn">${n}</span></button>`)) +
        `<p class="a-sub">Lines <span>from the voiceover transcript</span></p>${role("cap").clips.map((c) => `<button class="a-row${sel(c)}" data-act="clip" data-id="${c.id}"><span class="a-rd">${mmss(c.start)}</span><span class="a-rn">${esc(c.text)}</span></button>`).join("")}`;
      if (k === "effects") return `<p class="a-sub">Looks</p>` + tiles([["None", "none"], ["Mono", "grayscale(1) contrast(1.1)"], ["Faded", "sepia(.4) saturate(.7) brightness(1.05)"], ["Cold", "hue-rotate(170deg) saturate(.8)"], ["Punch", "contrast(1.35) saturate(1.35)"], ["Soft", "blur(1.2px) brightness(1.12)"]].map(([n, f]) => `<button class="a-tile" data-act="soon"><span class="a-th" style="background-image:url(${thumbFor(1)});filter:${f}"></span><span class="a-tn">${n}</span></button>`));
      if (k === "transitions") return `<p class="a-sub">Between clips</p>` + tiles(["Cross dissolve", "Hard wipe", "Dip to black", "Soft wipe", "Push", "Dip to white"].map((n, i) => `<button class="a-tile" data-act="soon"><span class="a-th a-tr v${i % 3}"><i style="background-image:url(${thumbFor(1)})"></i><i style="background-image:url(${thumbFor(7)})"></i></span><span class="a-tn">${n}</span></button>`));
      return aiFeedHtml();
    }

    function props() {
      const s = S.sel;
      if (s?.t === "clip" && clipById(s.id)) {
        const c = clipById(s.id), t = trackOf(c.id), sound = t.kind !== "caption" && c.overlay !== "title" && c.overlay !== "lower";
        return `<div class="a-ph"><h3>${t.kind === "caption" ? "Caption" : t.kind === "audio" ? "Audio" : "Video"}</h3><span>${t.name} · ${t.id}</span></div><div class="a-pb">
          ${c.look != null ? `<div class="a-pthumb" style="background-image:url(${thumbFor(c.look)})"></div>` : ""}
          <div class="a-f"><label>${t.kind === "caption" ? "Text" : "Name"}</label><div>${esc(c.name || c.text)}</div></div>
          <div class="a-f2"><div class="a-f"><label>Starts at</label><div>${mmss(c.start)}</div></div><div class="a-f"><label>Duration</label><div>${secs(c.dur)}</div></div></div>
          ${sound ? `<div class="a-sec"><h4>Volume</h4><div class="a-slider"><input type="range" min="-60" max="12" step="0.5" value="${c.gain}" data-live="gain" data-id="${c.id}" aria-label="Clip volume"><output>${db(c.gain)}</output></div>
            <button class="a-toggle${c.muted ? " on" : ""}" data-act="clip-mute" data-id="${c.id}" aria-pressed="${c.muted}">${ic(c.muted ? "volx" : "vol", 14)} ${c.muted ? "Muted" : "Mute clip"}</button></div>` : ""}
          ${t.kind === "caption" ? `<div class="a-sec"><h4>Style</h4><div class="a-chips2">${["clean", "bold"].map((v) => `<button class="a-chip${S.p.capStyle === v ? " on" : ""}" data-act="capstyle" data-v="${v}">${v === "clean" ? "Clean" : "Bold"}</button>`).join("")}</div></div>` : ""}
          ${t.kind !== "caption" ? `<div class="a-sec"><h4>Speed</h4><div class="a-chips2">${["0.5×", "1×", "1.5×", "2×"].map((v) => `<button class="a-chip${v === "1×" ? " on" : ""}" data-act="soon">${v}</button>`).join("")}</div></div>` : ""}</div>`;
      }
      if (s?.t === "scene" && ctxScene()) {
        const sc = ctxScene();
        return `<div class="a-ph"><h3>Scene ${sceneNo(sc)}</h3><span>${mmss(sc.start)} – ${mmss(sc.start + sc.dur)} · ${secs(sc.dur)}</span></div><div class="a-pb">
          <div class="a-pthumb" style="background-image:url(${thumbFor(sc.look)})"></div><div class="a-f"><label>Title</label><div>${esc(sc.title)}</div></div><p class="a-about">${esc(sc.about)}</p>
          <div class="a-sec"><h4>In this scene</h4>${sceneClips(sc).filter((x) => x.clips.length).map(({ t, clips }) => `<div class="a-inrow"><span class="a-ri r-${t.role}">${ic(roleIc(t), 13)}</span><span>${t.name}</span><em>${clips.length}</em></div>`).join("")}</div>
          <div class="a-sec"><div class="a-btns"><button class="a-btn" data-act="up" data-id="${sc.id}">${ic("chl", 14)} Earlier</button><button class="a-btn" data-act="down" data-id="${sc.id}">Later ${ic("chr", 14)}</button></div></div></div>`;
      }
      return `<div class="a-ph"><h3>Project</h3><span>Nothing selected</span></div><div class="a-pb">
        <div class="a-f"><label>Name</label><div>${esc(S.p.name)}</div></div>
        <div class="a-f2"><div class="a-f"><label>Canvas</label><div>1920 × 1080</div></div><div class="a-f"><label>Frame rate</label><div>30 fps</div></div></div>
        <div class="a-f2"><div class="a-f"><label>Duration</label><div>${mmss(duration())}</div></div><div class="a-f"><label>Scenes</label><div>${S.p.scenes.length}</div></div></div>
        <div class="a-f"><label>Source</label><div>${S.p.engine} · ${S.p.run}</div></div>
        <p class="a-hint">Select a clip or a scene to edit it.<br><kbd>Space</kbd> play · <kbd>S</kbd> split · <kbd>Del</kbd> delete · <kbd>↑</kbd><kbd>↓</kbd> scenes</p></div>`;
    }

    return {
      root,
      update() {
        const k = tab(), dr = q(".a-drawer");
        setHtml(q(".a-rail"), TABS.map(([key, icn, l]) => `<button class="a-rb${k === key ? " on" : ""}" data-act="tab" data-group="a" data-tab="${key}" aria-pressed="${k === key}">${ic(icn, 19)}<span>${l}</span></button>`).join(""));
        if (dr._tab !== k) {
          dr._tab = k;
          dr.innerHTML = k === "ai"
            ? `<div class="a-dh"><h3>AI edit</h3><span>Describe a change — review it before it lands.</span></div><div class="a-feed" data-fill data-stick></div><div class="a-chips">${chipsHtml(3)}</div>${composerHtml("e.g. make scene 3 shorter", 2)}`
            : `<div class="a-dh"><h3>${TABS.find((x) => x[0] === k)[2]}</h3></div><div class="a-db" data-fill></div>`;
        }
        setHtml(dr.querySelector("[data-fill]"), fill(k));
        setHtml(q(".a-props"), props());
        q(".a-hist").textContent = S.past.length ? "Last edit · " + S.past.at(-1).label : "";
        q("[data-act=undo]").disabled = !S.past.length;
        q("[data-act=redo]").disabled = !S.future.length;
        q("[data-live=zoom]").value = S.pps;
        renderTimeline(root, tlo);
        refreshCommon(root);
      },
      tick() { tickCommon(root); },
    };
  },
};
