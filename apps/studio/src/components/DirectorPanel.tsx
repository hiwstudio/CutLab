"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { DirectorResult } from "@/lib/types";

/** Natural-language command box for the AI Director (P2). Automatic backends
 * turn the command straight into a proposal; the manual backend shows the prompt
 * to run through Claude and takes the answer back. Either way the result is a
 * proposal reviewed in the panel above. */
export function DirectorPanel({
  projectId,
  onProposed,
  disabled = false,
}: {
  projectId: string;
  disabled?: boolean;
  onProposed: () => void;
}) {
  const [backend, setBackend] = useState<string>("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<{ requestId: string; prompt: string } | null>(null);
  const [answer, setAnswer] = useState("");

  useEffect(() => {
    api.directorBackend(projectId).then((b) => setBackend(b.backend)).catch(() => undefined);
  }, [projectId]);

  const handleResult = (r: DirectorResult) => {
    if (r.status === "proposed") {
      setText("");
      setPending(null);
      setAnswer("");
      onProposed();
    } else if (r.status === "awaiting_answer") {
      setPending({ requestId: r.request_id, prompt: r.prompt });
    } else {
      setError(
        r.issues.length ? `Plan rejected: ${r.issues[0].code} ${r.issues[0].message}` : "Plan rejected",
      );
    }
  };

  const submit = async () => {
    if (disabled || busy || !text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      handleResult(await api.directorCommand(projectId, text));
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  };

  const submitAnswer = async () => {
    if (disabled || busy || !pending || !answer.trim()) return;
    setBusy(true);
    setError(null);
    try {
      handleResult(await api.directorAnswer(projectId, pending.requestId, answer));
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="border-b border-zinc-800 p-3" data-testid="director-panel">
      <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-zinc-400">
        AI Director
        {backend && (
          <span className="rounded bg-zinc-800 px-1.5 text-[9px] lowercase text-zinc-400">
            {backend}
          </span>
        )}
      </h2>

      <div className="mt-2 flex gap-1">
        <input
          data-testid="director-input"
          className="flex-1 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-[11px] outline-none focus:border-indigo-600"
          placeholder='e.g. "remove the silences" or "make it vertical"'
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          disabled={disabled || busy}
        />
        <button
          data-testid="director-send"
          className="rounded bg-indigo-700 px-2 py-1 text-[11px] font-semibold text-white hover:bg-indigo-600 disabled:opacity-40"
          onClick={submit}
          disabled={disabled || busy || !text.trim()}
        >
          {busy ? "…" : "Send"}
        </button>
      </div>

      {error && (
        <p className="mt-1 text-[10px] text-red-400" data-testid="director-error">
          {error}
        </p>
      )}

      {pending && (
        <div className="mt-2 rounded border border-indigo-800 bg-indigo-950/40 p-2" data-testid="director-manual">
          <p className="text-[10px] text-indigo-200">
            Manual backend: run this prompt through Claude, then paste the JSON plan back.
          </p>
          <textarea
            readOnly
            className="mt-1 h-16 w-full resize-none rounded bg-zinc-950 p-1 text-[9px] text-zinc-400"
            value={pending.prompt}
          />
          <textarea
            data-testid="director-answer"
            className="mt-1 h-14 w-full resize-none rounded border border-zinc-700 bg-zinc-950 p-1 text-[10px] text-zinc-200 outline-none focus:border-indigo-600"
            placeholder='{"ops": [...], "note": "..."}'
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
          />
          <button
            data-testid="director-answer-send"
            className="mt-1 rounded bg-indigo-700 px-2 py-0.5 text-[10px] font-semibold text-white hover:bg-indigo-600 disabled:opacity-40"
            onClick={submitAnswer}
            disabled={disabled || busy || !answer.trim()}
          >
            Submit plan
          </button>
        </div>
      )}

      <p className="mt-2 text-[10px] leading-relaxed text-zinc-600">
        The director proposes an edit you accept or reject below — it never commits
        on its own.
      </p>
    </div>
  );
}
