"""Control-room dashboard: run the engine, watch the live log, review clips.

Run:  python dashboard.py   ->  http://localhost:5000  (or PORT env)
"""
import json
import os
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

from flask import (Flask, abort, jsonify, render_template, request,
                   send_from_directory)

import config
from engine.fonts import list_fonts
from engine.styles import describe as describe_styles
from engine.utils import safe_slug

app = Flask(__name__)

# ------------------------------------------------------------------ jobs ---
# One job at a time: renders are CPU-bound, a queue would just hide that.
JOB = {"proc": None, "lines": deque(maxlen=800), "status": "idle",
       "started": 0.0, "label": ""}
LOCK = threading.Lock()


def _pump(proc):
    for line in proc.stdout:
        JOB["lines"].append(line.rstrip())
    proc.wait()
    JOB["status"] = "done" if proc.returncode == 0 else "failed"


@app.route("/api/run", methods=["POST"])
def api_run():
    f = request.get_json(force=True)
    video = (f.get("video") or "").strip().strip('"').strip("'")
    if not video:
        return jsonify(error="Give me a video path or URL first."), 400
    mode = f.get("mode", "clip")
    with LOCK:
        if JOB["proc"] and JOB["proc"].poll() is None:
            return jsonify(error="The engine is already running a job."), 409
        cmd = [sys.executable, "-u", "run.py",
               "--mode", mode,
               "--style", f.get("style", "blur"),
               "--font", f.get("font", "Arial"),
               "--subtitles", f.get("subtitles", "auto"),
               "--caption", f.get("overlay", "yes"),
               "--clips", str(f.get("clips") or config.MAX_CLIPS)]
        if f.get("redo"):
            cmd.append("--redo")
        cmd.append(video)

        # a typed top caption is pre-seeded so reframe modes never prompt
        cap = (f.get("caption_text") or "").strip()
        src = Path(video.strip())
        if cap and mode != "clip" and src.exists():
            workdir = config.OUTPUT_DIR / safe_slug(src.stem, 60)
            workdir.mkdir(parents=True, exist_ok=True)
            (workdir / "caption.txt").write_text(cap, encoding="utf-8")

        JOB["lines"].clear()
        JOB["status"] = "running"
        JOB["started"] = time.time()
        JOB["label"] = f"{mode} · {f.get('style','blur')} · {src.name if src.exists() else video}"
        JOB["proc"] = subprocess.Popen(
            cmd, cwd=config.ROOT, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace")
        threading.Thread(target=_pump, args=(JOB["proc"],), daemon=True).start()
    return jsonify(ok=True)


@app.route("/api/stop", methods=["POST"])
def api_stop():
    with LOCK:
        if JOB["proc"] and JOB["proc"].poll() is None:
            JOB["proc"].terminate()
            JOB["status"] = "failed"
            JOB["lines"].append("[dashboard] job stopped by operator")
    return jsonify(ok=True)


@app.route("/api/job")
def api_job():
    running = JOB["proc"] is not None and JOB["proc"].poll() is None
    return jsonify(
        status="running" if running else JOB["status"],
        label=JOB["label"],
        elapsed=int(time.time() - JOB["started"]) if JOB["started"] else 0,
        lines=list(JOB["lines"]),
    )


# ----------------------------------------------------------------- pages ---

def _projects():
    if not config.OUTPUT_DIR.exists():
        return []
    out = []
    for d in sorted(config.OUTPUT_DIR.iterdir()):
        meta = d / "clips.json"
        if meta.exists():
            data = json.loads(meta.read_text(encoding="utf-8-sig"))
            first = next((c.get("file") for c in data.get("clips", [])
                          if c.get("file")), None)
            out.append({"name": d.name, "count": data.get("clip_count", 0),
                        "poster": first, "when": data.get("generated_at", "")})
    out.sort(key=lambda p: p["when"], reverse=True)
    return out


def _options():
    return {
        "styles": describe_styles(),
        "fonts": [f["name"] for f in list_fonts()],
        "max_clips": config.MAX_CLIPS,
    }


@app.route("/")
def index():
    return render_template("dashboard.html", projects=_projects(),
                           data=None, project=None, **_options())


def _project_dir(name):
    """Resolve a project name to its folder, rejecting anything outside output/."""
    d = (config.OUTPUT_DIR / name).resolve()
    if d.parent != config.OUTPUT_DIR.resolve() or not d.is_dir():
        abort(404)
    return d


@app.route("/p/<project>")
def project(project):
    meta = _project_dir(project) / "clips.json"
    if not meta.exists():
        abort(404)
    data = json.loads(meta.read_text(encoding="utf-8-sig"))
    return render_template("dashboard.html", projects=None, data=data,
                           project=project, **_options())


@app.route("/file/<project>/<path:relpath>")
def file(project, relpath):
    return send_from_directory(_project_dir(project), relpath)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print(f"Dashboard running at http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
