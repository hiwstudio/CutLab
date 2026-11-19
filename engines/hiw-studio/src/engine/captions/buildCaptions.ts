/**
 * Caption text shaping (architecture §12). Pure helpers.
 *
 * MVP captions are scene-level. This balances a caption into at most two lines so it
 * reads well on mobile, without measuring fonts (a simple word-count split).
 */

/** Split a caption into at most `maxLines` roughly balanced lines. */
export function balanceCaption(text: string, maxLines = 2): string[] {
  const clean = text.trim().replace(/\s+/g, " ");
  if (clean.length === 0) return [];
  const words = clean.split(" ");
  if (words.length === 1 || maxLines <= 1) return [clean];

  // Target a near-even character split across lines.
  const target = clean.length / maxLines;
  const lines: string[] = [];
  let current = "";

  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (
      current &&
      candidate.length > target &&
      lines.length < maxLines - 1
    ) {
      lines.push(current);
      current = word;
    } else {
      current = candidate;
    }
  }
  if (current) lines.push(current);
  return lines;
}
