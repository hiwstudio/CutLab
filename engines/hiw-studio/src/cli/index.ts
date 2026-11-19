#!/usr/bin/env node
/**
 * HIW Studio CLI (architecture §4.6 / §27).
 *
 * Commands:
 *   hiw validate <manifest>
 *   hiw render <manifest> [--quality draft|final]
 *   hiw preview <manifest>
 *   hiw create-project "<name>"
 *
 * Run via package scripts, e.g.:
 *   npm run validate -- ./projects/social-media-brain-test/manifest.json
 */
import { Command } from "commander";
import { validateCommand } from "./commands/validate";
import { renderCommand } from "./commands/render";
import { previewCommand } from "./commands/preview";
import { createProjectCommand } from "./commands/create-project";
import { thumbnailCommand } from "./commands/thumbnail";
import { shortsCommand } from "./commands/shorts";
import { captionsCommand } from "./commands/captions";
import { voiceoverCommand } from "./commands/voiceover";
import { inspectAssetsCommand } from "./commands/inspect-assets";
import { findAssetCommand } from "./commands/find-asset";
import { saveTemplateCommand } from "./commands/save-template";
import { templatesCommand } from "./commands/templates";
import { addSceneCommand } from "./commands/add-scene";
import { retimeCommand } from "./commands/retime";

const program = new Command();

program
  .name("hiw")
  .description("HIW Studio — Human Is Weird Animation Engine")
  .version("0.1.0");

program
  .command("validate")
  .argument("<manifest>", "path to a manifest.json")
  .description("Validate a scene manifest")
  .action(async (manifest: string) => {
    process.exitCode = await validateCommand(manifest);
  });

program
  .command("render")
  .argument("<manifest>", "path to a manifest.json")
  .option("-q, --quality <quality>", "draft | final", "draft")
  .description("Render a video from a manifest")
  .action(async (manifest: string, opts: { quality: string }) => {
    process.exitCode = await renderCommand(manifest, opts.quality);
  });

program
  .command("preview")
  .argument("<manifest>", "path to a manifest.json")
  .description("Open Remotion Studio for a manifest")
  .action(async (manifest: string) => {
    process.exitCode = await previewCommand(manifest);
  });

program
  .command("create-project")
  .argument("<name>", 'project name, e.g. "Why Humans Procrastinate"')
  .description("Scaffold a new project folder")
  .action(async (name: string) => {
    process.exitCode = await createProjectCommand(name);
  });

program
  .command("thumbnail")
  .argument("<manifest>", "path to a manifest.json")
  .option("-s, --scene <index>", "0-based scene index for background + characters", "0")
  .option("-t, --title <text>", "punch headline (defaults to manifest title; keep it short)")
  .option("-a, --accent <word>", "word within the headline to color red")
  .option("-c, --crop", "crop in on the subject (head/upper-body fills the frame)")
  .option("--vertical", "render a vertical 1080x1920 thumbnail (for Shorts)")
  .option("-o, --out <path>", "output PNG path")
  .description("Render a thumbnail PNG (full-bleed scene + punch headline)")
  .action(async (manifest: string, opts: { scene?: string; title?: string; accent?: string; crop?: boolean; vertical?: boolean; out?: string }) => {
    process.exitCode = await thumbnailCommand(manifest, opts);
  });

program
  .command("shorts")
  .argument("<manifest>", "path to a manifest.json")
  .option("-f, --from <n>", "first scene number (1-based, inclusive)")
  .option("-t, --to <n>", "last scene number (1-based, inclusive)")
  .option("-m, --max <seconds>", "max length when auto-selecting (default 30)")
  .option("-q, --quality <quality>", "draft | final", "final")
  .description("Render a vertical 1080x1920 Shorts cutdown")
  .action(async (manifest: string, opts: { from?: string; to?: string; max?: string; quality?: string }) => {
    process.exitCode = await shortsCommand(manifest, opts);
  });

program
  .command("captions")
  .argument("<manifest>", "path to a manifest.json")
  .option("-o, --out <path>", "output .srt path")
  .description("Export an SRT subtitle file")
  .action(async (manifest: string, opts: { out?: string }) => {
    process.exitCode = await captionsCommand(manifest, opts);
  });

program
  .command("voiceover")
  .argument("<manifest>", "path to a manifest.json")
  .description("Build a voiceover package (voice config + spoken script) next to the manifest")
  .action(async (manifest: string) => {
    process.exitCode = await voiceoverCommand(manifest);
  });

program
  .command("inspect-assets")
  .option("-k, --kind <kind>", "filter by kind (character, variant, background, motion, prop, effect, camera, captionStyle, expression)")
  .option("-u, --unused", "show only assets never used")
  .option("-j, --json", "output JSON")
  .description("List the asset library with tags + usage counts")
  .action(async (opts: { kind?: string; unused?: boolean; json?: boolean }) => {
    process.exitCode = await inspectAssetsCommand(opts);
  });

program
  .command("find-asset")
  .argument("<query>", 'what you need, e.g. "person panics at phone"')
  .option("-k, --kind <kind>", "restrict to one kind")
  .option("-l, --limit <n>", "max results (default 8)")
  .description("Suggest existing assets to reuse for a described need")
  .action(async (query: string, opts: { kind?: string; limit?: string }) => {
    process.exitCode = await findAssetCommand(query, opts);
  });

program
  .command("templates")
  .option("-f, --find <query>", "search templates by need")
  .option("-t, --tag <tag>", "filter by tag")
  .description("List or search the scene-template library")
  .action(async (opts: { find?: string; tag?: string }) => {
    process.exitCode = await templatesCommand(opts);
  });

program
  .command("save-template")
  .argument("<manifest>", "path to a manifest.json")
  .requiredOption("-s, --scene <id>", 'scene id (e.g. "scene_006") or 0-based index to capture')
  .requiredOption("-n, --name <name>", "template name")
  .option("-i, --id <slug>", "template id (defaults to a slug of the name)")
  .option("-t, --tags <a,b,c>", "comma-separated tags")
  .option("-d, --desc <text>", "description")
  .description("Save a scene as a reusable template")
  .action(async (manifest: string, opts: { scene?: string; name?: string; id?: string; tags?: string; desc?: string }) => {
    process.exitCode = await saveTemplateCommand(manifest, opts);
  });

program
  .command("add-scene")
  .argument("<manifest>", "path to a manifest.json")
  .requiredOption("-t, --template <id>", "template id to insert (see `templates`)")
  .option("--start <seconds>", "scene start (default: after the last scene)")
  .option("--duration <seconds>", "scene duration (default 4)")
  .option("--voiceover <text>", "voiceover line for the new scene")
  .option("--caption <text>", "caption text for the new scene")
  .description("Append a template's scene to a manifest")
  .action(async (manifest: string, opts: { template?: string; start?: string; duration?: string; voiceover?: string; caption?: string }) => {
    process.exitCode = await addSceneCommand(manifest, opts);
  });

program
  .command("retime")
  .argument("<manifest>", "path to a manifest.json")
  .option("--no-snap", "pure proportional timing (skip snapping cuts to pauses)")
  .option("-n, --noise <dB>", "silence threshold in dB (default -30)")
  .option("-m, --min-silence <seconds>", "minimum pause to count as a cut point (default 0.35)")
  .option("-w, --window <seconds>", "max distance a cut may snap to a pause (default 1.2)")
  .option("-t, --tail <seconds>", "extra hold on the final scene (default 0.1)")
  .description("Time scenes to the finished voiceover (voiceover-first), snapping cuts to natural pauses")
  .action(async (manifest: string, opts: { snap?: boolean; noise?: string; minSilence?: string; window?: string; tail?: string }) => {
    process.exitCode = await retimeCommand(manifest, opts);
  });

program.parseAsync(process.argv).catch((err) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exitCode = 1;
});
