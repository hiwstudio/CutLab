"use client";

import { useEffect, useRef, useState } from "react";

export function DrawOverlay({ width, height, onClose, onSave }: {
  width: number;
  height: number;
  onClose: () => void;
  onSave: (file: File, durationMs: number) => Promise<void>;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);
  const history = useRef<ImageData[]>([]);
  const [color, setColor] = useState("#ffd166");
  const [size, setSize] = useState(12);
  const [opacity, setOpacity] = useState(1);
  const [eraser, setEraser] = useState(false);
  const [duration, setDuration] = useState(3);
  const [saving, setSaving] = useState(false);
  const [, setHistorySize] = useState(0);
  const scale = Math.min(1, 960 / width, 640 / height);
  const canvasWidth = Math.max(1, Math.round(width * scale));
  const canvasHeight = Math.max(1, Math.round(height * scale));

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.width = canvasWidth;
    canvas.height = canvasHeight;
    history.current = [];
    setHistorySize(0);
  }, [canvasWidth, canvasHeight]);

  const point = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    return [(event.clientX - rect.left) * canvas.width / rect.width,
      (event.clientY - rect.top) * canvas.height / rect.height] as const;
  };
  const begin = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext("2d")!;
    history.current.push(ctx.getImageData(0, 0, canvas.width, canvas.height));
    if (history.current.length > 20) history.current.shift();
    setHistorySize(history.current.length);
    drawing.current = true;
    canvas.setPointerCapture(event.pointerId);
    const [x, y] = point(event);
    ctx.beginPath();
    ctx.moveTo(x, y);
  };
  const move = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawing.current) return;
    const ctx = canvasRef.current!.getContext("2d")!;
    const [x, y] = point(event);
    ctx.globalCompositeOperation = eraser ? "destination-out" : "source-over";
    ctx.globalAlpha = opacity;
    ctx.strokeStyle = color;
    ctx.lineWidth = size;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.lineTo(x, y);
    ctx.stroke();
  };
  const end = () => { drawing.current = false; };
  const undo = () => {
    const previous = history.current.pop();
    const ctx = canvasRef.current?.getContext("2d");
    if (previous && ctx) ctx.putImageData(previous, 0, 0);
    setHistorySize(history.current.length);
  };
  const clear = () => {
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext("2d")!;
    history.current.push(ctx.getImageData(0, 0, canvas.width, canvas.height));
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    setHistorySize(history.current.length);
  };
  const save = async () => {
    const canvas = canvasRef.current!;
    setSaving(true);
    try {
      const blob = await new Promise<Blob>((resolve, reject) =>
        canvas.toBlob(value => value ? resolve(value) : reject(new Error("Drawing export failed")), "image/png"));
      const stamp = new Date().toISOString().replace(/[:.]/g, "-");
      await onSave(new File([blob], `drawing-${stamp}.png`, { type: "image/png" }), Math.round(duration * 1000));
    } finally {
      setSaving(false);
    }
  };

  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4" onClick={onClose}>
    <div className="flex max-h-[94vh] w-full max-w-5xl flex-col gap-3 rounded-lg border border-zinc-700 bg-zinc-950 p-4" onClick={event => event.stopPropagation()}>
      <div className="flex items-center justify-between"><div><h2 className="text-sm font-semibold text-zinc-100">Draw overlay</h2><p className="text-[10px] text-zinc-500">Transparent canvas · placed at the playhead</p></div><button className="text-xs text-zinc-400" onClick={onClose}>Close</button></div>
      <div className="flex flex-wrap items-end gap-3 text-xs text-zinc-400"><label>Colour<input aria-label="Drawing colour" type="color" value={color} onChange={e => setColor(e.target.value)} className="ml-2 h-7 w-10 align-middle" disabled={eraser} /></label><label>Brush<input aria-label="Brush size" type="range" min="2" max="60" value={size} onChange={e => setSize(Number(e.target.value))} className="ml-2 align-middle" /> <span>{size}px</span></label><label>Opacity<input aria-label="Brush opacity" type="range" min="0.1" max="1" step="0.1" value={opacity} onChange={e => setOpacity(Number(e.target.value))} className="ml-2 align-middle" /></label><button type="button" aria-pressed={eraser} className={`rounded px-2 py-1 ${eraser ? "bg-amber-500 text-zinc-950" : "bg-zinc-800"}`} onClick={() => setEraser(value => !value)}>Eraser</button><button type="button" className="rounded bg-zinc-800 px-2 py-1" onClick={undo}>Undo</button><button type="button" className="rounded bg-zinc-800 px-2 py-1" onClick={clear}>Clear</button><label>Duration<input aria-label="Drawing duration" type="number" min="0.2" max="3600" step="0.1" value={duration} onChange={e => setDuration(Number(e.target.value))} className="ml-2 w-16 rounded border border-zinc-700 bg-zinc-900 px-2 py-1" />s</label></div>
      <canvas ref={canvasRef} aria-label="Drawing canvas" className="min-h-0 w-full flex-1 touch-none rounded border border-zinc-700" style={{ aspectRatio: `${canvasWidth}/${canvasHeight}`, backgroundColor: "#151515", backgroundImage: "linear-gradient(45deg,#222 25%,transparent 25%),linear-gradient(-45deg,#222 25%,transparent 25%),linear-gradient(45deg,transparent 75%,#222 75%),linear-gradient(-45deg,transparent 75%,#222 75%)", backgroundSize: "20px 20px", backgroundPosition: "0 0,0 10px,10px -10px,-10px 0" }} onPointerDown={begin} onPointerMove={move} onPointerUp={end} onPointerCancel={end} />
      <button disabled={saving} className="rounded bg-amber-500 px-3 py-2 text-xs font-semibold text-zinc-950 hover:bg-amber-400 disabled:opacity-50" onClick={() => void save()}>{saving ? "Adding drawing…" : "Add drawing to timeline"}</button>
    </div>
  </div>;
}
