"use client";

import { useEffect, useRef, useState } from "react";
import type { Job } from "@/lib/types";

interface Toast {
  id: string;
  kind: "ok" | "error" | "info";
  text: string;
}

const KIND_LABEL: Record<string, string> = {
  ingest: "Ingest",
  render: "Render",
  understanding: "Analysis",
  compaction: "Compaction",
  recap: "Recap",
};

/** Transient job-outcome toasts driven by WS job events: every async action's
 * completion is acknowledged without the user watching a panel. */
export function Toasts({ jobs }: { jobs: Record<string, Job> }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const seen = useRef<Record<string, string>>({});

  useEffect(() => {
    for (const job of Object.values(jobs)) {
      const prev = seen.current[job.id];
      if (prev === job.state) continue;
      seen.current[job.id] = job.state;
      if (prev === undefined && job.state !== "done" && job.state !== "failed") {
        continue; // don't toast states that predate mount
      }
      const label = KIND_LABEL[job.kind] ?? job.kind;
      if (job.state === "done") {
        push({ id: job.id, kind: "ok", text: `${label} finished` });
      } else if (job.state === "failed") {
        push({
          id: job.id, kind: "error",
          text: `${label} failed — ${String(job.error ?? "").split("\n")[0].slice(0, 80) || "see server log"}`,
        });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs]);

  const push = (t: Toast) => {
    setToasts((list) => [...list.filter((x) => x.id !== t.id), t]);
    setTimeout(() => {
      setToasts((list) => list.filter((x) => x.id !== t.id));
    }, t.kind === "error" ? 8000 : 4000);
  };

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          aria-live="polite"
          data-testid={`toast-${t.kind}`}
          className="toast-enter pointer-events-auto flex items-center gap-2 rounded-md border px-3 py-2 text-xs"
          style={{
            background: "var(--elevated)",
            borderColor: t.kind === "error" ? "var(--danger)" : "var(--border)",
            color: t.kind === "error" ? "var(--danger)" : "var(--foreground)",
          }}
        >
          <span>{t.kind === "ok" ? "✓" : t.kind === "error" ? "✕" : "•"}</span>
          {t.text}
        </div>
      ))}
    </div>
  );
}
