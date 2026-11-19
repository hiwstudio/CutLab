/**
 * `hiw validate <manifest>` (architecture §15).
 * Prints the ✅ / ⚠️ / ❌ report and returns a process exit code.
 */
import { loadManifest, makeFileExists } from "../../engine/manifest/loadManifest";
import { validateManifest, type ValidationReport } from "../../engine/manifest/validateManifest";

export function printReport(report: ValidationReport): void {
  const label = (scene?: string) => (scene ? `${scene}: ` : "");
  for (const e of report.errors) {
    console.log(`  ❌ ${label(e.scene)}${e.message}`);
  }
  for (const w of report.warnings) {
    console.log(`  ⚠️  ${label(w.scene)}${w.message}`);
  }
  if (report.ok && report.warnings.length === 0) {
    console.log("  ✅ Manifest valid.");
  }
  console.log(
    `\nSummary: ${report.errors.length} error(s), ${report.warnings.length} warning(s).`
  );
}

export async function validateCommand(manifestPath: string): Promise<number> {
  console.log(`Validating ${manifestPath}\n`);
  let raw: unknown;
  try {
    raw = loadManifest(manifestPath).raw;
  } catch (err) {
    console.error(`  ❌ ${(err as Error).message}`);
    return 1;
  }

  const report = validateManifest(raw, { fileExists: makeFileExists() });
  printReport(report);

  if (report.manifest) {
    const last = report.manifest.scenes[report.manifest.scenes.length - 1];
    const seconds = last ? last.end : 0;
    console.log(
      `Project "${report.manifest.projectId}" — ${report.manifest.scenes.length} scene(s), ~${seconds.toFixed(1)}s @ ${report.manifest.fps}fps, ${report.manifest.resolution.width}x${report.manifest.resolution.height}.`
    );
  }

  return report.ok ? 0 : 1;
}
