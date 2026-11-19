/**
 * `hiw thumbnail <manifest> [--scene N] [--title "..."]` — render a branded
 * 1280x720 thumbnail PNG to output/thumbnails/<projectId>.png.
 */
import { renderThumbnail } from "../../engine/renderer/renderThumbnail";

export async function thumbnailCommand(
  manifestPath: string,
  opts: { scene?: string; title?: string; accent?: string; crop?: boolean; vertical?: boolean; out?: string }
): Promise<number> {
  const sceneIndex = opts.scene !== undefined ? Number.parseInt(opts.scene, 10) : 0;
  if (Number.isNaN(sceneIndex)) {
    console.error(`  ❌ --scene must be a number (0-based scene index).`);
    return 1;
  }

  console.log(`Rendering thumbnail for ${manifestPath}...`);
  try {
    const result = await renderThumbnail({
      manifestPath,
      sceneIndex,
      headline: opts.title,
      accent: opts.accent,
      crop: opts.crop,
      vertical: opts.vertical,
      outputPath: opts.out,
    });
    console.log(`✅ Thumbnail saved: ${result.outputPath} (scene #${result.sceneIndex}).`);
    return 0;
  } catch (err) {
    console.error(`❌ Thumbnail failed: ${(err as Error).message}`);
    return 1;
  }
}
