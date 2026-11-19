// Concept B — Bay (Premiere/Resolve-inspired): docked panels, program monitor, inspector, full multitrack.
addCss(`
.cB{--gut:#0a0a0b;--panel:#1c1c1f;--head:#222225;--field:#141416;--hover:#2a2a2e;--line:#2c2c31;--text:#d4d4d8;--dim:#8a8a91;--faint:#5e5e65;--accent:#3d8bff;
  --head-w:176px;--ruler-h:24px;--band-h:0px;--h-cap:24px;--h-over:30px;--h-main:46px;--h-audio:40px;--clip-inset:1px;
  --tl-bg:#161618;--tl-head-bg:#1c1c1f;--tick:#323238;--tick-text:#7b7b82;--tick-font:400 10px/1 "IBM Plex Mono",Consolas,monospace;--ph:#3d8bff;
  --pr-a:rgba(61,139,255,.28);--pr-line:#3d8bff;--scope-dim:rgba(0,0,0,.38);--scope-line:#3d8bff;--range-bg:#35353b;--range-thumb:#d4d4d8;--mk:#e5a23a;--faint2:#46464c;
  width:1440px;height:860px;display:grid;grid-template-rows:38px 1fr 368px;gap:3px;padding:0 3px 3px;background:var(--gut);color:var(--text);font:12px/1.4 "IBM Plex Sans",system-ui,sans-serif}
.cB .m,.cB .b-v{font-family:"IBM Plex Mono",Consolas,monospace;font-variant-numeric:tabular-nums}
.b-top{display:flex;align-items:center;gap:2px;padding:0 6px}
.b-logo{width:22px;height:22px;border-radius:5px;background:linear-gradient(135deg,#3d8bff,#6a5cff);color:#fff;font:600 10px/22px "IBM Plex Sans",sans-serif;text-align:center;margin-right:8px}
.b-menu{padding:4px 7px;border-radius:4px;color:var(--dim)}.b-menu:hover{background:var(--hover);color:var(--text)}
.b-ws{margin:0 auto;display:flex;gap:18px}.b-ws button{height:38px;color:var(--dim);font-size:12.5px;box-shadow:inset 0 -2px transparent}
.b-ws button:hover{color:var(--text)}.b-ws button[aria-current=true]{color:#fff;box-shadow:inset 0 -2px var(--accent)}
.b-top-r{display:flex;align-items:center;gap:10px;color:var(--faint)}.b-top-r b{color:var(--dim);font-weight:500}
.b-qx{height:26px;padding:0 10px;border-radius:4px;background:var(--hover);color:var(--text);display:flex;align-items:center;gap:6px}
.b-up{display:grid;grid-template-columns:330px 1fr 336px;gap:3px;min-height:0}
.b-low{display:grid;grid-template-columns:36px 1fr 58px;gap:3px;min-height:0}
.b-pan{background:var(--panel);border-radius:4px;display:flex;flex-direction:column;min-height:0;overflow:hidden}
.b-tabs{height:28px;flex:none;display:flex;align-items:stretch;gap:14px;padding:0 10px;border-bottom:1px solid var(--line)}
.b-tabs button,.b-tabs span{color:var(--dim);display:flex;align-items:center;gap:6px;box-shadow:inset 0 -1px transparent}
.b-tabs button:hover{color:var(--text)}.b-tabs .on{color:#fff;box-shadow:inset 0 -2px var(--accent)}
.b-tabs .b-tr{margin-left:auto;gap:4px}
.b-body{flex:1;overflow:auto;min-height:0;scrollbar-width:thin;scrollbar-color:#3a3a40 transparent}
.b-search{display:flex;align-items:center;gap:8px;padding:6px 8px;border-bottom:1px solid var(--line)}
.b-search span{flex:1;height:22px;border-radius:3px;background:var(--field);color:var(--faint);padding:0 8px;display:flex;align-items:center}
.b-tbl{width:100%;border-collapse:collapse;table-layout:fixed}
.b-tbl th{position:sticky;top:0;background:var(--panel);font-weight:500;color:var(--faint);text-align:left;padding:5px 8px;border-bottom:1px solid var(--line);font-size:11px}
.b-tbl td{padding:0 8px;height:23px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--dim)}
.b-tbl tr:hover td{background:#232327}.b-tbl tr.sel td{background:#2b3a55;color:#fff}.b-tbl tr.now td:first-child{box-shadow:inset 2px 0 var(--accent)}
.b-tbl button{color:var(--text);text-align:left;overflow:hidden;text-overflow:ellipsis;max-width:100%}
.b-pn{display:flex;align-items:center;gap:6px;min-width:0}.b-pn .ic{color:var(--faint)}
.b-bin td{color:var(--faint)}
.b-sw2{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:7px;background:hsl(calc(var(--i)*43 + 20) 45% 55%)}
.b-ok{color:#57b28a}.b-no{color:var(--faint)}
.b-tree{padding:6px 0}.b-tree div{height:23px;display:flex;align-items:center;gap:6px;padding:0 10px;color:var(--dim)}
.b-tree div:hover{background:#232327}.b-tree .l2{padding-left:26px}.b-tree .l3{padding-left:42px;color:var(--text)}.b-tree .l3.on{color:#fff;background:#2b3a55}
.b-hist div{display:flex;gap:10px;align-items:center;height:24px;padding:0 10px;color:var(--dim);white-space:nowrap;overflow:hidden}
.b-hist div i{font-style:normal;color:var(--faint);width:18px;text-align:right}.b-hist .cur{color:#fff;background:#2b3a55}.b-hist .fut{color:var(--faint2)}
.b-mon{background:#0f0f10}.b-mon .b-body{display:flex;flex-direction:column;overflow:hidden}
.b-mv{flex:1;display:grid;place-items:center;min-height:0;padding:10px 0 6px}.b-mv .pv{height:100%;aspect-ratio:16/9;max-width:100%}.b-mv .pv canvas{height:100%;width:auto}
.b-mi{display:flex;align-items:center;justify-content:space-between;padding:0 12px;height:26px}
.b-tcb{color:var(--accent);font-size:14px}.b-dd{color:var(--dim);display:inline-flex;align-items:center;gap:4px;padding:1px 4px;border-radius:3px}.b-dd:hover{background:var(--hover)}
.b-tr2{display:flex;justify-content:center;gap:4px;padding:2px 0 8px}
.b-tb{width:28px;height:26px;border-radius:4px;display:grid;place-items:center;color:var(--dim);font-family:"IBM Plex Mono",monospace;font-size:13px}.b-tb:hover{background:var(--hover);color:#fff}
.b-tb.play{color:#fff;width:34px}.b-gap{width:10px}
.b-ih{display:flex;justify-content:space-between;padding:6px 10px;border-bottom:1px solid var(--line);color:var(--faint);gap:8px;white-space:nowrap}.b-ih b{color:var(--text);font-weight:500}
.b-sec{border-bottom:1px solid #242428}
.b-sh{display:flex;align-items:center;gap:6px;height:25px;padding:0 8px;color:var(--text);background:#202023}.b-sh b{font:italic 600 11px Georgia,serif;color:var(--faint)}
.b-prop{display:grid;grid-template-columns:120px 1fr;align-items:center;min-height:25px;padding:0 10px 0 8px}
.b-pl{display:flex;align-items:center;gap:6px;color:var(--dim);white-space:nowrap}.b-sw{width:14px;display:grid;place-items:center;color:var(--faint)}
.b-pv{display:flex;align-items:center;gap:12px;min-width:0}.b-v{color:var(--accent);font-size:11.5px}
.b-lvl input{flex:1;min-width:0}.b-lvl output{min-width:58px;text-align:right}
.b-cb{width:14px;height:14px;border-radius:3px;box-shadow:inset 0 0 0 1px #56565d;display:grid;place-items:center;color:#fff}.b-cb.on{background:var(--accent);box-shadow:none}
.b-captext{margin:6px 10px;padding:6px 8px;background:var(--field);border-radius:3px;color:var(--text)}
.b-seg{padding:2px 8px;border-radius:3px;background:var(--hover);color:var(--dim)}.b-seg.on{background:var(--accent);color:#fff}
.b-empty{height:100%;display:grid;place-items:center;color:var(--faint);text-align:center;line-height:1.7}
.b-meta{display:grid;grid-template-columns:96px 1fr;gap:0;padding:6px 0}.b-meta span{padding:4px 10px;color:var(--faint)}.b-meta b{padding:4px 10px;font-weight:400;color:var(--text)}
.b-btnrow{display:flex;gap:6px;padding:8px 10px}.b-btn{height:24px;padding:0 10px;border-radius:3px;background:var(--hover);display:flex;align-items:center;gap:5px}.b-btn:hover{background:#34343a}
.b-feedwrap{display:flex;flex-direction:column;height:100%}
.b-feed{flex:1;overflow:auto;padding:8px 10px;display:flex;flex-direction:column;gap:8px;scrollbar-width:thin}
.cB .ai-sys{color:var(--faint);font-size:11px}.cB .ai-user p{margin:0;color:#fff}.cB .ai-user small{color:var(--faint)}
.cB .ai-user{padding-left:8px;box-shadow:inset 2px 0 #46464c}.cB .ai-msg{color:var(--dim)}
.cB .ai-card{background:var(--field);border-radius:3px;padding:6px 8px}.cB .ai-card-h{display:flex;justify-content:space-between;gap:8px;color:var(--text)}
.cB .ai-card-h em{font:normal 10.5px "IBM Plex Mono",monospace;color:#57b28a;text-transform:uppercase}.cB .st-rejected em,.cB .st-expired em{color:var(--faint)!important}
.cB .ai-card ul,.cB .ai-prop ul{margin:4px 0 0;padding-left:14px;color:var(--dim)}
.cB .ai-thinking{color:var(--dim)}.cB .ai-thinking span{margin-left:4px}
.cB .ai-prop{border:1px solid var(--accent);border-radius:3px;padding:8px;background:#18202c}
.cB .ai-prop-k{font:500 10px "IBM Plex Mono",monospace;text-transform:uppercase;color:var(--accent);letter-spacing:.05em}.cB .ai-prop-t{color:#fff;margin-top:2px;font-weight:500}
.cB .ai-prop-a{display:flex;gap:6px;margin-top:8px;align-items:center}.cB .ai-prop-a small{margin-left:auto;color:var(--faint)}
.cB .b-apply{height:24px;padding:0 10px;border-radius:3px;background:var(--accent);color:#fff}.cB .b-dismiss{height:24px;padding:0 10px;border-radius:3px;background:var(--hover)}
.b-chips{display:flex;flex-wrap:wrap;gap:4px;padding:6px 10px;border-top:1px solid var(--line)}
.cB .chip{padding:2px 7px;border-radius:3px;background:var(--hover);color:var(--dim);font-size:11px}.cB .chip:hover{color:#fff}
.cB .ai-compose{margin:0 10px 10px;padding:6px 6px 6px 8px;background:var(--field);border-radius:3px;box-shadow:inset 0 0 0 1px var(--line);flex-wrap:wrap}
.cB .ai-compose:focus-within{box-shadow:inset 0 0 0 1px var(--accent)}.cB .ai-ctx{width:100%;color:var(--faint);font-size:10.5px}
.cB .ai-compose button{width:24px;height:24px;border-radius:3px;background:var(--accent);color:#fff;display:grid;place-items:center}
.b-mix{display:flex;height:100%;padding:10px 8px;gap:6px}
.b-strip{flex:1;display:flex;flex-direction:column;align-items:center;gap:6px;background:var(--field);border-radius:3px;padding:8px 0}
.b-strip.mst{background:#181c24}.b-sn{font:500 11px "IBM Plex Mono",monospace;color:#fff}.b-sname{color:var(--faint);font-size:10.5px}
.b-mtr{position:relative;width:8px;flex:1;background:linear-gradient(to top,#2fbf5a 0,#2fbf5a 68%,#e8c33a 84%,#e5484d 100%);border-radius:1px;overflow:hidden}
.b-mtr i{position:absolute;inset:0 0 auto;height:calc((1 - var(--lv,0)) * 100%);background:#0e0e10}
.b-mpair{flex:1;display:flex;gap:2px}
.b-ms{width:20px;height:18px;border-radius:3px;background:var(--hover);color:var(--dim);font:600 10px/18px "IBM Plex Sans",sans-serif;text-align:center}
.b-ms.on{background:#d9534f;color:#fff}.b-ms.s.on{background:#e5a23a;color:#111}.b-msrow{display:flex;gap:3px}
.b-tools{display:flex;flex-direction:column;align-items:center;gap:2px;padding:6px 0}
.b-tool{width:28px;height:28px;border-radius:4px;display:grid;place-items:center;color:var(--dim)}.b-tool:hover{background:var(--hover);color:#fff}.b-tool.on{background:#2b3a55;color:#fff}
.b-tlbar{height:34px;flex:none;display:flex;align-items:center;gap:6px;padding:0 10px;border-bottom:1px solid var(--line)}
.b-tlbar .b-tcb{font-size:17px;width:166px}.b-ti{width:24px;height:24px;border-radius:4px;display:grid;place-items:center;color:var(--dim)}.b-ti:hover{background:var(--hover);color:#fff}.b-ti.on{color:var(--accent)}
.b-tlwrap{flex:1;min-height:0}
.b-meters{display:grid;grid-template-columns:8px 8px 1fr;gap:3px;padding:30px 6px 10px}
.b-scale{display:flex;flex-direction:column;justify-content:space-between;font:9px "IBM Plex Mono",monospace;color:var(--faint);text-align:right}
.cB .th{display:flex;align-items:center;gap:4px;padding:0 6px;box-shadow:inset 0 -1px #26262a}
.cB .ln{box-shadow:inset 0 -1px #202023}
.cB .th.r-vo,.cB .ln.r-vo{box-shadow:inset 0 2px #3a3a40,inset 0 -1px #202023}
.b-tg{width:20px;height:20px;border-radius:3px;display:grid;place-items:center;color:var(--faint)}.b-tg:hover{color:#fff;background:var(--hover)}.b-tg.on{color:var(--accent)}
.b-id{min-width:26px;height:18px;border-radius:3px;background:#2b3a55;color:#cfe0ff;font:500 10.5px/18px "IBM Plex Mono",monospace;text-align:center}
.b-nm{flex:1;color:var(--dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cB .cl{border-radius:2px;font-size:10.5px;color:#0e0e10}
.cB .cl .cn{padding:2px 5px}
.cB .cl.r-main{background:#8286d6}.cB .cl.r-main .fs{width:min(64px,100%);background-size:cover;background-repeat:no-repeat}.cB .cl.r-main .cn{margin-left:64px}
.cB .cl.ov-insert{background:#b58ad8}.cB .cl.ov-insert .fs{width:min(44px,100%);background-size:cover}.cB .cl.ov-insert .cn{margin-left:44px}
.cB .cl.ov-title,.cB .cl.ov-lower{background:#d98ab8}.cB .cl.r-cap{background:#d6b44a}
.cB .cl.r-vo{background:#57b28a}.cB .cl.r-music{background:#4fa3a3}.cB .cl.r-sfx{background:#86a85a}
.cB .cl .wv{color:rgba(0,0,0,.42)}
.cB .cl.sel{box-shadow:inset 0 0 0 1px #fff;filter:brightness(1.18);z-index:2}
.cB .cl:hover .h-l{box-shadow:inset 2px 0 rgba(255,255,255,.8)}.cB .cl:hover .h-r{box-shadow:inset -2px 0 rgba(255,255,255,.8)}
.cB[data-tool=razor] .cl{cursor:crosshair}
`);

CONCEPTS.B = {
  name: "Bay",
  tag: "Premiere-inspired",
  thesis: "A professional edit bay. Docked panels (project, program monitor, inspector, director, mixer) sit over a full multitrack timeline with track headers, tools and meters. Every property is visible and exact.",
  pros: ["Everything visible at once — timecode, properties, meters, mixer", "Familiar to anyone who has cut in Premiere or Resolve", "Holds up on long, many-layer projects"],
  cons: ["Dense and slow for a quick review pass", "AI becomes one panel among many — easy to ignore", "Scenes shrink to ruler markers and a table"],
  mount(root) {
    const q = (s) => root.querySelector(s);
    const tab = (g, d) => S.tabs[g] || d;
    const tabs = (g, d, list, right = "") => list.map(([k, l]) => `<button class="${tab(g, d) === k ? "on" : ""}" data-act="tab" data-group="${g}" data-tab="${k}">${l}</button>`).join("") + right;
    const isSel = (c) => S.sel?.t === "clip" && S.sel.id === c.id;
    root.innerHTML = `<div class="cB">
      <header class="b-top"><span class="b-logo">CL</span>${["File", "Edit", "Clip", "Sequence", "Markers", "Graphics", "View", "Window", "Help"].map((m) => `<button class="b-menu" data-act="soon">${m}</button>`).join("")}
        <nav class="b-ws">${["Import", "Edit", "Audio", "Captions", "Color", "Export"].map((w) => `<button aria-current="${w === "Edit"}" data-act="soon">${w}</button>`).join("")}</nav>
        <div class="b-top-r"><span><b>${esc(S.p.name)}</b> · ${S.p.engine}</span><button class="b-qx" data-act="soon">${ic("export", 13)} Quick export</button></div></header>
      <div class="b-up">
        <section class="b-pan b-left"><div class="b-tabs"></div><div class="b-body"></div></section>
        <section class="b-pan b-mon"><div class="b-tabs"><span class="on">Program: ${esc(S.p.name)}</span></div><div class="b-body">
          <div class="b-mv">${previewHtml()}</div>
          <div class="b-mi"><span class="m b-tcb" data-tc></span><span><button class="b-dd" data-act="soon">Fit ${ic("chd", 11)}</button> <button class="b-dd" data-act="soon">Full ${ic("chd", 11)}</button></span><span class="m" style="color:var(--dim)" data-tc="dur"></span></div>
          <div class="b-tr2"><button class="b-tb" data-act="soon" aria-label="Add marker">${ic("flag", 13)}</button><span class="b-gap"></span><button class="b-tb" data-act="soon" aria-label="Mark in">{</button><button class="b-tb" data-act="soon" aria-label="Mark out">}</button><span class="b-gap"></span>
            <button class="b-tb" data-act="scene-prev" aria-label="Previous scene">${ic("prev", 13)}</button><button class="b-tb" data-act="step" data-ms="-34" aria-label="Back one frame">${ic("chl", 14)}</button><button class="b-tb play" data-act="play" data-s="16" aria-label="Play"></button><button class="b-tb" data-act="step" data-ms="34" aria-label="Forward one frame">${ic("chr", 14)}</button><button class="b-tb" data-act="scene-next" aria-label="Next scene">${ic("next", 13)}</button>
            <span class="b-gap"></span><button class="b-tb" data-act="split" aria-label="Split at playhead">${ic("split", 13)}</button><button class="b-tb" data-act="soon" aria-label="Export frame">${ic("image", 13)}</button></div></div></section>
        <section class="b-pan b-right"><div class="b-tabs"></div><div class="b-body b-rbody"></div></section></div>
      <div class="b-low">
        <section class="b-pan b-tools"></section>
        <section class="b-pan"><div class="b-tabs"><span class="on">${ic("x", 11)} ${esc(S.p.name)}</span></div>
          <div class="b-tlbar"><span class="m b-tcb" data-tc></span><button class="b-ti on" data-act="soon" aria-label="Snap" title="Snap">${ic("magnet", 14)}</button><button class="b-ti" data-act="soon" aria-label="Add marker">${ic("flag", 14)}</button>
            <span style="flex:1"></span><button class="b-ti" data-act="undo" aria-label="Undo">${ic("undo", 14)}</button><button class="b-ti" data-act="redo" aria-label="Redo">${ic("redo", 14)}</button><button class="b-ti" data-act="zoom-out" aria-label="Zoom out">${ic("minus", 14)}</button><button class="b-ti" data-act="zoom-in" aria-label="Zoom in">${ic("plus", 14)}</button><button class="b-ti" data-act="fit" aria-label="Fit sequence">${ic("max", 14)}</button></div>
          <div class="b-tlwrap">${timelineHtml()}</div></section>
        <section class="b-pan b-meters"><div class="b-mtr" data-meter="master"><i></i></div><div class="b-mtr" data-meter="master"><i></i></div><div class="b-scale"><span>0</span><span>−12</span><span>−24</span><span>−36</span><span>−48</span><span>dB</span></div></section></div></div>`;

    const tlo = {
      markers: true, tickPx: 96, fmt: tc,
      head: (t) => `<button class="b-tg${t.locked ? " on" : ""}" data-act="lock" data-id="${t.id}" aria-label="${t.locked ? "Unlock" : "Lock"} ${t.id}">${ic(t.locked ? "lock" : "unlock", 12)}</button><span class="b-id">${t.id}</span><span class="b-nm">${t.name}</span>` +
        (t.kind === "audio" ? `<button class="b-ms${t.muted ? " on" : ""}" data-act="mute" data-id="${t.id}" aria-pressed="${t.muted}" aria-label="Mute ${t.id}">M</button><button class="b-ms s${t.solo ? " on" : ""}" data-act="solo" data-id="${t.id}" aria-pressed="${t.solo}" aria-label="Solo ${t.id}">S</button>`
          : `<button class="b-tg${t.muted ? " on" : ""}" data-act="mute" data-id="${t.id}" aria-label="Toggle output ${t.id}">${ic(t.muted ? "x" : "eye", 12)}</button>`),
    };

    function left() {
      const k = tab("b1", "project");
      if (k === "scenes") return `<table class="b-tbl"><colgroup><col style="width:34px"><col><col style="width:92px"><col style="width:62px"><col style="width:26px"></colgroup><thead><tr><th>#</th><th>Scene</th><th>Timeline in</th><th>Dur</th><th></th></tr></thead><tbody>${S.p.scenes.map((s, i) => `<tr class="${S.sel?.t === "scene" && S.sel.id === s.id ? "sel" : ""}" data-now="${s.id}" data-act="scene" data-id="${s.id}"><td class="m">${pad(i + 1)}</td><td><i class="b-sw2" style="--i:${s.look}"></i><button data-act="scene" data-id="${s.id}">${esc(s.title)}</button></td><td class="m">${tc(s.start)}</td><td class="m">${secs(s.dur)}</td><td>${s.ok ? '<span class="b-ok" title="Approved">●</span>' : '<span class="b-no" title="Needs review">○</span>'}</td></tr>`).join("")}</tbody></table>`;
      if (k === "effects") {
        const cap = (v, n) => `<div class="l3${S.p.capStyle === v ? " on" : ""}" data-act="capstyle" data-v="${v}">${ic("cc", 12)}${n}</div>`;
        return `<div class="b-search"><span>Search effects</span></div><div class="b-tree">${[["Video Effects", ["Blur & Sharpen", "Color Correction", "Distort", "Stylize"]], ["Video Transitions", ["Dissolve", "Wipe", "Zoom"]], ["Audio Effects", ["Amplitude", "Noise Reduction"]]].map(([g, kids]) => `<div data-act="soon">${ic("chd", 11)}${ic("fx", 12)}${g}</div>${kids.map((c) => `<div class="l2" data-act="soon">${ic("chr", 11)}${c}</div>`).join("")}`).join("")}<div>${ic("chd", 11)}${ic("fx", 12)}Caption Styles</div>${cap("clean", "Clean")}${cap("bold", "Bold")}</div>`;
      }
      if (k === "history") return `<div class="b-hist">${S.past.slice(-16).map((h, i, a) => `<div><i>${S.past.length - a.length + i + 1}</i>${esc(h.label)}</div>`).join("")}<div class="cur"><i>●</i>Current state</div>${S.future.slice().reverse().map((h) => `<div class="fut"><i></i>${esc(h.label)}</div>`).join("")}</div>`;
      const row = (icn, name, type, dur, act, id, d, sel) => `<tr class="${sel ? "sel" : ""}"><td><span class="b-pn" style="padding-left:${d * 14}px">${ic(icn, 12)}<button data-act="${act}"${id ? ` data-id="${id}"` : ""}>${esc(name)}</button></span></td><td>${type}</td><td class="m">${dur}</td></tr>`;
      const bin = (name, n, open) => `<tr class="b-bin"><td><span class="b-pn">${ic(open ? "chd" : "chr", 11)}${ic("grid", 12)}${name}</span></td><td>Bin</td><td class="m">${n} items</td></tr>`;
      const over = role("over").clips;
      return `<div class="b-search"><span>Search project</span>${ic("list", 14)}${ic("grid", 14)}</div><table class="b-tbl"><colgroup><col><col style="width:74px"><col style="width:88px"></colgroup><thead><tr><th>Name</th><th>Type</th><th>Duration</th></tr></thead><tbody>
        ${row("layers", S.p.name, "Sequence", tc(duration()), "deselect", "", 0, false)}
        ${bin("Scenes", S.p.scenes.length, true)}${role("main").clips.map((c) => row("film", c.name, "Video", tc(c.dur), "clip", c.id, 1, isSel(c))).join("")}
        ${bin("Inserts &amp; graphics", over.length, true)}${over.map((c) => row(c.look != null ? "film" : "type", c.name, c.look != null ? "Video" : "Graphic", tc(c.dur), "clip", c.id, 1, isSel(c))).join("")}
        ${bin("Voiceover", role("vo").clips.length, false)}${bin("Music", role("music").clips.length, true)}${role("music").clips.map((c) => row("music", c.name, "Audio", tc(c.dur), "clip", c.id, 1, isSel(c))).join("")}${bin("SFX", role("sfx").clips.length, false)}</tbody></table>`;
    }

    function inspector() {
      const s = S.sel;
      if (s?.t === "clip" && clipById(s.id)) {
        const c = clipById(s.id), t = trackOf(c.id);
        const row = (l, v, kf = true) => `<div class="b-prop"><span class="b-pl"><i class="b-sw">${kf ? ic("history", 11) : ""}</i>${l}</span><span class="b-pv">${v}</span></div>`;
        const sec = (n, rows, fx = true) => `<div class="b-sec"><div class="b-sh">${ic("chd", 11)}${fx ? "<b>fx</b>" : ""}${n}</div>${rows}</div>`;
        let body = sec("Clip", row("Source in", `<span class="b-v">${tc(c.in)}</span>`, false) + row("Timeline in", `<span class="b-v">${tc(c.start)}</span>`, false) + row("Duration", `<span class="b-v">${tc(c.dur)}</span>`, false), false);
        if (c.look != null) body += sec("Motion", row("Position", '<span class="b-v">960.0</span><span class="b-v">540.0</span>') + row("Scale", '<span class="b-v">100.0</span>') + row("Rotation", '<span class="b-v">0.0°</span>')) + sec("Opacity", row("Opacity", '<span class="b-v">100.0 %</span>') + row("Blend mode", '<span class="b-dd">Normal</span>', false)) + sec("Time Remapping", row("Speed", '<span class="b-v">100.00 %</span>'));
        if (c.overlay === "title" || c.overlay === "lower") body += sec("Text", `<div class="b-captext">${esc(c.text)}${c.sub ? " — " + esc(c.sub) : ""}</div>` + row("Opacity", '<span class="b-v">100.0 %</span>'));
        if (t.kind === "audio" || t.role === "main") body += sec("Volume", row("Mute", `<button class="b-cb${c.muted ? " on" : ""}" data-act="clip-mute" data-id="${c.id}" aria-label="Mute clip" aria-pressed="${c.muted}">${c.muted ? ic("check", 10) : ""}</button>`, false) + `<div class="b-prop b-lvl"><span class="b-pl"><i class="b-sw">${ic("history", 11)}</i>Level</span><span class="b-pv"><input type="range" min="-60" max="12" step="0.5" value="${c.gain}" data-live="gain" data-id="${c.id}" aria-label="Level"><output class="b-v">${db(c.gain)}</output></span></div>`) + sec("Panner", row("Balance", '<span class="b-v">0.0</span>'));
        if (t.kind === "caption") body += sec("Caption", `<div class="b-captext">${esc(c.text)}</div>` + row("Style", ["clean", "bold"].map((v) => `<button class="b-seg${S.p.capStyle === v ? " on" : ""}" data-act="capstyle" data-v="${v}">${v === "clean" ? "Clean" : "Bold"}</button>`).join(""), false), false);
        return `<div class="b-ih"><span>Source · <b>${esc(nameOf(c))}</b></span><span class="m">${t.id}</span></div>${body}`;
      }
      if (s?.t === "scene" && ctxScene()) {
        const sc = ctxScene();
        return `<div class="b-ih"><span>Scene metadata · <b>${pad(sceneNo(sc))} ${esc(sc.title)}</b></span></div><div class="b-meta"><span>Timeline in</span><b class="m">${tc(sc.start)}</b><span>Timeline out</span><b class="m">${tc(sc.start + sc.dur)}</b><span>Duration</span><b class="m">${tc(sc.dur)}</b><span>Description</span><b>${esc(sc.about)}</b><span>Voiceover</span><b>${esc(sc.vo)}</b><span>Status</span><b>${sc.ok ? "Approved" : "Needs review"}</b></div>
          <div class="b-btnrow"><button class="b-btn" data-act="approve" data-id="${sc.id}">${ic("check", 12)} ${sc.ok ? "Unapprove" : "Approve"}</button><button class="b-btn" data-act="up" data-id="${sc.id}">${ic("chu", 12)} Earlier</button><button class="b-btn" data-act="down" data-id="${sc.id}">${ic("chd", 12)} Later</button></div>
          <div class="b-sec"><div class="b-sh">${ic("chd", 11)}Clips in range</div>${sceneClips(sc).flatMap(({ t, clips }) => clips.map((c) => `<div class="b-prop"><span class="b-pl m">${t.id}</span><span class="b-pv"><button data-act="clip" data-id="${c.id}" style="color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(nameOf(c))}</button></span></div>`)).join("")}</div>`;
      }
      return `<div class="b-empty">(no clips selected)<br>Sequence · 1920×1080 · 30 fps</div>`;
    }

    function mixer() {
      const strip = (t) => `<div class="b-strip"><div class="b-sn">${t.id}</div><div class="b-sname">${t.name}</div><div class="b-mpair"><div class="b-mtr" data-meter="${t.role}"><i></i></div><div class="b-mtr" data-meter="${t.role}"><i></i></div></div><div class="m b-v">${db(t.clips[0]?.gain ?? 0)}</div><div class="b-msrow"><button class="b-ms${t.muted ? " on" : ""}" data-act="mute" data-id="${t.id}">M</button><button class="b-ms s${t.solo ? " on" : ""}" data-act="solo" data-id="${t.id}">S</button></div></div>`;
      return `<div class="b-mix">${["vo", "music", "sfx"].map((r) => strip(role(r))).join("")}<div class="b-strip mst"><div class="b-sn">Mix</div><div class="b-sname">Master</div><div class="b-mpair"><div class="b-mtr" data-meter="master"><i></i></div><div class="b-mtr" data-meter="master"><i></i></div></div><div class="m b-v">0.0 dB</div><div class="b-msrow"></div></div></div>`;
    }

    return {
      root,
      update() {
        root.firstElementChild.dataset.tool = S.tool;
        setHtml(q(".b-left .b-tabs"), tabs("b1", "project", [["project", "Project"], ["scenes", "Scenes"], ["effects", "Effects"], ["history", "History"]]));
        setHtml(q(".b-left .b-body"), left());
        const rk = tab("b2", "inspector"), rb = q(".b-rbody");
        setHtml(q(".b-right .b-tabs"), tabs("b2", "inspector", [["inspector", "Effect Controls"], ["director", "Director"], ["mixer", "Audio Mixer"]]));
        if (rb._tab !== rk) {
          rb._tab = rk; rb._h = null;
          rb.innerHTML = rk === "director" ? `<div class="b-feedwrap"><div class="b-feed" data-fill data-stick></div><div class="b-chips">${chipsHtml(4)}</div>${composerHtml("Tell the director what to change", 2)}</div>` : `<div data-fill style="height:100%"></div>`;
        }
        setHtml(rb.querySelector("[data-fill]"), rk === "director" ? aiFeedHtml() : rk === "mixer" ? mixer() : inspector());
        setHtml(q(".b-tools"), [["select", "pointer", "Selection tool (V)"], ["ripple", "ripple", "Ripple edit"], ["razor", "split", "Razor tool (C)"], ["slip", "slip", "Slip"], ["pen", "pen", "Pen"], ["hand", "hand", "Hand"], ["type", "type", "Type"]]
          .map(([k, i, l]) => `<button class="b-tool${S.tool === k ? " on" : ""}" ${k === "select" || k === "razor" ? `data-act="tool" data-tool="${k}"` : 'data-act="soon"'} aria-label="${l}" title="${l}">${ic(i, 15)}</button>`).join(""));
        q(".b-tlbar [data-act=undo]").disabled = !S.past.length;
        q(".b-tlbar [data-act=redo]").disabled = !S.future.length;
        renderTimeline(root, tlo);
        refreshCommon(root);
      },
      tick() { tickCommon(root); },
    };
  },
};
