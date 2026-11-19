"""Recap job (kind='recap') — P5.

Stages (checkpointed under {project}/recap/{asset}/, resume-safe like the
owner's recap-engine which caches every stage):
  outline — map-reduce the transcript into a story outline (LLM)
  script  — original narration beats sized to the target (LLM)
  tts     — Piper voiceover per beat, loudness-normalized (EBU R128)
  match   — beat -> scene assignment (time prior + dialogue overlap) + coverage
  propose — EDL ops plan applied in PROPOSE mode (+ Telegram gate if configured)

LLM backend: the same pluggable stack as the director. The manual backend
writes `<step>.prompt.txt` into the stage dir and polls for `<step>.answer.txt`
    (cancellable) — the same file hand-off as the bundled Recap Engine, so a crash or restart
resumes exactly where it left off.

Input: {project_id, asset_id, target_minutes, project_dir}.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from .. import config
from ..director import backends
from ..edl.engine import Engine, Rejected
from ..engines import recap
from ..gates import telegram
from ..understanding.schema import Understanding
from ..util.ffprobe import probe
from ..util.ffrun import run_ffmpeg
from .queue import JobContext

PIPER_VOICE = os.environ.get(
    "CUTLAB_PIPER_VOICE",
    str(config.DATA_DIR / "voices" / "en_US-lessac-medium.onnx"),
)
PIPER_HELP = (
    "Local TTS needs Piper + a voice model: pip install piper-tts, download a "
    "voice (.onnx + .onnx.json) from https://huggingface.co/rhasspy/piper-voices, "
    "then set CUTLAB_PIPER_VOICE to the .onnx path."
)
ANSWER_POLL_S = 2.0
ANSWER_TIMEOUT_S = float(os.environ.get("CUTLAB_MANUAL_LLM_TIMEOUT_S", "86400"))


def _llm(ctx: JobContext, workdir: Path, step: str, system: str, prompt: str) -> str:
    """One LLM call via the configured backend. Manual backend = file hand-off:
    write the prompt, poll for the answer (cancellable), resume on restart."""
    backend = backends.make_backend()
    if not getattr(backend, "manual", False):
        return backend.complete(system, prompt)

    answer_file = workdir / f"{step}.answer.txt"
    prompt_file = workdir / f"{step}.prompt.txt"
    if not answer_file.exists():
        prompt_file.write_text(system + "\n\n---\n\n" + prompt, encoding="utf-8")
    deadline = time.monotonic() + ANSWER_TIMEOUT_S
    while not answer_file.exists() or answer_file.stat().st_size == 0:
        ctx.check_cancelled()
        if time.monotonic() > deadline:
            raise TimeoutError(
                f"manual LLM answer not provided: drop the reply into {answer_file}"
            )
        time.sleep(ANSWER_POLL_S)
    return answer_file.read_text(encoding="utf-8")


def _parse_json(raw: str) -> dict | list:
    ops, note = None, None
    # Reuse the director's fence/prose-tolerant extraction for arbitrary JSON.
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    import re

    m = re.search(r"```(?:json)?\s*([\[{].*?[\]}])\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
    end = max(text.rfind("}"), text.rfind("]"))
    if 0 <= start < end:
        return json.loads(text[start : end + 1])
    raise ValueError("LLM reply is not parseable JSON")


def _piper_cmd() -> list[str]:
    exe = shutil.which("piper")
    if exe:
        return [exe]
    raise RuntimeError(f"Piper executable not found on PATH.\n{PIPER_HELP}")


def _synth(text: str, out_wav: Path) -> None:
    raw = out_wav.with_suffix(".raw.wav")
    cmd = _piper_cmd() + ["-m", PIPER_VOICE, "-f", str(raw)]
    proc = subprocess.run(cmd, input=text, text=True, capture_output=True, timeout=600)
    if proc.returncode != 0 or not raw.exists():
        raise RuntimeError(f"Piper failed: {(proc.stderr or '')[-500:]}")
    # Broadcast loudness + 48k stereo so narration mixes cleanly.
    run_ffmpeg(["-i", str(raw), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                "-ar", "48000", "-ac", "2", str(out_wav)])
    raw.unlink(missing_ok=True)


def recap_handler(ctx: JobContext) -> None:
    inp = ctx.input
    project_id: str = inp["project_id"]
    asset_id: str = inp["asset_id"]
    target_minutes: int = max(1, int(inp.get("target_minutes", 5)))
    project_dir = Path(inp["project_dir"])
    engine = Engine(ctx.queue.db, projects_dir=project_dir.parent)

    u_file = project_dir / "understanding" / f"{asset_id}.understanding.json"
    if not u_file.is_file():
        raise FileNotFoundError(f"asset {asset_id} has no understanding; analyze first")
    u = Understanding.model_validate_json(u_file.read_text(encoding="utf-8"))
    if not u.transcript or not u.transcript.segments:
        raise ValueError("recap needs a transcript; the asset has no speech")

    if not PIPER_VOICE or not Path(PIPER_VOICE).exists():
        raise RuntimeError(f"Piper voice not found at '{PIPER_VOICE}'.\n{PIPER_HELP}")

    workdir = project_dir / "recap" / asset_id
    workdir.mkdir(parents=True, exist_ok=True)
    outline_file = workdir / "outline.json"
    script_file = workdir / "script.json"
    edit_file = workdir / "edit.json"
    propose_file = workdir / "propose.json"

    # Stage 1: outline (map-reduce).
    def do_outline() -> str:
        chunks = recap.transcript_chunks(u)
        all_beats: list = []
        for i, chunk in enumerate(chunks):
            ctx.check_cancelled()
            raw = _llm(ctx, workdir, f"map_{i:02d}", recap.OUTLINE_MAP_SYSTEM,
                       recap.map_prompt(chunk, i, len(chunks)))
            data = _parse_json(raw)
            all_beats += data.get("beats", []) if isinstance(data, dict) else data
        raw = _llm(ctx, workdir, "reduce", recap.REDUCE_SYSTEM,
                   recap.reduce_prompt(all_beats, u.duration_ms / 1000))
        outline = _parse_json(raw)
        outline_file.write_text(json.dumps(outline, ensure_ascii=False, indent=1),
                                encoding="utf-8")
        return str(outline_file)

    ctx.run_stage("outline", do_outline)
    ctx.set_progress(0.25)

    # Stage 2: script.
    def do_script() -> str:
        outline = json.loads(outline_file.read_text(encoding="utf-8"))
        raw = _llm(ctx, workdir, "script", recap.SCRIPT_SYSTEM,
                   recap.script_prompt(outline, target_minutes))
        beats = recap.parse_beats(_parse_json(raw))
        if not beats:
            raise ValueError("script pass returned no usable narration beats")
        script_file.write_text(json.dumps(beats, ensure_ascii=False, indent=1),
                               encoding="utf-8")
        return str(script_file)

    ctx.run_stage("script", do_script)
    ctx.set_progress(0.45)

    # Stage 3: TTS (per-beat wavs live under media/ so the EDL can reference them).
    audio_dir = project_dir / "media" / "recap" / asset_id
    audio_dir.mkdir(parents=True, exist_ok=True)

    def do_tts() -> list[str]:
        beats = json.loads(script_file.read_text(encoding="utf-8"))
        outs: list[str] = []
        for b in beats:
            ctx.check_cancelled()
            wav = audio_dir / f"beat_{b['order']:03d}.wav"
            if not (wav.exists() and wav.stat().st_size > 0):
                _synth(b["narration"], wav)
            outs.append(str(wav))
        return outs

    ctx.run_stage("tts", do_tts)
    ctx.set_progress(0.7)

    # Stage 4: match beats to scenes (+ measured narration durations).
    def do_match() -> str:
        beats = json.loads(script_file.read_text(encoding="utf-8"))
        beats = recap.match_beats(beats, u)
        for b in beats:
            wav = audio_dir / f"beat_{b['order']:03d}.wav"
            b["audio"] = str(wav.relative_to(project_dir)).replace("\\", "/")
            b["audio_ms"] = probe(wav).duration_ms
        edit_file.write_text(json.dumps(beats, ensure_ascii=False, indent=1),
                             encoding="utf-8")
        return str(edit_file)

    ctx.run_stage("match", do_match)
    ctx.set_progress(0.85)

    # Stage 5: propose the recap timeline (+ gate).
    def do_propose() -> str:
        beats = json.loads(edit_file.read_text(encoding="utf-8"))
        narration = [
            recap.RecapAsset(
                asset_id=f"ast_rn{b['order']:03d}"[:16],
                src=b["audio"], duration_ms=int(b["audio_ms"]),
            )
            for b in beats
        ]
        ops = recap.plan_recap_edl(asset_id, beats, narration)
        head = engine.get_project(project_id)["head_rev"]
        try:
            result = engine.apply(project_id, head, ops, mode="propose")
        except Rejected as e:
            raise RuntimeError(f"recap proposal rejected: {e.issues[0].message}") from e
        total_s = sum(n.duration_ms for n in narration) / 1000
        payload = {"rev": result["rev"], "beats": len(beats),
                   "narration_s": round(total_s, 1)}
        propose_file.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        if telegram.configured():
            telegram.TelegramGate(engine).send_proposal_gate(
                project_id, result["rev"], "recap",
                f"Recap of {asset_id}: {len(beats)} beats, "
                f"{total_s / 60:.1f} min narration (target {target_minutes} min).",
                "Accept to place the recap timeline; render for the final video.",
            )
        return str(propose_file)

    ctx.run_stage("propose", do_propose)
    ctx.set_progress(1.0)
