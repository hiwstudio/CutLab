"use client";

import type { RevisionRow } from "@/lib/types";

/** The plan→propose→accept loop's review surface (P2). Proposed revisions —
 * from a human-triggered smart op now, or the AI Director later — appear here
 * for the user to accept (commit) or reject. */
export function ProposalReview({
  proposals,
  onAccept,
  onReject,
}: {
  proposals: RevisionRow[];
  onAccept: (rev: number) => void;
  onReject: (rev: number) => void;
}) {
  if (proposals.length === 0) return null;
  return (
    <div
      className="border-b border-indigo-800 bg-indigo-950/40 p-2"
      data-testid="proposal-review"
    >
      <h2 className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-indigo-300">
        Proposals
        <span className="rounded-full bg-indigo-700 px-1.5 text-[10px] text-white">
          {proposals.length}
        </span>
      </h2>
      {proposals.map((p) => (
        <div
          key={p.rev}
          data-testid={`proposal-${p.rev}`}
          className="mb-1 rounded border border-indigo-800 bg-indigo-950/60 p-2"
        >
          <p className="text-[11px] leading-snug text-indigo-100">{p.summary}</p>
          <div className="mt-1 flex gap-2">
            <button
              data-testid={`accept-proposal-${p.rev}`}
              className="rounded bg-emerald-700 px-2 py-0.5 text-[10px] font-semibold text-white hover:bg-emerald-600"
              onClick={() => onAccept(p.rev)}
            >
              Accept
            </button>
            <button
              data-testid={`reject-proposal-${p.rev}`}
              className="rounded bg-zinc-700 px-2 py-0.5 text-[10px] text-zinc-100 hover:bg-zinc-600"
              onClick={() => onReject(p.rev)}
            >
              Reject
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
