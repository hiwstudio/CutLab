"use client";

import {useEffect, useState} from "react";
import {api, API_BASE, type EngineLink} from "@/lib/api";
import type {EditorApi} from "@/lib/useEditor";
import type {Scene} from "@/lib/types";

export function EnginePanel({ed, scene}: {ed: EditorApi; scene?: Scene}) {
  const [link, setLink] = useState<EngineLink | null>(null);
  const [note, setNote] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const projectId = ed.edl?.project.id;
  const source = ed.edl?.project.engine_source;
  useEffect(() => {
    let active = true;
    setLink(null);
    if (projectId && source) api.engineLink(projectId, ed.viewRev ?? undefined).then(r => {if(active) setLink(r);}).catch(e => {if(active) setError(String(e));});
    return () => {active = false;};
  }, [projectId, source, ed.headRev, ed.viewRev]);
  useEffect(() => {
    if (!jobId || !projectId) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const job = await api.getJob(jobId);
        if (stopped) return;
        if (job.state === "done") {
          setStatus(job.kind === "engine_request" ? "Request saved · awaiting MixFix operator" : "Update prepared · preview the proposal, then accept or reject it below.");
          setJobId(null); await ed.refresh();
          const r = await api.engineLink(projectId); if(!stopped) setLink(r);
          return;
        }
        if (job.state === "failed" || job.state === "cancelled") {setError(job.error ?? job.state); setJobId(null); return;}
        setStatus(`Preparing · ${Math.round(job.progress * 100)}%`);
        timer = setTimeout(poll, 1500);
      } catch(e) {if(!stopped) {setError(String(e)); timer = setTimeout(poll, 3000);}}
    };
    void poll();
    return () => {stopped = true; clearTimeout(timer);};
  }, [jobId, projectId, ed.refresh]);
  const mapping = scene && link?.scenes[scene.id];
  const details = link?.manifest.scenes.find(s => s.id === mapping?.source_scene_id);
  const act = async (action: "refresh" | "request") => {
    if (!projectId || !scene) return;
    setSubmitting(true); setError(""); setStatus("Preparing…");
    try {const r = await api.engineScene(projectId, scene.id, ed.headRev, action, note); setJobId(r.job_id);}
    catch(e) {setError(String(e)); setStatus("");}
    finally {setSubmitting(false);}
  };
  const disabled = Boolean(submitting || jobId || ed.busy || ed.viewRev !== null);
  const visibleStatus = status.startsWith("Update prepared") && !ed.proposals.length ? "" : status;
  return <div className="space-y-4 p-4 text-xs" data-testid="engine-panel">
    <h2 className="font-semibold text-amber-200">Production engines</h2>
    {!source ? <p className="leading-5 text-zinc-400">This is a CutLab project. MixFix-linked projects show their source scenes here.</p> : <>
      <p className="text-zinc-300">MixFix · {source.source_project} · {source.mode?.toUpperCase()}</p>
      {link?.manifest.warnings.map(w => <p key={w} className="leading-5 text-amber-200/70">{w}</p>)}
      {!details ? <p className="text-zinc-500">Move the playhead into an imported scene to inspect its source.</p> : <>
        <div className="space-y-2 rounded-lg border border-zinc-700 p-3">
          <strong className="text-zinc-200">{details.id}</strong>
          <p className="leading-5 text-zinc-400">{details.visual_intent || details.narration}</p>
          {details.visual?.source?.title && <p className="text-zinc-400">Source: {details.visual.source.title}</p>}
          {details.visual?.source?.url && /^https?:\/\//i.test(details.visual.source.url) && <a className="text-amber-200 underline" href={details.visual.source.url} target="_blank" rel="noreferrer">View original source</a>}
          {!!details.alternatives?.length && <p className="text-zinc-500">{details.alternatives.length} alternative visuals saved in MixFix.</p>}
        </div>
        <button disabled={disabled} onClick={() => act("refresh")} className="w-full rounded-lg bg-amber-400 px-3 py-2 font-semibold text-zinc-950 disabled:opacity-40">Prepare scene update</button>
        <p className="leading-5 text-zinc-500">Imports the latest MixFix visual for this scene. Your timing, speed, and effects stay intact. Review the proposal before applying it.</p>
        <label className="block text-zinc-300">New visual request<textarea aria-label="New visual request" value={note} onChange={e => setNote(e.target.value)} rows={3} maxLength={4000} className="mt-2 w-full rounded-lg border border-zinc-700 bg-zinc-950 p-2" placeholder="Describe what this scene should show…" /></label>
        <button disabled={disabled || !note.trim()} onClick={() => act("request")} className="w-full rounded-lg border border-zinc-600 px-3 py-2 text-zinc-200 disabled:opacity-40">Prepare regeneration request</button>
        <p className="leading-5 text-zinc-500">Saves a handoff for MixFix’s operator workflow. Generation is not automatic yet. Once the engine finishes, prepare a scene update above.</p>
      </>}
      {link?.requests.filter(r => r.scene_id === scene?.id).map(r => <div key={r.id} className="rounded border border-zinc-700 p-2 text-zinc-400"><p>{r.state.replaceAll("_", " ")} · {r.note}</p>{r.state === "awaiting_operator" && <a className="mt-1 inline-block text-amber-200 underline" href={`${API_BASE}/api/v1/projects/${projectId}/engine-requests/${r.id}`}>Download handoff</a>}</div>)}
    </>}
    {visibleStatus && <p role="status" className="leading-5 text-amber-200">{visibleStatus}</p>}
    {error && <p role="alert" className="break-words leading-5 text-red-300">{error}</p>}
  </div>;
}
