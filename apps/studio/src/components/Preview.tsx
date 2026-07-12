"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, mediaUrl } from "@/lib/api";
import type { EDL, Job, MediaClip, CaptionClip } from "@/lib/types";
import { clipEndMs, isMediaClip } from "@/lib/types";

/** L0 compositor: for each video track (bottom-up), the media clip under the
 * playhead becomes a layer; caption/text clips overlay as styled text. This is
 * the instant, approximate preview tier — L1 (segment render) and L2 (full
 * render) are exact. */

interface Layer {
  clip: MediaClip;
  trackIndex: number;
}

function layersUnder(edl: EDL | null, ms: number): Layer[] {
  if (!edl) return [];
  const layers: Layer[] = [];
  edl.tracks.forEach((t, i) => {
    if (t.kind !== "video") return;
    for (const c of t.clips) {
      if (isMediaClip(c) && c.start_ms <= ms && ms < clipEndMs(c)) {
        layers.push({ clip: c, trackIndex: i });
        break; // no overlaps within a track
      }
    }
  });
  return layers; // bottom-up (track order)
}

function captionsUnder(edl: EDL | null, ms: number): CaptionClip[] {
  if (!edl) return [];
  const out: CaptionClip[] = [];
  for (const t of edl.tracks) {
    if (t.kind !== "caption" && t.kind !== "text") continue;
    for (const c of t.clips) {
      const cap = c as CaptionClip;
      if (!isMediaClip(c) && cap.start_ms <= ms && ms < cap.end_ms) out.push(cap);
    }
  }
  return out;
}

/** One stacked video/image layer, kept in sync with the playhead. */
function VideoLayer({
  projectId,
  edl,
  clip,
  playheadMs,
  playing,
  topmost,
  topRef,
}: {
  projectId: string;
  edl: EDL;
  clip: MediaClip;
  playheadMs: number;
  playing: boolean;
  topmost: boolean;
  topRef: React.MutableRefObject<{ el: HTMLVideoElement; clip: MediaClip } | null>;
}) {
  const ref = useRef<HTMLVideoElement>(null);

  // The topmost video layer is the master media clock for the transport.
  useEffect(() => {
    if (topmost && ref.current) {
      topRef.current = { el: ref.current, clip };
      return () => {
        if (topRef.current?.el === ref.current) topRef.current = null;
      };
    }
  });
  const asset = edl.assets[clip.asset];
  const speed = clip.speed ?? 1;
  const isImage = asset?.kind === "image";
  const srcRel = isImage ? asset?.src : (asset?.proxy ?? null);
  const url = srcRel ? mediaUrl(projectId, srcRel) : null;

  // Emulate the render compiler: fit to canvas (contain), then transform
  // scale + pixel offsets (as % of canvas so the box can be any size);
  // center crop -> cover.
  const canvasW = edl.project.canvas.width;
  const canvasH = edl.project.canvas.height;
  const style: React.CSSProperties = {
    position: "absolute",
    inset: 0,
    width: "100%",
    height: "100%",
    objectFit: clip.crop?.mode === "center" ? "cover" : "contain",
    transform: `translate(${(100 * (clip.transform?.x ?? 0)) / canvasW}%, ${
      (100 * (clip.transform?.y ?? 0)) / canvasH
    }%) scale(${clip.transform?.scale ?? 1})`,
  };

  // Sync playback state + position to the master clock.
  useEffect(() => {
    const v = ref.current;
    if (!v || isImage) return;
    const wantS = (clip.in_ms + (playheadMs - clip.start_ms) * speed) / 1000;
    if (!Number.isFinite(wantS)) return;
    const drift = Math.abs(v.currentTime - wantS);
    if (playing) {
      if (v.playbackRate !== speed) v.playbackRate = speed;
      if (drift > 0.2) v.currentTime = wantS; // resync only on real drift
      if (v.paused) v.play().catch(() => undefined);
    } else {
      if (!v.paused) v.pause();
      if (drift > 0.05) v.currentTime = wantS;
    }
  }, [playheadMs, playing, clip.id, clip.in_ms, clip.start_ms, speed, isImage, url]);

  if (!url) return null;
  if (isImage) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={url} alt="" style={style} draggable={false} />;
  }
  return (
    <video
      ref={ref}
      key={clip.id}
      src={url}
      style={style}
      muted={!topmost}
      preload="auto"
      playsInline
      data-testid={`layer-${clip.id}`}
    />
  );
}

export function Preview({
  projectId,
  edl,
  playheadMs,
  renderJob,
  onRender,
  onSeek,
}: {
  projectId: string;
  edl: EDL | null;
  playheadMs: number;
  renderJob: Job | null;
  onRender: () => void;
  onSeek: (ms: number) => void;
}) {
  const [playing, setPlaying] = useState(false);
  const [segment, setSegment] = useState<{ url: string } | null>(null);
  const [segmentJob, setSegmentJob] = useState<Job | null>(null);
  const playheadRef = useRef(playheadMs);
  playheadRef.current = playheadMs;
  const onSeekRef = useRef(onSeek);
  onSeekRef.current = onSeek;
  const topRef = useRef<{ el: HTMLVideoElement; clip: MediaClip } | null>(null);

  const duration = edl?.project.duration_ms ?? 0;
  const layers = useMemo(() => layersUnder(edl, playheadMs), [edl, playheadMs]);
  const captions = useMemo(() => captionsUnder(edl, playheadMs), [edl, playheadMs]);
  const topmostId = layers.length ? layers[layers.length - 1].clip.id : null;

  // Master clock: wall-clock interval, corrected by the topmost video's media
  // clock (authoritative — keeps running even in hidden tabs and can't drift
  // from what's actually playing). Gaps with no video advance by wall clock.
  useEffect(() => {
    if (!playing) return;
    let last = performance.now();
    const id = setInterval(() => {
      const now = performance.now();
      let next = playheadRef.current + (now - last);
      last = now;
      const top = topRef.current;
      if (top && !top.el.paused && top.el.readyState >= 2) {
        const c = top.clip;
        const mediaMs =
          c.start_ms + (top.el.currentTime * 1000 - c.in_ms) / (c.speed ?? 1);
        // Trust the media clock unless it's wildly off (src just swapped).
        if (Math.abs(mediaMs - next) < 2000) next = mediaMs;
      }
      if (next >= duration) {
        onSeekRef.current(duration);
        setPlaying(false);
        return;
      }
      onSeekRef.current(next);
    }, 50);
    return () => clearInterval(id);
  }, [playing, duration]);

  // Space toggles playback (unless typing in an input).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code !== "Space") return;
      const el = document.activeElement;
      if (el && ["INPUT", "TEXTAREA", "SELECT", "VIDEO"].includes(el.tagName)) return;
      e.preventDefault();
      setPlaying((p) => (duration > 0 ? !p : p));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [duration]);

  // L1 segment preview: render the next 10s from the playhead exactly.
  const previewSegment = useCallback(async () => {
    if (!edl) return;
    const from = Math.floor(playheadRef.current);
    const to = Math.min(duration, from + 10_000);
    if (to <= from) return;
    setPlaying(false);
    const r = await api.previewSegment(projectId, from, to);
    const poll = async () => {
      const job = await api.getJob(r.job_id);
      setSegmentJob(job);
      if (job.state === "done") {
        setSegment({ url: mediaUrl(projectId, r.output) + `?t=${Date.now()}` });
        setSegmentJob(null);
      } else if (job.state === "failed" || job.state === "cancelled") {
        setSegmentJob(job);
      } else {
        setTimeout(poll, 400);
      }
    };
    poll();
  }, [edl, duration, projectId]);

  const renderDone = renderJob?.state === "done";
  const renderOut = renderDone
    ? String((renderJob!.artifacts as { mux?: { file?: string } }).mux?.file ?? "")
        .split(/[\\/]/)
        .pop()
    : null;

  const canvasAspect = edl
    ? `${edl.project.canvas.width} / ${edl.project.canvas.height}`
    : "16 / 9";

  return (
    <div className="flex h-full flex-col bg-zinc-950">
      <div className="flex min-h-0 flex-1 items-center justify-center p-3">
        {segment ? (
          <div className="relative max-h-full" style={{ aspectRatio: canvasAspect }}>
            <video
              src={segment.url}
              className="max-h-full max-w-full rounded border border-sky-800 bg-black"
              controls
              autoPlay
              data-testid="segment-video"
            />
            <button
              className="absolute right-2 top-2 rounded bg-zinc-900/80 px-2 py-0.5 text-[11px] text-zinc-200 hover:bg-zinc-800"
              onClick={() => setSegment(null)}
              data-testid="segment-close"
            >
              ✕ back to live
            </button>
            <span className="absolute left-2 top-2 rounded bg-sky-900/80 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-sky-200">
              L1 exact
            </span>
          </div>
        ) : layers.length > 0 || captions.length > 0 ? (
          <div
            className="relative h-full max-h-full w-full overflow-hidden rounded border border-zinc-800 bg-black"
            style={{ aspectRatio: canvasAspect, maxWidth: "100%" }}
            data-testid="compositor"
            onClick={() => duration > 0 && setPlaying((p) => !p)}
          >
            {edl &&
              layers.map((l) => (
                <VideoLayer
                  key={l.clip.id}
                  projectId={projectId}
                  edl={edl}
                  clip={l.clip}
                  playheadMs={playheadMs}
                  playing={playing}
                  topmost={l.clip.id === topmostId}
                  topRef={topRef}
                />
              ))}
            {captions.map((c) => (
              <div
                key={c.id}
                data-testid={`caption-overlay-${c.id}`}
                className="pointer-events-none absolute inset-x-0 bottom-[8%] px-[6%] text-center"
              >
                <span
                  className="inline-block rounded px-2 py-0.5 font-semibold text-white"
                  style={{
                    fontSize: "clamp(12px, 3.2cqw, 42px)",
                    background: "rgba(0,0,0,0.55)",
                    textShadow: "0 1px 3px rgba(0,0,0,0.9)",
                  }}
                >
                  {c.text}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div
            className="flex aspect-video w-2/3 items-center justify-center rounded border border-dashed border-zinc-800 text-xs text-zinc-600"
            data-testid="preview-empty"
          >
            {edl && duration > 0
              ? "No clip under playhead"
              : "Timeline is empty — drop a clip to see the live preview"}
          </div>
        )}
      </div>

      <div className="flex items-center gap-3 border-t border-zinc-800 px-3 py-2">
        <button
          data-testid="play-button"
          className="rounded bg-zinc-800 px-3 py-1 text-xs font-semibold text-zinc-100 hover:bg-zinc-700 disabled:opacity-40"
          disabled={!edl || duration === 0}
          onClick={() => setPlaying((p) => !p)}
        >
          {playing ? "⏸" : "▶"}
        </button>
        <button
          data-testid="render-button"
          className="rounded bg-emerald-700 px-3 py-1 text-xs font-semibold text-white hover:bg-emerald-600 disabled:opacity-40"
          disabled={
            !edl || duration === 0 ||
            renderJob?.state === "queued" || renderJob?.state === "running"
          }
          onClick={onRender}
        >
          Render
        </button>
        <button
          data-testid="preview-segment-button"
          className="rounded bg-sky-800 px-3 py-1 text-xs font-semibold text-sky-100 hover:bg-sky-700 disabled:opacity-40"
          disabled={!edl || duration === 0 || !!segmentJob}
          onClick={previewSegment}
          title="Exact render of the next 10s from the playhead"
        >
          {segmentJob && segmentJob.state !== "failed"
            ? `L1… ${Math.round((segmentJob.progress ?? 0) * 100)}%`
            : "Preview 10s"}
        </button>
        {segmentJob?.state === "failed" && (
          <span className="text-xs text-red-400">segment failed</span>
        )}
        {renderJob && (renderJob.state === "queued" || renderJob.state === "running") && (
          <div className="flex flex-1 items-center gap-2">
            <div className="h-1.5 flex-1 overflow-hidden rounded bg-zinc-800">
              <div
                className="h-full bg-emerald-600 transition-all"
                style={{ width: `${Math.round(renderJob.progress * 100)}%` }}
              />
            </div>
            <span className="text-[10px] text-zinc-400" data-testid="render-progress">
              {renderJob.stage ?? renderJob.state} · {Math.round(renderJob.progress * 100)}%
            </span>
          </div>
        )}
        {renderJob?.state === "failed" && (
          <span className="text-xs text-red-400" data-testid="render-failed">
            Render failed
          </span>
        )}
        {renderDone && renderOut && (
          <a
            data-testid="render-result"
            className="text-xs text-emerald-400 underline"
            href={mediaUrl(projectId, `renders/${renderOut}`)}
            target="_blank"
            rel="noreferrer"
          >
            {renderOut}
          </a>
        )}
        <span className="ml-auto text-[10px] tabular-nums text-zinc-500">
          {(playheadMs / 1000).toFixed(2)}s{edl ? ` / ${(duration / 1000).toFixed(2)}s` : ""}
        </span>
      </div>
    </div>
  );
}
