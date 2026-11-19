/**
 * Asset library (V2 — Pillar 4). Pure "reuse before create" search over the asset
 * metadata, plus a coverage check that every catalog id has metadata. No fs/React.
 */
import {
  BACKGROUND_IDS,
  CAMERA_TYPES,
  CAPTION_STYLES,
  CHARACTER_IDS,
  CHARACTER_VARIANTS,
  EFFECT_IDS,
  EXPRESSIONS,
  MOTION_IDS,
  PROP_IDS,
} from "./catalog";
import { ASSET_META, type AssetRecord, type MetaKind } from "./assetMeta";

export type { AssetRecord, MetaKind };

export function allAssets(): AssetRecord[] {
  return ASSET_META;
}

export function assetsByKind(kind: MetaKind): AssetRecord[] {
  return ASSET_META.filter((a) => a.kind === kind);
}

export interface ScoredAsset {
  record: AssetRecord;
  score: number;
}

function tokenize(s: string): string[] {
  return s
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((t) => t.length > 1);
}

/** Score a record against query tokens (name/id strong, tags exact > partial, desc weak). */
function scoreRecord(record: AssetRecord, tokens: string[]): number {
  const idL = record.id.toLowerCase();
  const nameL = record.name.toLowerCase();
  const descL = record.description.toLowerCase();
  const tagsL = record.tags.map((t) => t.toLowerCase());

  let score = 0;
  for (const tok of tokens) {
    if (idL === tok || nameL === tok) score += 4;
    else if (nameL.includes(tok)) score += 2;
    if (tagsL.includes(tok)) score += 3;
    else if (tagsL.some((t) => t.includes(tok) || tok.includes(t))) score += 1;
    if (descL.includes(tok)) score += 1;
  }
  return score;
}

export interface SearchOptions {
  kind?: MetaKind;
  limit?: number;
}

/** Ranked reuse suggestions for a free-text need. */
export function searchAssets(query: string, options: SearchOptions = {}): ScoredAsset[] {
  const tokens = tokenize(query);
  if (tokens.length === 0) return [];
  const pool = options.kind ? assetsByKind(options.kind) : ASSET_META;
  const scored = pool
    .map((record) => ({ record, score: scoreRecord(record, tokens) }))
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score || a.record.id.localeCompare(b.record.id));
  return typeof options.limit === "number" ? scored.slice(0, options.limit) : scored;
}

const CATALOG_BY_KIND: Record<MetaKind, readonly string[]> = {
  character: CHARACTER_IDS,
  variant: CHARACTER_VARIANTS,
  background: BACKGROUND_IDS,
  motion: MOTION_IDS,
  prop: PROP_IDS,
  effect: EFFECT_IDS,
  camera: CAMERA_TYPES,
  captionStyle: CAPTION_STYLES,
  expression: EXPRESSIONS,
};

/** Catalog ids that are missing an ASSET_META record (should always be empty). */
export function metaCoverageGaps(): Array<{ kind: MetaKind; id: string }> {
  const have = new Set(ASSET_META.map((a) => `${a.kind}:${a.id}`));
  const gaps: Array<{ kind: MetaKind; id: string }> = [];
  for (const kind of Object.keys(CATALOG_BY_KIND) as MetaKind[]) {
    for (const id of CATALOG_BY_KIND[kind]) {
      if (!have.has(`${kind}:${id}`)) gaps.push({ kind, id });
    }
  }
  return gaps;
}

export const META_KINDS: MetaKind[] = Object.keys(CATALOG_BY_KIND) as MetaKind[];
