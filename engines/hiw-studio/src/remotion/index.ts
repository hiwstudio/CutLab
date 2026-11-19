/**
 * Remotion entry point. Registered via remotion.config.ts setEntryPoint and used by
 * the programmatic bundler in src/engine/renderer/renderVideo.ts.
 */
import { registerRoot } from "remotion";
import { Root } from "./Root";

registerRoot(Root);
