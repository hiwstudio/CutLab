/**
 * `hiw templates [--find "<query>"] [--tag <tag>]` (V2 — reuse engine).
 * Lists or searches the saved scene-template library.
 */
import { loadTemplates, searchTemplates, type TemplateRecord } from "../../engine/templates/templateStore";

function line(t: TemplateRecord): string {
  const used = t.usageCount > 0 ? `${t.usageCount}× ` : "·  ";
  return `  ${used}${t.id.padEnd(24)} ${t.name}\n        tags: ${t.tags.join(", ")}`;
}

export async function templatesCommand(opts: { find?: string; tag?: string }): Promise<number> {
  let templates = loadTemplates();
  if (opts.tag) {
    const tag = opts.tag.toLowerCase();
    templates = templates.filter((t) => t.tags.map((x) => x.toLowerCase()).includes(tag));
  }

  if (opts.find) {
    const scored = searchTemplates(opts.find, templates);
    if (scored.length === 0) {
      console.log(`No templates match "${opts.find}".`);
      return 0;
    }
    console.log(`Scene templates for "${opts.find}":\n`);
    for (const { template, score } of scored) console.log(`${line(template)}  (score ${score})`);
    return 0;
  }

  if (templates.length === 0) {
    console.log("No templates yet. Capture one with:  npm run save-template -- <manifest> --scene <id> --name \"...\"");
    return 0;
  }
  console.log(`${templates.length} scene template(s):\n`);
  for (const t of templates.sort((a, b) => b.usageCount - a.usageCount || a.id.localeCompare(b.id))) {
    console.log(line(t));
  }
  return 0;
}
