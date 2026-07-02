"use client";

import type { RevisionRow } from "@/lib/types";

export function RevisionStrip({
  revisions,
  headRev,
  viewRev,
  onView,
}: {
  revisions: RevisionRow[];
  headRev: number;
  viewRev: number | null;
  onView: (rev: number | null) => void;
}) {
  const rows = [...revisions].reverse().slice(0, 40);
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between border-b border-zinc-800 px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
          Revisions
        </h2>
        {viewRev !== null && (
          <button
            data-testid="back-to-head"
            className="rounded bg-amber-800 px-2 py-0.5 text-[10px] text-amber-100 hover:bg-amber-700"
            onClick={() => onView(null)}
          >
            Back to head
          </button>
        )}
      </div>
      <div className="flex-1 overflow-y-auto p-1" data-testid="revision-list">
        {rows.map((r) => {
          const isHead = r.rev === headRev;
          const isViewed = viewRev === r.rev;
          return (
            <button
              key={r.rev}
              data-testid={`revision-${r.rev}`}
              className={`mb-0.5 block w-full rounded px-2 py-1 text-left text-[11px] leading-tight ${
                isViewed
                  ? "bg-amber-900/50 text-amber-200"
                  : isHead
                    ? "bg-emerald-900/40 text-emerald-200"
                    : r.state === "proposed"
                      ? "text-indigo-300 hover:bg-zinc-800"
                      : "text-zinc-400 hover:bg-zinc-800"
              }`}
              onClick={() => onView(r.rev === headRev ? null : r.rev)}
              title={r.summary}
            >
              <span className="mr-1 font-mono text-[10px] text-zinc-500">r{r.rev}</span>
              {isHead && <span className="mr-1 text-[9px] text-emerald-400">HEAD</span>}
              {r.state === "proposed" && (
                <span className="mr-1 text-[9px] text-indigo-400">PROPOSED</span>
              )}
              <span className="line-clamp-2">{r.summary}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
