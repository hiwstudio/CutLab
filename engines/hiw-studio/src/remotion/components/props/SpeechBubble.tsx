/**
 * Speech bubble prop (architecture §10). With `text` it shows the words a character is
 * saying (wrapped via foreignObject); without it, the decorative "…" bubble.
 *
 * For most dialogue prefer a `scene.texts` element of kind "speech" — it auto-sizes,
 * animates in, and anchors above the speaker. This prop stays for the simple/decorative
 * case (and so a bubble is never forced to be empty when text IS supplied).
 */
import React from "react";
import type { PropProps } from "../../../engine/assets/assetTypes";
import { HIW_PALETTE as C } from "../../theme";
import { BRAND_FONT } from "../../fonts";

export const SpeechBubble: React.FC<PropProps> = ({ text }) => (
  <svg viewBox="0 0 100 100" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" style={{ overflow: "visible" }}>
    <g stroke={C.outline} strokeWidth={4} strokeLinejoin="round">
      <path d="M16,18 L84,18 Q92,18 92,26 L92,60 Q92,68 84,68 L44,68 L28,84 L30,68 L16,68 Q8,68 8,60 L8,26 Q8,18 16,18 Z" fill={C.white} />
    </g>
    {text && text.trim() ? (
      <foreignObject x={10} y={20} width={80} height={44}>
        <div
          // @ts-expect-error xmlns is valid on a div inside foreignObject
          xmlns="http://www.w3.org/1999/xhtml"
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            textAlign: "center",
            fontFamily: `'${BRAND_FONT}', 'Segoe UI', sans-serif`,
            fontWeight: 800,
            fontSize: 13,
            lineHeight: 1.02,
            color: C.ink,
            overflow: "hidden",
          }}
        >
          {text}
        </div>
      </foreignObject>
    ) : (
      <g>
        <circle cx={36} cy={43} r={4.5} fill={C.outline} />
        <circle cx={50} cy={43} r={4.5} fill={C.outline} />
        <circle cx={64} cy={43} r={4.5} fill={C.outline} />
      </g>
    )}
  </svg>
);
