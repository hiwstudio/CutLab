"use client";

import { useEffect, useRef } from "react";
import { mediaUrl } from "@/lib/api";

const peaksCache = new Map<string, Promise<number[]>>();

function loadPeaks(projectId: string, assetId: string): Promise<number[]> {
  const key = `${projectId}/${assetId}`;
  if (!peaksCache.has(key)) {
    peaksCache.set(
      key,
      fetch(mediaUrl(projectId, `understanding/${assetId}.peaks.json`))
        .then((r) => (r.ok ? r.json() : { buckets: [] }))
        .then((d) => (d.buckets ?? []) as number[])
        .catch(() => []),
    );
  }
  return peaksCache.get(key)!;
}

/** Waveform strip drawn from the ingest peaks JSON, windowed to the clip's
 * source range. */
export function WaveStrip({
  projectId,
  assetId,
  inFrac,
  outFrac,
}: {
  projectId: string;
  assetId: string;
  inFrac: number; // in_ms / asset duration
  outFrac: number;
}) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    let alive = true;
    loadPeaks(projectId, assetId).then((peaks) => {
      const canvas = ref.current;
      if (!alive || !canvas || peaks.length === 0) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const { width, height } = canvas;
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "rgba(255,255,255,0.35)";
      const start = Math.floor(inFrac * peaks.length);
      const end = Math.max(start + 1, Math.ceil(outFrac * peaks.length));
      const window = peaks.slice(start, end);
      for (let x = 0; x < width; x++) {
        const v = window[Math.floor((x / width) * window.length)] ?? 0;
        const h = Math.max(1, v * height);
        ctx.fillRect(x, (height - h) / 2, 1, h);
      }
    });
    return () => {
      alive = false;
    };
  }, [projectId, assetId, inFrac, outFrac]);

  return <canvas ref={ref} width={200} height={24} className="h-full w-full" />;
}
