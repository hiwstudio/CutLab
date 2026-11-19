"use client";

import {useEffect, useState} from "react";
import {useRouter} from "next/navigation";
import {api} from "@/lib/api";
import type {Canvas} from "@/lib/types";

export function EngineImport({canvas}: {canvas: Canvas}) {
  const router = useRouter();
  const [projects, setProjects] = useState<Awaited<ReturnType<typeof api.engineProjects>>>([]);
  const [source, setSource] = useState("");
  const [mode, setMode] = useState("mix");
  const [job, setJob] = useState<{job_id: string; project_id: string} | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {api.engineProjects().then(p => {setProjects(p); setSource(p[0]?.name ?? "");}).catch(e => setError(String(e)));}, []);
  useEffect(() => {
    if (!job) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const current = await api.getJob(job.job_id);
        if (stopped) return;
        setStatus(`Preparing editable timeline · ${Math.round(current.progress * 100)}%`);
        if (current.state === "done") {router.push(`/p/${job.project_id}`); return;}
        if (current.state === "failed" || current.state === "cancelled") {
          setError(current.error ?? `Import ${current.state}`); setBusy(false); setJob(null); return;
        }
        timer = setTimeout(poll, 1500);
      } catch (e) {if (!stopped) {setError(String(e)); timer = setTimeout(poll, 3000);}}
    };
    void poll();
    return () => {stopped = true; clearTimeout(timer);};
  }, [job, router]);
  const start = async () => {
    setBusy(true); setError(""); setStatus("Checking MixFix project…");
    try {setJob(await api.importEngine(source, mode, canvas));}
    catch(e) {setError(String(e)); setBusy(false); setStatus("");}
  };
  return <section className="mt-6 rounded-2xl border border-zinc-700 bg-zinc-900/70 p-5" data-testid="engine-import">
    <h2 className="text-base font-semibold">Bring in an engine project</h2>
    <p className="mt-1 text-xs leading-5 text-zinc-400">MixFix connects footage, narration, captions, and scenes to an editable CutLab timeline. Uses the canvas selected above.</p>
    <div className="mt-4 flex flex-wrap gap-2">
      <select aria-label="MixFix project" value={source} disabled={busy} onChange={e => setSource(e.target.value)} className="min-w-0 flex-1 rounded-lg border border-zinc-700 bg-zinc-950 p-2 text-xs">
        {projects.length === 0 && <option value="">No MixFix timelines found</option>}
        {projects.map(p => <option key={p.name} value={p.name}>{p.name} · {p.scene_count} scenes · {Math.round(p.duration_ms / 1000)}s</option>)}
      </select>
      <select aria-label="MixFix mode" value={mode} disabled={busy} onChange={e => setMode(e.target.value)} className="rounded-lg border border-zinc-700 bg-zinc-950 p-2 text-xs"><option value="mix">MIX · Narrated film</option><option value="fix">FIX · Original + overlays</option></select>
      <button disabled={busy || !source} onClick={start} className="rounded-lg bg-amber-400 px-3 py-2 text-xs font-semibold text-zinc-950 disabled:opacity-40">{busy ? "Importing…" : "Open in CutLab"}</button>
    </div>
    {!busy && projects.length === 0 && <p className="mt-3 text-[11px] leading-5 text-zinc-500">No MixFix projects found yet. Run a MixFix workflow, then refresh this page. You can also point `CUTLAB_MIXFIX_ROOT` at another MixFix folder.</p>}
    {busy && <div className="mt-3 flex items-center justify-between gap-3"><p role="status" className="text-xs text-amber-200">{status}</p>{job && <button className="text-xs text-zinc-400 underline" onClick={() => api.cancelJob(job.job_id).catch(e => setError(String(e)))}>Stop import</button>}</div>}
    {error && <p role="alert" className="mt-3 break-words text-xs text-red-300">{error}</p>}
    <p className="mt-3 text-[11px] text-zinc-500">MIX uses hard cuts. Split layouts run as a standalone MixFix workflow; Clipinn, Viral Clip, Recap, and HIW Studio are listed below.</p>
  </section>;
}
