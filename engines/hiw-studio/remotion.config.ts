/**
 * Remotion CLI configuration.
 *
 * This file is only read by the Remotion CLI (`remotion studio` / `remotion render`).
 * Programmatic rendering done through `src/engine/renderer/renderVideo.ts` configures
 * the bundler and renderer directly and does NOT depend on this file.
 *
 * See: https://www.remotion.dev/docs/config
 */
import { Config } from "@remotion/cli/config";

// Entry point for the Remotion studio / CLI render.
Config.setEntryPoint("src/remotion/index.ts");

// Draft-friendly defaults. The programmatic renderer overrides these per quality.
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);

// Serve the whole workspace as the public dir so that audio assets referenced by
// manifests (./projects/... and ./assets/...) are reachable from the browser via
// staticFile(). See src/engine/audio/audioUtils.ts.
// Guarded because older Remotion versions may not expose this setter.
const maybeSetPublicDir = (Config as unknown as {
  setPublicDir?: (dir: string) => void;
}).setPublicDir;
if (typeof maybeSetPublicDir === "function") {
  maybeSetPublicDir(".");
}
