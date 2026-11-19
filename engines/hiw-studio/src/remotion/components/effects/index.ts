/** Effect registry (architecture §11). Maps effect id -> overlay component. */
import type React from "react";
import type { EffectProps } from "../../../engine/assets/assetTypes";
import type { EffectId } from "../../../engine/assets/catalog";
import { SweatDrops } from "./SweatDrops";
import { SpeedLines } from "./SpeedLines";
import { AlarmFlash } from "./AlarmFlash";
import { PopEffect } from "./PopEffect";
import { ThoughtBubble } from "./ThoughtBubble";
import { MotionLines } from "./MotionLines";
import { GlowEffect } from "./GlowEffect";
import { FaceDetect } from "./FaceDetect";

export const EFFECTS: Record<EffectId, React.FC<EffectProps>> = {
  pop: PopEffect,
  sweatDrops: SweatDrops,
  speedLines: SpeedLines,
  glow: GlowEffect,
  alarmFlash: AlarmFlash,
  thoughtBubble: ThoughtBubble,
  motionLines: MotionLines,
  faceDetect: FaceDetect,
};

export { CameraRig } from "./CameraRig";
