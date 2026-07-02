"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";

const PRESETS = [
  { label: "1920×1080 · 30fps", width: 1920, height: 1080, fps: 30 },
  { label: "1080×1920 · 30fps (vertical)", width: 1080, height: 1920, fps: 30 },
  { label: "1280×720 · 30fps", width: 1280, height: 720, fps: 30 },
  { label: "3840×2160 · 30fps", width: 3840, height: 2160, fps: 30 },
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
      <h1 className="text-2xl font-bold">CutLab</h1>
      <p className="mt-1 text-sm text-zinc-500">
        Timeline-based editing with an AI director inside. Phase 0.
      </p>

      <div className="mt-8 rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
        <h2 className="text-sm font-semibold">New project</h2>
        <div className="mt-3 flex gap-2">
          <input
            data-testid="new-project-name"
            className="flex-1 rounded border border-zinc-700 bg-zinc-950 px-3 py-1.5 text-sm outline-none focus:border-emerald-600"
            placeholder="Project name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && create()}
          />
          <select
            className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm"
            value={preset}
            onChange={(e) => setPreset(Number(e.target.value))}
          >
            {PRESETS.map((p, i) => (
              <option key={p.label} value={i}>
                {p.label}
              </option>
            ))}
          </select>
          <button
            data-testid="create-project"
            className="rounded bg-emerald-700 px-4 py-1.5 text-sm font-semibold hover:bg-emerald-600 disabled:opacity-40"
            disabled={creating || !name.trim()}
            onClick={create}
          >
            Create
          </button>
        </div>
      </div>

      {error && <p className="mt-4 text-sm text-red-400">{error}</p>}

      <div className="mt-8">
        <h2 className="text-sm font-semibold text-zinc-400">Projects</h2>
        <div className="mt-2 divide-y divide-zinc-800 rounded-lg border border-zinc-800">
          {projects === null && !error && (
            <p className="p-3 text-sm text-zinc-600">Loading…</p>
          )}
          {projects?.length === 0 && (
            <p className="p-3 text-sm text-zinc-600">No projects yet.</p>
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
      </div>
    </main>
  );
}
