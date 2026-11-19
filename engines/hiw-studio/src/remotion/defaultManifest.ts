/**
 * A minimal, self-contained manifest used as Remotion defaultProps so the studio /
 * composition list opens even when no project props are supplied. Render and preview
 * always pass a real manifest via inputProps, overriding this.
 */
import { ManifestSchema, type Manifest, type ManifestInput } from "../engine/manifest/schema";
import { normalizeManifest } from "../engine/manifest/normalizeManifest";

const DEFAULT_INPUT: ManifestInput = {
  projectId: "default-preview",
  title: "HIW Studio Preview",
  fps: 30,
  resolution: { width: 1920, height: 1080 },
  scenes: [
    {
      id: "scene_001",
      voiceover: "This is HIW Studio.",
      start: 0,
      end: 3,
      background: "abstract_explainer",
      characters: [
        { id: "human", variant: "modern", position: "left", expression: "happy", motion: "idle" },
        { id: "ancient_brain", position: "right", expression: "neutral", motion: "lookAround" },
      ],
      caption: { text: "This is HIW Studio.", style: "hiw_default" },
    },
    {
      id: "scene_002",
      voiceover: "Render videos from a manifest.",
      start: 3,
      end: 6,
      background: "office",
      characters: [{ id: "human", variant: "office", position: "center", expression: "confused", motion: "shrug" }],
      props: [{ id: "laptop", position: "right" }],
      caption: { text: "Render videos from a manifest.", style: "hiw_default" },
    },
  ],
};

export const DEFAULT_MANIFEST: Manifest = normalizeManifest(ManifestSchema.parse(DEFAULT_INPUT));
