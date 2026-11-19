/** Prop registry (architecture §10). Maps prop id -> component. */
import type React from "react";
import type { PropProps } from "../../../engine/assets/assetTypes";
import type { PropId } from "../../../engine/assets/catalog";
import { Phone } from "./Phone";
import { NotificationBubble } from "./NotificationBubble";
import { MoneyStack } from "./MoneyStack";
import { Brain } from "./Brain";
import { SpeechBubble } from "./SpeechBubble";
import { Club } from "./Club";
import { Coin } from "./Coin";
import { Bill } from "./Bill";
import { Laptop } from "./Laptop";
import { WarningSign } from "./WarningSign";
import { Bone } from "./Bone";
import { VendingMachine } from "./VendingMachine";

export const PROPS: Record<PropId, React.FC<PropProps>> = {
  phone: Phone,
  notification_bubble: NotificationBubble,
  money_stack: MoneyStack,
  brain: Brain,
  speech_bubble: SpeechBubble,
  club: Club,
  coin: Coin,
  bill: Bill,
  laptop: Laptop,
  warning_sign: WarningSign,
  bone: Bone,
  vending_machine: VendingMachine,
};
