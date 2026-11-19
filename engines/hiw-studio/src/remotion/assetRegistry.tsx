/**
 * Asset registry (architecture §16). Single place that maps catalog ids to their
 * React components. Browser-side (imports components). The CLI/validator uses the
 * plain-data catalog instead (src/engine/assets/catalog.ts).
 */
import type React from "react";
import type {
  BackgroundProps,
  CharacterProps,
  EffectProps,
  PropProps,
} from "../engine/assets/assetTypes";
import {
  BACKGROUND_IDS,
  CHARACTER_IDS,
  EFFECT_IDS,
  MOTION_IDS,
  PROP_IDS,
  type BackgroundId,
  type CharacterId,
} from "../engine/assets/catalog";

import { Human } from "./components/characters/Human";
import { AncientBrain } from "./components/characters/AncientBrain";
import { Dog } from "./components/characters/Dog";
import { CaveBackground } from "./components/backgrounds/CaveBackground";
import { LivingRoomBackground } from "./components/backgrounds/LivingRoomBackground";
import { OfficeBackground } from "./components/backgrounds/OfficeBackground";
import { AbstractBackground } from "./components/backgrounds/AbstractBackground";
import { StreetBackground } from "./components/backgrounds/StreetBackground";
import { ParkBackground } from "./components/backgrounds/ParkBackground";
import { DinerBackground } from "./components/backgrounds/DinerBackground";
import { PROPS } from "./components/props";
import { EFFECTS } from "./components/effects";
import { MOTIONS } from "./components/motions";

export const CHARACTERS: Record<CharacterId, React.FC<CharacterProps>> = {
  human: Human,
  ancient_brain: AncientBrain,
  dog: Dog,
};

export const BACKGROUNDS: Record<BackgroundId, React.FC<BackgroundProps>> = {
  cave: CaveBackground,
  living_room: LivingRoomBackground,
  office: OfficeBackground,
  abstract_explainer: AbstractBackground,
  street: StreetBackground,
  park: ParkBackground,
  diner: DinerBackground,
};

export { PROPS, EFFECTS, MOTIONS };
export type { CharacterProps, BackgroundProps, PropProps, EffectProps };

/**
 * Dev-time guard: every id in the catalog must have a component, so the catalog
 * (used by validation) and the registry (used by rendering) cannot silently drift.
 * Throws with a clear message listing the gap.
 */
export function assertRegistryComplete(): void {
  const checks: Array<[string, readonly string[], Record<string, unknown>]> = [
    ["character", CHARACTER_IDS, CHARACTERS],
    ["background", BACKGROUND_IDS, BACKGROUNDS],
    ["prop", PROP_IDS, PROPS],
    ["effect", EFFECT_IDS, EFFECTS],
    ["motion", MOTION_IDS, MOTIONS],
  ];
  const missing: string[] = [];
  for (const [kind, ids, registry] of checks) {
    for (const id of ids) {
      if (!(id in registry)) missing.push(`${kind}:${id}`);
    }
  }
  if (missing.length > 0) {
    throw new Error(`Asset registry is missing components for: ${missing.join(", ")}`);
  }
}
