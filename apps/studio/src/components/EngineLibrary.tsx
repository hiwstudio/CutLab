const engines = [
  {
    name: "Clipinn",
    purpose: "Pick self-contained spoken moments and download only those sections.",
    command: "scripts\\engine.ps1 clipinn run <YouTube URL> --style blur",
  },
  {
    name: "Viral Clip Engine",
    purpose: "Find moments, reframe them for vertical video, and add subtitles and hooks.",
    command: "scripts\\engine.ps1 viral --mode clip <video file>",
  },
  {
    name: "Recap Engine",
    purpose: "Build a narrated story recap from long-form footage.",
    command: "scripts\\engine.ps1 recap <video file>",
  },
  {
    name: "HIW Studio",
    purpose: "Create deterministic animated videos from scene manifests.",
    command: 'scripts\\engine.ps1 hiw create-project "Your video title"',
  },
];

export function EngineLibrary() {
  return (
    <section className="mt-8 rounded-2xl border border-zinc-800 bg-zinc-950/70 p-5" data-testid="engine-library">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold">Production engines</h2>
          <p className="mt-1 max-w-xl text-xs leading-5 text-zinc-400">
            Choose an engine for the job, then bring its video into CutLab to keep editing.
          </p>
        </div>
        <span className="text-[10px] text-zinc-500">Run from the repository folder</span>
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {engines.map((engine) => (
          <details key={engine.name} className="group rounded-xl border border-zinc-800 bg-zinc-900/70 p-3">
            <summary className="cursor-pointer list-none text-sm font-semibold text-zinc-200 marker:hidden">
              <span className="flex items-center justify-between gap-2">
                {engine.name}
                <span aria-hidden="true" className="text-zinc-500 transition group-open:rotate-45">＋</span>
              </span>
            </summary>
            <p className="mt-2 text-xs leading-5 text-zinc-400">{engine.purpose}</p>
            <code className="mt-2 block overflow-x-auto rounded bg-black/40 p-2 text-[10px] text-amber-200">{engine.command}</code>
          </details>
        ))}
      </div>
      <p className="mt-3 text-[11px] leading-5 text-zinc-500">
        MixFix MIX/FIX projects can be opened directly above. Other engines save their own output; upload the rendered file in the CutLab Media Library.
      </p>
    </section>
  );
}
