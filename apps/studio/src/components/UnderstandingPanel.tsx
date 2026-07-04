"use client";

import type { Understanding } from "@/lib/types";

function ms(v: number): string {
  const s = v / 1000;
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
}

/** Read-only summary of an asset's understanding artifact (P1). A later phase
 * turns these signals into edits; here they're just surfaced so the analysis is
 * observable. */
export function UnderstandingPanel({
  name,
  understanding,
  onClose,
}: {
  name: string;
  understanding: Understanding;
  onClose: () => void;
}) {
  const u = understanding;
  const words = u.transcript?.segments.reduce((n, s) => n + s.words.length, 0) ?? 0;
  const peak =
    u.saliency && u.saliency.windows.length
      ? u.saliency.windows.reduce((a, b) => (b.score > a.score ? b : a))
      : null;
  const preview = (u.transcript?.segments ?? [])
    .map((s) => s.text)
    .join(" ")
    .slice(0, 400);

  const Stat = ({ label, value }: { label: string; value: string | number }) => (
    <div className="rounded border border-zinc-800 bg-zinc-900 p-2">
      <div className="text-lg font-semibold text-zinc-100">{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</div>
    </div>
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6"
      data-testid="understanding-panel"
      onClick={onClose}
    >
      <div
        className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-lg border border-zinc-700 bg-zinc-950 p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-100">
            Understanding · <span className="text-zinc-400">{name}</span>
          </h2>
          <button
            className="rounded bg-zinc-800 px-2 py-0.5 text-xs text-zinc-300 hover:bg-zinc-700"
            onClick={onClose}
          >
            Close
          </button>
        </div>

        <div className="grid grid-cols-4 gap-2">
          <Stat label="Scenes" value={u.scenes.length} />
          <Stat label="Silences" value={u.silence.length} />
          <Stat label="Words" value={words} />
          <Stat label="Tempo" value={u.tempo_bpm ? `${Math.round(u.tempo_bpm)}` : "—"} />
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-zinc-400">
          <div>
            Duration <span className="text-zinc-200">{ms(u.duration_ms)}</span>
          </div>
          <div>
            Active ranges <span className="text-zinc-200">{u.active_ranges.length}</span>
          </div>
          <div>
            Beats <span className="text-zinc-200">{u.beats_ms.length}</span>
          </div>
          <div>
            Saliency windows{" "}
            <span className="text-zinc-200">{u.saliency?.windows.length ?? 0}</span>
          </div>
        </div>

        {peak && (
          <div className="mt-3 rounded border border-sky-900 bg-sky-950/40 p-2 text-[11px] text-sky-200">
            Most salient moment: {ms(peak.start_ms)}–{ms(peak.end_ms)} (score{" "}
            {peak.score.toFixed(2)}) — the compaction engine will favour spans like
            this in a later phase.
          </div>
        )}

        {preview && (
          <div className="mt-3">
            <div className="mb-1 text-[10px] uppercase tracking-wide text-zinc-500">
              Transcript preview
            </div>
            <p className="max-h-40 overflow-y-auto rounded border border-zinc-800 bg-zinc-900 p-2 text-[11px] leading-relaxed text-zinc-300">
              {preview}
              {preview.length >= 400 ? "…" : ""}
            </p>
          </div>
        )}
        {!preview && (
          <p className="mt-3 text-[11px] text-zinc-600">
            No speech detected in this asset.
          </p>
        )}
      </div>
    </div>
  );
}
