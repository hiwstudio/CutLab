"use client";

import { useEffect, useMemo, useRef, useState } from "react";

export interface Command {
  id: string;
  label: string;
  hint?: string;      // keyboard hint shown right-aligned
  group: string;
  disabled?: boolean;
  run: () => void;
}

/** ⌘K / Ctrl+K command palette (Linear-style shell affordance). Pure keyboard:
 * arrows + Enter, Esc closes. Filter is simple substring over label+group. */
export function CommandPalette({ commands }: { commands: Command[] }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
        setQuery("");
        setIndex(0);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = q
      ? commands.filter((c) =>
          `${c.group} ${c.label}`.toLowerCase().includes(q))
      : commands;
    return list.slice(0, 12);
  }, [commands, query]);

  useEffect(() => {
    if (index >= filtered.length) setIndex(Math.max(0, filtered.length - 1));
  }, [filtered.length, index]);

  if (!open) return null;

  const runAt = (i: number) => {
    const cmd = filtered[i];
    if (cmd && !cmd.disabled) {
      setOpen(false);
      cmd.run();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 pt-[18vh]"
      onClick={() => setOpen(false)}
      data-testid="command-palette"
    >
      <div
        className="w-[520px] overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--elevated)] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          data-testid="palette-input"
          className="w-full border-b border-[var(--border)] bg-transparent px-4 py-3 text-sm text-[var(--foreground)] outline-none placeholder:text-[var(--muted)]"
          placeholder="Type a command…"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIndex(0);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setIndex((i) => Math.min(filtered.length - 1, i + 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setIndex((i) => Math.max(0, i - 1));
            } else if (e.key === "Enter") {
              e.preventDefault();
              runAt(index);
            }
          }}
          aria-label="Command"
        />
        <ul className="max-h-80 overflow-y-auto py-1" role="listbox">
          {filtered.length === 0 && (
            <li className="px-4 py-3 text-xs text-[var(--muted)]">No matching commands</li>
          )}
          {filtered.map((c, i) => (
            <li key={c.id} role="option" aria-selected={i === index}>
              <button
                data-testid={`palette-cmd-${c.id}`}
                className={`flex w-full items-center gap-2 px-4 py-2 text-left text-[13px] ${
                  i === index ? "bg-[var(--accent-soft)]" : ""
                } ${c.disabled ? "opacity-40" : "hover:bg-[var(--accent-soft)]"}`}
                disabled={c.disabled}
                onMouseEnter={() => setIndex(i)}
                onClick={() => runAt(i)}
              >
                <span className="text-[10px] uppercase tracking-wide text-[var(--muted)]">
                  {c.group}
                </span>
                <span className="flex-1 text-[var(--foreground)]">{c.label}</span>
                {c.hint && (
                  <kbd className="rounded border border-[var(--border)] bg-[var(--surface)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--muted)]">
                    {c.hint}
                  </kbd>
                )}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
