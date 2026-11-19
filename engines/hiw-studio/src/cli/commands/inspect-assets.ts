/**
 * `hiw inspect-assets [--kind k] [--unused] [--json]` (V2 — Pillar 4).
 * Lists the asset library with tags and usage counts; flags unused assets.
 */
import { allAssets, assetsByKind, META_KINDS, metaCoverageGaps, type MetaKind } from "../../engine/assets/assetLibrary";
import { loadUsage, usageKey } from "../../engine/assets/usageStore";

export async function inspectAssetsCommand(opts: { kind?: string; unused?: boolean; json?: boolean }): Promise<number> {
  const usage = loadUsage();
  const kindFilter = opts.kind as MetaKind | undefined;
  if (kindFilter && !META_KINDS.includes(kindFilter)) {
    console.error(`  ❌ Unknown kind "${opts.kind}". Valid: ${META_KINDS.join(", ")}`);
    return 1;
  }

  const records = (kindFilter ? assetsByKind(kindFilter) : allAssets())
    .map((r) => ({ ...r, uses: usage[usageKey(r.kind, r.id)] ?? 0 }))
    .filter((r) => (opts.unused ? r.uses === 0 : true));

  if (opts.json) {
    console.log(JSON.stringify(records, null, 2));
    return 0;
  }

  const kinds = kindFilter ? [kindFilter] : META_KINDS;
  let total = 0;
  let unusedCount = 0;
  let totalUses = 0;

  for (const kind of kinds) {
    const inKind = records.filter((r) => r.kind === kind).sort((a, b) => b.uses - a.uses || a.id.localeCompare(b.id));
    if (inKind.length === 0) continue;
    console.log(`\n${kind.toUpperCase()} (${inKind.length})`);
    for (const r of inKind) {
      total += 1;
      totalUses += r.uses;
      if (r.uses === 0) unusedCount += 1;
      const used = r.uses === 0 ? "·  " : `${r.uses}× `;
      console.log(`  ${used}${r.id.padEnd(20)} ${r.tags.slice(0, 5).join(", ")}`);
    }
  }

  const gaps = metaCoverageGaps();
  console.log(`\n${total} asset(s), ${totalUses} total use(s), ${unusedCount} never used.`);
  if (gaps.length > 0) {
    console.log(`⚠️  ${gaps.length} catalog id(s) missing metadata: ${gaps.map((g) => `${g.kind}:${g.id}`).join(", ")}`);
  }
  return 0;
}
