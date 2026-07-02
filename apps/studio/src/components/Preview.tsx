"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { mediaUrl } from "@/lib/api";
import type { EDL, Job, MediaClip } from "@/lib/types";
import { clipEndMs, isMediaClip } from "@/lib/types";

/** Topmost video-track media clip under the playhead (tracks render bottom-up). */
function clipUnderPlayhead(edl: EDL | null, ms: number): MediaClip | null {
  if (!edl) return null;
  for (let i = edl.tracks.length - 1; i >= 0; i--) {
    const t = edl.tracks[i];
    if (t.kind !== "video") continue;
    for (const c of t.clips) {
      if (isMediaClip(c) && c.start_ms <= ms && ms < clipEndMs(c)) return c;
    }
  }
  return null;
}

export function Preview({
  projectId,
  edl,
  playheadMs,
  renderJob,
  onRender,
}: {
  projectId: string;
  edl: EDL | null;
  playheadMs: number;
  renderJob: Job | null;
  onRender: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);

  const clip = useMemo(() => clipUnderPlayhead(edl, playheadMs), [edl, playheadMs]);
  const asset = clip && edl ? edl.assets[clip.asset] : null;
  const proxyRel = asset?.proxy ?? (asset?.kind === "video" ? null : asset?.src);
  const srcUrl = proxyRel ? mediaUrl(projectId, proxyRel) : null;

  // Seek the proxy to the source position under the playhead.
  useEffect(() => {
    const v = videoRef.current;
    if (!v || !clip || playing) return;
    const sourceS =
      (clip.in_ms + (playheadMs - clip.start_ms) * (clip.speed ?? 1)) / 1000;
    if (Number.isFinite(sourceS) && Math.abs(v.currentTime - sourceS) > 0.05) {
      v.currentTime = sourceS;
    }
  }, [clip, playheadMs, playing, srcUrl]);

  const renderDone = renderJob?.state === "done";
  const renderOut = renderDone
    ? String(
        (renderJob!.artifacts as { mux?: { file?: string } }).mux?.file ?? "",
      )
        .split(/[\\/]/)
        .pop()
    : null;

  return (
    <div className="flex h-full flex-col bg-zinc-950">
      <div className="flex min-h-0 flex-1 items-center justify-center p-3">
        {srcUrl ? (
          <video
            ref={videoRef}
            key={srcUrl}
            src={srcUrl}
            className="max-h-full max-w-full rounded border border-zinc-800 bg-black"
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            controls
            preload="auto"
            data-testid="preview-video"
          />
        ) : (
          <div
            className="flex aspect-video w-2/3 items-center justify-center rounded border border-dashed border-zinc-800 text-xs text-zinc-600"
            data-testid="preview-empty"
          >
            {edl && edl.project.duration_ms > 0
              ? "No clip under playhead"
              : "Timeline is empty — proxy preview appears here"}
          </div>
        )}
      </div>
      <div className="flex items-center gap-3 border-t border-zinc-800 px-3 py-2">
        <button
          data-testid="render-button"
          className="rounded bg-emerald-700 px-3 py-1 text-xs font-semibold text-white hover:bg-emerald-600 disabled:opacity-40"
          disabled={
            !edl ||
            edl.project.duration_ms === 0 ||
            renderJob?.state === "queued" ||
            renderJob?.state === "running"
          }
          onClick={onRender}
        >
          Render
        </button>
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
          {(playheadMs / 1000).toFixed(2)}s
          {edl ? ` / ${(edl.project.duration_ms / 1000).toFixed(2)}s` : ""}
        </span>
      </div>
    </div>
  );
}
