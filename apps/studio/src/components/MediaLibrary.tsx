"use client";

import { useRef } from "react";
import { mediaUrl } from "@/lib/api";
import type { AssetRow, Job } from "@/lib/types";

function fmtDuration(ms?: number | null): string {
  if (!ms) return "";
  const s = Math.round(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function MediaLibrary({
  projectId,
  assets,
  jobs,
  onUpload,
  onAssetPointerDown,
  onAssetAdd,
}: {
  projectId: string;
  assets: AssetRow[];
  jobs: Record<string, Job>;
  onUpload: (file: File) => void;
  onAssetPointerDown: (asset: AssetRow, e: React.PointerEvent) => void;
  onAssetAdd: (asset: AssetRow) => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const ingestJobs = Object.values(jobs).filter((j) => j.kind === "ingest");

  return (
    <div className="flex h-full flex-col border-r border-zinc-800 bg-zinc-950">
      <div className="flex items-center justify-between border-b border-zinc-800 px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
          Media
        </h2>
        <button
          data-testid="upload-button"
          className="rounded bg-zinc-800 px-2 py-1 text-xs text-zinc-200 hover:bg-zinc-700"
          onClick={() => fileRef.current?.click()}
        >
          Upload
        </button>
        <input
          ref={fileRef}
          data-testid="upload-input"
          type="file"
          accept="video/*,audio/*,image/*"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onUpload(f);
            e.target.value = "";
          }}
        />
      </div>
      <div className="flex-1 overflow-y-auto p-2" data-testid="asset-list">
        {assets.length === 0 && (
          <p className="p-2 text-xs text-zinc-600">
            No media yet. Upload a video, audio file, or image.
          </p>
        )}
        {assets.map((a) => {
          const job = ingestJobs.find(
            (j) => (j as Job & { project_id: string | null }).project_id === projectId &&
              j.state !== "done" && j.state !== "failed",
          );
          const name = a.src.split("/").pop() ?? a.asset_id;
          return (
            <div
              key={a.asset_id}
              data-testid={`asset-${a.asset_id}`}
              data-asset-status={a.status}
              className={`mb-1 flex cursor-grab select-none items-center gap-2 rounded border border-zinc-800 bg-zinc-900 p-2 hover:border-zinc-600 ${
                a.status !== "ready" ? "opacity-60" : ""
              }`}
              style={{ touchAction: "none" }}
              title="Drag onto a track, or double-click to append"
              onPointerDown={(e) => a.status === "ready" && onAssetPointerDown(a, e)}
              onDoubleClick={() => a.status === "ready" && onAssetAdd(a)}
            >
              {a.kind === "video" && a.status === "ready" ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={mediaUrl(projectId, `thumbs/${a.asset_id}/t_0001.jpg`)}
                  alt=""
                  className="h-8 w-14 rounded object-cover"
                  draggable={false}
                />
              ) : (
                <div className="flex h-8 w-14 items-center justify-center rounded bg-zinc-800 text-[10px] text-zinc-500">
                  {a.kind}
                </div>
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs text-zinc-200">{name}</p>
                <p className="text-[10px] text-zinc-500">
                  {a.status === "ready"
                    ? `${a.kind} ${fmtDuration(a.duration_ms)}`
                    : a.status === "failed"
                      ? "ingest failed"
                      : `ingesting… ${job ? Math.round(job.progress * 100) + "%" : ""}`}
                </p>
              </div>
            </div>
          );
        })}
      </div>
      <p className="border-t border-zinc-800 p-2 text-[10px] text-zinc-600">
        Drag a ready asset onto a timeline track — or double-click it to
        append to the timeline.
      </p>
    </div>
  );
}
