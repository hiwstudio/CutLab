/**
 * Top-level composition (architecture §14). Turns a manifest into a sequence of
 * scenes on the Remotion timeline and mixes in the audio track.
 *
 * Receives an already-normalized manifest via props (normalization happens in
 * Root's calculateMetadata) plus a pre-resolved audio plan.
 */
import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import type { Manifest } from "../engine/manifest/schema";
import type { AudioPlan } from "../engine/audio/audioUtils";
import { planSequences } from "../engine/timeline/sequencePlanner";
import { AudioTrack } from "../engine/audio/AudioTrack";
import { Scene } from "./Scene";
import { HIW_PALETTE as C } from "./theme";

export type HIWCompositionProps = {
  manifest: Manifest;
  audioPlan?: AudioPlan;
};

export const HIWComposition: React.FC<HIWCompositionProps> = ({ manifest, audioPlan }) => {
  const plan = planSequences(manifest);
  const showCaptions = manifest.style?.captions ?? false;

  return (
    <AbsoluteFill style={{ backgroundColor: C.studio }}>
      {plan.scenes.map((range) => (
        <Sequence
          key={range.scene.id}
          from={range.from}
          durationInFrames={range.durationInFrames}
          name={range.scene.id}
        >
          <Scene
            scene={range.scene}
            durationInFrames={range.durationInFrames}
            showCaptions={showCaptions}
          />
        </Sequence>
      ))}

      <AudioTrack plan={audioPlan} />
    </AbsoluteFill>
  );
};
