// Concept C — Director (AI-native): story strip + review notes + propose/apply; manual controls only on selection.
addCss(`
.cC{--bg:#101217;--panel:#161920;--raised:#1d2129;--hover:#262b35;--line:rgba(170,190,230,.08);--text:#e7e9ef;--dim:#8d94a5;--faint:#5b6173;--ai:#a594ff;--ai-bg:rgba(165,148,255,.1);--ok:#5fd39a;
  --head-w:40px;--ruler-h:20px;--band-h:0px;--h-cap:16px;--h-over:18px;--h-main:30px;--h-audio:20px;--clip-inset:2px;
  --tl-bg:transparent;--tl-head-bg:var(--bg);--tick:rgba(170,190,230,.08);--tick-text:#5b6173;--tick-font:400 9.5px/1 "Geist Mono",Consolas,monospace;--ph:#fff;
  --pr-a:rgba(165,148,255,.3);--pr-line:#a594ff;--scope-dim:rgba(16,18,23,.5);--scope-line:rgba(255,255,255,.4);--note:#a594ff;--range-bg:#2a2f3a;--range-thumb:#e7e9ef;
  width:1440px;height:860px;display:grid;grid-template-columns:1fr 392px;grid-template-rows:52px 1fr;background:var(--bg);color:var(--text);font:13px/1.45 "Instrument Sans",system-ui,sans-serif}
.cC .mono{font-family:"Geist Mono",Consolas,monospace;font-variant-numeric:tabular-nums}
.c-top{grid-column:1/-1;display:flex;align-items:center;gap:14px;padding:0 16px 0 20px;border-bottom:1px solid var(--line)}
.c-top h1{margin:0;font-size:15px;font-weight:600;letter-spacing:-.01em}
.c-pill{padding:3px 8px;border-radius:999px;background:var(--ai-bg);color:var(--ai);font-size:11.5px;font-weight:500}
.c-src{color:var(--faint);font-size:12px}
.c-prog{margin:0 auto;display:flex;align-items:center;gap:10px;color:var(--dim);font-size:12px}
.c-bar{width:140px;height:4px;border-radius:2px;background:var(--raised);overflow:hidden}.c-bar i{display:block;height:100%;background:var(--ok);border-radius:2px}
.c-ib{width:30px;height:30px;border-radius:8px;display:grid;place-items:center;color:var(--dim)}.c-ib:hover:not(:disabled){background:var(--raised);color:var(--text)}
.c-btn{height:30px;padding:0 12px;border-radius:8px;background:var(--raised);display:flex;align-items:center;gap:6px;font-weight:500}.c-btn:hover{background:var(--hover)}
.c-main{grid-column:1;grid-row:2;display:grid;grid-template-rows:452px 178px 178px;min-height:0;min-width:0}
.c-view{display:flex;flex-direction:column;align-items:center;padding:18px 24px 0;min-height:0}
.c-view .pv{height:382px;aspect-ratio:16/9;border-radius:10px}.c-view .pv canvas{height:100%;width:auto}
.c-tr{width:680px;display:grid;grid-template-columns:1fr auto 1fr;align-items:center;height:52px}
.c-tc{color:var(--dim);font-size:12px}.c-tc b{color:var(--text);font-weight:500}
.c-play{width:36px;height:36px;border-radius:50%;background:var(--text);color:var(--bg);display:grid;place-items:center;margin:0 6px}
.c-trm{display:flex;align-items:center}
.c-nowl{justify-self:end;color:var(--dim);font-size:12px;white-space:nowrap}.c-nowl span{display:none}.c-nowl span.now{display:inline}.c-nowl b{color:var(--text);font-weight:500}
.c-story{display:flex;gap:10px;contain:inline-size;overflow-x:auto;padding:8px 24px 14px;scrollbar-width:thin;scrollbar-color:#2a2f3a transparent}
.c-card{flex:none;width:208px;border-radius:10px;background:var(--panel);box-shadow:inset 0 0 0 1px var(--line);overflow:hidden;display:flex;flex-direction:column;text-align:left}
.c-card:hover{box-shadow:inset 0 0 0 1px rgba(255,255,255,.16)}.c-card.now{box-shadow:inset 0 0 0 1px rgba(255,255,255,.28)}.c-card.sel{box-shadow:inset 0 0 0 2px var(--text)}
.c-cth{display:block;height:50px;background-size:cover;background-position:center;position:relative}
.c-cth b{position:absolute;left:8px;bottom:6px;font:500 11px "Geist Mono",monospace;color:#fff;text-shadow:0 1px 2px #000}
.c-cth em{position:absolute;right:8px;bottom:6px;font:normal 11px "Geist Mono",monospace;color:#fff;text-shadow:0 1px 2px #000}
.c-cb{display:flex;flex-direction:column;gap:4px;padding:8px 10px 10px;flex:1;min-height:0}
.c-ct{display:flex;justify-content:space-between;gap:6px;font-weight:600;font-size:12.5px}
.c-flag{font-size:10.5px;font-weight:500;color:var(--ai);white-space:nowrap}.c-flag.ok{color:var(--ok)}
.c-cvo{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;color:var(--dim);font-size:11.5px;line-height:1.45}
.c-tlsec{display:flex;flex-direction:column;border-top:1px solid var(--line);min-height:0}
.c-selbar{height:34px;flex:none;display:flex;align-items:center;gap:8px;padding:0 12px 0 16px}
.c-sbn{display:flex;align-items:baseline;gap:8px;min-width:0;white-space:nowrap;overflow:hidden;margin-right:auto}.c-sbn em{font-style:normal;color:var(--faint);font-size:12px}.c-hint{color:var(--faint)}
.c-sb{height:26px;padding:0 9px;border-radius:7px;background:var(--raised);display:flex;align-items:center;gap:5px;font-size:12px;white-space:nowrap}.c-sb:hover{background:var(--hover)}.c-sb.on{background:var(--ok);color:#0b1f15}
.c-vol{display:flex;align-items:center;gap:8px;color:var(--dim)}.c-vol input{width:110px}.c-vol output{font:12px "Geist Mono",monospace;min-width:52px}
.c-vr{width:1px;height:16px;background:var(--line);margin:0 2px}
.c-tlw{flex:1;min-height:0;padding:0 0 6px}
.c-th{width:100%;height:100%;font:500 9.5px "Geist Mono",monospace;color:var(--faint)}.c-th:hover{color:var(--text)}.cC .th.is-muted .c-th{color:#e0795f;text-decoration:line-through}
.cC .cl{border-radius:4px;font-size:10.5px}.cC .cl .cn{padding:1px 5px}
.cC .cl.r-main::after{content:"";position:absolute;inset:0;background:rgba(10,12,16,.15)}.cC .cl.r-main .cn{color:#fff;text-shadow:0 1px 2px #000}
.cC .cl.r-over{background:#342e4a;color:#cfc5ff}.cC .cl.r-cap{background:#39362a;color:#e9d9a0}
.cC .cl.r-vo{background:#1b2f40;color:#7fb8e6}.cC .cl.r-music{background:#1c3530;color:#6fcfae}.cC .cl.r-sfx{background:#36271f;color:#e3a07f}
.cC .cl .wv{opacity:.9}.cC .ln.r-vo .cn,.cC .ln.r-music .cn,.cC .ln.r-sfx .cn,.cC .ln.r-cap .cn{display:none}
.cC .cl.sel{box-shadow:inset 0 0 0 2px #fff;z-index:2}.cC .cl.sel .h{background:rgba(255,255,255,.9)}
.c-dir{grid-column:2;grid-row:2;border-left:1px solid var(--line);display:flex;flex-direction:column;min-height:0;background:var(--panel)}
.c-dh{display:flex;align-items:center;gap:10px;padding:14px 18px 10px}
.c-dh h2{margin:0;font-size:14px;font-weight:600}.c-dh .ai-ctx{margin-left:auto;font-size:11.5px;color:var(--dim);padding:3px 8px;border-radius:6px;background:var(--raised);max-width:220px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.c-notes{padding:0 12px 10px;display:flex;flex-direction:column;gap:6px;border-bottom:1px solid var(--line)}
.c-nh{display:flex;justify-content:space-between;padding:0 6px 2px;font-size:11px;color:var(--faint);text-transform:uppercase;letter-spacing:.06em;font-weight:500}
.c-note{display:grid;grid-template-columns:auto 1fr auto;gap:10px;align-items:center;padding:8px 8px 8px 10px;border-radius:9px;background:var(--bg)}
.c-note i{width:7px;height:7px;border-radius:2px;transform:rotate(45deg);background:var(--ai)}
.c-note p{margin:0;font-size:12.5px;line-height:1.35}.c-note p small{display:block;color:var(--faint);font-size:11px}
.c-fix{height:26px;padding:0 10px;border-radius:7px;color:var(--ai);background:var(--ai-bg);font-size:12px;font-weight:500}.c-fix:hover{background:rgba(165,148,255,.2)}
.c-clean{padding:8px 10px;color:var(--ok);font-size:12.5px}
.c-feed{flex:1;overflow:auto;padding:14px 18px;display:flex;flex-direction:column;gap:12px;scrollbar-width:thin;scrollbar-color:#2a2f3a transparent}
.cC .ai-sys{font-size:11px;color:var(--faint)}
.cC .ai-user{display:flex;flex-direction:column;align-items:flex-end;gap:3px}.cC .ai-user p{margin:0;padding:8px 12px;border-radius:12px 12px 3px 12px;background:var(--raised);max-width:88%}.cC .ai-user small{font-size:10.5px;color:var(--faint)}
.cC .ai-msg{color:var(--dim)}
.cC .ai-card{padding:10px 12px;border-radius:10px;box-shadow:inset 2px 0 var(--ai);background:var(--bg)}
.cC .ai-card-h{display:flex;justify-content:space-between;gap:10px}.cC .ai-card-h em{font-style:normal;font-size:11px;color:var(--ok);white-space:nowrap}
.cC .st-rejected,.cC .st-expired{box-shadow:inset 2px 0 var(--faint);opacity:.7}.cC .st-rejected em,.cC .st-expired em{color:var(--faint)!important}
.cC .ai-card ul,.cC .ai-prop ul{margin:6px 0 0;padding-left:16px;color:var(--dim);font-size:12px}
.cC .ai-thinking{color:var(--ai);font-size:12px}.cC .ai-thinking span{margin-left:5px;color:var(--dim)}
.cC .ai-prop{padding:12px 14px;border-radius:12px;background:linear-gradient(180deg,rgba(165,148,255,.13),rgba(165,148,255,.05));box-shadow:inset 0 0 0 1px rgba(165,148,255,.45)}
.cC .ai-prop-k{font-size:10.5px;font-weight:600;color:var(--ai);text-transform:uppercase;letter-spacing:.07em}.cC .ai-prop-t{font-size:14px;font-weight:600;margin-top:4px}
.cC .ai-prop-a{display:flex;align-items:center;gap:8px;margin-top:12px}.cC .ai-prop-a small{margin-left:auto;color:var(--faint);font-size:11px}
.cC .b-apply{height:30px;padding:0 14px;border-radius:8px;background:var(--ai);color:#15102e;font-weight:600}.cC .b-dismiss{height:30px;padding:0 12px;border-radius:8px;background:var(--hover)}
.c-sugg{display:flex;gap:6px;flex-wrap:wrap;padding:0 16px 10px}
.cC .chip{padding:5px 10px;border-radius:999px;box-shadow:inset 0 0 0 1px var(--line);color:var(--dim);font-size:11.5px}.cC .chip:hover{color:var(--text);box-shadow:inset 0 0 0 1px rgba(165,148,255,.5)}
.cC .ai-compose{margin:0 14px 14px;padding:12px 10px 10px 14px;border-radius:14px;background:var(--bg);box-shadow:inset 0 0 0 1px var(--line);flex-wrap:wrap}
.cC .ai-compose:focus-within{box-shadow:inset 0 0 0 1px var(--ai),0 0 0 4px rgba(165,148,255,.12)}
.cC .ai-compose .ai-ctx{display:none}.cC .ai-compose textarea{font-size:13.5px}
.cC .ai-compose button{width:32px;height:32px;border-radius:10px;background:var(--ai);color:#15102e;display:grid;place-items:center}
.c-kb{padding:0 18px 12px;margin-top:-6px;color:var(--faint);font-size:11px}
`);

CONCEPTS.C = {
  name: "Director",
  tag: "AI-native",
  thesis: "Built around talking to the edit. The story strip reads like a script — each scene with its voiceover — while the Director reviews the cut, flags problems on the timeline and proposes fixes you apply or dismiss. Manual controls appear only for what you select.",
  pros: ["Fastest path from “this feels off” to a fixed cut", "Review notes make the AI a second editor, not a chat box", "Scenes and voiceover readable at a glance"],
  cons: ["Precise manual work (trims, levels) gets little room", "Leans on the AI being right — trust has to be earned", "Compact timeline gets cramped with many layers"],
  mount(root) {
    const q = (s) => root.querySelector(s);
    const approved = () => S.p.scenes.filter((s) => s.ok).length;
    root.innerHTML = `<div class="cC">
      <header class="c-top"><h1>${esc(S.p.name)}</h1><span class="c-pill">In review</span><span class="c-src">${S.p.engine} · ${S.p.run}</span>
        <div class="c-prog"></div>
        <button class="c-ib" data-act="undo" aria-label="Undo">${ic("undo")}</button><button class="c-ib" data-act="redo" aria-label="Redo">${ic("redo")}</button><button class="c-btn" data-act="soon">${ic("export", 14)} Export</button></header>
      <div class="c-main">
        <section class="c-view">${previewHtml()}
          <div class="c-tr"><span class="c-tc mono"><b data-tc></b> / <span data-tc="dur"></span></span>
            <div class="c-trm"><button class="c-ib" data-act="scene-prev" aria-label="Previous scene">${ic("prev", 15)}</button><button class="c-play" data-act="play" data-s="16" aria-label="Play"></button><button class="c-ib" data-act="scene-next" aria-label="Next scene">${ic("next", 15)}</button></div>
            <span class="c-nowl"></span></div></section>
        <section class="c-story" aria-label="Story"></section>
        <section class="c-tlsec"><div class="c-selbar"></div><div class="c-tlw">${timelineHtml()}</div></section></div>
      <aside class="c-dir"><div class="c-dh"><h2>Director</h2><span class="ai-ctx" data-ctx></span></div><div class="c-notes"></div>
        <div class="c-feed" data-stick></div><div class="c-sugg">${chipsHtml(3, 0)}</div>${composerHtml("Tell the director what to change…", 2)}
        <div class="c-kb">Enter to send · / to focus · edits are proposed, never applied silently</div></aside></div>`;

    const tlo = {
      notes: true, tickPx: 64,
      head: (t) => `<button class="c-th" data-act="mute" data-id="${t.id}" aria-label="${t.muted ? "Unmute" : "Mute"} ${t.name}" title="${t.name}">${t.id}</button>`,
    };

    function story() {
      const notes = reviewNotes();
      return S.p.scenes.map((s, i) => {
        const n = notes.filter((x) => x.at >= s.start && x.at < s.start + s.dur).length;
        const flag = n ? `<span class="c-flag">${n} note${n > 1 ? "s" : ""}</span>` : s.ok ? `<span class="c-flag ok">Approved</span>` : "";
        return `<button class="c-card${S.sel?.t === "scene" && S.sel.id === s.id ? " sel" : ""}" data-act="scene" data-id="${s.id}" data-now="${s.id}"><span class="c-cth" style="background-image:url(${thumbFor(s.look)})"><b>${pad(i + 1)}</b><em>${secs(s.dur)}</em></span><span class="c-cb"><span class="c-ct"><span>${esc(s.title)}</span>${flag}</span><span class="c-cvo">${esc(s.vo)}</span></span></button>`;
      }).join("");
    }

    function selbar() {
      if (S.sel?.t === "clip" && clipById(S.sel.id)) {
        const c = clipById(S.sel.id), t = trackOf(c.id), sound = t.kind === "audio" || t.role === "main";
        return `<span class="c-sbn"><b>${esc(nameOf(c))}</b><em>${t.name} · ${secs(c.dur)}</em></span>` +
          (sound ? `<span class="c-vol">${ic("vol", 14)}<input type="range" min="-60" max="12" step="0.5" value="${c.gain}" data-live="gain" data-id="${c.id}" aria-label="Clip volume"><output>${db(c.gain)}</output></span><button class="c-sb" data-act="clip-mute" data-id="${c.id}" aria-pressed="${c.muted}">${c.muted ? "Unmute" : "Mute"}</button><span class="c-vr"></span>` : "") +
          `<button class="c-sb" data-act="split">${ic("split", 13)} Split</button><button class="c-sb" data-act="del">${ic("trash", 13)} Delete</button><span class="c-vr"></span><button class="c-ib" data-act="zoom-out" aria-label="Zoom out">${ic("minus", 14)}</button><button class="c-ib" data-act="zoom-in" aria-label="Zoom in">${ic("plus", 14)}</button>`;
      }
      if (S.sel?.t === "scene" && ctxScene()) {
        const s = ctxScene();
        return `<span class="c-sbn"><b>Scene ${sceneNo(s)} · ${esc(s.title)}</b><em>${mmss(s.start)} – ${mmss(s.start + s.dur)}</em></span><button class="c-sb${s.ok ? " on" : ""}" data-act="approve" data-id="${s.id}">${ic("check", 13)} ${s.ok ? "Approved" : "Approve scene"}</button><button class="c-sb" data-act="up" data-id="${s.id}">${ic("chl", 13)} Earlier</button><button class="c-sb" data-act="down" data-id="${s.id}">Later ${ic("chr", 13)}</button><span class="c-vr"></span><button class="c-ib" data-act="zoom-out" aria-label="Zoom out">${ic("minus", 14)}</button><button class="c-ib" data-act="zoom-in" aria-label="Zoom in">${ic("plus", 14)}</button>`;
      }
      return `<span class="c-sbn c-hint">Select a clip or scene to adjust it — or tell the Director what to change.</span><button class="c-ib" data-act="zoom-out" aria-label="Zoom out">${ic("minus", 14)}</button><button class="c-ib" data-act="zoom-in" aria-label="Zoom in">${ic("plus", 14)}</button><button class="c-sb" data-act="fit">Fit</button>`;
    }

    function notes() {
      const list = reviewNotes();
      if (!list.length) return `<div class="c-nh"><span>Review notes</span></div><div class="c-clean">${ic("check", 13)} No open notes on this cut</div>`;
      return `<div class="c-nh"><span>Review notes</span><span>${list.length} open</span></div>` + list.map((n) => `<div class="c-note"><i></i><p>${esc(n.text)}<small>${n.kind} · ${mmss(n.at)}</small></p><button class="c-fix" data-act="ask" data-q="${esc(n.fix)}">Fix</button></div>`).join("");
    }

    return {
      root,
      update() {
        setHtml(q(".c-prog"), `<span>${approved()} of ${S.p.scenes.length} scenes approved</span><span class="c-bar"><i style="width:${(approved() / S.p.scenes.length) * 100}%"></i></span>`);
        setHtml(q(".c-nowl"), S.p.scenes.map((s, i) => `<span data-now="${s.id}">Scene ${i + 1} of ${S.p.scenes.length} · <b>${esc(s.title)}</b></span>`).join(""));
        setHtml(q(".c-story"), story());
        setHtml(q(".c-selbar"), selbar());
        setHtml(q(".c-notes"), notes());
        setHtml(q(".c-feed"), aiFeedHtml());
        q("[data-act=undo]").disabled = !S.past.length;
        q("[data-act=redo]").disabled = !S.future.length;
        renderTimeline(root, tlo);
        refreshCommon(root);
      },
      tick() { tickCommon(root); },
    };
  },
};
