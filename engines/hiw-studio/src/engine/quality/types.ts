/**
 * Shared types + helpers for the validation / quality layer.
 * Pure (no fs / React).
 */
export type IssueSeverity = "error" | "warning";

export interface ValidationIssue {
  severity: IssueSeverity;
  code: string;
  message: string;
  /** Scene id the issue relates to, if any. */
  scene?: string;
}

export interface QualityOptions {
  /** Max recommended scene duration (s) before warning (architecture §7.4). */
  maxSceneSeconds: number;
  /** Min sensible scene duration (s) before warning. */
  minSceneSeconds: number;
  /** Max caption characters before warning about 2-line overflow (architecture §12). */
  maxCaptionChars: number;
}

export const QUALITY_DEFAULTS: QualityOptions = {
  maxSceneSeconds: 10,
  minSceneSeconds: 0.5,
  maxCaptionChars: 90,
};

/** Tiny Levenshtein distance, used for "did you mean" suggestions. */
export function levenshtein(a: string, b: string): number {
  const m = a.length;
  const n = b.length;
  const dp = Array.from({ length: m + 1 }, () => new Array<number>(n + 1).fill(0));
  for (let i = 0; i <= m; i++) dp[i][0] = i;
  for (let j = 0; j <= n; j++) dp[0][j] = j;
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      dp[i][j] = Math.min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost);
    }
  }
  return dp[m][n];
}

/** Returns ` Did you mean "x"?` when a close match exists, else "". */
export function suggest(value: string, list: readonly string[]): string {
  let best: string | undefined;
  let bestDist = Infinity;
  for (const candidate of list) {
    const d = levenshtein(value.toLowerCase(), candidate.toLowerCase());
    if (d < bestDist) {
      bestDist = d;
      best = candidate;
    }
  }
  return best && bestDist <= Math.max(2, Math.ceil(value.length / 3))
    ? ` Did you mean "${best}"?`
    : "";
}
