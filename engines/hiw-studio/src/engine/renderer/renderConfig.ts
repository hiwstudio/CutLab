/**
 * Render quality presets (architecture §23). Draft = fast/low quality, Final = high.
 */
export type Quality = "draft" | "final";

export interface RenderQualityConfig {
  /** H.264 constant rate factor (lower = higher quality / bigger file). */
  crf: number;
  /** JPEG frame quality for the headless capture (1-100). */
  jpegQuality: number;
  /** Output scale multiplier (0.5 = half resolution, faster). */
  scale: number;
}

export const RENDER_PRESETS: Record<Quality, RenderQualityConfig> = {
  draft: { crf: 28, jpegQuality: 80, scale: 0.5 },
  final: { crf: 18, jpegQuality: 95, scale: 1 },
};

export function isQuality(value: string): value is Quality {
  return value === "draft" || value === "final";
}
