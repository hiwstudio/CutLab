/**
 * Style library — reusable LOOK profiles for the image-generated (stick-hiw) path.
 *
 * Each style lives in `styles/<name>/`:
 *   style.json   the look only (same fields as the original stick-hiw/style.json + `status`)
 *   source.md    reference link, frames reviewed, what was taken / deliberately left out,
 *                motion & pacing notes (NOT look), approval + dated corrections log
 *   approved/    owner-approved test stills (used as visual references for that style)
 *
 * Pure Node helpers (no rendering, no network, no image generation). The Remotion
 * puppet style is code and is NOT driven by these files.
 */
import fs from "node:fs";
import path from "node:path";

/** Style used when neither `--style` nor the manifest's `style.imageStyle` names one. */
export const DEFAULT_STYLE = "stick-hiw";

export type StyleStatus = "draft" | "approved";

export interface StyleDescriptor {
  styleName?: string;
  /** `draft` until the owner approves its test stills; only `approved` styles feed real videos. */
  status?: StyleStatus;
  model?: string;
  aspectRatio?: string;
  resolution?: string;
  stylePreamble?: string;
  characterStyle?: string;
  backgroundStyle?: string;
  colorPalette?: string;
  composition?: string;
  negativePrompt?: string;
  _note?: string;
}

/** The look fields a correction may change (`style:correct --field <one of these>`). */
export const LOOK_FIELDS = [
  "stylePreamble",
  "characterStyle",
  "backgroundStyle",
  "colorPalette",
  "composition",
  "negativePrompt",
  "model",
  "aspectRatio",
  "resolution",
] as const;
export type LookField = (typeof LOOK_FIELDS)[number];

/** Marker the extractor leaves in fields that still need a visual review of the frames. */
export const PLACEHOLDER = "TODO(visual-review)";

export interface SceneLike {
  id: string;
  voiceover?: string;
  notes?: string;
  image?: string;
  /** Ids of recurring characters from the character library that appear in this scene. */
  cast?: string[];
}

export interface Character {
  id: string;
  name?: string;
  appearance?: string;
  ref?: string;
}

export interface LoadedStyle {
  name: string;
  style: StyleDescriptor;
  /** Absolute path of the style.json actually read ("" when missing). */
  path: string;
  /** `library` = styles/<name>/style.json; `legacy` = old stick-hiw/style.json fallback. */
  source: "library" | "legacy" | "missing";
  status: StyleStatus;
}

export function stylesRoot(cwd: string = process.cwd()): string {
  return path.resolve(cwd, "styles");
}

export function styleDir(name: string, cwd: string = process.cwd()): string {
  return path.join(stylesRoot(cwd), name);
}

export function legacyStylePath(cwd: string = process.cwd()): string {
  return path.resolve(cwd, "stick-hiw", "style.json");
}

/** Style folder names: lowercase kebab-case, 1–63 chars. */
export function isValidStyleName(name: string): boolean {
  return /^[a-z0-9][a-z0-9-]{0,62}$/.test(name);
}

/**
 * Status of a loaded style. Library styles without an explicit `"approved"` are treated as
 * draft (fail closed). The legacy stick-hiw file predates the field and is the channel's
 * long-running approved look.
 */
export function statusOf(style: StyleDescriptor, source: LoadedStyle["source"]): StyleStatus {
  if (style.status === "approved") return "approved";
  if (style.status === "draft") return "draft";
  return source === "legacy" ? "approved" : "draft";
}

export function loadStyle(name: string, cwd: string = process.cwd()): LoadedStyle {
  const libPath = path.join(styleDir(name, cwd), "style.json");
  if (fs.existsSync(libPath)) {
    const style = JSON.parse(fs.readFileSync(libPath, "utf8")) as StyleDescriptor;
    return { name, style, path: libPath, source: "library", status: statusOf(style, "library") };
  }
  // Back-compat: before the library existed the only style was stick-hiw/style.json.
  const legacy = legacyStylePath(cwd);
  if (name === DEFAULT_STYLE && fs.existsSync(legacy)) {
    const style = JSON.parse(fs.readFileSync(legacy, "utf8")) as StyleDescriptor;
    return { name, style, path: legacy, source: "legacy", status: statusOf(style, "legacy") };
  }
  return { name, style: {}, path: "", source: "missing", status: "draft" };
}

export interface StyleListing {
  name: string;
  status: StyleStatus;
  styleName: string;
  approvedStills: number;
}

/** Every `styles/<name>/style.json`, sorted by name (the default style first). */
export function listStyles(cwd: string = process.cwd()): StyleListing[] {
  const root = stylesRoot(cwd);
  if (!fs.existsSync(root)) return [];
  return fs
    .readdirSync(root, { withFileTypes: true })
    .filter((d) => d.isDirectory() && fs.existsSync(path.join(root, d.name, "style.json")))
    .map((d) => {
      const loaded = loadStyle(d.name, cwd);
      return {
        name: d.name,
        status: loaded.status,
        styleName: loaded.style.styleName ?? d.name,
        approvedStills: approvedStills(d.name, cwd).length,
      };
    })
    .sort((a, b) => (a.name === DEFAULT_STYLE ? -1 : b.name === DEFAULT_STYLE ? 1 : a.name.localeCompare(b.name)));
}

const IMAGE_EXT = /\.(png|jpe?g|webp)$/i;

/** Absolute paths of the owner-approved stills in `styles/<name>/approved/`. */
export function approvedStills(name: string, cwd: string = process.cwd()): string[] {
  const dir = path.join(styleDir(name, cwd), "approved");
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((f) => IMAGE_EXT.test(f))
    .sort()
    .map((f) => path.join(dir, f));
}

/**
 * Which style a project uses: explicit `--style` flag, else the manifest's optional
 * `style.imageStyle`, else the default (`stick-hiw`). Old manifests need no change.
 */
export function resolveStyleName(flag: string | undefined, manifest: unknown): string {
  if (flag && flag.trim()) return flag.trim();
  const fromManifest = (manifest as { style?: { imageStyle?: unknown } } | undefined)?.style?.imageStyle;
  if (typeof fromManifest === "string" && fromManifest.trim()) return fromManifest.trim();
  return DEFAULT_STYLE;
}

/** Look fields still holding the extractor's placeholder (must be filled from the frames). */
export function unfilledFields(style: StyleDescriptor): string[] {
  return (Object.keys(style) as Array<keyof StyleDescriptor>).filter(
    (k) => k !== "_note" && typeof style[k] === "string" && (style[k] as string).includes(PLACEHOLDER)
  );
}

/** Build the "Cast" clause: canonical appearance of each library character in the scene. */
export function castClause(scene: SceneLike, charById: Map<string, Character>): string {
  const ids = Array.isArray(scene.cast) ? scene.cast : [];
  const blocks = ids
    .map((id) => {
      const c = charById.get(id);
      if (!c) {
        console.warn(`  ⚠️  ${scene.id}: cast id "${id}" not found in characters.json — skipped.`);
        return "";
      }
      const ref = c.ref ? ` (match the reference image ${c.ref})` : "";
      return `${c.appearance ?? c.name ?? id}${ref}`;
    })
    .filter(Boolean);
  if (!blocks.length) return "";
  return `Cast — keep these recurring characters visually consistent across videos: ${blocks.join(" ")}`;
}

/** One image prompt = global style block + the scene's own subject (+ cast). */
export function buildPrompt(style: StyleDescriptor, scene: SceneLike, charById: Map<string, Character>): string {
  const subject = (scene.notes?.trim() || scene.voiceover?.trim() || "").replace(/\s+/g, " ");
  const parts = [
    style.stylePreamble,
    subject ? `Scene: ${subject}` : "",
    castClause(scene, charById),
    style.characterStyle,
    style.backgroundStyle,
    style.colorPalette ? `Colors: ${style.colorPalette}` : "",
    style.composition,
    style.aspectRatio ? `${style.aspectRatio} aspect ratio` : "",
    style.negativePrompt ? `Avoid: ${style.negativePrompt}` : "",
  ];
  return parts.map((p) => (p ?? "").trim()).filter(Boolean).join(". ").replace(/\.\.+/g, ".") + ".";
}

/** Apply one correction to a look field. `append` adds a sentence; `set` replaces the field. */
export function applyCorrection(
  style: StyleDescriptor,
  field: LookField,
  op: "set" | "append",
  text: string
): StyleDescriptor {
  const t = text.trim();
  const prev = (style[field] ?? "").trim();
  let next: string;
  if (op === "set" || !prev) next = t;
  else next = `${prev.replace(/[\s.;,]+$/, "")}. ${t}`;
  return { ...style, [field]: next };
}

/** YYYY-MM-DD in local time (dated log lines in source.md). */
export function localDate(d: Date = new Date()): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/** Append a dated bullet under the `## Log` heading of source.md (created if missing). */
export function appendSourceLog(sourceMdPath: string, line: string, date: string = localDate()): void {
  let md = fs.existsSync(sourceMdPath) ? fs.readFileSync(sourceMdPath, "utf8") : "";
  if (!/^## Log\b/m.test(md)) md = `${md.replace(/\s*$/, "")}\n\n## Log\n\n`;
  if (!md.endsWith("\n")) md += "\n";
  md += `- ${date} — ${line.replace(/\s+/g, " ").trim()}\n`;
  fs.writeFileSync(sourceMdPath, md);
}

/** Write style.json the same way the original file is laid out (2-space JSON + newline). */
export function writeStyle(stylePath: string, style: StyleDescriptor): void {
  fs.writeFileSync(stylePath, JSON.stringify(style, null, 2) + "\n");
}

/** Flags that never take a value (so they can't swallow a following positional). */
export const BOOLEAN_FLAGS = ["allow-draft", "reuse", "revoke"];

/** Minimal flag parser: `--key value`, `--key=value`, `--flag` (boolean), everything else positional. */
export function parseCliArgs(
  argv: string[],
  booleans: string[] = BOOLEAN_FLAGS
): { positional: string[]; flags: Record<string, string | boolean> } {
  const positional: string[] = [];
  const flags: Record<string, string | boolean> = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const eq = a.indexOf("=");
      if (eq > 2) {
        flags[a.slice(2, eq)] = a.slice(eq + 1);
        continue;
      }
      const key = a.slice(2);
      const next = argv[i + 1];
      if (!booleans.includes(key) && next !== undefined && !next.startsWith("--")) {
        flags[key] = next;
        i++;
      } else flags[key] = true;
    } else positional.push(a);
  }
  return { positional, flags };
}

export interface PaletteEntry {
  hex: string;
  share: number;
}

/**
 * Dominant colours of raw RGB24 pixels: bucket each channel to 16 levels, average the
 * real colours inside each bucket, return the biggest buckets with their pixel share.
 * Measured evidence for the palette — the visual review still decides what to keep.
 */
export function dominantColors(rgb: Uint8Array, top = 10): PaletteEntry[] {
  const buckets = new Map<number, { n: number; r: number; g: number; b: number }>();
  const total = Math.floor(rgb.length / 3);
  for (let i = 0; i + 2 < rgb.length; i += 3) {
    const r = rgb[i], g = rgb[i + 1], b = rgb[i + 2];
    const key = ((r >> 4) << 8) | ((g >> 4) << 4) | (b >> 4);
    const e = buckets.get(key) ?? { n: 0, r: 0, g: 0, b: 0 };
    e.n++; e.r += r; e.g += g; e.b += b;
    buckets.set(key, e);
  }
  const hex2 = (v: number) => Math.round(v).toString(16).padStart(2, "0");
  return [...buckets.values()]
    .sort((a, b) => b.n - a.n)
    .slice(0, top)
    .map((e) => ({
      hex: `#${hex2(e.r / e.n)}${hex2(e.g / e.n)}${hex2(e.b / e.n)}`,
      share: total ? Math.round((e.n / total) * 1000) / 10 : 0,
    }));
}
