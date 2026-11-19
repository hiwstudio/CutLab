"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";
import {EngineImport} from "@/components/EngineImport";
import {EngineLibrary} from "@/components/EngineLibrary";

const PRESETS = [
  { label: "Landscape", detail: "1920 × 1080 · 30 fps", width: 1920, height: 1080, fps: 30 },
  { label: "Vertical", detail: "1080 × 1920 · 30 fps", width: 1080, height: 1920, fps: 30 },
  { label: "HD", detail: "1280 × 720 · 30 fps", width: 1280, height: 720, fps: 30 },
  { label: "4K", detail: "3840 × 2160 · 30 fps", width: 3840, height: 2160, fps: 30 },
];

export default function Home() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [name, setName] = useState("");
  const [preset, setPreset] = useState(0);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listProjects()
      .then(setProjects)
      .catch(() =>
        setError("Cannot reach the CutLab server on :8787 — is it running?"),
      );
  }, []);

  const create = async () => {
    if (!name.trim()) return;
    setCreating(true);
    try {
      const { width, height, fps } = PRESETS[preset];
      const p = await api.createProject(name.trim(), { width, height, fps });
      // New projects start with one video, one audio and one caption track.
      await api.apply(p.id, 0, [
        { op: "add_track", kind: "video" },
        { op: "add_track", kind: "audio" },
        { op: "add_track", kind: "caption" },
      ]);
      router.push(`/p/${p.id}`);
    } catch (e) {
      setError(String(e));
      setCreating(false);
    }
  };

  return (
    <main className="mx-auto w-full max-w-2xl p-8 text-zinc-100">
      <header className="mt-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-amber-300">CutLab / Video editor</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Start a video project.</h1>
        <p className="mt-3 max-w-xl text-sm leading-6 text-zinc-400">
          Create a timeline or bring in work from a production engine. Add footage, audio, and images, then shape the edit scene by scene.
        </p>
      </header>

      <section className="mt-8 rounded-2xl border border-zinc-700/80 bg-zinc-900/70 p-5 shadow-2xl shadow-black/20">
        <div className="flex items-baseline justify-between gap-4">
          <div><h2 className="text-base font-semibold">New project</h2><p className="mt-1 text-xs text-zinc-500">Every new project includes video, audio, and caption tracks.</p></div>
          <span className="rounded-full border border-amber-400/20 bg-amber-400/10 px-2 py-1 text-[10px] font-medium uppercase tracking-wide text-amber-200">Ready to edit</span>
        </div>
        <label className="mt-5 block text-xs font-medium text-zinc-300">Project name
          <input
            data-testid="new-project-name"
            className="mt-2 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-sm outline-none transition focus:border-amber-400"
            placeholder="For example, Summer campaign edit"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && create()}
          />
        </label>
        <fieldset className="mt-5"><legend className="text-xs font-medium text-zinc-300">Canvas</legend>
          <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {PRESETS.map((p, i) => <button key={p.label} type="button" aria-pressed={preset === i} onClick={() => setPreset(i)} className={`rounded-lg border p-3 text-left transition ${preset === i ? "border-amber-400 bg-amber-400/10 text-amber-100" : "border-zinc-700 bg-zinc-950 text-zinc-300 hover:border-zinc-500"}`}>
              <strong className="block text-xs">{p.label}</strong><span className="mt-1 block text-[10px] text-zinc-500">{p.detail}</span>
            </button>)}
          </div>
        </fieldset>
        <div className="mt-5 flex items-center justify-between gap-4 border-t border-zinc-800 pt-4">
          <p className="text-[11px] text-zinc-500">You can change the canvas later and reframe the edit for another format.</p>
          <button
            data-testid="create-project"
            className="shrink-0 rounded-lg bg-amber-400 px-4 py-2 text-sm font-semibold text-zinc-950 transition hover:bg-amber-300 disabled:opacity-40"
            disabled={creating || !name.trim()}
            onClick={create}
          >
            {creating ? "Creating…" : "Create project"}
          </button>
        </div>
      </section>

      {error && <p className="mt-4 text-sm text-red-400">{error}</p>}
      <EngineImport canvas={{width: PRESETS[preset].width, height: PRESETS[preset].height, fps: PRESETS[preset].fps}} />
      <EngineLibrary />

      <section className="mt-10">
        <h2 className="text-sm font-semibold text-zinc-400">Recent projects</h2>
        <div className="mt-2 divide-y divide-zinc-800 rounded-lg border border-zinc-800">
          {projects === null && !error && (
            <p className="p-3 text-sm text-zinc-600">Loading…</p>
          )}
          {projects?.length === 0 && (
            <p className="p-3 text-sm text-zinc-500">No projects yet. Create one above to start editing.</p>
          )}
          {projects?.map((p) => (
            <button
              key={p.id}
              data-testid={`project-${p.id}`}
              className="block w-full px-3 py-2 text-left hover:bg-zinc-900"
              onClick={() => router.push(`/p/${p.id}`)}
            >
              <span className="text-sm">{p.name}</span>
              <span className="ml-2 text-xs text-zinc-600">
                r{p.head_rev} · {p.id}
              </span>
            </button>
          ))}
        </div>
      </section>
    </main>
  );
}
