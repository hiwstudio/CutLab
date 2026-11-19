/**
 * `hiw render <manifest> --quality draft|final` (architecture §23).
 */
import { loadManifest, makeFileExists } from "../../engine/manifest/loadManifest";
import { validateManifest } from "../../engine/manifest/validateManifest";
import { renderVideo } from "../../engine/renderer/renderVideo";
import { prepareProjectFromManifest } from "../../engine/renderer/prepareRender";
import { isQuality, type Quality } from "../../engine/renderer/renderConfig";
import { printReport } from "./validate";

export async function renderCommand(manifestPath: string, qualityArg: string): Promise<number> {
  const quality: Quality = isQuality(qualityArg) ? qualityArg : "draft";
  if (!isQuality(qualityArg)) {
    console.warn(`Unknown quality "${qualityArg}"; defaulting to "draft".`);
  }

  // Pre-validate so the user sees warnings and we abort cleanly on errors.
  let raw: unknown;
  try {
    raw = loadManifest(manifestPath).raw;
  } catch (err) {
    console.error(`  ❌ ${(err as Error).message}`);
    return 1;
  }
  const report = validateManifest(raw, { fileExists: makeFileExists() });
  printReport(report);
  if (!report.ok) {
    console.error("\nRefusing to render: fix the errors above first.");
    return 1;
  }

  console.log(`\nRendering "${report.manifest?.projectId}" at ${quality} quality...`);
  let lastPct = -1;
  try {
    const result = await renderVideo({
      manifestPath,
      quality,
      // Reuse the manifest validated above instead of loading + validating again.
      prepared: report.manifest ? prepareProjectFromManifest(report.manifest) : undefined,
      onProgress: (p) => {
        const pct = Math.floor(p * 100);
        if (pct !== lastPct && pct % 5 === 0) {
          lastPct = pct;
          process.stdout.write(`\r  rendering ${pct}%   `);
        }
      },
    });
    process.stdout.write("\r  rendering 100%   \n");
    console.log(`\n✅ Done.`);
    console.log(`   Output: ${result.outputPath}`);
    console.log(
      `   ${result.width}x${result.height} @ ${result.fps}fps, ${result.durationInFrames} frames (~${(result.durationInFrames / result.fps).toFixed(1)}s).`
    );
    return 0;
  } catch (err) {
    console.error(`\n❌ Render failed: ${(err as Error).message}`);
    return 1;
  }
}
