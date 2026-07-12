"use client";

import { useState } from "react";
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
  captionTrackId,
  onPropose,
  onCompact,
  onRecap,
}: {
  name: string;
  understanding: Understanding;
  onClose: () => void;
  captionTrackId: string | null;
  onPropose: (op: Record<string, unknown>) => void;
  onCompact: (targetMs: number) => void;
  onRecap: (targetMinutes: number) => void;
}) {
  const u = understanding;
  const hasSilence = u.silence.length > 0;
  const hasSpeech = (u.transcript?.segments.length ?? 0) > 0;
  const hasContent = hasSpeech || u.active_ranges.length > 0;
  const [compactTarget, setCompactTarget] = useState(30_000);
  const [recapTarget, setRecapTarget] = useState(5);
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

        <div className="mt-3" data-testid="propose-smart-edits">
          <div className="mb-1 text-[10px] uppercase tracking-wide text-zinc-500">
            Propose a smart edit
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              data-testid="propose-remove-silence"
              disabled={!hasSilence}
              className="rounded bg-indigo-800 px-2 py-1 text-[11px] text-indigo-100 enabled:hover:bg-indigo-700 disabled:opacity-40"
              onClick={() =>
                onPropose({ op: "remove_silence", asset: u.asset_id })
              }
              title={hasSilence ? "" : "No silence detected"}
            >
              Remove silence
            </button>
            <button
              data-testid="propose-captions"
              disabled={!hasSpeech || !captionTrackId}
              className="rounded bg-indigo-800 px-2 py-1 text-[11px] text-indigo-100 enabled:hover:bg-indigo-700 disabled:opacity-40"
              onClick={() =>
                captionTrackId &&
                onPropose({
                  op: "caption_from_transcript",
                  asset: u.asset_id,
                  track: captionTrackId,
                })
              }
              title={
                !hasSpeech
                  ? "No speech detected"
                  : !captionTrackId
                    ? "No caption track"
                    : ""
              }
            >
              Captions from transcript
            </button>
            <button
              data-testid="propose-reframe"
              className="rounded bg-indigo-800 px-2 py-1 text-[11px] text-indigo-100 hover:bg-indigo-700"
              onClick={() => onPropose({ op: "reframe", width: 1080, height: 1920 })}
            >
              Reframe 9:16
            </button>
          </div>
          <p className="mt-1 text-[10px] text-zinc-600">
            Each proposes a revision you review and accept in the AI Director panel.
          </p>
        </div>

        <div className="mt-3 border-t border-zinc-800 pt-3" data-testid="compact-section">
          <div className="mb-1 text-[10px] uppercase tracking-wide text-zinc-500">
            Compaction engine
          </div>
          <div className="flex items-center gap-2">
            <select
              data-testid="compact-target"
              className="rounded border border-zinc-700 bg-zinc-950 px-1.5 py-1 text-[11px] text-zinc-200"
              value={compactTarget}
              onChange={(e) => setCompactTarget(Number(e.target.value))}
            >
              <option value={30_000}>~30s short</option>
              <option value={60_000}>~60s short</option>
              <option value={120_000}>~2min cut</option>
            </select>
            <button
              data-testid="compact-run"
              disabled={!hasContent}
              className="rounded bg-fuchsia-800 px-2 py-1 text-[11px] font-semibold text-fuchsia-100 enabled:hover:bg-fuchsia-700 disabled:opacity-40"
              onClick={() => onCompact(compactTarget)}
              title={hasContent ? "" : "No speech or active ranges detected"}
            >
              Compact
            </button>
          </div>
          <p className="mt-1 text-[10px] text-zinc-600">
            Scores the best moments (saliency + density + fit), keeps them in story
            order, and proposes the short cut for your review.
          </p>
        </div>

        <div className="mt-3 border-t border-zinc-800 pt-3" data-testid="recap-section">
          <div className="mb-1 text-[10px] uppercase tracking-wide text-zinc-500">
            Recap engine
          </div>
          <div className="flex items-center gap-2">
            <select
              data-testid="recap-target"
              className="rounded border border-zinc-700 bg-zinc-950 px-1.5 py-1 text-[11px] text-zinc-200"
              value={recapTarget}
              onChange={(e) => setRecapTarget(Number(e.target.value))}
            >
              <option value={2}>~2 min recap</option>
              <option value={5}>~5 min recap</option>
              <option value={12}>~12 min recap</option>
            </select>
            <button
              data-testid="recap-run"
              disabled={!hasSpeech}
              className="rounded bg-amber-800 px-2 py-1 text-[11px] font-semibold text-amber-100 enabled:hover:bg-amber-700 disabled:opacity-40"
              onClick={() => onRecap(recapTarget)}
              title={hasSpeech ? "" : "Recap needs a transcript"}
            >
              Recap
            </button>
          </div>
          <p className="mt-1 text-[10px] text-zinc-600">
            Outlines the story, writes original narration (LLM), voices it with
            Piper, matches scenes, and proposes the recap timeline.
          </p>
        </div>

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
