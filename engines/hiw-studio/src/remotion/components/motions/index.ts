/**
 * Motion registry (architecture §8.5/§8.6). Maps motion id -> MotionFn.
 * A motion is a pure function of frame returning CSS transforms.
 */
import type { MotionFn } from "../../../engine/assets/assetTypes";
import type { MotionId } from "../../../engine/assets/catalog";
import { idle } from "./idle";
import { walk } from "./walk";
import { panic } from "./panic";
import { scrollPhone } from "./scrollPhone";
import { point } from "./point";
import { shrug } from "./shrug";
import { facepalm } from "./facepalm";
import { celebrate } from "./celebrate";
import { lookAround } from "./lookAround";
import { lightbulbIdea } from "./lightbulbIdea";
import { wave } from "./wave";

export const MOTIONS: Record<MotionId, MotionFn> = {
  idle,
  walk,
  panic,
  scrollPhone,
  point,
  shrug,
  facepalm,
  celebrate,
  lookAround,
  lightbulbIdea,
  wave,
};

export function getMotion(id: MotionId): MotionFn {
  return MOTIONS[id] ?? idle;
}

export {
  idle,
  walk,
  panic,
  scrollPhone,
  point,
  shrug,
  facepalm,
  celebrate,
  lookAround,
  lightbulbIdea,
  wave,
};
