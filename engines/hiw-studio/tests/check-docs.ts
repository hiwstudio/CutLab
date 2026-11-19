/**
 * Doc-drift check: every catalog id must appear (backtick-quoted) in
 * docs/MANIFEST_SCHEMA.md. Run with: npx tsx tests/check-docs.ts
 */
import fs from "node:fs";
import {
  BACKGROUND_IDS,
  CAMERA_TYPES,
  CAPTION_STYLES,
  CHARACTER_IDS,
  CHARACTER_VARIANTS,
  EFFECT_IDS,
  EXPRESSIONS,
  MOTION_IDS,
  POSITION_PRESETS,
  PROP_IDS,
} from "../src/engine/assets/catalog";

const doc = fs.readFileSync("docs/MANIFEST_SCHEMA.md", "utf8");
const lists: Array<[string, readonly string[]]> = [
  ["backgrounds", BACKGROUND_IDS],
  ["characters", CHARACTER_IDS],
  ["variants", CHARACTER_VARIANTS],
  ["expressions", EXPRESSIONS],
  ["motions", MOTION_IDS],
  ["props", PROP_IDS],
  ["camera", CAMERA_TYPES],
  ["effects", EFFECT_IDS],
  ["captionStyles", CAPTION_STYLES],
  ["positions", POSITION_PRESETS],
];

let missing = 0;
for (const [kind, ids] of lists) {
  for (const id of ids) {
    if (!doc.includes(`\`${id}\``)) {
      console.log(`MISSING ${kind}:${id}`);
      missing++;
    }
  }
}
console.log(missing === 0 ? "OK: every catalog id appears in MANIFEST_SCHEMA.md" : `${missing} id(s) missing`);
process.exit(missing > 0 ? 1 : 0);
