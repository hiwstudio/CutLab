"use client";

import { useCallback, useRef, useState } from "react";
import { mediaUrl } from "@/lib/api";
import type { Clip, EDL, MediaClip, Op, Track } from "@/lib/types";
import { clipEndMs, clipLenMs, isMediaClip } from "@/lib/types";
import { WaveStrip } from "./WaveStrip";

const LABEL_W = 72;
const LANE_H = 44;

type DragMode =
  | { kind: "move"; clip: Clip; track: Track; dxMs: number; toTrackId: string | null }
  | { kind: "trim-l" | "trim-r"; clip: MediaClip; track: Track; dxMs: number }
  | { kind: "playhead" };

export function Timeline({
  projectId,
  edl,
  selection,
  playheadMs,
  pxPerSec,
  readOnly,
  onSelect,
  onPlayhead,
  onZoom,
  onOps,
}: {
  projectId: string;
  edl: EDL | null;
  selection: string | null;
  playheadMs: number;
  pxPerSec: number;
  readOnly: boolean;
  onSelect: (id: string | null) => void;
  onPlayhead: (ms: number) => void;
  onZoom: (pxPerSec: number) => void;
  onOps: (ops: Op[]) => Promise<boolean>;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<DragMode | null>(null);
  const dragRef = useRef<DragMode | null>(null);
  const dragStartX = useRef(0);

  const msPerPx = 1000 / pxPerSec;
  const durationMs = Math.max(edl?.project.duration_ms ?? 0, 30_000);
  const contentW = durationMs / msPerPx + 200;

  const xToMs = useCallback(
    (clientX: number): number => {
      const el = scrollRef.current;
      if (!el) return 0;
      const rect = el.getBoundingClientRect();
      const x = clientX - rect.left - LABEL_W + el.scrollLeft;
      return Math.max(0, Math.round(x * msPerPx));
    },
    [msPerPx],
  );

  const beginDrag = (mode: DragMode, e: React.PointerEvent) => {
    if (readOnly) return;
    dragStartX.current = e.clientX;
    dragRef.current = mode;
    setDrag(mode);
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    e.stopPropagation();
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const d = dragRef.current;
    if (!d) return;
    if (d.kind === "playhead") {
      onPlayhead(xToMs(e.clientX));
      return;
    }
    const dxMs = Math.round((e.clientX - dragStartX.current) * msPerPx);
    let toTrackId: string | null = null;
    if (d.kind === "move") {
      const under = document
        .elementFromPoint(e.clientX, e.clientY)
        ?.closest("[data-track-id]") as HTMLElement | null;
      toTrackId = under?.dataset.trackId ?? null;
    }
    const next = { ...d, dxMs, ...(d.kind === "move" ? { toTrackId } : {}) } as DragMode;
    dragRef.current = next;
    setDrag(next);
  };

  const onPointerUp = async () => {
    const d = dragRef.current;
    dragRef.current = null;
    setDrag(null);
    if (!d || d.kind === "playhead") return;
    if (Math.abs(d.dxMs) < msPerPx * 3 && (d.kind !== "move" || !d.toTrackId)) return;

    if (d.kind === "move") {
      const toStart = Math.max(0, d.clip.start_ms + d.dxMs);
      const crossTrack = d.toTrackId && d.toTrackId !== d.track.id;
      if (toStart === d.clip.start_ms && !crossTrack) return;
      await onOps([
        {
          op: "move",
          clip: d.clip.id,
          to_start_ms: toStart,
          ...(crossTrack ? { to_track: d.toTrackId } : {}),
        },
      ]);
    } else {
      const speed = d.clip.speed ?? 1;
      const deltaSrc = Math.round(d.dxMs * speed);
      if (d.kind === "trim-r") {
        const maxOut = edl?.assets[d.clip.asset]?.duration_ms ?? Infinity;
        const newOut = Math.min(Math.max(d.clip.out_ms + deltaSrc, d.clip.in_ms + 1), maxOut);
        if (newOut !== d.clip.out_ms) {
          await onOps([{ op: "trim", clip: d.clip.id, new_out_ms: newOut, edge_mode: "hold_start" }]);
        }
      } else {
        const newIn = Math.max(Math.min(d.clip.in_ms + deltaSrc, d.clip.out_ms - 1), 0);
        if (newIn !== d.clip.in_ms) {
          await onOps([{ op: "trim", clip: d.clip.id, new_in_ms: newIn, edge_mode: "hold_end" }]);
        }
      }
    }
  };

  const ruler = () => {
    const stepS = pxPerSec >= 60 ? 1 : pxPerSec >= 25 ? 5 : 10;
    const marks = [];
    for (let s = 0; s * 1000 <= durationMs + 10_000; s += stepS) {
      marks.push(
        <div
          key={s}
          className="absolute top-0 h-full border-l border-zinc-800 pl-1 text-[9px] text-zinc-500"
          style={{ left: (s * 1000) / msPerPx }}
        >
          {s % 60 === 0 ? `${s / 60}:00` : `${s}s`}
        </div>,
      );
    }
    return marks;
  };

  const dragOffsetPx = (c: Clip): number => {
    if (drag && drag.kind === "move" && drag.clip.id === c.id) return drag.dxMs / msPerPx;
    return 0;
  };

  const clipWidthPx = (c: Clip): number => {
    let len = clipLenMs(c);
    if (drag && drag.kind !== "move" && drag.kind !== "playhead" && drag.clip.id === c.id) {
      len = Math.max(50, len + (drag.kind === "trim-r" ? drag.dxMs : -drag.dxMs));
    }
    return Math.max(8, len / msPerPx);
  };

  return (
    <div className="flex h-full flex-col border-t border-zinc-800 bg-zinc-950">
      <div className="flex items-center gap-2 border-b border-zinc-800 px-3 py-1">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
          Timeline
        </h2>
        {readOnly && (
          <span className="rounded bg-amber-900/60 px-2 text-[10px] text-amber-300">
            read-only (viewing history)
          </span>
        )}
        <div className="ml-auto flex items-center gap-1 text-xs text-zinc-400">
          <button
            className="rounded bg-zinc-800 px-2 hover:bg-zinc-700"
            onClick={() => onZoom(pxPerSec / 1.5)}
            title="Zoom out"
          >
            −
          </button>
          <span className="w-14 text-center text-[10px]">{Math.round(pxPerSec)} px/s</span>
          <button
            className="rounded bg-zinc-800 px-2 hover:bg-zinc-700"
            onClick={() => onZoom(pxPerSec * 1.5)}
            title="Zoom in"
          >
            +
          </button>
        </div>
      </div>

      <div
        ref={scrollRef}
        className="relative flex-1 overflow-auto"
        data-testid="timeline"
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={() => {
          dragRef.current = null;
          setDrag(null);
        }}
        onPointerDown={(e) => {
          // Clicking empty timeline space: set playhead, clear selection.
          if ((e.target as HTMLElement).closest("[data-clip-id]")) return;
          onSelect(null);
          onPlayhead(xToMs(e.clientX));
          beginDrag({ kind: "playhead" }, e);
        }}
      >
        <div style={{ width: contentW + LABEL_W, minWidth: "100%" }}>
          {/* ruler */}
          <div className="sticky top-0 z-20 flex h-6 bg-zinc-950">
            <div className="sticky left-0 z-10 w-[72px] shrink-0 border-b border-r border-zinc-800 bg-zinc-950" />
            <div className="relative h-full flex-1 border-b border-zinc-800">{ruler()}</div>
          </div>

          {(edl?.tracks ?? []).map((track) => (
            <div key={track.id} className="flex" style={{ height: LANE_H }}>
              <div className="sticky left-0 z-10 flex w-[72px] shrink-0 items-center border-b border-r border-zinc-800 bg-zinc-950 px-2 text-[10px] uppercase text-zinc-500">
                {track.kind}
              </div>
              <div
                className="relative flex-1 border-b border-zinc-900"
                data-track-id={track.id}
                data-track-kind={track.kind}
              >
                {track.clips.map((clip) => {
                  const media = isMediaClip(clip);
                  const asset = media && edl ? edl.assets[(clip as MediaClip).asset] : null;
                  const selected = selection === clip.id;
                  return (
                    <div
                      key={clip.id}
                      data-clip-id={clip.id}
                      className={`absolute top-1 flex h-[36px] cursor-grab items-stretch overflow-hidden rounded border text-[10px] ${
                        selected
                          ? "clip-selected z-10 border-transparent bg-[var(--elevated)]"
                          : media
                            ? "border-zinc-600 bg-zinc-800"
                            : "border-indigo-700 bg-indigo-950"
                      }`}
                      style={{
                        left: clip.start_ms / msPerPx + dragOffsetPx(clip),
                        width: clipWidthPx(clip),
                        touchAction: "none",
                      }}
                      onPointerDown={(e) => {
                        onSelect(clip.id);
                        beginDrag({ kind: "move", clip, track, dxMs: 0, toTrackId: null }, e);
                      }}
                    >
                      {media && (
                        <div
                          className="absolute inset-y-0 left-0 z-20 w-1.5 cursor-ew-resize bg-white/10 hover:bg-white/40"
                          data-testid={`trim-l-${clip.id}`}
                          onPointerDown={(e) =>
                            beginDrag(
                              { kind: "trim-l", clip: clip as MediaClip, track, dxMs: 0 },
                              e,
                            )
                          }
                        />
                      )}
                      <div className="pointer-events-none relative min-w-0 flex-1">
                        {media && asset?.kind === "video" && (
                          <div
                            className="absolute inset-0 opacity-30"
                            style={{
                              backgroundImage: `url(${mediaUrl(projectId, `thumbs/${(clip as MediaClip).asset}/t_0001.jpg`)})`,
                              backgroundSize: "auto 100%",
                              backgroundRepeat: "repeat-x",
                            }}
                          />
                        )}
                        {media && track.kind === "audio" && asset?.duration_ms ? (
                          <div className="absolute inset-0">
                            <WaveStrip
                              projectId={projectId}
                              assetId={(clip as MediaClip).asset}
                              inFrac={(clip as MediaClip).in_ms / asset.duration_ms}
                              outFrac={(clip as MediaClip).out_ms / asset.duration_ms}
                            />
                          </div>
                        ) : null}
                        <span className="relative z-10 block truncate px-2 pt-1 text-zinc-200">
                          {media
                            ? (asset?.src.split("/").pop() ?? (clip as MediaClip).asset)
                            : `“${(clip as CaptionText).text}”`}
                        </span>
                        <span className="relative z-10 block px-2 text-[9px] text-zinc-400">
                          {(clipLenMs(clip) / 1000).toFixed(2)}s
                          {media && ((clip as MediaClip).speed ?? 1) !== 1
                            ? ` · ${(clip as MediaClip).speed}x`
                            : ""}
                        </span>
                      </div>
                      {media && (
                        <div
                          className="absolute inset-y-0 right-0 z-20 w-1.5 cursor-ew-resize bg-white/10 hover:bg-white/40"
                          data-testid={`trim-r-${clip.id}`}
                          onPointerDown={(e) =>
                            beginDrag(
                              { kind: "trim-r", clip: clip as MediaClip, track, dxMs: 0 },
                              e,
                            )
                          }
                        />
                      )}
                    </div>
                  );
                })}
                {drag?.kind === "move" &&
                  drag.toTrackId === track.id &&
                  drag.track.id !== track.id && (
                    <div className="absolute inset-0 bg-emerald-500/10" />
                  )}
              </div>
            </div>
          ))}

          {(edl?.tracks.length ?? 0) === 0 && (
            <p className="p-4 text-xs text-zinc-600">No tracks.</p>
          )}

          {/* playhead */}
          <div
            className="pointer-events-none absolute bottom-0 top-6 z-30 w-px bg-red-500"
            data-testid="playhead"
            style={{ left: LABEL_W + playheadMs / msPerPx }}
          >
            <div className="-ml-[5px] h-0 w-0 border-l-[5px] border-r-[5px] border-t-[6px] border-l-transparent border-r-transparent border-t-red-500" />
          </div>
        </div>
      </div>
    </div>
  );
}

interface CaptionText {
  text: string;
}
