"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { SpineIcon } from "./SpineIcon";
import { api, mediaUrl } from "@/lib/api";
import type { EDL, Job, MediaClip, CaptionClip } from "@/lib/types";
import { clipEndMs, isMediaClip } from "@/lib/types";

/** L0 compositor: for each video track (bottom-up), the media clip under the
 * playhead becomes a layer; caption/text clips overlay as styled text. This is
 * the instant, approximate preview tier — L1 (segment render) and L2 (full
 * render) are exact. */

interface Layer {
  clip: MediaClip;
  trackIndex: number;
}

function layersUnder(edl: EDL | null, ms: number): Layer[] {
  if (!edl) return [];
  const layers: Layer[] = [];
  edl.tracks.forEach((t, i) => {
    if (t.kind !== "video" || t.muted) return;
    for (const c of t.clips) {
      if (isMediaClip(c) && c.start_ms <= ms && ms < clipEndMs(c)) {
        layers.push({ clip: c, trackIndex: i });
        break; // no overlaps within a track
      }
    }
  });
  return layers; // bottom-up (track order)
}

function captionsUnder(edl: EDL | null, ms: number): CaptionClip[] {
  if (!edl) return [];
  const out: CaptionClip[] = [];
  for (const t of edl.tracks) {
    if (t.muted || (t.kind !== "caption" && t.kind !== "text")) continue;
    for (const c of t.clips) {
      const cap = c as CaptionClip;
      if (!isMediaClip(c) && cap.start_ms <= ms && ms < cap.end_ms) out.push(cap);
    }
  }
  return out;
}

/** One stacked video/image layer, kept in sync with the playhead. */
function VideoLayer({
  projectId,
  edl,
  clip,
  playheadMs,
  playing,
  topmost,
  topRef,
}: {
  projectId: string;
  edl: EDL;
  clip: MediaClip;
  playheadMs: number;
  playing: boolean;
  topmost: boolean;
  topRef: React.MutableRefObject<{ el: HTMLVideoElement; clip: MediaClip } | null>;
}) {
  const ref = useRef<HTMLVideoElement>(null);

  // The topmost video layer is the master media clock for the transport.
  useEffect(() => {
    if (topmost && ref.current && clip.freeze_frame_at_ms === undefined) {
      const element = ref.current;
      topRef.current = { el: element, clip };
      return () => {
        if (topRef.current?.el === element) topRef.current = null;
      };
    }
  });
  const asset = edl.assets[clip.asset];
  const speed = clip.speed ?? 1;
  const frozen = clip.freeze_frame_at_ms !== undefined;
  const isImage = asset?.kind === "image";
  const srcRel = isImage ? asset?.src : (asset?.proxy ?? null);
  const url = srcRel ? mediaUrl(projectId, srcRel) : null;

  // Emulate the render compiler: fit to canvas (contain), then transform
  // scale + pixel offsets (as % of canvas so the box can be any size);
  // center crop -> cover.
  const canvasW = edl.project.canvas.width;
  const canvasH = edl.project.canvas.height;
  const elapsed = Math.max(0, playheadMs - clip.start_ms);
  const remaining = Math.max(0, clipEndMs(clip) - playheadMs);
  const enterOpacity = clip.video_fade_in_ms ? Math.min(1, elapsed / clip.video_fade_in_ms) : 1;
  const exitOpacity = clip.video_fade_out_ms ? Math.min(1, remaining / clip.video_fade_out_ms) : 1;
  const color = clip.effects?.find((effect) => effect.cap === "color-adjust")?.params ?? {};
  const effect = (cap: string) => clip.effects?.find((item) => item.cap === cap);
  const previewFilters = [
    effect("grayscale") ? "grayscale(1)" : "",
    effect("blur") ? `blur(${Number(effect("blur")?.params.radius ?? 8)}px)` : "",
    `brightness(${Math.max(0, 1 + Number(color.brightness ?? 0))})`,
    `contrast(${Number(color.contrast ?? 1)})`,
    `saturate(${Number(color.saturation ?? 1)})`,
  ].filter(Boolean).join(" ");
  const style: React.CSSProperties = {
    position: "absolute",
    inset: 0,
    width: "100%",
    height: "100%",
    objectFit: clip.crop?.mode === "center" ? "cover" : "contain",
    opacity: (clip.opacity ?? 1) * Math.min(enterOpacity, exitOpacity),
    filter: previewFilters,
    clipPath: effect("circle-mask") ? "circle(50% at 50% 50%)" : undefined,
    transform: `translate(${(100 * (clip.transform?.x ?? 0)) / canvasW}%, ${
      (100 * (clip.transform?.y ?? 0)) / canvasH
    }%) scale(${clip.transform?.scale ?? 1})${effect("mirror") ? " scaleX(-1)" : ""}`,
  };

  // Sync playback state + position to the master clock.
  useEffect(() => {
    const v = ref.current;
    if (!v || isImage) return;
    const wantS = (frozen ? clip.freeze_frame_at_ms! : clip.in_ms + (playheadMs - clip.start_ms) * speed) / 1000;
    if (!Number.isFinite(wantS)) return;
    const drift = Math.abs(v.currentTime - wantS);
    if (frozen) {
      if (!v.paused) v.pause();
      if (drift > 0.01) v.currentTime = wantS;
    } else if (playing) {
      if (v.playbackRate !== speed) v.playbackRate = speed;
      if (drift > 0.2) v.currentTime = wantS; // resync only on real drift
      if (v.paused) v.play().catch(() => undefined);
    } else {
      if (!v.paused) v.pause();
      if (drift > 0.05) v.currentTime = wantS;
    }
  }, [playheadMs, playing, clip.id, clip.in_ms, clip.start_ms, clip.freeze_frame_at_ms, speed, frozen, isImage, url]);

  if (!url) return null;
  if (isImage) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={url} alt="" style={style} draggable={false} />;
  }
  return (
    <video
      ref={ref}
      key={clip.id}
      src={url}
      style={style}
      muted
      preload="auto"
      playsInline
      data-testid={`layer-${clip.id}`}
    />
  );
}

/** Separate media audio allows every audible track to share clip + track gain. */
function AudioLayer({ projectId, edl, clip, gainDb, playing, playheadMs, context }: {
  projectId: string; edl: EDL; clip: MediaClip; gainDb: number; playing: boolean;
  playheadMs: number; context: AudioContext | null;
}) {
  const element = useRef<HTMLAudioElement>(null);
  const gain = useRef<GainNode | null>(null);
  const lowCut = useRef<BiquadFilterNode | null>(null);
  const highCut = useRef<BiquadFilterNode | null>(null);
  const voiceEq = useRef<BiquadFilterNode | null>(null);
  const source = useRef<MediaElementAudioSourceNode | null>(null);
  const asset = edl.assets[clip.asset];
  const url = mediaUrl(projectId, asset.proxy || asset.src);
  useEffect(() => {
    const audio = element.current;
    if (!audio || !context) return;
    // Strict Mode can reconnect the same element; it must never create a second source.
    source.current ??= context.createMediaElementSource(audio);
    gain.current = context.createGain();
    lowCut.current = context.createBiquadFilter();
    lowCut.current.type = "highpass";
    highCut.current = context.createBiquadFilter();
    highCut.current.type = "lowpass";
    voiceEq.current = context.createBiquadFilter();
    voiceEq.current.type = "peaking";
    voiceEq.current.frequency.value = 3000;
    voiceEq.current.Q.value = 1;
    source.current.connect(lowCut.current);
    lowCut.current.connect(highCut.current);
    highCut.current.connect(voiceEq.current);
    voiceEq.current.connect(gain.current);
    gain.current.connect(context.destination);
    // Effects run after the toolbar click, so the first render can still see
    // a suspended context. Wake it here as well as in the click handler.
    void context.resume();
    return () => { audio.pause(); source.current?.disconnect(); lowCut.current?.disconnect(); highCut.current?.disconnect(); voiceEq.current?.disconnect(); gain.current?.disconnect(); };
  }, [context]);
  useEffect(() => {
    const elapsed = Math.max(0, playheadMs - clip.start_ms);
    const remaining = Math.max(0, clipEndMs(clip) - playheadMs);
    const fadeIn = clip.fade_in_ms ? Math.min(1, elapsed / clip.fade_in_ms) : 1;
    const fadeOut = clip.fade_out_ms ? Math.min(1, remaining / clip.fade_out_ms) : 1;
    if (gain.current) gain.current.gain.value = Math.pow(10, gainDb / 20) * Math.min(fadeIn, fadeOut);
    const telephone = clip.audio_effect === "telephone";
    if (lowCut.current) lowCut.current.frequency.value = telephone ? 300 : clip.audio_low_cut_hz || (clip.audio_effect === "voice-enhance" ? 80 : 10);
    if (highCut.current) highCut.current.frequency.value = telephone ? 3400 : clip.audio_high_cut_hz || Math.min(22000, context?.sampleRate ? context.sampleRate / 2 - 100 : 22000);
    if (voiceEq.current) voiceEq.current.gain.value = clip.audio_effect === "voice-enhance" ? 3 : 0;
    const audio = element.current;
    if (!audio) return;
    const speed = clip.speed ?? 1;
    const time = (clip.in_ms + (playheadMs - clip.start_ms) * speed) / 1000;
    audio.playbackRate = speed;
    if (Math.abs(audio.currentTime - time) > (playing ? .2 : .02)) audio.currentTime = time;
    if (!playing) {
      audio.pause();
      return;
    }
    // Waiting for resume avoids racing the browser's suspended -> running
    // transition. The old synchronous state check left review audio paused.
    const resume = context ? context.resume() : Promise.resolve();
    void resume.then(() => audio.play()).catch(() => undefined);
  }, [playing, playheadMs, clip, gainDb, context]);
  return <audio ref={element} crossOrigin="anonymous" src={url} preload="auto" data-testid={`audio-${clip.id}`} />;
}

export function Preview({
  projectId,
  edl,
  playheadMs,
  renderJob,
  onSeek,
}: {
  projectId: string;
  edl: EDL | null;
  playheadMs: number;
  renderJob: Job | null;
  onRender: () => void;
  onSeek: (ms: number) => void;
}) {
  const [playing, setPlaying] = useState(false);
  const audioContextRef = useRef<AudioContext | null>(null);
  const [audioContext, setAudioContext] = useState<AudioContext | null>(null);
  const primeAudio = useCallback(() => {
    audioContextRef.current ??= new AudioContext();
    setAudioContext(audioContextRef.current);
    void audioContextRef.current.resume();
  }, []);
  useEffect(() => () => { void audioContextRef.current?.close(); audioContextRef.current = null; }, []);
  const [segment, setSegment] = useState<{ url: string } | null>(null);
  const [segmentJob, setSegmentJob] = useState<Job | null>(null);
  const playheadRef = useRef(playheadMs);
  useLayoutEffect(() => { playheadRef.current = playheadMs; }, [playheadMs]);
  const onSeekRef = useRef(onSeek);
  useLayoutEffect(() => { onSeekRef.current = onSeek; }, [onSeek]);
  const topRef = useRef<{ el: HTMLVideoElement; clip: MediaClip } | null>(null);

  const duration = edl?.project.duration_ms ?? 0;
  const layers = useMemo(() => layersUnder(edl, playheadMs), [edl, playheadMs]);
  const captions = useMemo(() => captionsUnder(edl, playheadMs), [edl, playheadMs]);
  const topmostId = layers.length ? layers[layers.length - 1].clip.id : null;

  // Master clock: wall-clock interval, corrected by the topmost video's media
  // clock (authoritative — keeps running even in hidden tabs and can't drift
  // from what's actually playing). Gaps with no video advance by wall clock.
  useEffect(() => {
    if (!playing) return;
    let last = performance.now();
    const id = setInterval(() => {
      const now = performance.now();
      let next = playheadRef.current + (now - last);
      last = now;
      const top = topRef.current;
      if (top && !top.el.paused && top.el.readyState >= 2) {
        const c = top.clip;
        const mediaMs =
          c.start_ms + (top.el.currentTime * 1000 - c.in_ms) / (c.speed ?? 1);
        // Trust the media clock unless it's wildly off (src just swapped).
        if (Math.abs(mediaMs - next) < 2000) next = mediaMs;
      }
      if (next >= duration) {
        onSeekRef.current(duration);
        setPlaying(false);
        return;
      }
      onSeekRef.current(next);
    }, 50);
    return () => clearInterval(id);
  }, [playing, duration]);

  // Space toggles playback (unless typing in an input).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code !== "Space") return;
      const el = document.activeElement;
      if (el && ["INPUT", "TEXTAREA", "SELECT", "VIDEO", "BUTTON"].includes(el.tagName)) return;
      e.preventDefault();
      primeAudio();
      setPlaying((p) => (duration > 0 ? !p : p));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [duration, primeAudio]);

  // L1 segment preview: render the next 10s from the playhead exactly.
  const previewSegment = useCallback(async () => {
    if (!edl) return;
    const from = Math.floor(playheadRef.current);
    const to = Math.min(duration, from + 10_000);
    if (to <= from) return;
    setPlaying(false);
    const r = await api.previewSegment(projectId, from, to);
    const poll = async () => {
      const job = await api.getJob(r.job_id);
      setSegmentJob(job);
      if (job.state === "done") {
        setSegment({ url: mediaUrl(projectId, r.output) + `?t=${Date.now()}` });
        setSegmentJob(null);
      } else if (job.state === "failed" || job.state === "cancelled") {
        setSegmentJob(job);
      } else {
        setTimeout(poll, 400);
      }
    };
    poll();
  }, [edl, duration, projectId]);

  const renderDone = renderJob?.state === "done";
  const renderOut = renderDone
    ? String((renderJob!.artifacts as { mux?: { file?: string } }).mux?.file ?? "")
        .split(/[\\/]/)
        .pop()
    : null;

  const sceneIndex = edl?.scenes?.findIndex(s => s.start_ms <= playheadMs && playheadMs < s.end_ms) ?? -1;
  const scene = edl?.scenes?.[sceneIndex];
  const timecode = (ms:number) => `${String(Math.floor(ms/60000)).padStart(2,"0")}:${String(Math.floor(ms/1000)%60).padStart(2,"0")}:${String(Math.floor(ms%1000/(1000/(edl?.project.canvas.fps ?? 30)))).padStart(2,"0")}`;
  const canvasAspect = edl
    ? `${edl.project.canvas.width} / ${edl.project.canvas.height}`
    : "16 / 9";

  return (
    <div className="spine-preview flex h-full flex-col bg-zinc-950" data-audio-context={audioContext?.state ?? "uninitialized"} data-audio-playing={playing ? "true" : "false"}>
      {edl && edl.tracks.filter(t => !t.muted && (t.kind === "audio" || t.kind === "video") && (!edl.tracks.some(t => (t.kind === "video" || t.kind === "audio") && t.solo) || t.solo)).flatMap(t => t.clips.filter(c => isMediaClip(c) && edl.assets[c.asset]?.kind !== "image" && c.start_ms <= playheadMs && clipEndMs(c) > playheadMs).map(c => <AudioLayer key={c.id} projectId={projectId} edl={edl} clip={c as MediaClip} gainDb={(t.gain_db ?? 0) + ((c as MediaClip).gain_db ?? 0)} playing={playing && !segment} playheadMs={playheadMs} context={audioContext} />))}
      <div className="spine-preview-heading"><span><i style={{background:`hsl(${sceneIndex*45+25} 45% 58%)`}} />{scene ? `Scene ${String(sceneIndex+1).padStart(2,"0")} · ${scene.title}` : "Project preview"}</span><small>{timecode(duration)}</small></div>
      <div className="spine-preview-canvas flex min-h-0 flex-1 items-center justify-center p-3" style={{containerType: "size", aspectRatio: canvasAspect, flex: "0 1 auto"}}>
        {segment ? (
          <div className="relative max-h-full" style={{ aspectRatio: canvasAspect }}>
            <video
              src={segment.url}
              className="max-h-full max-w-full rounded border border-sky-800 bg-black"
              controls
              autoPlay
              data-testid="segment-video"
            />
            <button
              className="absolute right-2 top-2 rounded bg-zinc-900/80 px-2 py-0.5 text-[11px] text-zinc-200 hover:bg-zinc-800"
              onClick={() => setSegment(null)}
              data-testid="segment-close"
            >
              ✕ back to live
            </button>
            <span className="absolute left-2 top-2 rounded bg-sky-900/80 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-sky-200">
              L1 exact
            </span>
          </div>
        ) : layers.length > 0 || captions.length > 0 ? (
          <div
            className="relative max-h-full overflow-hidden rounded border border-zinc-800 bg-black"
            style={{ aspectRatio: canvasAspect, width: `min(100cqw, ${100 * (edl?.project.canvas.width ?? 16) / (edl?.project.canvas.height ?? 9)}cqh)`, maxWidth: "100%", backgroundColor: edl?.project.canvas.background_color ?? "#000000" }}
            data-testid="compositor"
            onClick={() => { primeAudio(); if (duration > 0) setPlaying(p => !p); }}
          >
            {edl &&
              layers.map((l) => (
                <VideoLayer
                  key={l.clip.id}
                  projectId={projectId}
                  edl={edl}
                  clip={l.clip}
                  playheadMs={playheadMs}
                  playing={playing}
                  topmost={l.clip.id === topmostId}
                  topRef={topRef}
                />
              ))}
            {captions.map((c) => (
              <div
                key={c.id}
                data-testid={`caption-overlay-${c.id}`}
                className={`pointer-events-none absolute px-[6%] ${c.cap_style === "title-card" ? "inset-0 flex items-center justify-center text-center" : c.cap_style === "lower-third" ? "inset-x-0 bottom-[10%] text-left" : c.cap_style === "top-title" ? "inset-x-0 top-[8%] text-center" : "inset-x-0 bottom-[8%] text-center"}`}
              >
                <span
                  className={`inline-block rounded px-2 py-0.5 font-semibold ${c.cap_style === "bold-pop" ? "text-yellow-300" : c.cap_style === "karaoke" ? "text-cyan-100" : "text-white"}`}
                  style={{
                    fontSize: c.cap_style === "title-card" ? "clamp(20px, 5.5cqw, 72px)" : c.cap_style === "bold-pop" ? "clamp(15px, 4.3cqw, 56px)" : c.cap_style === "karaoke" ? "clamp(15px, 4cqw, 52px)" : c.cap_style === "top-title" ? "clamp(14px, 3.7cqw, 48px)" : "clamp(12px, 3.2cqw, 42px)",
                    background: c.cap_style === "boxed" || c.cap_style === "lower-third" ? "rgba(0,0,0,0.82)" : "rgba(0,0,0,0.55)",
                    textShadow: c.cap_style === "karaoke" ? "0 2px 0 #164e63, 0 0 5px #000" : "0 1px 3px rgba(0,0,0,0.9)",
                  }}
                >
                  {c.text}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div
            className="flex aspect-video w-2/3 items-center justify-center rounded border border-dashed border-zinc-800 text-xs text-zinc-600"
            data-testid="preview-empty"
          >
            {edl && duration > 0
              ? "No clip under playhead"
              : "Timeline is empty — drop a clip to see the live preview"}
          </div>
        )}
      </div>

      <div className="spine-scrubber">{edl?.scenes?.length ? edl.scenes.map((s,i) => <button key={s.id} title={s.title} onClick={() => onSeek(s.start_ms)} className={scene?.id === s.id ? "active" : ""} style={{flex:s.end_ms-s.start_ms,background:`hsl(${i*45+25} ${scene?.id === s.id ? "45% 55%" : "20% 28%"})`}} />) : <input type="range" min={0} max={duration} value={playheadMs} onChange={e => onSeek(Number(e.target.value))} aria-label="Seek preview" />}<i style={{left:`${duration ? 100*playheadMs/duration : 0}%`}} /></div>
      <div className="spine-transport"><span className="spine-timecode">{timecode(playheadMs)}<small> / {timecode(duration)}</small></span><div className="spine-play-controls"><button title="Previous scene" className="spine-icon" onClick={() => onSeek(edl?.scenes?.[Math.max(0,sceneIndex-1)]?.start_ms ?? 0)}><SpineIcon name="prev" size={15} /></button>
        <button
          title={playing ? "Pause (Space)" : "Play (Space)"}
          data-testid="play-button"
          className="rounded bg-zinc-800 px-3 py-1 text-xs font-semibold text-zinc-100 hover:bg-zinc-700 disabled:opacity-40"
          disabled={!edl || duration === 0}
          onClick={() => { primeAudio(); setPlaying(p => !p); }}
        >
          <SpineIcon name={playing ? "pause" : "play"} size={17} />
        </button>
        <button title="Next scene" className="spine-icon" onClick={() => onSeek(edl?.scenes?.[Math.min((edl.scenes?.length ?? 1)-1,sceneIndex+1)]?.start_ms ?? duration)}><SpineIcon name="next" size={15} /></button></div><div className="spine-frame-controls">
        <button title="Previous frame" onClick={() => { setPlaying(false); onSeek(Math.max(0, playheadMs - 1000 / (edl?.project.canvas.fps ?? 30))); }}><SpineIcon name="chl" size={15} /></button>
        <button title="Next frame" onClick={() => { setPlaying(false); onSeek(Math.min(duration, playheadMs + 1000 / (edl?.project.canvas.fps ?? 30))); }}><SpineIcon name="chr" size={15} /></button>
        <button
          data-testid="preview-segment-button"
          className="rounded bg-sky-800 px-3 py-1 text-xs font-semibold text-sky-100 hover:bg-sky-700 disabled:opacity-40"
          disabled={!edl || duration === 0 || !!segmentJob}
          onClick={previewSegment}
          title="Exact render of the next 10s from the playhead"
        >
          {segmentJob && segmentJob.state !== "failed"
            ? `L1… ${Math.round((segmentJob.progress ?? 0) * 100)}%`
            : "Preview 10s"}
        </button>
        </div></div><div className="spine-render-status">
        {segmentJob?.state === "failed" && (
          <span className="text-xs text-red-400">segment failed</span>
        )}
        {renderJob && (renderJob.state === "queued" || renderJob.state === "running") && (
          <div className="flex flex-1 items-center gap-2">
            <div className="h-1.5 flex-1 overflow-hidden rounded bg-zinc-800">
              <div
                className="h-full bg-emerald-600 transition-all"
                style={{ width: `${Math.round(renderJob.progress * 100)}%` }}
              />
            </div>
            <span className="text-[10px] text-zinc-400" data-testid="render-progress">
              {renderJob.stage ?? renderJob.state} · {Math.round(renderJob.progress * 100)}%
            </span>
          </div>
        )}
        {renderJob?.state === "failed" && (
          <span className="text-xs text-red-400" data-testid="render-failed">
            Render failed
          </span>
        )}
        {renderDone && renderOut && (
          <a
            data-testid="render-result"
            className="text-xs text-emerald-400 underline"
            href={mediaUrl(projectId, `renders/${renderOut}`)}
            target="_blank"
            rel="noreferrer"
          >
            {renderOut}
          </a>
        )}
        <span className="ml-auto text-[10px] tabular-nums text-zinc-500">
          {(playheadMs / 1000).toFixed(2)}s{edl ? ` / ${(duration / 1000).toFixed(2)}s` : ""}
        </span>
      </div>
    </div>
  );
}
