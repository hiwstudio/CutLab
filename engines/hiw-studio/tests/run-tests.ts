/**
 * Lightweight test runner for the pure engine layers (no rendering required).
 * Run with: npm test
 */
import fs from "node:fs";
import path from "node:path";
import { validateManifest } from "../src/engine/manifest/validateManifest";
import { planSequences } from "../src/engine/timeline/sequencePlanner";
import { secondsToFrames } from "../src/engine/timeline/calculateDurations";
import { buildAudioPlan } from "../src/engine/audio/audioUtils";
import { autoShortsRange, buildShortsManifest } from "../src/engine/renderer/buildShortsManifest";
import { estimateWordTimings, parseEmphasis } from "../src/engine/captions/wordTiming";
import { retimeToAudio } from "../src/engine/timeline/retimeToAudio";
import { parseSilenceStarts } from "../src/engine/audio/probeAudio";
import { buildSrt } from "../src/engine/captions/buildSrt";
import { metaCoverageGaps, searchAssets } from "../src/engine/assets/assetLibrary";
import { tallyManifest, usageKey } from "../src/engine/assets/usageStore";
import {
  buildSceneFromTemplate,
  extractTemplateScene,
  loadTemplates,
  nextSceneId,
  searchTemplates,
} from "../src/engine/templates/templateStore";
import {
  DEFAULT_STYLE,
  PLACEHOLDER,
  applyCorrection,
  appendSourceLog,
  buildPrompt,
  dominantColors,
  isValidStyleName,
  listStyles,
  loadStyle,
  parseCliArgs,
  resolveStyleName,
  unfilledFields,
} from "../src/engine/styles/styleLibrary";
import os from "node:os";

let passed = 0;
let failed = 0;
function check(name: string, cond: boolean): void {
  if (cond) {
    passed++;
    console.log(`  ✅ ${name}`);
  } else {
    failed++;
    console.log(`  ❌ ${name}`);
  }
}

function readJson(rel: string): unknown {
  return JSON.parse(fs.readFileSync(path.join(__dirname, rel), "utf8"));
}

console.log("Engine tests\n");

// 1. Valid basic manifest passes.
const valid = readJson("manifests/valid-basic.json");
const validReport = validateManifest(valid);
check("valid-basic has no errors", validReport.ok && validReport.errors.length === 0);

// 2. Invalid manifest surfaces the expected error codes.
const invalid = readJson("manifests/invalid-missing-assets.json");
const invalidReport = validateManifest(invalid);
const codes = new Set(invalidReport.errors.map((e) => e.code));
check("invalid manifest is rejected", !invalidReport.ok);
check("detects unknown-background", codes.has("unknown-background"));
check("detects unknown-character", codes.has("unknown-character"));
check("detects unknown-motion", codes.has("unknown-motion"));
check("detects unknown-prop", codes.has("unknown-prop"));
check("detects bad-timing", codes.has("bad-timing"));

// 3. The shipped sample project validates cleanly.
const sample = readJson("../projects/social-media-brain-test/manifest.json");
const sampleReport = validateManifest(sample);
check("sample project has no errors", sampleReport.ok);

// 4. Timeline math.
check("secondsToFrames(2, 30) === 60", secondsToFrames(2, 30) === 60);
if (validReport.manifest) {
  const plan = planSequences(validReport.manifest);
  check("valid-basic total duration is 240 frames", plan.totalDurationInFrames === 240);
  check("valid-basic has 2 scenes", plan.scenes.length === 2);
  check("first scene starts at frame 0 with 120 frames", plan.scenes[0].from === 0 && plan.scenes[0].durationInFrames === 120);
}

// 5. Audio plan respects file existence.
if (sampleReport.manifest) {
  const all = buildAudioPlan(sampleReport.manifest, { fileExists: () => true });
  check("audio plan includes voiceover when present", Boolean(all.voiceover));
  check("audio plan includes music when present", Boolean(all.music));
  check("audio plan includes sfx when present", all.sfx.length === 2);
  const none = buildAudioPlan(sampleReport.manifest, { fileExists: () => false });
  check("audio plan empty when files missing", !none.voiceover && !none.music && none.sfx.length === 0);
}

// 6. Shorts cutdown builder.
if (sampleReport.manifest) {
  const { manifest: short, window } = buildShortsManifest(sampleReport.manifest, 0, 5);
  check("shorts manifest is vertical 1080x1920", short.resolution.width === 1080 && short.resolution.height === 1920);
  check("shorts format is youtube_vertical", short.format === "youtube_vertical");
  check("shorts keeps the selected scene count", short.scenes.length === 6);
  check("shorts first scene re-times to 0", short.scenes[0].start === 0);
  check("shorts projectId is suffixed", short.projectId.endsWith("-short"));

  const mid = buildShortsManifest(sampleReport.manifest, 2, 4);
  check("shorts shifts a mid-range slice to 0", mid.manifest.scenes[0].start === 0);

  const [from, to] = autoShortsRange(sampleReport.manifest, 30);
  check("autoShortsRange starts at 0 and stays in range", from === 0 && to >= 0 && window.durationSeconds > 0);

  // --from without --to: window extends forward from the requested scene.
  const [f2, t2] = autoShortsRange(sampleReport.manifest, 30, 2);
  check("autoShortsRange honors a fromIdx start", f2 === 2 && t2 >= 2);
  const s2 = sampleReport.manifest.scenes;
  check(
    "fromIdx window stays within maxSeconds",
    s2[t2].end - s2[2].start <= 30 && (t2 === s2.length - 1 || s2[t2 + 1].end - s2[2].start > 30)
  );
  const lastIdx = s2.length - 1;
  const [f3, t3] = autoShortsRange(sampleReport.manifest, 30, 999);
  check("out-of-range fromIdx clamps to the last scene", f3 === lastIdx && t3 === lastIdx);
}

// 7. Captions: word timing + emphasis + SRT.
{
  const words = estimateWordTimings("Hello brave new world", 0, 120);
  check("word timing splits all words", words.length === 4);
  check("word timing has a small lead-in", words[0].startF >= 0 && words[0].startF <= 8);
  check("word timing ends at duration", words[words.length - 1].endF === 120);
  // pause-aware: a sentence-final word is held longer than a similar mid-line word
  const pw = estimateWordTimings("go stop. go on", 0, 240);
  check("pause-aware holds punctuated words longer", pw[1].endF - pw[1].startF > pw[0].endF - pw[0].startF);
  const emph = parseEmphasis("this is *very* BIG").filter((w) => w.emphasis).length;
  check("emphasis detects *word* and ALL-CAPS", emph === 2);
}

// 7c. Voiceover-first retiming (retimeToAudio + silence parsing).
{
  // Proportional, no silences: equal weights split evenly; last scene ends at dur+tail.
  const prop = retimeToAudio({ weights: [10, 10, 10], audioDuration: 30, tail: 0.1 });
  check("retime covers all scenes contiguously", prop[0].start === 0 && prop[0].end === prop[1].start && prop[1].end === prop[2].start);
  check("retime equal weights split evenly", prop[0].end === 10 && prop[1].end === 20);
  check("retime last scene holds the tail", prop[2].end === 30.1 && prop[2].snapped === false);

  // Weighting: a longer line gets a longer scene.
  const weighted = retimeToAudio({ weights: [30, 10], audioDuration: 40 });
  check("retime weights longer lines longer", weighted[0].end - weighted[0].start > weighted[1].end - weighted[1].start);

  // Snapping: a cut near a real pause snaps onto it (proportional cut = 10, pause at 10.4).
  const snapped = retimeToAudio({ weights: [10, 10], audioDuration: 20, silences: [3.1, 10.4, 17.0], snapWindow: 1.2 });
  check("retime snaps a cut to a nearby pause", snapped[0].end === 10.4 && snapped[0].snapped === true);

  // A pause outside the window is ignored (stays proportional).
  const noSnap = retimeToAudio({ weights: [10, 10], audioDuration: 20, silences: [15.0], snapWindow: 1.2 });
  check("retime ignores pauses outside the window", noSnap[0].end === 10 && noSnap[0].snapped === false);

  // Ordering guard: snapping never produces a scene shorter than minScene.
  const guarded = retimeToAudio({ weights: [10, 10, 10], audioDuration: 30, silences: [0.2, 0.3], minScene: 0.6, snapWindow: 2 });
  check("retime keeps min scene length under bad snaps", guarded.every((t) => t.end - t.start >= 0.6 - 1e-9));

  // Silence parsing from ffmpeg stderr.
  const times = parseSilenceStarts("x\n[silencedetect] silence_start: 1.115\ny silence_end: 1.5\n silence_start: 4.858\n");
  check("parseSilenceStarts extracts start times", times.length === 2 && times[0] === 1.115 && times[1] === 4.858);
}
// 7b. Caption contract: caption is optional (style-only); text is deprecated/ignored.
{
  const scene = {
    id: "scene_001",
    voiceover: "No caption block at all.",
    start: 0,
    end: 4,
    background: "abstract_explainer",
    characters: [{ id: "human" }],
  };
  const noCaption = {
    projectId: "cap-test",
    title: "Cap",
    fps: 30,
    resolution: { width: 1920, height: 1080 },
    scenes: [scene],
  };
  const r = validateManifest(noCaption);
  check("scene without caption validates", r.ok);
  check(
    "omitted caption defaults to hiw_default/bottom",
    r.manifest?.scenes[0].caption.style === "hiw_default" && r.manifest?.scenes[0].caption.position === "bottom"
  );

  const longLine = "word ".repeat(30).trim(); // 149 chars > 90 max
  const longScene = { ...scene, voiceover: longLine };
  const offReport = validateManifest({ ...noCaption, scenes: [longScene] });
  check(
    "no overflow warning while captions are off",
    offReport.warnings.every((w) => w.code !== "caption-overflow")
  );
  const onReport = validateManifest({ ...noCaption, style: { captions: true }, scenes: [longScene] });
  check(
    "overflow warning targets voiceover when captions are burned",
    onReport.warnings.some((w) => w.code === "caption-overflow")
  );
}

if (sampleReport.manifest) {
  const srt = buildSrt(sampleReport.manifest);
  check("srt contains cue timings", srt.includes(" --> "));
  check("srt cue count matches captioned scenes", srt.trim().split(/\n\n/).length === sampleReport.manifest.scenes.length);
}

// 8. Asset library (Pillar 4).
{
  check("every catalog id has metadata", metaCoverageGaps().length === 0);
  const r = searchAssets("person panics at phone", { limit: 6 });
  check("search returns ranked results", r.length > 0 && r[0].score >= r[r.length - 1].score);
  check("search surfaces a relevant asset", r.some((x) => ["phone", "panic", "scrollPhone"].includes(x.record.id)));
  const motions = searchAssets("celebrate win", { kind: "motion", limit: 3 });
  check("kind filter restricts to that kind", motions.every((x) => x.record.kind === "motion") && motions.some((x) => x.record.id === "celebrate"));
}
if (sampleReport.manifest) {
  const t = tallyManifest(sampleReport.manifest);
  check("usage tally counts a background", (t[usageKey("background", "cave")] ?? 0) >= 1);
  check("usage tally counts a character", (t[usageKey("character", "ancient_brain")] ?? 0) >= 1);
}

// 9. Scene templates (reuse engine).
{
  const templates = loadTemplates();
  check("scene templates are seeded", templates.length >= 4);
  const found = searchTemplates("brain panics emergency", templates);
  check("template search ranks the relevant one first", found.length > 0 && found[0].template.id === "brain-panic-emergency");
  check("nextSceneId increments correctly", nextSceneId(["scene_001", "scene_003"]) === "scene_004");

  if (sampleReport.manifest) {
    const extracted = extractTemplateScene(sampleReport.manifest.scenes[5]);
    check("extract drops content fields", !("id" in extracted) && !("start" in extracted) && !("voiceover" in extracted));
    check("extract keeps structural fields", typeof extracted.background === "string" && Array.isArray(extracted.characters));
  }

  const tpl = templates.find((x) => x.id === "human-celebrate-win");
  if (tpl) {
    const scene = buildSceneFromTemplate(tpl, { id: "scene_001", start: 0, end: 4, voiceover: "hi", captionText: "yay" });
    const m = { projectId: "tpl-test", title: "T", fps: 30, resolution: { width: 1920, height: 1080 }, scenes: [scene] };
    check("template instantiates into a valid manifest scene", validateManifest(m).ok);
  }
}

// 10. Style library (image-generated path only; the puppet style is code).
{
  const lib = listStyles();
  const stick = lib.find((s) => s.name === DEFAULT_STYLE);
  check("style library lists stick-hiw as approved", !!stick && stick.status === "approved");
  check("stick-hiw is listed first", lib.length > 0 && lib[0].name === DEFAULT_STYLE);
  const loaded = loadStyle(DEFAULT_STYLE);
  check("stick-hiw loads from styles/", loaded.source === "library" && loaded.style.styleName === "stick-hiw");

  check("resolveStyleName: default when nothing set", resolveStyleName(undefined, { style: {} }) === DEFAULT_STYLE);
  check("resolveStyleName: manifest style.imageStyle", resolveStyleName(undefined, { style: { imageStyle: "ink-wash" } }) === "ink-wash");
  check("resolveStyleName: --style wins", resolveStyleName("chalk", { style: { imageStyle: "ink-wash" } }) === "chalk");
  check("style names are kebab-case", isValidStyleName("ink-wash-2") && !isValidStyleName("Ink Wash") && !isValidStyleName("../x"));

  // Legacy fallback + fail-closed status in an isolated temp tree.
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "hiw-style-test-"));
  fs.mkdirSync(path.join(tmp, "stick-hiw"), { recursive: true });
  fs.writeFileSync(path.join(tmp, "stick-hiw", "style.json"), JSON.stringify({ styleName: "stick-hiw" }));
  const legacy = loadStyle(DEFAULT_STYLE, tmp);
  check("legacy stick-hiw/style.json fallback", legacy.source === "legacy" && legacy.status === "approved");
  check("unknown style is missing", loadStyle("nope", tmp).source === "missing");
  fs.mkdirSync(path.join(tmp, "styles", "nostatus"), { recursive: true });
  fs.writeFileSync(path.join(tmp, "styles", "nostatus", "style.json"), JSON.stringify({ styleName: "nostatus" }));
  check("library style without status is treated as draft", loadStyle("nostatus", tmp).status === "draft");
  const src = path.join(tmp, "styles", "nostatus", "source.md");
  appendSourceLog(src, "colours too bright", "2026-01-02");
  appendSourceLog(src, "lines too clean", "2026-01-03");
  const md = fs.readFileSync(src, "utf8");
  check(
    "source.md log gets dated lines",
    md.includes("## Log") && md.includes("- 2026-01-02 — colours too bright") && md.includes("- 2026-01-03 — lines too clean")
  );
  fs.rmSync(tmp, { recursive: true, force: true });

  check("placeholders are detected", unfilledFields({ stylePreamble: `${PLACEHOLDER} x`, colorPalette: "ok" }).join() === "stylePreamble");
  const corrected = applyCorrection({ colorPalette: "bright primaries." }, "colorPalette", "append", "Muted, desaturated");
  check("append correction adds a sentence", corrected.colorPalette === "bright primaries. Muted, desaturated");
  check("set correction replaces", applyCorrection({ colorPalette: "a" }, "colorPalette", "set", "b").colorPalette === "b");

  const a = parseCliArgs(["--allow-draft", "./m.json", "--style", "x"]);
  check("boolean flags don't swallow positionals", a.positional[0] === "./m.json" && a.flags.style === "x" && a.flags["allow-draft"] === true);

  const px = new Uint8Array([255, 255, 255, 255, 255, 255, 255, 255, 255, 0, 0, 0]);
  const pal = dominantColors(px, 2);
  check("dominantColors ranks by pixel share", pal[0].hex === "#ffffff" && pal[0].share === 75 && pal[1].hex === "#000000");

  const p = buildPrompt({ stylePreamble: "Ink.", negativePrompt: "no text", aspectRatio: "16:9" }, { id: "s", notes: "a cat" }, new Map());
  check("buildPrompt joins style + subject", p === "Ink. Scene: a cat. 16:9 aspect ratio. Avoid: no text.");
}

console.log(`\n${passed} passed, ${failed} failed.`);
process.exit(failed > 0 ? 1 : 0);
