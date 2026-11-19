import React from "react";
import { Composition } from "remotion";
import { Scene015, Scene020, Scene022, Scene024, Scene032, Scene035, Scene041 } from "./Scenes";

const FPS = 30;
// Durations come straight from the Timing Map scene slots, rounded to frames.
// Keeping them exact means the insert needs no stretching at assemble time.
const F = (ms: number) => Math.round((ms / 1000) * FPS);

const SCENES = [
  { id: "scene-020", ms: 13000, C: Scene020 },
  { id: "scene-015", ms: 8000, C: Scene015 },
  { id: "scene-022", ms: 9080, C: Scene022 },
  { id: "scene-024", ms: 3920, C: Scene024 },
  { id: "scene-032", ms: 11760, C: Scene032 },
  { id: "scene-035", ms: 10280, C: Scene035 },
  { id: "scene-041", ms: 10040, C: Scene041 },
];

export const RemotionRoot: React.FC = () => (
  <>
    {SCENES.map((s) => (
      <Composition
        key={s.id}
        id={s.id}
        component={s.C}
        durationInFrames={F(s.ms)}
        fps={FPS}
        width={1920}
        height={1080}
      />
    ))}
  </>
);
