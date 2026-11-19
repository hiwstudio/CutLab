/**
 * Asset usage tracking (V2 — Pillar 4). File-based (assets/usage.json), no database.
 * Records how often each asset is used across rendered manifests so the library can
 * surface popular vs. unused assets.
 *
 * Node-only (fs). tallyManifest is pure and unit-tested.
 */
import fs from "fs-extra";
import path from "node:path";
import type { Manifest } from "../manifest/schema";
import type { MetaKind } from "./assetMeta";

export type UsageMap = Record<string, number>;

export function usageKey(kind: MetaKind, id: string): string {
  return `${kind}:${id}`;
}

const DEFAULT_USAGE_PATH = path.resolve(process.cwd(), "assets", "usage.json");

export function loadUsage(usagePath: string = DEFAULT_USAGE_PATH): UsageMap {
  try {
    if (fs.existsSync(usagePath)) return fs.readJsonSync(usagePath) as UsageMap;
  } catch {
    /* ignore corrupt usage file */
  }
  return {};
}

export function saveUsage(usage: UsageMap, usagePath: string = DEFAULT_USAGE_PATH): void {
  fs.ensureDirSync(path.dirname(usagePath));
  fs.writeJsonSync(usagePath, usage, { spaces: 2 });
}

/** Count every asset reference in a manifest. Pure. */
export function tallyManifest(manifest: Manifest): UsageMap {
  const t: UsageMap = {};
  const bump = (kind: MetaKind, id: string | undefined) => {
    if (!id) return;
    const k = usageKey(kind, id);
    t[k] = (t[k] ?? 0) + 1;
  };

  for (const scene of manifest.scenes) {
    bump("background", scene.background);
    bump("captionStyle", scene.caption.style);
    if (scene.camera) bump("camera", scene.camera.type);
    for (const e of scene.effects) bump("effect", e);
    for (const ch of scene.characters) {
      bump("character", ch.id);
      bump("variant", ch.variant ?? "default");
      bump("expression", ch.expression ?? "neutral");
      bump("motion", ch.motion ?? "idle");
    }
    for (const p of scene.props) bump("prop", p.id);
  }
  return t;
}

/** Merge a manifest's usage into the on-disk store and return the updated map. */
export function recordManifestUsage(manifest: Manifest, usagePath: string = DEFAULT_USAGE_PATH): UsageMap {
  const usage = loadUsage(usagePath);
  const tally = tallyManifest(manifest);
  for (const [k, n] of Object.entries(tally)) {
    usage[k] = (usage[k] ?? 0) + n;
  }
  saveUsage(usage, usagePath);
  return usage;
}
