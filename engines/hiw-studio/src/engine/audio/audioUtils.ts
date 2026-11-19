/**
 * Audio planning (architecture §13). Pure — no Remotion import.
 *
 * The browser side stays "dumb": instead of guessing which audio files exist (it
 * can't touch the filesystem), the CLI builds a concrete AudioPlan with an injected
 * fileExists probe and passes it via Remotion inputProps. This prevents 404s /
 * render failures when a voiceover / music / sfx file is missing.
 *
 * Paths are normalized to be relative to the workspace root, which the renderer and
 * studio serve as Remotion's public dir — so the component resolves them with
 * staticFile().
 */
import type { Manifest } from "../manifest/schema";
import { secondsToFrames } from "../timeline/calculateDurations";

export interface AudioClip {
  src: string;
  volume: number;
}

export interface SfxClip {
  src: string;
  fromFrame: number;
  volume: number;
}

export interface AudioPlan {
  voiceover?: AudioClip;
  music?: AudioClip;
  sfx: SfxClip[];
}

/** Normalize a manifest path into a staticFile()-friendly path relative to public dir. */
export function toPublicPath(p: string): string {
  return p.replace(/\\/g, "/").replace(/^\.\//, "").replace(/^\/+/, "");
}

/** Convention for resolving an sfx id to a file under assets/audio/sfx. */
export function sfxPathForId(id: string): string {
  return `assets/audio/sfx/${id}.mp3`;
}

export interface BuildAudioPlanOptions {
  /** Probe resolving workspace-relative paths. Defaults to "everything exists". */
  fileExists?: (path: string) => boolean;
}

/**
 * Build a concrete audio plan from a manifest. Files that fail the existence probe
 * are omitted so the render never references a missing asset.
 */
export function buildAudioPlan(
  manifest: Manifest,
  options: BuildAudioPlanOptions = {}
): AudioPlan {
  const exists = options.fileExists ?? (() => true);
  const fps = manifest.fps;
  const plan: AudioPlan = { sfx: [] };

  const vo = manifest.audio.voiceoverPath;
  if (vo && exists(vo)) {
    plan.voiceover = { src: toPublicPath(vo), volume: 1 };
  }

  const music = manifest.audio.musicPath;
  if (music && exists(music)) {
    plan.music = { src: toPublicPath(music), volume: manifest.audio.musicVolume ?? 0.12 };
  }

  for (const scene of manifest.scenes) {
    for (const sfx of scene.sfx) {
      const rel = sfxPathForId(sfx.id);
      if (!exists(rel)) continue;
      plan.sfx.push({
        src: toPublicPath(rel),
        fromFrame: secondsToFrames(scene.start + sfx.at, fps),
        volume: sfx.volume ?? 0.7,
      });
    }
  }

  return plan;
}
