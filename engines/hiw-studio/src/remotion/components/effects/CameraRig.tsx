/**
 * Camera rig (architecture §11). Wraps scene content and applies a camera move
 * (zoom / shake / pan) based on the manifest camera type + intensity.
 * Rendered inside a scene <Sequence>, so `frame` is scene-relative.
 */
import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import type { Camera } from "../../../engine/manifest/schema";
import { resolveCameraType } from "../../../engine/assets/resolveAsset";

export const CameraRig: React.FC<{
  camera?: Camera;
  frame: number;
  fps: number;
  durationInFrames: number;
  children: React.ReactNode;
}> = ({ camera, frame, fps, durationInFrames, children }) => {
  const type = resolveCameraType(camera?.type);
  const intensity = camera?.intensity ?? 0.2;
  const dur = Math.max(1, durationInFrames);

  let transform = "none";
  switch (type) {
    case "slowZoomIn": {
      const s = interpolate(frame, [0, dur], [1, 1 + 0.18 * intensity], { extrapolateRight: "clamp" });
      transform = `scale(${s})`;
      break;
    }
    case "slowZoomOut": {
      const s = interpolate(frame, [0, dur], [1 + 0.18 * intensity, 1], { extrapolateRight: "clamp" });
      transform = `scale(${s})`;
      break;
    }
    case "quickZoom": {
      const s = interpolate(frame, [0, Math.max(1, fps * 0.3)], [1, 1 + 0.25 * intensity], { extrapolateRight: "clamp" });
      transform = `scale(${s})`;
      break;
    }
    case "shake": {
      const x = Math.sin(frame * 1.5) * 12 * intensity;
      const y = Math.cos(frame * 2.1) * 9 * intensity;
      transform = `translate(${x.toFixed(2)}px, ${y.toFixed(2)}px) scale(${1 + 0.03 * intensity})`;
      break;
    }
    case "panLeft": {
      const x = interpolate(frame, [0, dur], [60 * intensity, -60 * intensity], { extrapolateRight: "clamp" });
      transform = `translateX(${x.toFixed(2)}px) scale(${1 + 0.06 * intensity})`;
      break;
    }
    case "panRight": {
      const x = interpolate(frame, [0, dur], [-60 * intensity, 60 * intensity], { extrapolateRight: "clamp" });
      transform = `translateX(${x.toFixed(2)}px) scale(${1 + 0.06 * intensity})`;
      break;
    }
    default:
      transform = "none";
  }

  return (
    <AbsoluteFill style={{ transform, transformOrigin: "center center" }}>
      {children}
    </AbsoluteFill>
  );
};
