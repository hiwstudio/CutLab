/**
 * `hiw preview <manifest>` — launches Remotion Studio with the manifest loaded as
 * input props so you can scrub scenes interactively (architecture §4.6).
 */
import { spawn } from "node:child_process";
import path from "node:path";
import fs from "fs-extra";
import { ENTRY_POINT, prepareProject } from "../../engine/renderer/prepareRender";

export async function previewCommand(manifestPath: string): Promise<number> {
  let prepared;
  try {
    prepared = prepareProject(manifestPath, { strict: false });
  } catch (err) {
    console.error(`  ❌ ${(err as Error).message}`);
    return 1;
  }

  const propsFile = path.resolve(process.cwd(), ".hiw", `preview-props-${prepared.manifest.projectId}.json`);
  fs.ensureDirSync(path.dirname(propsFile));
  fs.writeJsonSync(propsFile, prepared.inputProps, { spaces: 2 });

  console.log(`Opening Remotion Studio for "${prepared.manifest.title}"...`);
  console.log("(Close the studio / press Ctrl+C to stop.)\n");

  const args = [
    "remotion",
    "studio",
    ENTRY_POINT,
    `--props=${propsFile}`,
    `--public-dir=${prepared.publicDir}`,
  ];

  return new Promise<number>((resolve) => {
    const child = spawn("npx", args, { stdio: "inherit", shell: true });
    child.on("exit", (code) => resolve(code ?? 0));
    child.on("error", (err) => {
      console.error(`Failed to launch Remotion Studio: ${err.message}`);
      resolve(1);
    });
  });
}
