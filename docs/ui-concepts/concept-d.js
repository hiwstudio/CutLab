// Concept D — Spine (CutLab original): scenes are the backbone; Lens inspector; AI command line proposes in place.
addCss(`
.cD{--bg:#0f0f0e;--panel:#161614;--raised:#1f1f1c;--hover:#292925;--line:rgba(255,248,230,.07);--text:#edebe5;--dim:#9c998f;--faint:#65635c;--accent:#ffb547;--accent-ink:#1d1405;--ai:#a79bff;--ok:#7fd6a4;
  --head-w:178px;--ruler-h:22px;--band-h:26px;--h-cap:24px;--h-over:28px;--h-main:52px;--h-audio:33px;--clip-inset:2px;
  --tl-bg:#121211;--tl-head-bg:#121211;--tick:rgba(255,248,230,.07);--tick-text:#6d6a62;--tick-font:400 10px/1 "JetBrains Mono",Consolas,monospace;--ph:#ffb547;
  --pr-a:rgba(167,155,255,.3);--pr-line:#a79bff;--scope-dim:rgba(15,15,14,.55);--scope-line:rgba(255,181,71,.6);--range-bg:#2d2c28;--range-thumb:#ffb547;
  width:1440px;height:860px;display:grid;grid-template-rows:50px 1fr 318px;background:var(--bg);color:var(--text);font:13px/1.45 "Hanken Grotesk",system-ui,sans-serif}
.cD .mono{font-family:"JetBrains Mono",Consolas,monospace;font-variant-numeric:tabular-nums}
.cD .hue{--h:calc(var(--i) * 45 + 25)}
.d-top{display:flex;align-items:center;gap:14px;padding:0 14px 0 18px;border-bottom:1px solid var(--line)}
.d-word{font:700 18px/1 "Bricolage Grotesque",system-ui,sans-serif;letter-spacing:-.03em}
.d-crumb{color:var(--faint);font-size:12.5px}.d-crumb b{color:var(--dim);font-weight:500}
.d-rev{margin:0 auto;display:flex;align-items:center;gap:12px;font-size:12px;color:var(--dim)}
.d-cells{display:flex;gap:2px;width:260px;height:10px}
.d-cells button{--h:calc(var(--i) * 45 + 25);border-radius:2px;background:hsl(var(--h) 14% 24%)}.d-cells button.ok{background:hsl(var(--h) 45% 58%)}.d-cells button:hover{outline:1px solid var(--text)}
.d-ib{width:30px;height:30px;border-radius:8px;display:grid;place-items:center;color:var(--dim)}.d-ib:hover:not(:disabled){background:var(--raised);color:var(--text)}.d-ib.on{color:var(--accent);background:var(--raised)}
.d-saved{color:var(--faint);font-size:12px;max-width:260px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.d-primary{height:32px;padding:0 14px;border-radius:8px;background:var(--accent);color:var(--accent-ink);font-weight:600;display:flex;align-items:center;gap:7px}.d-primary:hover{filter:brightness(1.07)}
.d-mid{display:grid;grid-template-columns:264px 1fr 336px;min-height:0}
.d-rail{border-right:1px solid var(--line);display:flex;flex-direction:column;min-height:0}
.d-rh{display:flex;justify-content:space-between;align-items:baseline;padding:12px 16px 8px;font-size:12px;color:var(--faint)}.d-rh b{color:var(--text);font-weight:600;font-size:13px}
.d-list{overflow:auto;flex:1;scrollbar-width:thin;scrollbar-color:#2d2c28 transparent}
.d-sr{--h:calc(var(--i) * 45 + 25);width:100%;display:grid;grid-template-columns:40px 1fr 20px;align-items:center;gap:8px;height:54px;padding:0 14px 0 12px;text-align:left;box-shadow:inset 3px 0 hsl(var(--h) 40% 50% / .55)}
.d-sr:hover{background:var(--panel)}.d-sr.now{background:var(--panel)}.d-sr.sel{background:var(--raised);box-shadow:inset 3px 0 var(--accent)}
.d-num{font:500 22px/1 "Bricolage Grotesque",system-ui,sans-serif;color:var(--faint);letter-spacing:-.02em}.d-sr.now .d-num,.d-sr.sel .d-num{color:hsl(var(--h) 60% 70%)}
.d-st{display:flex;flex-direction:column;gap:3px;min-width:0}.d-st b{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.d-lay{display:flex;align-items:center;gap:5px;color:var(--dim)}.d-lay i.off{opacity:.25}.d-lay em{margin-left:auto;font:normal 11px "JetBrains Mono",monospace;color:var(--faint)}
.d-ok{width:18px;height:18px;border-radius:50%;box-shadow:inset 0 0 0 1px var(--faint);display:grid;place-items:center}.d-sr.ok .d-ok{background:var(--ok);box-shadow:none;color:#0c2118}
.d-view{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;padding:10px 24px;min-height:0;min-width:0}
.d-vh{width:640px;display:flex;justify-content:space-between;align-items:center;font-size:12px;color:var(--dim)}
.d-chip{--h:calc(var(--i) * 45 + 25);display:flex;align-items:center;gap:8px}.d-chip i{width:8px;height:8px;border-radius:2px;background:hsl(var(--h) 45% 58%)}.d-chip b{color:var(--text);font-weight:600}
.d-vh span[data-now]{display:none}.d-vh span.now{display:flex}
.d-view .pv{width:640px;border-radius:6px}
.d-scrub{position:relative;width:640px;height:18px;display:flex;gap:2px;align-items:center}
.d-scrub button{--h:calc(var(--i) * 45 + 25);height:6px;border-radius:2px;background:hsl(var(--h) 20% 28%)}.d-scrub button:hover,.d-scrub button.now{height:10px;background:hsl(var(--h) 45% 55%)}
.d-scrub .d-sp{position:absolute;top:0;bottom:0;left:calc(var(--p, 0) * 100%);width:2px;margin-left:-1px;background:var(--accent);border-radius:1px;pointer-events:none}
.d-tr{width:640px;display:grid;grid-template-columns:1fr auto 1fr;align-items:center}
.d-tc{font-size:15px;color:var(--text)}.d-tc small{font-size:11px;color:var(--faint)}
.d-trc{display:flex;align-items:center;gap:4px}.d-play{width:40px;height:40px;border-radius:50%;background:var(--accent);color:var(--accent-ink);display:grid;place-items:center}.d-play:hover{filter:brightness(1.07)}
.d-trr{justify-self:end;display:flex;gap:2px}
.d-lens{border-left:1px solid var(--line);display:flex;flex-direction:column;min-height:0}
.d-tabs{display:flex;gap:4px;padding:10px 12px 0}.d-tabs button{height:28px;padding:0 10px;border-radius:7px;color:var(--dim);font-weight:500}.d-tabs button:hover{color:var(--text)}.d-tabs button.on{background:var(--raised);color:var(--text)}
.d-tabs button span{font-size:11px;color:var(--ai);margin-left:4px}
.d-body{flex:1;overflow:auto;padding:14px 18px 18px;display:flex;flex-direction:column;gap:14px;min-height:0;scrollbar-width:thin;scrollbar-color:#2d2c28 transparent}
.d-lh{--h:calc(var(--i) * 45 + 25);display:grid;grid-template-columns:auto 1fr;gap:2px 14px;align-items:end}
.d-big{grid-row:span 2;font:500 46px/.85 "Bricolage Grotesque",system-ui,sans-serif;color:hsl(var(--h) 55% 66%);letter-spacing:-.04em}
.d-lh h3{margin:0;font-size:17px;font-weight:600;letter-spacing:-.01em;line-height:1.2}.d-lh small{color:var(--faint);font-size:11.5px}
.d-k{font-size:11px;color:var(--faint);text-transform:uppercase;letter-spacing:.08em;font-weight:500;margin-bottom:-6px}
.d-script{margin:0;font-size:14px;line-height:1.55;color:var(--text);text-wrap:pretty}
.d-about{margin:-6px 0 0;color:var(--dim);font-size:12.5px}
.d-lr{display:flex;align-items:center;gap:6px;border-radius:8px}.d-lr:hover{background:var(--panel)}.d-lr.muted .d-lrm{opacity:.45}
.d-lrm{flex:1;display:flex;align-items:center;gap:10px;padding:6px 6px;text-align:left;min-width:0}
.d-tid{flex:none;width:26px;height:20px;border-radius:5px;display:grid;place-items:center;font:500 10px "JetBrains Mono",monospace;background:var(--raised);color:var(--dim)}
.d-ln{display:flex;flex-direction:column;min-width:0}.d-ln b{font-weight:500;font-size:12.5px}.d-ln small{color:var(--faint);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.d-db{font:11px "JetBrains Mono",monospace;color:var(--faint);white-space:nowrap}
.d-btns{display:flex;gap:6px}.d-btn{flex:1;height:32px;border-radius:8px;background:var(--raised);display:flex;align-items:center;justify-content:center;gap:6px;font-size:12.5px}.d-btn:hover{background:var(--hover)}.d-btn.ok{background:var(--ok);color:#0c2118;font-weight:600}
.d-ask{display:flex;flex-wrap:wrap;gap:6px}.cD .chip{padding:5px 10px;border-radius:999px;box-shadow:inset 0 0 0 1px var(--line);color:var(--dim);font-size:11.5px}.cD .chip:hover{color:var(--text);box-shadow:inset 0 0 0 1px rgba(167,155,255,.55)}
.d-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px 12px}.d-grid div{display:flex;flex-direction:column;gap:2px}.d-grid span{font-size:11px;color:var(--faint)}.d-grid b{font:500 12.5px "JetBrains Mono",monospace}
.d-vol{display:flex;align-items:center;gap:10px}.d-vol input{flex:1}.d-vol output{font:12px "JetBrains Mono",monospace;min-width:58px;text-align:right}
.d-link{color:var(--dim);font-size:12px;text-align:left}.d-link:hover{color:var(--text)}
.cD .ai-sys{font-size:11px;color:var(--faint)}.cD .ai-user p{margin:0;color:var(--text)}.cD .ai-user small{color:var(--faint);font-size:10.5px}.cD .ai-user{padding-left:10px;box-shadow:inset 2px 0 var(--faint)}
.cD .ai-msg{color:var(--dim)}.cD .ai-card{padding-left:10px;box-shadow:inset 2px 0 var(--ai)}.cD .ai-card-h{display:flex;justify-content:space-between;gap:8px}.cD .ai-card-h em{font-style:normal;font-size:11px;color:var(--ok)}
.cD .st-rejected em,.cD .st-expired em{color:var(--faint)!important}.cD .ai-card ul{margin:4px 0 0;padding-left:16px;color:var(--dim);font-size:12px}
.d-tlsec{position:relative;display:flex;flex-direction:column;border-top:1px solid var(--line);min-height:0}
.d-bar{height:44px;flex:none;display:flex;align-items:center;gap:4px;padding:0 12px}
.d-vr{width:1px;height:16px;background:var(--line);margin:0 6px}
.d-tools{display:flex;gap:2px}
.cD .ai-compose{flex:1;max-width:620px;margin:0 auto;height:32px;align-items:center;padding:0 4px 0 6px;border-radius:9px;background:var(--panel);box-shadow:inset 0 0 0 1px var(--line)}
.cD .ai-compose:focus-within{box-shadow:inset 0 0 0 1px var(--ai),0 0 0 3px rgba(167,155,255,.12)}
.cD .ai-compose .ai-ctx{flex:none;max-width:190px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:11.5px;color:var(--ai);padding:3px 7px;border-radius:6px;background:rgba(167,155,255,.1)}
.cD .ai-compose textarea{height:20px;min-height:20px;line-height:20px;overflow:hidden;white-space:nowrap}
.cD .ai-compose button{width:26px;height:26px;border-radius:7px;background:var(--ai);color:#16112e;display:grid;place-items:center}
.d-float{position:absolute;left:50%;bottom:calc(100% + 10px);transform:translateX(-50%);width:620px;z-index:20;border-radius:12px;background:#1b1a22;box-shadow:inset 0 0 0 1px rgba(167,155,255,.5),0 18px 50px rgba(0,0,0,.55);padding:12px 14px}
.d-float .ai-prop-k{font-size:10.5px;text-transform:uppercase;letter-spacing:.08em;color:var(--ai);font-weight:600}
.d-float .ai-prop-t{font-size:14px;font-weight:600;margin-top:3px}.d-float ul{margin:6px 0 0;padding-left:16px;color:var(--dim);font-size:12px;columns:2;column-gap:20px}
.d-float .ai-prop-a{display:flex;align-items:center;gap:8px;margin-top:10px}.d-float .ai-prop-a small{margin-left:auto;color:var(--faint);font-size:11px}
.d-float .b-apply{height:30px;padding:0 14px;border-radius:8px;background:var(--ai);color:#16112e;font-weight:600}.d-float .b-dismiss{height:30px;padding:0 12px;border-radius:8px;background:var(--hover)}
.d-float .ai-thinking{color:var(--ai);font-size:12.5px}.d-float .ai-thinking span{color:var(--dim);margin-left:5px}
.d-tlw{flex:1;min-height:0;padding:0 0 8px}
.cD .th{display:flex;align-items:center;gap:6px;padding:0 8px 0 12px}
.d-hid{font:500 10px "JetBrains Mono",monospace;color:var(--faint);width:22px}.d-hn{flex:1;font-size:12px;color:var(--dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.d-hb{width:22px;height:22px;border-radius:6px;display:grid;place-items:center;color:var(--faint);font:600 10px "Hanken Grotesk",sans-serif}.d-hb:hover{background:var(--raised);color:var(--text)}.d-hb.on{color:var(--accent)}
.cD .tl-corner{padding-left:12px;font-size:10.5px;color:var(--faint);text-transform:uppercase;letter-spacing:.08em;align-items:flex-start;padding-top:6px}
.cD .sb{--h:calc(var(--i) * 45 + 25);border-right:2px solid var(--tl-bg);background:hsl(var(--h) 22% 17%);box-shadow:inset 0 2px hsl(var(--h) 45% 55%);color:var(--dim);font-size:11px;padding:0 7px}
.cD .sb b{font:600 12px "Bricolage Grotesque",sans-serif;color:hsl(var(--h) 55% 70%)}.cD .sb.now{color:var(--text)}
.cD .sb.sel{background:hsl(var(--h) 28% 24%);box-shadow:inset 0 0 0 1.5px var(--accent);color:var(--text)}
.cD .sb.ok span::after{content:" ✓";color:var(--ok)}
.cD .cl{border-radius:5px;font-size:10.5px;background:var(--raised)}.cD .cl .cn{padding:2px 6px}
.cD .cl.r-main{box-shadow:inset 0 -3px hsl(calc(var(--i, 0) * 45 + 25) 45% 55%)}.cD .cl.r-main .cn{margin:3px;padding:0 5px;border-radius:4px;background:rgba(0,0,0,.6);color:#fff}
.cD .cl.r-over{background:#2d2a3a;color:#cbc3f0}.cD .cl.ov-insert .cn{margin:2px;padding:0 5px;border-radius:4px;background:rgba(0,0,0,.6)}
.cD .cl.r-cap{background:#2e2a1e;color:#e8d7a6}.cD .cl.r-vo{background:#1e2527;color:#d3dcd8}.cD .cl.r-music{background:#1f251d;color:#a2c79c}.cD .cl.r-sfx{background:#2c221b;color:#d8a57f}
.cD .cl .wv{opacity:.55}.cD .ln.r-vo .cn,.cD .ln.r-music .cn,.cD .ln.r-sfx .cn{color:var(--text);opacity:.8}
.cD .cl.sel{box-shadow:inset 0 0 0 2px var(--accent);z-index:2}.cD .cl.sel .h{background:var(--accent)}
.cD[data-tool=razor] .cl{cursor:crosshair}
`);

CONCEPTS.D = {
  name: "Spine",
  tag: "CutLab original",
  thesis: "Scenes are the backbone. A scene rail, a scene-coloured spine across the timeline and a scene-segmented scrubber keep story structure visible everywhere. The Lens shows everything inside the selected scene, and the AI command line lives in the timeline, proposing edits in place.",
  pros: ["Built for engine output: each scene's footage, voiceover, captions and audio in one view", "Review → approve per scene → export is the core flow, not an add-on", "AI proposals land on the timeline you're already looking at"],
  cons: ["New patterns to learn — it isn't a copy of any editor", "Scene-first framing is less natural for raw, unscened footage"],
  mount(root) {
    const q = (s) => root.querySelector(s);
    const sceneOf = () => (S.sel ? ctxScene() : sceneAt(S.playhead));
    root.innerHTML = `<div class="cD">
      <header class="d-top"><span class="d-word">CutLab</span><span class="d-crumb">${S.p.engine} / <b>${esc(S.p.name)}</b></span>
        <div class="d-rev"></div>
        <span class="d-saved"></span><button class="d-ib" data-act="undo" aria-label="Undo">${ic("undo")}</button><button class="d-ib" data-act="redo" aria-label="Redo">${ic("redo")}</button>
        <button class="d-primary" data-act="soon">${ic("check", 14)} Approve &amp; export</button></header>
      <div class="d-mid">
        <nav class="d-rail" aria-label="Scenes"><div class="d-rh"></div><div class="d-list"></div></nav>
        <section class="d-view"><div class="d-vh"><span class="d-nowh"></span><span class="mono" data-tc="dur"></span></div>${previewHtml()}
          <div class="d-scrub"></div>
          <div class="d-tr"><span class="d-tc mono" data-tc></span><div class="d-trc"><button class="d-ib" data-act="scene-prev" aria-label="Previous scene">${ic("prev", 15)}</button><button class="d-play" data-act="play" data-s="17" aria-label="Play"></button><button class="d-ib" data-act="scene-next" aria-label="Next scene">${ic("next", 15)}</button></div>
            <div class="d-trr"><button class="d-ib" data-act="step" data-ms="-34" aria-label="Back one frame">${ic("chl", 15)}</button><button class="d-ib" data-act="step" data-ms="34" aria-label="Forward one frame">${ic("chr", 15)}</button><button class="d-ib" data-act="soon" aria-label="Full screen">${ic("max", 15)}</button></div></div></section>
        <aside class="d-lens"><div class="d-tabs"></div><div class="d-body"></div></aside></div>
      <section class="d-tlsec"><div class="d-floatwrap"></div>
        <div class="d-bar"><div class="d-tools"></div><span class="d-vr"></span><button class="d-ib" data-act="split" aria-label="Split at playhead (S)" title="Split (S)">${ic("split")}</button><button class="d-ib" data-act="del" aria-label="Delete selected" title="Delete (Del)">${ic("trash")}</button>
          ${composerHtml("Ask CutLab to edit…   press / to type", 1)}
          <button class="d-ib" data-act="zoom-out" aria-label="Zoom out">${ic("minus", 15)}</button><button class="d-ib" data-act="zoom-in" aria-label="Zoom in">${ic("plus", 15)}</button><button class="d-ib" data-act="fit" aria-label="Fit timeline">${ic("max", 15)}</button></div>
        <div class="d-tlw">${timelineHtml("Scenes")}</div></section></div>`;

    const tlo = {
      band: true, tickPx: 80,
      head: (t) => `<span class="d-hid">${t.id}</span><span class="d-hn">${t.name}</span>` +
        (t.kind === "audio" ? `<button class="d-hb${t.muted ? " on" : ""}" data-act="mute" data-id="${t.id}" aria-pressed="${t.muted}" aria-label="Mute ${t.name}">M</button><button class="d-hb${t.solo ? " on" : ""}" data-act="solo" data-id="${t.id}" aria-pressed="${t.solo}" aria-label="Solo ${t.name}">S</button>`
          : `<button class="d-hb${t.muted ? " on" : ""}" data-act="mute" data-id="${t.id}" aria-label="Hide ${t.name}">${ic(t.muted ? "x" : "eye", 13)}</button>`) +
        `<button class="d-hb${t.locked ? " on" : ""}" data-act="lock" data-id="${t.id}" aria-label="${t.locked ? "Unlock" : "Lock"} ${t.name}">${ic(t.locked ? "lock" : "unlock", 12)}</button>`,
    };

    function rail() {
      return S.p.scenes.map((s, i) => {
        const has = (r) => sceneClips(s).find((x) => x.t.role === r)?.clips.length;
        return `<button class="d-sr${S.sel?.t === "scene" && S.sel.id === s.id ? " sel" : ""}${s.ok ? " ok" : ""}" data-act="scene" data-id="${s.id}" data-now="${s.id}" style="--i:${s.look}"><span class="d-num">${pad(i + 1)}</span><span class="d-st"><b>${esc(s.title)}</b><span class="d-lay">${[["main", "film", "Footage"], ["vo", "mic", "Voiceover"], ["cap", "cc", "Captions"], ["over", "layers", "Overlays"]].map(([r, n, l]) => `<i class="${has(r) ? "" : "off"}" title="${l}">${ic(n, 11)}</i>`).join("")}<em>${secs(s.dur)}</em></span></span><span class="d-ok">${s.ok ? ic("check", 11) : ""}</span></button>`;
      }).join("");
    }

    function lens() {
      if (S.sel?.t === "clip" && clipById(S.sel.id)) {
        const c = clipById(S.sel.id), t = trackOf(c.id), sc = sceneAt(c.start), sound = t.kind === "audio" || t.role === "main";
        return `<div class="d-k">${t.name} · ${t.id}</div><div class="d-lh" style="--i:${c.look ?? sc.look}"><h3 style="grid-column:1/-1">${esc(nameOf(c))}</h3></div>
          <div class="d-grid"><div><span>Start</span><b>${tc(c.start)}</b></div><div><span>End</span><b>${tc(endOf(c))}</b></div><div><span>Duration</span><b>${tc(c.dur)}</b></div><div><span>Source in</span><b>${tc(c.in)}</b></div></div>
          ${sound ? `<div class="d-k">Volume</div><div class="d-vol"><input type="range" min="-60" max="12" step="0.5" value="${c.gain}" data-live="gain" data-id="${c.id}" aria-label="Clip volume"><output>${db(c.gain)}</output></div><div class="d-btns"><button class="d-btn" data-act="clip-mute" data-id="${c.id}" aria-pressed="${c.muted}">${ic(c.muted ? "volx" : "vol", 14)} ${c.muted ? "Unmute clip" : "Mute clip"}</button></div>` : ""}
          ${t.kind === "caption" ? `<div class="d-k">Caption style</div><div class="d-btns">${["clean", "bold"].map((v) => `<button class="d-btn${S.p.capStyle === v ? " ok" : ""}" data-act="capstyle" data-v="${v}">${v === "clean" ? "Clean" : "Bold"}</button>`).join("")}</div>` : ""}
          <div class="d-btns"><button class="d-btn" data-act="split">${ic("split", 14)} Split at playhead</button><button class="d-btn" data-act="del">${ic("trash", 14)} Delete</button></div>
          <button class="d-link" data-act="scene" data-id="${sc.id}">Part of scene ${pad(sceneNo(sc))} · ${esc(sc.title)} →</button>`;
      }
      const sc = sceneOf(), n = sceneNo(sc);
      return `<div class="d-lh" style="--i:${sc.look}"><span class="d-big">${pad(n)}</span><h3>${esc(sc.title)}</h3><small class="mono">${tc(sc.start)} → ${tc(sc.start + sc.dur)} · ${secs(sc.dur)}</small></div>
        <div class="d-btns"><button class="d-btn${sc.ok ? " ok" : ""}" data-act="approve" data-id="${sc.id}">${ic("check", 14)} ${sc.ok ? "Approved" : "Approve scene"}</button><button class="d-ib" data-act="up" data-id="${sc.id}" aria-label="Move scene earlier">${ic("chu", 15)}</button><button class="d-ib" data-act="down" data-id="${sc.id}" aria-label="Move scene later">${ic("chd", 15)}</button></div>
        <div class="d-k">Voiceover</div><p class="d-script">“${esc(sc.vo)}”</p><p class="d-about">${esc(sc.about)}</p>
        <div class="d-k">Layers in this scene</div><div>${sceneClips(sc).filter((x) => x.clips.length).map(({ t, clips }) => `<div class="d-lr${t.muted ? " muted" : ""}"><button class="d-lrm" data-act="clip" data-id="${clips[0].id}"><span class="d-tid">${t.id}</span><span class="d-ln"><b>${t.name}</b><small>${esc(clips.map((c) => (t.kind === "caption" ? c.text : c.name)).join(" · "))}</small></span></button>${t.kind === "audio" ? `<span class="d-db">${db(clips[0].gain)}</span>` : ""}<button class="d-hb${t.muted ? " on" : ""}" data-act="mute" data-id="${t.id}" title="Mutes the whole ${t.name} track" aria-label="${t.muted ? "Unmute" : "Mute"} ${t.name} track">${ic(t.kind === "audio" ? (t.muted ? "volx" : "vol") : t.muted ? "x" : "eye", 14)}</button></div>`).join("")}</div>
        <div class="d-k">Ask about this scene</div><div class="d-ask"><button class="chip" data-act="ask" data-q="Tighten the pauses in scene ${n}">Tighten the pauses</button><button class="chip" data-act="ask" data-q="Make scene ${n} shorter">Make it shorter</button>${n > 1 ? `<button class="chip" data-act="ask" data-q="Move scene ${n} before scene ${n - 1}">Move before scene ${n - 1}</button>` : ""}</div>`;
    }

    function float() {
      if (S.thinking) return `<div class="d-float"><div class="ai-thinking"><i></i><i></i><i></i><span>${esc(S.thinking)}…</span></div></div>`;
      if (S.proposal) return `<div class="d-float">${proposalHtml()}</div>`;
      return "";
    }

    return {
      root,
      update() {
        const ok = S.p.scenes.filter((s) => s.ok).length, lt = S.tabs.d || "lens";
        root.firstElementChild.dataset.tool = S.tool;
        setHtml(q(".d-rev"), `<span>Review</span><span class="d-cells">${S.p.scenes.map((s, i) => `<button class="${s.ok ? "ok" : ""}" style="flex:${s.dur};--i:${s.look}" data-act="scene" data-id="${s.id}" aria-label="Scene ${i + 1} · ${esc(s.title)} · ${s.ok ? "approved" : "needs review"}"></button>`).join("")}</span><span><b style="color:var(--text)">${ok}</b>/${S.p.scenes.length} approved</span>`);
        q(".d-saved").textContent = S.past.length ? `r${S.past.length + 14} · ${S.past.at(-1).label}` : "r14 · saved";
        setHtml(q(".d-rh"), `<b>Scenes</b><span class="mono">${S.p.scenes.length} · ${mmss(duration())}</span>`);
        setHtml(q(".d-list"), rail());
        setHtml(q(".d-nowh"), S.p.scenes.map((s, i) => `<span class="d-chip" data-now="${s.id}" style="--i:${s.look}"><i></i><b>${pad(i + 1)}</b> ${esc(s.title)}</span>`).join(""));
        setHtml(q(".d-scrub"), S.p.scenes.map((s, i) => `<button style="flex:${s.dur};--i:${s.look}" data-act="scene" data-id="${s.id}" data-now="${s.id}" aria-label="Scene ${i + 1}"></button>`).join("") + `<i class="d-sp"></i>`);
        const logN = S.log.filter((m) => m.who === "ai" && m.summary).length;
        setHtml(q(".d-tabs"), `<button class="${lt === "lens" ? "on" : ""}" data-act="tab" data-group="d" data-tab="lens">Lens</button><button class="${lt === "log" ? "on" : ""}" data-act="tab" data-group="d" data-tab="log">Director<span>${logN}</span></button>`);
        setHtml(q(".d-body"), lt === "log" ? aiFeedHtml() + `<div class="d-ask">${chipsHtml(4)}</div>` : lens());
        setHtml(q(".d-tools"), `<button class="d-ib${S.tool === "select" ? " on" : ""}" data-act="tool" data-tool="select" aria-label="Select (V)" title="Select (V)">${ic("pointer", 15)}</button><button class="d-ib${S.tool === "razor" ? " on" : ""}" data-act="tool" data-tool="razor" aria-label="Blade (C)" title="Blade (C)">${ic("split", 15)}</button>`);
        setHtml(q(".d-floatwrap"), float());
        q("[data-act=undo]").disabled = !S.past.length;
        q("[data-act=redo]").disabled = !S.future.length;
        root._lensScene = sceneOf()?.id;
        renderTimeline(root, tlo);
        root.querySelectorAll(".cl.r-main").forEach((el) => { const c = clipById(el.dataset.clip); if (c) el.style.setProperty("--i", c.look); });
        refreshCommon(root);
      },
      tick() {
        tickCommon(root);
        const sc = q(".d-scrub");
        const p = duration() ? S.playhead / duration() : 0;
        if (sc && sc._p !== p) { sc._p = p; sc.style.setProperty("--p", p); }
        if (!S.sel && (S.tabs.d || "lens") === "lens" && sceneAt(S.playhead)?.id !== root._lensScene) this.update();
      },
    };
  },
};
