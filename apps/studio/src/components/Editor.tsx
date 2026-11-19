"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { AssetRow, Job, LibrarySound, Op, Scene } from "@/lib/types";
import { clipEndMs } from "@/lib/types";
import { useEditor, type InitialEditor } from "@/lib/useEditor";
import type { Understanding } from "@/lib/types";
import { CommandPalette, type Command } from "./CommandPalette";
import { DirectorPanel } from "./DirectorPanel";
import { DrawOverlay } from "./DrawOverlay";
import { EnginePanel } from "./EnginePanel";
import { MediaLibrary } from "./MediaLibrary";
import { Toasts } from "./Toasts";
import { Preview } from "./Preview";
import { ProposalReview } from "./ProposalReview";
import { RevisionStrip } from "./RevisionStrip";
import { Timeline } from "./Timeline";
import { UnderstandingPanel } from "./UnderstandingPanel";

import { SpineIcon } from "./SpineIcon";
import { SceneRail, SpineLens, TrackMixer } from "./SpinePanels";

interface AssetDrag {
  asset: AssetRow;
  x: number;
  y: number;
}

export function Editor({ projectId, initial }: { projectId: string; initial?: InitialEditor }) {
  const ed = useEditor(projectId, initial);
  // Keep a live ref to editor api for window-level handlers.
  const edRef = useRef(ed);
  useLayoutEffect(() => { edRef.current = ed; }, [ed]);

  const [chosenLeftTab, setLeftTab] = useState<"Scenes" | "Media" | null>(null);
  const leftTab = chosenLeftTab ?? (ed.edl?.scenes?.length ? "Scenes" : "Media");
  const [rightTab, setRightTab] = useState<"Lens" | "Audio" | "Engines" | "History">("Lens");
  const scene = ed.edl?.scenes?.find(s => s.start_ms <= ed.playheadMs && ed.playheadMs < s.end_ms);
  const selectScene = (s: Scene) => { ed.select(null); ed.setPlayhead(s.start_ms); setRightTab("Lens"); };

  const [assetDrag, setAssetDrag] = useState<AssetDrag | null>(null);
  const [renderJobId, setRenderJobId] = useState<string | null>(null);
  const [textComposer, setTextComposer] = useState(false);
  const [drawComposer, setDrawComposer] = useState(false);
  const [insights, setInsights] = useState<
    { name: string; assetId: string; u: Understanding } | null
  >(null);
  const assetDragRef = useRef<AssetDrag | null>(null);

  const readOnly = ed.viewRev !== null;
  const renderJob: Job | null = renderJobId ? (ed.jobs[renderJobId] ?? null) : null;

  // ---- library -> timeline drag (pointer-based) ----------------------------

  const onAssetPointerDown = useCallback((asset: AssetRow, e: React.PointerEvent) => {
    const d = { asset, x: e.clientX, y: e.clientY };
    assetDragRef.current = d;
    setAssetDrag(d);
  }, []);

  useEffect(() => {
    const move = (e: PointerEvent) => {
      if (!assetDragRef.current) return;
      const d = { ...assetDragRef.current, x: e.clientX, y: e.clientY };
      assetDragRef.current = d;
      setAssetDrag(d);
    };
    const up = async (e: PointerEvent) => {
      const d = assetDragRef.current;
      assetDragRef.current = null;
      setAssetDrag(null);
      if (!d) return;
      const laneEl = document
        .elementFromPoint(e.clientX, e.clientY)
        ?.closest("[data-track-id]") as HTMLElement | null;
      if (!laneEl) return;
      const trackId = laneEl.dataset.trackId!;
      const trackKind = laneEl.dataset.trackKind!;
      const compatible =
        (trackKind === "video" && (d.asset.kind === "video" || d.asset.kind === "image")) ||
        (trackKind === "audio" && (d.asset.kind === "audio" || d.asset.kind === "video"));
      if (!compatible) return;
      const rect = laneEl.getBoundingClientRect();
      const msPerPx = 1000 / edRef.current.pxPerSec;
      const dropMs = Math.max(0, Math.round((e.clientX - rect.left) * msPerPx));
      const durMs = d.asset.duration_ms ?? 3000;
      // Snap into the nearest free slot: clamp to the end of the previous clip.
      const edl = edRef.current.edl;
      const track = edl?.tracks.find((t) => t.id === trackId);
      let start = dropMs;
      if (track) {
        for (const c of track.clips) {
          const s = c.start_ms;
          const end = clipEndMs(c);
          if (start >= s && start < end) start = end;
        }
      }
      const ok = await edRef.current.applyOps([
        {
          op: "add_clip",
          track: trackId,
          asset: d.asset.asset_id,
          in_ms: 0,
          out_ms: durMs,
          start_ms: start,
        },
      ]);
      if (ok) edRef.current.setPlayhead(start); // preview shows the new clip
    };
    const cancel = () => {
      // Touch scrolling / OS gestures can cancel the pointer mid-drag.
      assetDragRef.current = null;
      setAssetDrag(null);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", cancel);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", cancel);
    };
  }, []);


  // ---- keyboard: S split, Del remove, Ctrl+Z/Y ------------------------------

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      const s = edRef.current;
      if (e.ctrlKey && e.key.toLowerCase() === "z") {
        e.preventDefault();
        s.undo();
      } else if (e.ctrlKey && e.key.toLowerCase() === "y") {
        e.preventDefault();
        s.redo();
      } else if (e.key.toLowerCase() === "s" && !e.ctrlKey && s.selection) {
        const found = s.edl?.tracks
          .flatMap((t) => t.clips)
          .find((c) => c.id === s.selection);
        if (found && found.start_ms < s.playheadMs && s.playheadMs < clipEndMs(found)) {
          s.applyOps([{ op: "split", clip: found.id, at_ms: s.playheadMs }]);
        }
      } else if ((e.key === "Delete" || e.key === "Backspace") && s.selection) {
        s.applyOps([{ op: "remove_clip", clip: s.selection, ripple: false }]);
        s.select(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const addTrack = (kind: "video" | "audio" | "caption", role?: "overlay") =>
    ed.applyOps([{ op: "add_track", kind, ...(role ? { role, name: "Overlays & stickers" } : {}) }]);

  // Double-click fallback: append the asset to the first compatible track.
  const addAssetToTimeline = useCallback(async (asset: AssetRow) => {
    const s = edRef.current;
    const wantKind = asset.kind === "audio" ? "audio" : "video";
    const track = asset.kind === "image"
      ? s.edl?.tracks.find((t) => t.kind === "video" && t.role === "overlay") ?? s.edl?.tracks.find((t) => t.kind === "video")
      : s.edl?.tracks.find((t) => t.kind === wantKind);
    if (!track) {
      return;
    }
    let start = 0;
    for (const c of track.clips) start = Math.max(start, clipEndMs(c));
    const ok = await s.applyOps([
      {
        op: "add_clip",
        track: track.id,
        asset: asset.asset_id,
        in_ms: 0,
        out_ms: asset.duration_ms ?? 3000,
        start_ms: start,
      },
    ]);
    if (ok) s.setPlayhead(start);
  }, []);

  const importSoundToTimeline = useCallback(async (sound: LibrarySound) => {
    const existing = edRef.current.assets.find(asset =>
      asset.status === "ready" &&
      asset.src.split("/").pop()?.replace(/_\d+(?=\.[^.]+$)/, "") === sound.filename,
    );
    const asset = existing ?? await edRef.current.importSound(sound.id);
    if (!asset?.duration_ms) return;
    const current = edRef.current;
    const start = current.playheadMs;
    const end = start + asset.duration_ms;
    const role = sound.kind === "music" ? "music" : "sfx";
    const track = current.edl?.tracks.find(t =>
      t.kind === "audio" && t.role === role &&
      t.clips.every(c => clipEndMs(c) <= start || c.start_ms >= end),
    );
    const ops: Op[] = [];
    let trackId = track?.id;
    if (!track) {
      trackId = `trk_${crypto.randomUUID().replace(/-/g, "").slice(0, 8)}`;
      ops.push({ op: "add_track", id: trackId, kind: "audio", role,
        name: sound.kind === "music" ? `Music · ${sound.title}` : "Sound effects" });
    }
    ops.push({ op: "add_clip", track: trackId!, asset: asset.asset_id,
      in_ms: 0, out_ms: asset.duration_ms, start_ms: start });
    if (await current.applyOps(ops)) current.setPlayhead(start);
  }, []);

  const addCaption = () => {
    const track = ed.edl?.tracks.find((t) => t.kind === "caption" || t.kind === "text");
    if (!track) return;
    const text = window.prompt("Caption text:");
    if (!text) return;
    const start = ed.playheadMs;
    ed.applyOps([
      { op: "add_caption", track: track.id, text, start_ms: start, end_ms: start + 2000 },
    ]);
  };

  const addTextLayer = async (text: string, template: string, durationMs: number) => {
    const current = edRef.current;
    const start = current.playheadMs;
    const end = start + durationMs;
    const freeTrack = current.edl?.tracks.find(track =>
      track.kind === "text" && track.clips.every(clip => clipEndMs(clip) <= start || clip.start_ms >= end),
    );
    const ops: Op[] = [];
    const trackId = freeTrack?.id ?? `trk_${crypto.randomUUID().replace(/-/g, "").slice(0, 8)}`;
    const clipId = `clp_${crypto.randomUUID().replace(/-/g, "").slice(0, 8)}`;
    if (!freeTrack) ops.push({ op: "add_track", id: trackId, kind: "text", role: "other", name: "Text & titles" });
    ops.push({ op: "add_caption", id: clipId, track: trackId, text,
      start_ms: start, end_ms: end, cap_style: template });
    if (await current.applyOps(ops)) {
      current.select(clipId);
      setRightTab("Lens");
      setTextComposer(false);
    }
  };

  const addDrawingLayer = async (file: File, durationMs: number) => {
    const asset = await edRef.current.uploadAndWait(file);
    if (!asset) return;
    const current = edRef.current;
    const start = current.playheadMs;
    const end = start + durationMs;
    const freeTrack = current.edl?.tracks.find(track =>
      track.kind === "video" && track.role === "overlay" &&
      track.clips.every(clip => clipEndMs(clip) <= start || clip.start_ms >= end),
    );
    const ops: Op[] = [];
    const trackId = freeTrack?.id ?? `trk_${crypto.randomUUID().replace(/-/g, "").slice(0, 8)}`;
    const clipId = `clp_${crypto.randomUUID().replace(/-/g, "").slice(0, 8)}`;
    if (!freeTrack) ops.push({ op: "add_track", id: trackId, kind: "video", role: "overlay", name: "Drawings & annotations" });
    ops.push({ op: "add_clip", id: clipId, track: trackId, asset: asset.asset_id,
      in_ms: 0, out_ms: durationMs, start_ms: start });
    if (await current.applyOps(ops)) {
      current.select(clipId);
      setRightTab("Lens");
      setDrawComposer(false);
    }
  };

  const onRender = async () => {
    const jobId = await ed.startRender();
    if (jobId) setRenderJobId(jobId);
  };

  const onAnalyze = (asset: AssetRow, language?: string) => {
    ed.analyze(asset.asset_id, language);
  };

  const onViewUnderstanding = async (asset: AssetRow) => {
    const u = await ed.loadUnderstanding(asset.asset_id);
    if (u) {
      setInsights({
        name: asset.src.split("/").pop() ?? asset.asset_id,
        assetId: asset.asset_id,
        u,
      });
    }
  };

  // Trigger a smart edit as a proposal the user then accepts/rejects.
  const proposeSmartEdit = async (op: Record<string, unknown>) => {
    const ok = await ed.proposeOps([op as never]);
    if (ok) setInsights(null); // proposal now shows in the review panel
  };

  const hasTimeline = !!ed.edl && ed.edl.project.duration_ms > 0;
  const commands: Command[] = [
    { id: "undo", group: "Edit", label: "Undo", hint: "Ctrl+Z",
      disabled: readOnly, run: ed.undo },
    { id: "redo", group: "Edit", label: "Redo", hint: "Ctrl+Y",
      disabled: readOnly, run: ed.redo },
    { id: "split", group: "Edit", label: "Split selected clip at playhead", hint: "S",
      disabled: !ed.selection,
      run: () => {
        const found = ed.edl?.tracks.flatMap((t) => t.clips)
          .find((c) => c.id === ed.selection);
        if (found && found.start_ms < ed.playheadMs && ed.playheadMs < clipEndMs(found)) {
          ed.applyOps([{ op: "split", clip: found.id, at_ms: ed.playheadMs }]);
        }
      } },
    { id: "delete", group: "Edit", label: "Delete selected clip", hint: "Del",
      disabled: !ed.selection,
      run: () => {
        if (ed.selection) {
          ed.applyOps([{ op: "remove_clip", clip: ed.selection, ripple: false }]);
          ed.select(null);
        }
      } },
    { id: "track-video", group: "Timeline", label: "Add video track",
      run: () => addTrack("video") },
    { id: "track-overlay", group: "Timeline", label: "Add overlay / sticker track",
      run: () => addTrack("video", "overlay") },
    { id: "track-audio", group: "Timeline", label: "Add audio track",
      run: () => addTrack("audio") },
    { id: "track-caption", group: "Timeline", label: "Add caption track",
      run: () => addTrack("caption") },
    { id: "caption", group: "Timeline", label: "Add caption at playhead",
      run: addCaption },
    { id: "text", group: "Timeline", label: "Add text layer at playhead",
      run: () => setTextComposer(true) },
    { id: "draw", group: "Timeline", label: "Draw annotation at playhead",
      run: () => setDrawComposer(true) },
    { id: "render", group: "Output", label: "Render (L2 final)",
      disabled: !hasTimeline, run: onRender },
    { id: "reframe", group: "AI", label: "Propose: reframe to 9:16 (vertical)",
      disabled: !hasTimeline,
      run: () => proposeSmartEdit({ op: "reframe", width: 1080, height: 1920 }) },
  ];

  return (
    <div className="spine-editor flex h-screen min-w-0 flex-col bg-zinc-950 text-zinc-100">
      <header className="spine-top">
        <Link href="/" className="spine-word" title="All projects">CutLab</Link>
        <h1 className="spine-project" data-testid="project-name">{ed.edl?.project.name ?? "…"}</h1>
        <span className="spine-format" data-testid="project-format">{ed.edl ? `${ed.edl.project.canvas.width}×${ed.edl.project.canvas.height}` : ""}</span>
        <div className="spine-review"><span>Review</span><div className="spine-review-cells">{ed.edl?.scenes?.map((s,i) => <button key={s.id} title={`${s.title} · ${s.approved ? "approved" : "needs review"}`} onClick={() => selectScene(s)} style={{flex:s.end_ms-s.start_ms, background:`hsl(${i*45+25} ${s.approved ? "45% 58%" : "14% 24%"})`}} />)}</div><span><b>{ed.edl?.scenes?.filter(s=>s.approved).length ?? 0}</b>/{ed.edl?.scenes?.length ?? 0} approved</span></div>
        <span className="spine-saved">r{ed.headRev} · {ed.busy ? "saving…" : "saved"}</span>
        <button className="spine-icon" data-testid="undo-button" disabled={readOnly || ed.busy} onClick={ed.undo} title="Undo (Ctrl+Z)" aria-label="Undo"><SpineIcon name="undo" /></button>
        <button className="spine-icon" data-testid="redo-button" disabled={readOnly || ed.busy} onClick={ed.redo} title="Redo (Ctrl+Y)" aria-label="Redo"><SpineIcon name="redo" /></button>
        <button className="spine-export" data-testid="render-button" onClick={onRender} disabled={!hasTimeline || ed.busy || renderJob?.state === "running" || renderJob?.state === "queued"}><SpineIcon name="check" size={14} /> Export</button>
      </header>

      {ed.serverDown && (
        <div
          className="flex items-center gap-3 bg-red-900 px-3 py-2 text-sm text-red-100"
          data-testid="offline-banner"
        >
          <span className="font-semibold">CutLab server is offline</span>
          <span className="text-red-200">
            Nothing can be saved. Start it with{" "}
            <code className="rounded bg-red-950 px-1">scripts\dev.ps1</code> — retrying
            automatically…
          </span>
        </div>
      )}
      {ed.error && (
        <div
          className="flex items-center justify-between bg-red-950 px-3 py-1 text-xs text-red-200"
          data-testid="error-banner"
        >
          <span>{ed.error}</span>
          <button className="ml-4 underline" onClick={ed.clearError}>
            dismiss
          </button>
        </div>
      )}

      {/* main panes */}
      <div className="spine-mid flex min-h-0 flex-1">
        <div className="spine-left flex min-h-0 shrink-0 flex-col">
          <nav className="spine-tabs" aria-label="Story navigation">{(["Scenes", "Media"] as const).map(tab => <button key={tab} aria-pressed={leftTab === tab} onClick={() => setLeftTab(tab)}>{tab}</button>)}</nav>
          {leftTab === "Scenes" ? <SceneRail ed={ed} scene={scene} onScene={selectScene} onMedia={() => setLeftTab("Media")} /> : <div className="min-h-0 flex-1">
          <MediaLibrary
            projectId={projectId}
            assets={ed.assets}
            jobs={ed.jobs}
            onUpload={ed.upload}
            onAssetPointerDown={onAssetPointerDown}
            onAssetAdd={addAssetToTimeline}
            onAnalyze={onAnalyze}
            onCutout={(asset) => { void ed.cutout(asset.asset_id); }}
            onExtractAudio={(asset) => { void ed.extractAudio(asset.asset_id); }}
            onTextToSound={(text) => { void ed.textToSound(text); }}
            onImportSound={(sound) => { void importSoundToTimeline(sound); }}
            onViewUnderstanding={onViewUnderstanding}
          /></div>}
        </div>
        <div className="min-w-0 flex-1">
          <Preview
            projectId={projectId}
            edl={ed.edl}
            playheadMs={ed.playheadMs}
            renderJob={renderJob}
            onRender={onRender}
            onSeek={ed.setPlayhead}
          />
        </div>
        <aside className="spine-right flex min-h-0 shrink-0 flex-col border-l border-zinc-800">
          <nav className="spine-tabs" aria-label="Inspector">{(["Lens", "Audio", "Engines", "History"] as const).map(tab => <button key={tab} aria-pressed={rightTab === tab} onClick={() => setRightTab(tab)}>{tab}</button>)}</nav>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {rightTab === "Lens" && <SpineLens ed={ed} scene={scene} />}
            {rightTab === "Audio" && <TrackMixer ed={ed} />}
            {rightTab === "Engines" && <EnginePanel ed={ed} scene={scene} />}
            {rightTab === "History" && <RevisionStrip revisions={ed.revisions} headRev={ed.headRev} viewRev={ed.viewRev} onView={ed.viewRevision} />}
          </div>
        </aside>
      </div>
      {readOnly && <div className="spine-history-banner">Viewing revision {ed.viewRev} · editing paused <button onClick={() => ed.viewRevision(null)}>Return to current edit</button></div>}
      <div className="spine-director">
        <div className="spine-edit-tools"><button className="spine-icon" aria-label="Select clips" title="Select clips" onClick={() => ed.select(null)}><SpineIcon name="pointer" /></button><button className="spine-icon" title="Split at playhead (S)" disabled={!ed.selection || readOnly} onClick={() => ed.selection && ed.applyOps([{op:"split",clip:ed.selection,at_ms:ed.playheadMs}])}><SpineIcon name="split" /></button><button className="spine-icon" title="Delete selected clip" disabled={!ed.selection || readOnly} onClick={() => ed.selection && ed.applyOps([{op:"remove_clip",clip:ed.selection}])}><SpineIcon name="trash" /></button><details className="spine-add"><summary title="Add track, text, drawing, or caption"><SpineIcon name="plus" /></summary><div><button onClick={() => setTextComposer(true)}>Text layer</button><button onClick={() => setDrawComposer(true)}>Draw annotation</button><button onClick={addCaption}>Caption</button><button onClick={() => addTrack("video")}>Video track</button><button onClick={() => addTrack("video", "overlay")}>Overlay / sticker track</button><button onClick={() => addTrack("audio")}>Audio track</button></div></details></div>
        <DirectorPanel projectId={projectId} disabled={readOnly} onProposed={ed.refresh} />
        <div className="spine-proposal-float max-h-40 overflow-auto"><ProposalReview proposals={ed.proposals} onAccept={ed.acceptProposal} onReject={ed.rejectProposal} onView={ed.viewRevision} /></div>
      </div>

      {/* timeline */}
      <div className="spine-timeline-wrap shrink-0">
        <Timeline
          projectId={projectId}
          edl={ed.edl}
          selection={ed.selection}
          playheadMs={ed.playheadMs}
          pxPerSec={ed.pxPerSec}
          readOnly={readOnly || ed.busy}
          onSelect={(id) => { ed.select(id); if (id) setRightTab("Lens"); }}
          onPlayhead={ed.setPlayhead}
          onZoom={ed.setZoom}
          onOps={ed.applyOps}
        />
      </div>

      <footer className="spine-footer"><span>CUTLAB / STUDIO</span><span>{ed.busy ? "Saving…" : ed.serverDown ? "Offline" : `Revision ${ed.headRev}`} · {ed.edl?.scenes?.filter(s => s.approved).length ?? 0} scenes approved</span><span>Space · Play &nbsp; S · Split &nbsp; Ctrl K · Commands</span></footer>

      {insights && (
        <UnderstandingPanel
          name={insights.name}
          understanding={insights.u}
          onClose={() => setInsights(null)}
          captionTrackId={
            ed.edl?.tracks.find((t) => t.kind === "caption" || t.kind === "text")?.id ?? null
          }
          onPropose={proposeSmartEdit}
          onCompact={async (targetMs) => {
            if (!insights) return;
            await api.compactAsset(projectId, insights.assetId, targetMs);
            setInsights(null); // job runs; proposal appears in the review panel
          }}
          onRecap={async (targetMinutes) => {
            if (!insights) return;
            await api.recapAsset(projectId, insights.assetId, targetMinutes);
            setInsights(null);
          }}
        />
      )}

      {textComposer && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6" onClick={() => setTextComposer(false)}><form className="w-full max-w-sm space-y-3 rounded-lg border border-zinc-700 bg-zinc-950 p-4" onClick={e => e.stopPropagation()} onSubmit={e => { e.preventDefault(); const f = new FormData(e.currentTarget); void addTextLayer(String(f.get("text")).trim(), String(f.get("template")), Math.round(Number(f.get("duration")) * 1000)); }}><div className="flex items-center justify-between"><h2 className="text-sm font-semibold text-zinc-100">Add text at playhead</h2><button type="button" className="text-xs text-zinc-400" onClick={() => setTextComposer(false)}>Close</button></div><label className="block text-xs text-zinc-400">Text<textarea name="text" aria-label="Text layer content" required maxLength={500} autoFocus className="mt-1 min-h-20 w-full rounded border border-zinc-700 bg-zinc-900 p-2 text-zinc-100" placeholder="Title, name, callout, or note" /></label><label className="block text-xs text-zinc-400">Template<select name="template" aria-label="Text template" defaultValue="title-card" className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 p-2 text-zinc-100"><option value="title-card">Title Card · centered</option><option value="lower-third">Lower Third · bottom left</option><option value="top-title">Top Title</option><option value="boxed">Boxed Callout</option><option value="default">Clean Text</option></select></label><label className="block text-xs text-zinc-400">Duration · seconds<input name="duration" aria-label="Text duration" type="number" min="0.2" max="3600" step="0.1" defaultValue="3" required className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 p-2 text-zinc-100" /></label><button className="w-full rounded bg-amber-500 px-3 py-2 text-xs font-semibold text-zinc-950 hover:bg-amber-400">Add text layer</button></form></div>}
      {drawComposer && <DrawOverlay width={ed.edl?.project.canvas.width ?? 1920} height={ed.edl?.project.canvas.height ?? 1080} onClose={() => setDrawComposer(false)} onSave={addDrawingLayer} />}

      {/* asset drag ghost */}
      {assetDrag && (
        <div
          className="pointer-events-none fixed z-50 rounded border border-emerald-500 bg-emerald-950/90 px-2 py-1 text-[10px] text-emerald-200"
          style={{ left: assetDrag.x + 8, top: assetDrag.y + 8 }}
        >
          {assetDrag.asset.src.split("/").pop()}
        </div>
      )}

      <CommandPalette commands={commands} />
      <Toasts jobs={ed.jobs} />
    </div>
  );
}
