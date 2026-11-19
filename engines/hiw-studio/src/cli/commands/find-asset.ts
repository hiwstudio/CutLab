/**
 * `hiw find-asset "<query>" [--kind k] [--limit n]` (V2 — Pillar 4).
 * Ranked "reuse before create" suggestions from the asset library.
 */
import { searchAssets, META_KINDS, type MetaKind } from "../../engine/assets/assetLibrary";

export async function findAssetCommand(
  query: string,
  opts: { kind?: string; limit?: string }
): Promise<number> {
  const kindFilter = opts.kind as MetaKind | undefined;
  if (kindFilter && !META_KINDS.includes(kindFilter)) {
    console.error(`  ❌ Unknown kind "${opts.kind}". Valid: ${META_KINDS.join(", ")}`);
    return 1;
  }
  const limit = opts.limit ? Math.max(1, Number.parseInt(opts.limit, 10) || 8) : 8;

  const results = searchAssets(query, { kind: kindFilter, limit });
  if (results.length === 0) {
    console.log(`No existing assets match "${query}". This may be a genuine gap — consider adding a new asset (see docs/ASSET_LIBRARY_RULES.md).`);
    return 0;
  }

  console.log(`Reuse suggestions for "${query}":\n`);
  for (const { record, score } of results) {
    console.log(`  [${record.kind}] ${record.id.padEnd(20)} (score ${score})  ${record.tags.slice(0, 6).join(", ")}`);
  }
  return 0;
}
