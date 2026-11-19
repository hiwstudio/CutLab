/**
 * Audio track component (architecture §13).
 *
 * Renders the voiceover, optional looped music bed, and timed sound effects from a
 * pre-resolved AudioPlan (built by the CLI so only existing files are referenced).
 */
import React from "react";
import { Audio, Sequence, staticFile } from "remotion";
import type { AudioPlan } from "./audioUtils";

export const AudioTrack: React.FC<{ plan?: AudioPlan }> = ({ plan }) => {
  if (!plan) return null;

  return (
    <>
      {plan.voiceover ? (
        <Audio src={staticFile(plan.voiceover.src)} volume={plan.voiceover.volume} />
      ) : null}

      {plan.music ? (
        <Audio src={staticFile(plan.music.src)} volume={plan.music.volume} loop />
      ) : null}

      {plan.sfx.map((clip, i) => (
        <Sequence key={`${clip.src}-${i}`} from={clip.fromFrame}>
          <Audio src={staticFile(clip.src)} volume={clip.volume} />
        </Sequence>
      ))}
    </>
  );
};
