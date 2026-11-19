/**
 * Word-level caption timing (V2 — Pillar 3). Pure, dependency-free.
 *
 * Produces per-word start/end times by distributing a caption across its scene
 * duration weighted by syllable count — a reliable estimate that drives the animated
 * karaoke captions. The renderer can also accept a *supplied* WordTiming[] (e.g. from
 * real forced alignment via Whisper/ElevenLabs), which overrides this estimate with
 * zero changes elsewhere.
 */

export interface WordTiming {
  text: string;
  /** Inclusive start frame (scene-relative). */
  startF: number;
  /** Exclusive end frame (scene-relative). */
  endF: number;
  emphasis: boolean;
}

/** Rough syllable count for English-ish words (vowel groups, silent-e adjust). */
export function syllables(word: string): number {
  const w = word.toLowerCase().replace(/[^a-z]/g, "");
  if (w.length === 0) return 1;
  const groups = w.match(/[aeiouy]+/g);
  let n = groups ? groups.length : 1;
  if (w.length > 2 && w.endsWith("e") && !/[aeiouy]e$/.test(w)) n -= 1;
  return Math.max(1, n);
}

export interface ParsedWord {
  text: string;
  emphasis: boolean;
}

/** Split caption text into words, marking emphasis via *word* markup or ALL-CAPS. */
export function parseEmphasis(text: string): ParsedWord[] {
  return text
    .trim()
    .split(/\s+/)
    .filter((t) => t.length > 0)
    .map((token) => {
      const starred = /^\*.+\*$/.test(token);
      const clean = token.replace(/^\*|\*$/g, "");
      const letters = clean.replace(/[^A-Za-z]/g, "");
      const allCaps = letters.length > 1 && letters === letters.toUpperCase();
      return { text: clean, emphasis: starred || allCaps };
    });
}

/**
 * Extra "hold" weight from trailing punctuation, approximating the natural pause a
 * speaker takes at commas (short) and sentence ends (longer). Quotes/brackets after
 * the punctuation are ignored.
 */
function pauseWeight(text: string): number {
  const last = text.trim().replace(/["')\]]+$/, "").slice(-1);
  if (".!?…".includes(last)) return 1.2;
  if (",;:—-".includes(last)) return 0.6;
  return 0;
}

/**
 * Distribute words across [fromFrame, toFrame) weighted by syllables + punctuation
 * pauses, with a small lead-in before the first word (speech rarely starts exactly on
 * the cut). Pass `fps` for a time-based lead-in; otherwise it's derived from the span.
 * Returns at least one entry when text is non-empty; the last word ends at toFrame.
 */
export function estimateWordTimings(
  text: string,
  fromFrame: number,
  toFrame: number,
  fps?: number
): WordTiming[] {
  const words = parseEmphasis(text);
  if (words.length === 0) return [];

  const span = Math.max(1, toFrame - fromFrame);
  const lead = fps
    ? Math.min(Math.round(fps * 0.08), Math.round(span * 0.12))
    : Math.min(Math.round(span * 0.04), 4);
  const usable = Math.max(1, span - lead);

  const weights = words.map((w) => syllables(w.text) + pauseWeight(w.text));
  const total = weights.reduce((a, b) => a + b, 0) || 1;

  const out: WordTiming[] = [];
  let acc = 0;
  for (let i = 0; i < words.length; i++) {
    const start = fromFrame + lead + Math.round((acc / total) * usable);
    acc += weights[i];
    const end = fromFrame + lead + Math.round((acc / total) * usable);
    out.push({ text: words[i].text, emphasis: words[i].emphasis, startF: start, endF: Math.max(start + 1, end) });
  }
  return out;
}
