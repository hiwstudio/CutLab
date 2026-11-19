/**
 * `hiw shorts <manifest> [--from N] [--to M] [--quality]` — render a vertical
 * 1080x1920 Shorts cutdown of a scene range to output/shorts/<id>_short.mp4.
 * Scene numbers are 1-based and inclusive.
 */
import { renderShorts } from "../../engine/renderer/renderShorts";
import { isQuality, type Quality } from "../../engine/renderer/renderConfig";

export async function shortsCommand(
  manifestPath: string,
  opts: { from?: string; to?: string; quality?: string; max?: string }
): Promise<number> {
  const quality: Quality = opts.quality && isQuality(opts.quality) ? opts.quality : "final";

  const parse1Based = (v: string | undefined): number | undefined => {
    if (v === undefined) return undefined;
    const n = Number.parseInt(v, 10);
    return Number.isNaN(n) ? undefined : n - 1; // 1-based -> 0-based
  };
  const fromIndex = parse1Based(opts.from);
  const toIndex = parse1Based(opts.to);
  const maxSeconds = opts.max ? Number.parseInt(opts.max, 10) : undefined;

  console.log(`Rendering Shorts cutdown for ${manifestPath} (vertical 1080x1920, ${quality})...`);
  let lastPct = -1;
  try {
    const result = await renderShorts({
      manifestPath,
      fromIndex,
      toIndex,
      maxSeconds,
      quality,
      onProgress: (p) => {
        const pct = Math.floor(p * 100);
        if (pct !== lastPct && pct % 5 === 0) {
          lastPct = pct;
          process.stdout.write(`\r  rendering ${pct}%   `);
        }
      },
    });
    process.stdout.write("\r  rendering 100%   \n");
    console.log(`\n✅ Short saved: ${result.outputPath}`);
    console.log(
      `   scenes ${result.fromIndex + 1}–${result.toIndex + 1}, ${result.width}x${result.height} @ ${result.fps}fps, ~${(result.durationInFrames / result.fps).toFixed(1)}s.`
    );
    if (!result.voiceoverTrimmed) {
      console.log("   (no trimmed voiceover — rendered with music only)");
    }
    return 0;
  } catch (err) {
    console.error(`\n❌ Shorts render failed: ${(err as Error).message}`);
    return 1;
  }
}
