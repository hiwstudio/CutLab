"use client";

import { useEffect, useRef, useState } from "react";
import { api, mediaUrl } from "@/lib/api";
import type { AssetRow, Job, LibrarySound } from "@/lib/types";

function fmtDuration(ms?: number | null): string {
  if (!ms) return "";
  const s = Math.round(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function MediaLibrary({
  projectId,
  assets,
  jobs,
  onUpload,
  onAssetPointerDown,
  onAssetAdd,
  onAnalyze,
  onCutout,
  onExtractAudio,
  onTextToSound,
  onImportSound,
  onViewUnderstanding,
}: {
  projectId: string;
  assets: AssetRow[];
  jobs: Record<string, Job>;
  onUpload: (file: File) => void;
  onAssetPointerDown: (asset: AssetRow, e: React.PointerEvent) => void;
  onAssetAdd: (asset: AssetRow) => void;
  onAnalyze: (asset: AssetRow, language?: string) => void;
  onCutout: (asset: AssetRow) => void;
  onExtractAudio: (asset: AssetRow) => void;
  onTextToSound: (text: string) => void;
  onImportSound: (sound: LibrarySound) => void;
  onViewUnderstanding: (asset: AssetRow) => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const [recording, setRecording] = useState(false);
  const [recordedSeconds, setRecordedSeconds] = useState(0);
  const [recordError, setRecordError] = useState<string | null>(null);
  const [sounds, setSounds] = useState<LibrarySound[]>([]);
  const [soundFilter, setSoundFilter] = useState<"all" | "music" | "sfx">("all");
  const ingestJobs = Object.values(jobs).filter((j) => j.kind === "ingest");
  const analyzeJobs = Object.values(jobs).filter((j) => j.kind === "understanding");

  useEffect(() => {
    if (!recording) return;
    const started = Date.now();
    const timer = window.setInterval(() => setRecordedSeconds(Math.floor((Date.now() - started) / 1000)), 250);
    return () => window.clearInterval(timer);
  }, [recording]);

  useEffect(() => { api.listSounds().then(setSounds).catch(() => setSounds([])); }, []);

  useEffect(() => () => {
    const recorder = recorderRef.current;
    if (recorder?.state === "recording") recorder.stop();
    streamRef.current?.getTracks().forEach(track => track.stop());
  }, []);

  const startRecording = async () => {
    setRecordError(null);
    try {
      if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
        throw new Error("Microphone recording is not supported by this browser.");
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      streamRef.current = stream;
      const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"]
        .find(type => MediaRecorder.isTypeSupported(type));
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      recorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = event => { if (event.data.size) chunksRef.current.push(event.data); };
      recorder.onerror = () => setRecordError("The microphone recording stopped unexpectedly.");
      recorder.onstop = () => {
        const type = recorder.mimeType || mimeType || "audio/webm";
        const extension = type.includes("mp4") ? "m4a" : type.includes("ogg") ? "ogg" : "webm";
        const blob = new Blob(chunksRef.current, { type });
        stream.getTracks().forEach(track => track.stop());
        streamRef.current = null;
        recorderRef.current = null;
        setRecording(false);
        if (!blob.size) {
          setRecordError("No audio was captured. Check the selected microphone and try again.");
          return;
        }
        const stamp = new Date().toISOString().replace(/[:.]/g, "-");
        onUpload(new File([blob], `voice-take-${stamp}.${extension}`, { type }));
      };
      recorder.start(250);
      setRecordedSeconds(0);
      setRecording(true);
    } catch (error) {
      streamRef.current?.getTracks().forEach(track => track.stop());
      streamRef.current = null;
      setRecording(false);
      setRecordError(error instanceof Error ? error.message : "Microphone access failed.");
    }
  };

  const stopRecording = () => {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  };

  return (
    <div className="flex h-full flex-col border-r border-zinc-800 bg-zinc-950">
      <div className="flex items-center justify-between border-b border-zinc-800 px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
          Media
        </h2>
        <div className="flex items-center gap-1"><button
          type="button"
          data-testid="record-audio-button"
          aria-pressed={recording}
          className={`rounded px-2 py-1 text-xs ${recording ? "bg-red-600 text-white hover:bg-red-500" : "bg-zinc-800 text-zinc-200 hover:bg-zinc-700"}`}
          onClick={() => recording ? stopRecording() : void startRecording()}
        >
          {recording ? `Stop ${Math.floor(recordedSeconds / 60)}:${String(recordedSeconds % 60).padStart(2, "0")}` : "Record"}
        </button><label
          htmlFor="cutlab-upload-input"
          data-testid="upload-button"
          className="rounded bg-zinc-800 px-2 py-1 text-xs text-zinc-200 hover:bg-zinc-700"
          aria-label="Upload media"
        >
          Upload
        </label></div>
        <input
          id="cutlab-upload-input"
          ref={fileRef}
          data-testid="upload-input"
          type="file"
          accept="video/*,audio/*,image/*"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onUpload(f);
            e.target.value = "";
          }}
        />
      </div>
      {recordError && <p role="alert" className="border-b border-red-900 bg-red-950/60 px-3 py-2 text-[10px] text-red-300">{recordError}</p>}
      <details className="border-b border-zinc-800 px-3 py-2 text-xs">
        <summary className="cursor-pointer text-zinc-300">Sounds <span className="text-zinc-600">({sounds.length})</span></summary>
        <div className="mt-2 flex gap-1">{(["all", "music", "sfx"] as const).map(kind => <button type="button" key={kind} aria-pressed={soundFilter === kind} className={`rounded px-2 py-1 text-[10px] ${soundFilter === kind ? "bg-amber-500 text-zinc-950" : "bg-zinc-800 text-zinc-300"}`} onClick={() => setSoundFilter(kind)}>{kind === "all" ? "All" : kind === "music" ? "Music" : "SFX"}</button>)}</div>
        <div className="mt-2 max-h-56 space-y-1 overflow-y-auto">{sounds.filter(sound => soundFilter === "all" || sound.kind === soundFilter).map(sound => {
          const imported = assets.find(asset => asset.status === "ready" && asset.src.split("/").pop()?.replace(/_\d+(?=\.[^.]+$)/, "") === sound.filename);
          return <div key={sound.id} className={`rounded border border-zinc-800 bg-zinc-900 p-2 ${imported ? "cursor-grab" : ""}`} title={imported ? "Drag onto an audio track, or Add again at the playhead" : "Add at the playhead"} onPointerDown={e => imported && onAssetPointerDown(imported, e)}><div className="flex items-center justify-between gap-2"><span className="min-w-0"><b className="block truncate text-[11px] text-zinc-200">{sound.title}</b><small className="text-[9px] uppercase text-zinc-500">{sound.kind} · {sound.category}{imported ? " · ready to drag" : ""}</small></span><button type="button" className="rounded bg-amber-500 px-2 py-1 text-[10px] font-medium text-zinc-950 hover:bg-amber-400" onPointerDown={e => e.stopPropagation()} onClick={() => onImportSound(sound)}>Add at playhead</button></div><audio className="mt-1 h-7 w-full" controls preload="none" src={api.soundPreviewUrl(sound.id)} onPointerDown={e => e.stopPropagation()} /></div>;
        })}</div>
        <p className="mt-2 text-[10px] text-zinc-500">Add places the sound at the playhead. Once imported, drag the sound card onto any audio track.</p>
      </details>
      <details className="border-b border-zinc-800 px-3 py-2 text-xs"><summary className="cursor-pointer text-zinc-300">Text to sound</summary><form className="mt-2 space-y-2" onSubmit={e => { e.preventDefault(); const form = e.currentTarget; const text = String(new FormData(form).get("speech")).trim(); if (text) { onTextToSound(text); form.reset(); } }}><label className="block text-[10px] text-zinc-400">Voice text<textarea name="speech" aria-label="Text to sound" minLength={1} maxLength={2000} required className="mt-1 min-h-20 w-full rounded border border-zinc-700 bg-zinc-900 p-2 text-xs text-zinc-100" placeholder="Type the narration or line you want CutLab to speak." /></label><button className="rounded bg-amber-500 px-2 py-1 text-xs font-medium text-zinc-950 hover:bg-amber-400">Generate voice</button><p className="text-[10px] text-zinc-500">Uses the free Fish Audio voice. Piper keeps generation available if Fish is temporarily unavailable.</p></form></details>
      <div className="flex-1 overflow-y-auto p-2" data-testid="asset-list">
        {assets.length === 0 && (
          <p className="p-2 text-xs text-zinc-600">
            No media yet. Upload a video, audio file, or image.
          </p>
        )}
        {assets.map((a) => {
          const job = ingestJobs.find(
            (j) => (j as Job & { project_id: string | null }).project_id === projectId &&
              j.state !== "done" && j.state !== "failed",
          );
          const name = a.src.split("/").pop() ?? a.asset_id;
          return (
            <div
              key={a.asset_id}
              data-testid={`asset-${a.asset_id}`}
              data-asset-status={a.status}
              className={`mb-1 flex cursor-grab select-none items-center gap-2 rounded border border-zinc-800 bg-zinc-900 p-2 hover:border-zinc-600 ${
                a.status !== "ready" ? "opacity-60" : ""
              }`}
              style={{ touchAction: "none" }}
              title="Drag onto a track, or double-click to append"
              onPointerDown={(e) => a.status === "ready" && onAssetPointerDown(a, e)}
              onDoubleClick={() => a.status === "ready" && onAssetAdd(a)}
            >
              {a.kind === "video" && a.status === "ready" ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={mediaUrl(projectId, `thumbs/${a.asset_id}/t_0001.jpg`)}
                  alt=""
                  className="h-8 w-14 rounded object-cover"
                  draggable={false}
                />
              ) : (
                <div className="flex h-8 w-14 items-center justify-center rounded bg-zinc-800 text-[10px] text-zinc-500">
                  {a.kind === "image" ? "sticker / image" : a.kind}
                </div>
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs text-zinc-200">{name}</p>
                <p className="text-[10px] text-zinc-500">
                  {a.status === "ready"
                    ? `${a.kind} ${fmtDuration(a.duration_ms)}`
                    : a.status === "failed"
                      ? "ingest failed"
                      : `ingesting… ${job ? Math.round(job.progress * 100) + "%" : ""}`}
                </p>
                {a.status === "ready" && (
                  <><AnalyzeControl
                    asset={a}
                    job={analyzeJobs.find(
                      (j) =>
                        (j as Job & { asset_id?: string }).asset_id === a.asset_id &&
                        j.state !== "done" && j.state !== "failed",
                    )}
                    onAnalyze={onAnalyze}
                    onView={onViewUnderstanding}
                  />{a.kind === "image" && <button type="button" className="mt-1 rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-amber-300 hover:bg-zinc-700" onClick={e => { e.stopPropagation(); onCutout(a); }}>Remove background</button>}{a.kind === "video" && <button type="button" className="mt-1 rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-emerald-300 hover:bg-zinc-700" onClick={e => { e.stopPropagation(); onExtractAudio(a); }}>Extract audio</button>}</>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <p className="border-t border-zinc-800 p-2 text-[10px] text-zinc-600">
        Upload a PNG, JPG, or WebP as a sticker. Double-clicking an image adds
        it to your Overlay / sticker track when one exists.
      </p>
    </div>
  );
}

function AnalyzeControl({
  asset,
  job,
  onAnalyze,
  onView,
}: {
  asset: AssetRow;
  job?: Job;
  onAnalyze: (a: AssetRow, language?: string) => void;
  onView: (a: AssetRow) => void;
}) {
  const [language, setLanguage] = useState("auto");
  const analyzing = job && (job.state === "queued" || job.state === "running");
  const analyzed = !!asset.understanding;

  if (analyzing) {
    return (
      <div className="mt-1 flex items-center gap-1" data-testid={`analyze-progress-${asset.asset_id}`}>
        <div className="h-1 flex-1 overflow-hidden rounded bg-zinc-800">
          <div
            className="h-full bg-sky-500 transition-all"
            style={{ width: `${Math.round((job?.progress ?? 0) * 100)}%` }}
          />
        </div>
        <span className="text-[9px] text-sky-300">
          {job?.stage ?? "analyzing"}…
        </span>
      </div>
    );
  }
  return (
    <div className="mt-1 flex flex-wrap items-center gap-1">
      <select aria-label={`Caption language for ${asset.asset_id}`} value={language} onChange={e => setLanguage(e.target.value)} onClick={e => e.stopPropagation()} className="rounded bg-zinc-800 px-1 py-0.5 text-[10px] text-zinc-300"><option value="auto">Auto language</option><option value="en">English</option><option value="es">Spanish</option><option value="fr">French</option><option value="de">German</option><option value="pt">Portuguese</option><option value="it">Italian</option><option value="ja">Japanese</option><option value="ko">Korean</option><option value="zh">Chinese</option></select>
      <button
        data-testid={`analyze-${asset.asset_id}`}
        className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-sky-300 hover:bg-zinc-700"
        onClick={(e) => {
          e.stopPropagation();
          onAnalyze(asset, language === "auto" ? undefined : language);
        }}
      >
        {analyzed ? "Re-analyze" : "Analyze"}
      </button>
      {analyzed && (
        <button
          data-testid={`view-understanding-${asset.asset_id}`}
          className="rounded bg-sky-900/60 px-1.5 py-0.5 text-[10px] text-sky-200 hover:bg-sky-800"
          onClick={(e) => {
            e.stopPropagation();
            onView(asset);
          }}
        >
          ✓ Insights
        </button>
      )}
    </div>
  );
}
