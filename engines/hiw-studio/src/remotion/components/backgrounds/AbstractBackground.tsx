/**
 * Abstract explainer background (architecture §9).
 *
 * V2.1: the clean off-white studio — the channel's default explainer stage. Plain,
 * professional, character-first. Just two barely-there brand-tinted glows so it isn't
 * dead flat; the puppets and captions carry the frame.
 */
import React from "react";
import type { BackgroundProps } from "../../../engine/assets/assetTypes";
import { StudioBase } from "./StudioBase";

export const AbstractBackground: React.FC<BackgroundProps> = () => (
  <StudioBase>
    <circle cx={1300} cy={210} r={170} fill="#ffd24d" opacity={0.06} />
    <circle cx={250} cy={560} r={200} fill="#5b6cf0" opacity={0.05} />
  </StudioBase>
);
