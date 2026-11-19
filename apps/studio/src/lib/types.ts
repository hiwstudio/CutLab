// Hand-mirrored from apps/server (Phase 0 convention, see B6).

export interface Canvas {
  width: number;
  height: number;
  fps: number;
  background_color?: string;
}

export interface Project {
  id: string;
  name: string;
  head_rev: number;
  created_at: string;
  updated_at: string;
}

export interface Asset {
  kind: "video" | "audio" | "image";
  src: string;
  proxy?: string;
  duration_ms?: number;
  width?: number;
  height?: number;
  understanding?: string;
}

export interface AssetRow {
  project_id: string;
  asset_id: string;
  kind: Asset["kind"];
  src: string;
  proxy?: string | null;
  duration_ms?: number | null;
  width?: number | null;
  height?: number | null;
  understanding?: string | null;
  status: "ingesting" | "ready" | "failed";
}

export interface LibrarySound {
  id: string;
  title: string;
  kind: "music" | "sfx";
  category: string;
  filename: string;
}

export interface Transform {
  scale?: number;
  x?: number;
  y?: number;
  rotate?: number;
}

export interface MediaClip {
  id: string;
  asset: string;
  in_ms: number;
  out_ms: number;
  start_ms: number;
  speed?: number;
  gain_db?: number;
  fade_in_ms?: number;
  fade_out_ms?: number;
  audio_denoise?: boolean;
  audio_low_cut_hz?: number;
  audio_high_cut_hz?: number;
  audio_effect?: "none" | "voice-enhance" | "telephone" | "echo";
  reversed?: boolean;
  freeze_frame_at_ms?: number;
  video_fade_in_ms?: number;
  video_fade_out_ms?: number;
  opacity?: number;
  transform?: Transform;
  crop?: { mode: string; rect?: { x: number; y: number; w: number; h: number } };
  effects?: { cap: string; params: Record<string, unknown> }[];
  transition_out?: { cap: string; duration_ms: number };
}

export interface CaptionClip {
  id: string;
  start_ms: number;
  end_ms: number;
  text: string;
  cap_style?: string;
}

export type Clip = MediaClip | CaptionClip;

export type TrackKind = "video" | "audio" | "caption" | "text";

export interface Track {
  id: string;
  kind: TrackKind;
  clips: Clip[];
  name?: string;
  role?: "footage" | "overlay" | "voiceover" | "music" | "sfx" | "captions" | "other";
  muted?: boolean;
  solo?: boolean;
  locked?: boolean;
  gain_db?: number;
}

export interface Scene {
  id: string;
  title: string;
  start_ms: number;
  end_ms: number;
  approved: boolean;
}

export interface EDL {
  edl_version: string;
  project: {
    id: string;
    name: string;
    profile?: string;
    engine_source?: Record<string, string>;
    canvas: Canvas;
    duration_ms: number;
  };
  assets: Record<string, Asset>;
  tracks: Track[];
  scenes?: Scene[];
}

export interface Job {
  id: string;
  kind: string;
  project_id: string | null;
  asset_id?: string | null;
  state: "queued" | "running" | "done" | "failed" | "cancelled";
  stage: string | null;
  progress: number;
  error: string | null;
  artifacts: Record<string, unknown>;
}

export interface RevisionRow {
  rev: number;
  parent_rev: number | null;
  state: "committed" | "proposed" | "rejected";
  summary: string;
  created_at: string;
}

export interface Understanding {
  version: string;
  asset_id: string;
  kind: string;
  duration_ms: number;
  transcript?: {
    language?: string | null;
    segments: { start_ms: number; end_ms: number; text: string; words: unknown[] }[];
  } | null;
  scenes: { index: number; start_ms: number; end_ms: number }[];
  silence: { start_ms: number; end_ms: number }[];
  active_ranges: { start_ms: number; end_ms: number }[];
  beats_ms: number[];
  tempo_bpm?: number | null;
  saliency?: {
    profile: string;
    window_ms: number;
    windows: { start_ms: number; end_ms: number; score: number }[];
  } | null;
}

export type DirectorResult =
  | { status: "proposed"; rev: number; summary: string; note: string }
  | { status: "awaiting_answer"; request_id: string; prompt: string }
  | { status: "rejected"; issues: Issue[]; note: string };

export type Op = { op: string } & Record<string, unknown>;

export interface Issue {
  code: string;
  path: string;
  message: string;
}

export interface ApplyResult {
  rev: number;
  summary: string;
  edl: EDL;
  warnings: Issue[];
}

export function isMediaClip(c: Clip): c is MediaClip {
  return (c as MediaClip).asset !== undefined;
}

export function clipEndMs(c: Clip): number {
  if (isMediaClip(c)) {
    return c.start_ms + Math.round((c.out_ms - c.in_ms) / (c.speed ?? 1.0));
  }
  return c.end_ms;
}

export function clipLenMs(c: Clip): number {
  return clipEndMs(c) - c.start_ms;
}
