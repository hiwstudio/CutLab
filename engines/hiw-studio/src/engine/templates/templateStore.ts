/**
 * Scene-template library (V2 — reuse engine, architecture §17.3 / §18). File-based
 * (assets/templates/*.json), no database. Captures reusable scene *compositions*
 * (background + characters + props + camera + effects, minus content like id/timing/
 * voiceover/caption text) so a known-good scene can be reused across videos.
 *
 * Node-only (fs). Pure helpers (extract/build/score) are unit-tested.
 */
import fs from "fs-extra";
import path from "node:path";
import type { Scene } from "../manifest/schema";

export interface TemplateRecord {
  id: string;
  name: string;
  description: string;
  tags: string[];
  usageCount: number;
  /** Partial scene: structural fields only (no id/start/end; voiceover/caption text blank). */
  scene: Record<string, unknown>;
}

const TEMPLATES_DIR = path.resolve(process.cwd(), "assets", "templates");

export function templatesDir(): string {
  return TEMPLATES_DIR;
}

export function loadTemplates(dir: string = TEMPLATES_DIR): TemplateRecord[] {
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".json"))
    .map((f) => {
      try {
        return fs.readJsonSync(path.join(dir, f)) as TemplateRecord;
      } catch {
        return null;
      }
    })
    .filter((t): t is TemplateRecord => t !== null);
}

export function getTemplate(id: string, dir: string = TEMPLATES_DIR): TemplateRecord | undefined {
  const file = path.join(dir, `${id}.json`);
  if (!fs.existsSync(file)) return undefined;
  try {
    return fs.readJsonSync(file) as TemplateRecord;
  } catch {
    return undefined;
  }
}

export function saveTemplate(record: TemplateRecord, dir: string = TEMPLATES_DIR): string {
  fs.ensureDirSync(dir);
  const file = path.join(dir, `${record.id}.json`);
  fs.writeJsonSync(file, record, { spaces: 2 });
  return file;
}

export function bumpTemplateUsage(id: string, dir: string = TEMPLATES_DIR): void {
  const t = getTemplate(id, dir);
  if (!t) return;
  t.usageCount = (t.usageCount ?? 0) + 1;
  saveTemplate(t, dir);
}

/** Strip content-specific fields, keeping only the reusable visual composition. */
export function extractTemplateScene(scene: Scene): Record<string, unknown> {
  const out: Record<string, unknown> = {
    background: scene.background,
    characters: scene.characters,
  };
  if (scene.props && scene.props.length > 0) out.props = scene.props;
  if (scene.camera) out.camera = scene.camera;
  if (scene.effects && scene.effects.length > 0) out.effects = scene.effects;
  // Only the style is reusable; caption text mirrors the voiceover at render time.
  out.caption = { style: scene.caption.style };
  return out;
}

export interface InstantiateOptions {
  id: string;
  start: number;
  end: number;
  voiceover?: string;
  captionText?: string;
}

/** Build a concrete scene object from a template + per-use timing/content. */
export function buildSceneFromTemplate(template: TemplateRecord, opts: InstantiateOptions): Record<string, unknown> {
  const base = template.scene;
  const baseCaption = (base.caption as { style?: string } | undefined) ?? {};
  return {
    id: opts.id,
    voiceover: opts.voiceover ?? "",
    start: opts.start,
    end: opts.end,
    ...base,
    caption: { style: baseCaption.style ?? "hiw_default", text: opts.captionText ?? "" },
  };
}

function tokenize(s: string): string[] {
  return s.toLowerCase().split(/[^a-z0-9]+/).filter((t) => t.length > 1);
}

export interface ScoredTemplate {
  template: TemplateRecord;
  score: number;
}

/** Ranked template search by name/id/tags/description. */
export function searchTemplates(query: string, templates: TemplateRecord[]): ScoredTemplate[] {
  const tokens = tokenize(query);
  if (tokens.length === 0) return [];
  return templates
    .map((template) => {
      const idL = template.id.toLowerCase();
      const nameL = template.name.toLowerCase();
      const descL = template.description.toLowerCase();
      const tagsL = template.tags.map((t) => t.toLowerCase());
      let score = 0;
      for (const tok of tokens) {
        if (idL === tok || nameL.includes(tok)) score += 3;
        if (tagsL.includes(tok)) score += 3;
        else if (tagsL.some((t) => t.includes(tok) || tok.includes(t))) score += 1;
        if (descL.includes(tok)) score += 1;
      }
      return { template, score };
    })
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score || a.template.id.localeCompare(b.template.id));
}

/** Next sequential scene id ("scene_001", "scene_002", …) for a set of existing ids. */
export function nextSceneId(existingIds: string[]): string {
  let max = 0;
  for (const id of existingIds) {
    const m = /scene_(\d+)/.exec(id);
    if (m) max = Math.max(max, Number.parseInt(m[1], 10));
  }
  return `scene_${String(max + 1).padStart(3, "0")}`;
}
