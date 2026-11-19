/**
 * `hiw save-template <manifest> --scene <id|index> --name "..."` (V2 — reuse engine).
 * Captures a scene's reusable composition as a template in assets/templates/.
 */
import { loadManifest } from "../../engine/manifest/loadManifest";
import { validateManifest } from "../../engine/manifest/validateManifest";
import { extractTemplateScene, saveTemplate, type TemplateRecord } from "../../engine/templates/templateStore";
import { slugify } from "./create-project";

export async function saveTemplateCommand(
  manifestPath: string,
  opts: { scene?: string; name?: string; id?: string; tags?: string; desc?: string }
): Promise<number> {
  if (!opts.name) {
    console.error("  ❌ --name is required.");
    return 1;
  }
  if (!opts.scene) {
    console.error('  ❌ --scene is required (a scene id like "scene_006" or a 0-based index).');
    return 1;
  }

  let raw: unknown;
  try {
    raw = loadManifest(manifestPath).raw;
  } catch (err) {
    console.error(`  ❌ ${(err as Error).message}`);
    return 1;
  }
  const report = validateManifest(raw);
  if (!report.manifest) {
    console.error("  ❌ Manifest could not be parsed.");
    return 1;
  }

  const scenes = report.manifest.scenes;
  let scene = scenes.find((s) => s.id === opts.scene);
  if (!scene && /^\d+$/.test(opts.scene)) scene = scenes[Number.parseInt(opts.scene, 10)];
  if (!scene) {
    console.error(`  ❌ Scene "${opts.scene}" not found. Available: ${scenes.map((s) => s.id).join(", ")}`);
    return 1;
  }

  const id = slugify(opts.id ?? opts.name);
  const tags = opts.tags ? opts.tags.split(",").map((t) => t.trim().toLowerCase()).filter(Boolean) : [];
  const record: TemplateRecord = {
    id,
    name: opts.name,
    description: opts.desc ?? "",
    tags,
    usageCount: 0,
    scene: extractTemplateScene(scene),
  };

  const file = saveTemplate(record);
  console.log(`✅ Saved template "${id}" (from ${scene.id}) → ${file}`);
  console.log(`   Reuse it with:  npm run add-scene -- ./projects/<id>/manifest.json --template ${id}`);
  return 0;
}
