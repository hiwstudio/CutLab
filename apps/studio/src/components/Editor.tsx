"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { AssetRow, Job } from "@/lib/types";
import { clipEndMs, isMediaClip } from "@/lib/types";
import { useEditor } from "@/lib/useEditor";
import type { Understanding } from "@/lib/types";
import { MediaLibrary } from "./MediaLibrary";
import { Preview } from "./Preview";
import { ProposalReview } from "./ProposalReview";
import { RevisionStrip } from "./RevisionStrip";
import { Timeline } from "./Timeline";
import { UnderstandingPanel } from "./UnderstandingPanel";

interface AssetDrag {
  asset: AssetRow;
  x: number;
  y: number;
}

export function Editor({ projectId }: { projectId: string }) {
  const ed = useEditor(projectId);
  const [assetDrag, setAssetDrag] = useState<AssetDrag | null>(null);
  const [renderJobId, setRenderJobId] = useState<string | null>(null);
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

  // Keep a live ref to editor api for window-level handlers.
  const edRef = useRef(ed);
  edRef.current = ed;

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

  const addTrack = (kind: "video" | "audio" | "caption") =>
    ed.applyOps([{ op: "add_track", kind }]);

  // Double-click fallback: append the asset to the first compatible track.
  const addAssetToTimeline = useCallback(async (asset: AssetRow) => {
    const s = edRef.current;
    const wantKind = asset.kind === "audio" ? "audio" : "video";
    const track = s.edl?.tracks.find((t) => t.kind === wantKind);
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

  const onRender = async () => {
    const jobId = await ed.startRender();
    if (jobId) setRenderJobId(jobId);
  };

  const onAnalyze = (asset: AssetRow) => {
    ed.analyze(asset.asset_id);
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

  return (
    <div className="flex h-screen flex-col bg-zinc-950 text-zinc-100">
      {/* header */}
      <header className="flex items-center gap-3 border-b border-zinc-800 px-3 py-2">
        <Link href="/" className="text-xs text-zinc-500 hover:text-zinc-300">
          ← Projects
        </Link>
        <h1 className="text-sm font-semibold" data-testid="project-name">
          {ed.edl?.project.name ?? "…"}
        </h1>
        <span className="text-[10px] text-zinc-600">
          {ed.edl
            ? `${ed.edl.project.canvas.width}×${ed.edl.project.canvas.height} @${ed.edl.project.canvas.fps}fps · r${ed.headRev}`
            : ""}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <button
            data-testid="undo-button"
            className="rounded bg-zinc-800 px-2 py-1 text-xs hover:bg-zinc-700 disabled:opacity-40"
            disabled={readOnly}
            onClick={ed.undo}
            title="Undo (Ctrl+Z)"
          >
            ⟲ Undo
          </button>
          <button
            data-testid="redo-button"
            className="rounded bg-zinc-800 px-2 py-1 text-xs hover:bg-zinc-700 disabled:opacity-40"
            disabled={readOnly}
            onClick={ed.redo}
            title="Redo (Ctrl+Y)"
          >
            ⟳ Redo
          </button>
          <span className="mx-2 h-4 w-px bg-zinc-800" />
          <button
            className="rounded bg-zinc-800 px-2 py-1 text-xs hover:bg-zinc-700"
            onClick={() => addTrack("video")}
          >
            + Video track
          </button>
          <button
            className="rounded bg-zinc-800 px-2 py-1 text-xs hover:bg-zinc-700"
            onClick={() => addTrack("audio")}
          >
            + Audio track
          </button>
          <button
            className="rounded bg-zinc-800 px-2 py-1 text-xs hover:bg-zinc-700"
            onClick={addCaption}
          >
            + Caption
          </button>
        </div>
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
      <div className="flex min-h-0 flex-1">
        <div className="w-60 shrink-0">
          <MediaLibrary
            projectId={projectId}
            assets={ed.assets}
            jobs={ed.jobs}
            onUpload={ed.upload}
            onAssetPointerDown={onAssetPointerDown}
            onAssetAdd={addAssetToTimeline}
            onAnalyze={onAnalyze}
            onViewUnderstanding={onViewUnderstanding}
          />
        </div>
        <div className="min-w-0 flex-1">
          <Preview
            projectId={projectId}
            edl={ed.edl}
            playheadMs={ed.playheadMs}
            renderJob={renderJob}
            onRender={onRender}
          />
        </div>
        <div className="flex w-64 shrink-0 flex-col border-l border-zinc-800">
          <div className="border-b border-zinc-800 p-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
              AI Director
            </h2>
            <p className="mt-2 rounded border border-dashed border-zinc-800 p-3 text-[11px] leading-relaxed text-zinc-600">
              Smart edits (remove silence, captions, reframe) propose as revisions
              you accept or reject — trigger them from an analyzed asset&apos;s
              Insights. Natural-language commands land once the LLM backend is chosen.
            </p>
          </div>
          <ProposalReview
            proposals={ed.proposals}
            onAccept={ed.acceptProposal}
            onReject={ed.rejectProposal}
          />
          <RevisionStrip
            revisions={ed.revisions}
            headRev={ed.headRev}
            viewRev={ed.viewRev}
            onView={ed.viewRevision}
          />
        </div>
      </div>

      {/* timeline */}
      <div className="h-64 shrink-0">
        <Timeline
          projectId={projectId}
          edl={ed.edl}
          selection={ed.selection}
          playheadMs={ed.playheadMs}
          pxPerSec={ed.pxPerSec}
          readOnly={readOnly}
          onSelect={ed.select}
          onPlayhead={ed.setPlayhead}
          onZoom={ed.setZoom}
          onOps={ed.applyOps}
        />
      </div>

      {insights && (
        <UnderstandingPanel
          name={insights.name}
          understanding={insights.u}
          onClose={() => setInsights(null)}
          captionTrackId={
            ed.edl?.tracks.find((t) => t.kind === "caption" || t.kind === "text")?.id ?? null
          }
          onPropose={proposeSmartEdit}
        />
      )}

      {/* asset drag ghost */}
      {assetDrag && (
        <div
          className="pointer-events-none fixed z-50 rounded border border-emerald-500 bg-emerald-950/90 px-2 py-1 text-[10px] text-emerald-200"
          style={{ left: assetDrag.x + 8, top: assetDrag.y + 8 }}
        >
          {assetDrag.asset.src.split("/").pop()}
        </div>
      )}
    </div>
  );
}
