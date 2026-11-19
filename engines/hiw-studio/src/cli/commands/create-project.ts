/**
 * `hiw create-project "<name>"` — scaffolds a new project folder with a starter
 * script, voiceover notes, manifest, and settings (architecture §6/§27).
 */
import fs from "fs-extra";
import path from "node:path";
import { writeVoiceoverPackage } from "../../engine/voiceover/writeVoiceoverPackage";

export function slugify(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60) || "untitled-project";
}

export async function createProjectCommand(name: string): Promise<number> {
  const slug = slugify(name);
  const dir = path.resolve(process.cwd(), "projects", slug);

  if (fs.existsSync(dir)) {
    console.error(`  ❌ Project already exists: projects/${slug}`);
    return 1;
  }
  fs.ensureDirSync(dir);

  const voPath = `./projects/${slug}/voiceover.mp3`;
  const manifest = {
    projectId: slug,
    title: name,
    brand: "Human Is Weird",
    format: "youtube_landscape",
    fps: 30,
    resolution: { width: 1920, height: 1080 },
    audio: { voiceoverPath: voPath, musicVolume: 0.12 },
    // Per-episode voice tailoring; overrides the channel defaults in ./voice.json. Fill
    // deliveryNotes (and optionally style/pace/etc.) to match this video's tone, then run
    // `npm run voiceover -- <manifest>` to build voiceover-package.md.
    voice: { deliveryNotes: "" },
    style: { captionStyle: "hiw_default", visualStyle: "simple_2d_puppet", colorPalette: "hiw_default" },
    scenes: [
      {
        id: "scene_001",
        voiceover: "Replace this with your first line of narration.",
        start: 0,
        end: 4,
        background: "abstract_explainer",
        characters: [{ id: "human", variant: "modern", position: "center", expression: "happy", motion: "idle" }],
        caption: { text: "Replace this caption.", style: "hiw_default" },
        notes: "Opening scene.",
      },
      {
        id: "scene_002",
        voiceover: "Add as many scenes as you need.",
        start: 4,
        end: 8,
        background: "living_room",
        characters: [{ id: "ancient_brain", position: "center", expression: "confused", motion: "lookAround" }],
        caption: { text: "Add as many scenes as you need.", style: "hiw_default" },
      },
    ],
  };

  fs.writeFileSync(
    path.join(dir, "script.md"),
    `# ${name}\n\n_Topic / angle:_ TODO\n\n## Script\n\nWrite the narration here. Each paragraph roughly maps to one scene.\n`
  );
  fs.writeFileSync(
    path.join(dir, "voiceover.txt"),
    `${name}\n\nPaste the final voiceover transcript here, then record/generate it as voiceover.mp3 in this folder.\n`
  );
  fs.writeFileSync(path.join(dir, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
  fs.writeFileSync(
    path.join(dir, "notes.md"),
    `# Notes — ${name}\n\n- [ ] Write script\n- [ ] Tailor the \`voice\` block (deliveryNotes/tone) to this episode\n- [ ] Refresh the voiceover package after writing the script:  npm run voiceover -- ./projects/${slug}/manifest.json\n- [ ] Generate the voiceover from voiceover-package.md and save it as voiceover.mp3\n- [ ] Adjust scene timings to match audio\n- [ ] Validate and render a draft\n`
  );
  fs.writeFileSync(path.join(dir, "direction.md"), directionTemplate(name));
  fs.writeFileSync(path.join(dir, "social-captions.md"), socialCaptionsTemplate(name));
  fs.writeFileSync(path.join(dir, "thumbnail-prompt.md"), thumbnailPromptTemplate(name));

  // Scaffold the voiceover package from the channel voice.json + the starter manifest,
  // so every project is born with it (refresh it via `npm run voiceover` after scripting).
  writeVoiceoverPackage(path.join("projects", slug, "manifest.json"));

  console.log(`✅ Created projects/${slug}`);
  console.log(
    "   script.md, voiceover.txt, manifest.json, voiceover-package.md, notes.md, direction.md, social-captions.md, thumbnail-prompt.md"
  );
  console.log(`\nNext:`);
  console.log(`   (voiceover-package.md is ready; re-run \`npm run voiceover\` to refresh it after you write the script)`);
  console.log(`   npm run validate -- ./projects/${slug}/manifest.json`);
  console.log(`   npm run render:draft -- ./projects/${slug}/manifest.json`);
  return 0;
}

/**
 * Starter copy for the Director's shot list (`docs/HIW_DIRECTOR.md`). The Director step
 * runs between the finished script and the manifest: spec each scene from STORY NEED
 * (not existing ids), then resolve every visual reuse → extend → build. New characters/
 * settings/props are expected — repetition is the thing we fight. The id-must-exist rule
 * still holds, so the Build list below is what gets added to catalog.ts before authoring.
 */
export function directionTemplate(name: string): string {
  return `# Direction — ${name}

Story-first shot list. Ask "what does this scene need to show?" — if it doesn't exist in
\`src/engine/assets/catalog.ts\` yet, add it to the Build list and build it before the
manifest. Push for variety: no two consecutive scenes should share setting + cast +
staging + camera. Full reference: \`docs/HIW_DIRECTOR.md\`.

## Shot list (one block per scene)

### scene_001
- **Beat:** mirror / weird / loop / reveal / collision / reframe / button
- **Read-in-one-second:** TODO — the single visual idea the viewer instantly gets.
- **Setting:** TODO — choose freshly; don't default to a stock background.
- **Cast:** TODO — who's on screen + what they feel/do (new character if the story calls).
- **Staging:** TODO — composition, focal point, foreground/background.
- **Camera:** TODO — move + why.
- **Accent:** TODO — prop/effect that punctuates the beat.
- **Text:** TODO — none, or \`scene.texts\`: speech (a character's exact words) / reaction /
  label / emphasis. Contextual only — videos are caption-free; a speech bubble is never empty.
- **NEW?:** TODO — flag anything not in the catalog today.

### scene_002
- **Beat:**
- **Read-in-one-second:**
- **Setting:**
- **Cast:**
- **Staging:**
- **Camera:**
- **Accent:**
- **Text:**
- **NEW?:**

_(add a block per scene)_

## Build list — new assets this video needs

Resolve each required visual reuse → extend → build. List only what must be BUILT (new
catalog id + component). Build the smallest set of reusable pieces that covers the script.

| kind (character/background/prop/motion/effect/variant/expression) | proposed id | one-line brief | reuse / extend / build |
| --- | --- | --- | --- |
| TODO | TODO | TODO | build |

Each new asset: add to \`catalog.ts\` + \`assetMeta.ts\`, build the component, register it
(\`assertRegistryComplete()\` enforces parity), \`npm run typecheck && npm test\`. Conform to
\`docs/STYLE_GUIDE.md\` and the \`HIW_PALETTE\`/fonts in \`src/remotion/theme.ts\` — free in
subject, never in style.
`;
}

/**
 * Starter copy for the cross-platform social captions that ship with every project.
 * One section per platform we post to (YouTube, TikTok, X, Facebook, Instagram), each
 * pre-noted with that platform's quirks so the caption is written to fit, not retrofitted.
 */
export function socialCaptionsTemplate(name: string): string {
  return `# Social captions — ${name}

Platform-specific copy for this video. Keep the HIW voice: funny, curious, a little
sarcastic. Fill each section before posting; hashtags are suggestions, prune to fit.

## YouTube
<!-- Title ≤ 100 chars. Description: hook in the first 1–2 lines (shown before "more"),
     then context + CTA. -->
**Title:** ${name}

**Description:**
TODO — open with the hook, then 2–3 lines of context. End with a question to drive comments.

Subscribe for more — Ancient brain. Modern problems.

**Hashtags:** #HumanIsWeird #psychology #shorts

## TikTok
<!-- ≤ 2200 chars but punchy wins. Lead with the hook; 3–5 tight hashtags. -->
TODO — one-line hook that stops the scroll.

#HumanIsWeird #psychology #fyp

## X (Twitter)
<!-- ≤ 280 chars including the link. One sharp thought. -->
TODO — the single most shareable line from the script.

#HumanIsWeird

## Facebook
<!-- Conversational, slightly longer than X. A question lands well here. -->
TODO — hook + a relatable line that invites people to tag a friend.

#HumanIsWeird

## Instagram
<!-- Reels caption. Hook first line (rest is hidden behind "more"). Hashtags at the end. -->
TODO — hook first line, then a beat of context.

.
.
#HumanIsWeird #psychology #reels #animation
`;
}

/**
 * Starter copy for the YouTube thumbnail image-generation prompt that ships with every
 * project. The style, title rules, and negative prompt are fixed HIW house style (reuse
 * as-is); only the SCENE / BACKGROUND / supporting-element blocks are per-episode TODOs.
 * House rules baked in: two characters max, two supporting elements max, two-color title
 * (white + yellow), uncluttered background — the things that keep a thumbnail readable
 * at phone size.
 */
export function thumbnailPromptTemplate(name: string): string {
  return `# Thumbnail prompt — ${name}

Image-generation prompt for this video's YouTube thumbnail. House rules: TWO characters
max, at most TWO supporting elements, a two-color title (white + yellow), and one simple
uncluttered background. Fill the SCENE / BACKGROUND / SUPPORTING blocks for this episode;
the style, title, and negative-prompt blocks are HIW house style — reuse as-is.

## Main prompt
A vibrant 2D cartoon YouTube thumbnail, bold flat-color illustration style with thick
clean outlines and soft cel shading. 16:9, 1920x1080.

SCENE: TODO — the 1–2 main characters, their expressions and poses, and ONE optional
focal symbol between them (e.g. a curious human on the LEFT reacting to <subject> on the
RIGHT). Two characters max; give them a clean white outer stroke so they pop.

BACKGROUND: TODO — one simple setting, softly blurred with depth-of-field so the
characters pop. Warm light, gentle edge vignette. Keep it uncluttered.

SUPPORTING ELEMENTS (pick at most TWO, small, in the upper corners):
- TODO — e.g. a small white speech bubble with a relevant icon.
- TODO — e.g. a small symbol that signals the "ancient brain / instinct" angle.

LIGHTING & FINISH: Bright, high-saturation, high-contrast, energetic. Subtle radiating
light rays behind the title text. Professional high-CTR thumbnail polish, optimized for
small mobile display.

## Title text (add in an editor for clean type if the generator garbles it)
Top third, heavy bold rounded sans-serif, ALL CAPS, thick black outline. Two colors only:
WHITE + YELLOW (put the single most important word in yellow). No quotation marks, no red
banner, exact spelling.
  Suggested: "${name.toUpperCase()}"

## Negative prompt
no extra text, no misspellings, no quotation marks, no random letters, no multiple hearts,
no cluttered background, no floating question marks, no extra speech bubbles, no watermark,
no signature, characters not blurry, no third character, no busy patterns

## Note
Image generators are unreliable with text. If the title garbles (stray quotes, wrong
letters), generate the ART ONLY — drop the title from the prompt, keep the light rays —
and add the title in Canva/Photoshop where you control the font and the white+yellow
split exactly.
`;
}
