"""Review server — NLE-style review UI (review_ui.html) over a stdlib HTTP server.

GET  /               the review application
GET  /state          {timeline, review, video_ready, project}
GET  /video          preview video (HTTP Range supported for seeking)
GET  /thumb/<scene>  scene thumbnail (jpg)
POST /edit           {action, scene_id, ...} → timeline edit (existing actions)
POST /comment        {scene_id|null, text} → scene or project comment
POST /flag           {scene_id, flag: "revision"|"regen"|null}
POST /submit         {decision: "approve"|"changes"} → review_package.json;
                     "approve" also approves the timeline gate
POST /approve        legacy: approve the gate directly

The preview video is assembly/render.mp4 when fresh, else a fast 640x360 draft
(assembly/preview.mp4) built at server start. Scene review status lives in
timeline.json (engine-owned); comments/flags/history live in
timeline/review.json (review-owned).
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import timeline as tlmod
from .state import State, now


# ---- review store (comments / flags / history) ----
def _review_path(project_dir: Path) -> Path:
    return project_dir / "timeline" / "review.json"


def load_review(project_dir: Path) -> dict:
    p = _review_path(project_dir)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"scenes": {}, "project_comments": [], "submitted": None}


def save_review(project_dir: Path, review: dict) -> None:
    p = _review_path(project_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(review, indent=2), encoding="utf-8")


def _scene_review(review: dict, scene_id: str) -> dict:
    return review["scenes"].setdefault(
        scene_id, {"comments": [], "flag": None, "history": []})


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_history(project_dir: Path, scene_id: str, entry: str) -> None:
    review = load_review(project_dir)
    _scene_review(review, scene_id)["history"].append({"t": _ts(), "event": entry})
    save_review(project_dir, review)


# ---- preview video ----
def scene_workbench(project_dir: Path) -> dict:
    """Per-scene material the operator acts on, keyed by scene id.

    The timeline says what is IN the cut. It does not say what KIND of visual the
    scene wants, nor what the alternatives were — both live in files the board
    never read (`research/visual_plan.json`, `research/progress.json`), so every
    scene looked identical and the only options were approve or reject-and-rerun.
    A reviewer choosing between sourced clips needs to see the shortlist.
    """
    out: dict[str, dict] = {}
    plan_p = project_dir / "research" / "visual_plan.json"
    if plan_p.exists():
        for p in json.loads(plan_p.read_text(encoding="utf-8")).get("plans", []):
            out.setdefault(p["scene_id"], {})["visual_type"] = p.get("visual_type")
            out[p["scene_id"]]["queries"] = p.get("queries") or []
            out[p["scene_id"]]["sourcing"] = p.get("sourcing", "exact")

    prog_p = project_dir / "research" / "progress.json"
    if prog_p.exists():
        for sid, st in json.loads(prog_p.read_text(encoding="utf-8")).items():
            e = out.setdefault(sid, {})
            e["status"] = st.get("status")
            e["candidate_idx"] = st.get("candidate_idx", 0)
            e["candidates"] = [
                {"title": c.get("title", ""), "channel": c.get("channel", ""),
                 "url": c.get("url", ""), "video_id": c.get("video_id", ""),
                 "clip_start_ms": c.get("clip_start_ms"),
                 "clip_end_ms": c.get("clip_end_ms"),
                 "score": c.get("score"), "chosen": bool(c.get("chosen")),
                 "matched_text": c.get("matched_text", "")}
                for c in st.get("candidates", [])]

    # generated scenes: the prompts that were issued and the stills dropped back
    pdir = project_dir / "imagery" / "prompts"
    if pdir.exists():
        for f in pdir.glob("*.flowdeck.json"):
            sid = f.name.split(".")[0]
            if sid.startswith("_"):
                continue
            job = json.loads(f.read_text(encoding="utf-8"))
            e = out.setdefault(sid, {})
            e["prompts"] = [x.get("prompt", "") for x in job.get("prompts", [])]
            inc = project_dir / "imagery" / "incoming" / sid
            e["images"] = sorted(x.name for x in inc.glob("*")) if inc.exists() else []
    return out


def _inputs_mtime(project_dir: Path, tl_path: Path) -> float:
    """Newest mtime across everything a render is built FROM.

    timeline.json alone is not enough. Re-cutting a clip, or re-fetching the
    source, changes the pixels without touching the timeline — so a stale
    render kept being served as if it were current, and frames grabbed from it
    led to a wrong conclusion about a crop that had in fact worked.
    """
    newest = tl_path.stat().st_mtime
    for extra in ((project_dir / "input" / "source.mp4"),):
        if extra.exists():
            newest = max(newest, extra.stat().st_mtime)
    try:
        tl = json.loads(tl_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return newest
    for sc in tl.get("scenes", []):
        vis = sc.get("visual") or {}
        p = vis.get("path")
        if p and Path(p).exists():
            newest = max(newest, Path(p).stat().st_mtime)
    return newest


def preview_video(project_dir: Path, cfg: dict, mode: str = "mix") -> Path | None:
    """Full render if fresh, else a fast draft (built here if stale).

    `mode` matters: a SPLIT project previewed with the MIX renderer shows
    full-frame b-roll over the voiceover — not the stacked picture the reviewer
    is being asked to judge. Draft geometry follows the mode too, portrait for
    SPLIT, so the framing in the draft matches the final.
    """
    tl_path = project_dir / "timeline" / "timeline.json"
    if not tl_path.exists():
        return None
    tl_mtime = _inputs_mtime(project_dir, tl_path)
    full = project_dir / "assembly" / "render.mp4"
    if full.exists() and full.stat().st_mtime >= tl_mtime:
        return full
    draft = project_dir / "assembly" / "preview.mp4"
    if draft.exists() and draft.stat().st_mtime >= tl_mtime:
        return draft
    from . import assemble, modes, timing
    tl = tlmod.load(project_dir)
    if not tl or not tl.get("scenes"):
        return None
    tmap = timing.load(project_dir / "timing" / "timing_map.json")
    print("Building draft preview (one-time per timeline change)...")
    renderer = modes.RENDERERS.get(mode)
    if renderer is not None:
        # A registered mode renders its own draft. Geometry stays as configured
        # — a SPLIT draft must keep portrait framing or the reviewer judges a
        # shape the final will not have.
        out = renderer(project_dir, tl, tmap, cfg,
                       project_dir / "input" / "source.mp4")
    else:
        draft_cfg = {**cfg, "render": {**cfg["render"], "width": 640, "height": 360}}
        out = assemble.render(project_dir, tl, tmap, draft_cfg,
                              out_name="preview.mp4", seg_subdir="segments_draft")
    print(f"Draft preview ready: {out}")
    return out


def send_file_range(handler, p: Path, ctype: str) -> None:
    """Serve a file with HTTP Range support (seeking) — shared with graph.py.

    Without this a <video> can only stream from the start, and the browser
    pulls the whole file just to read its metadata.
    """
    size = p.stat().st_size
    rng = handler.headers.get("Range")
    start, end = 0, size - 1
    is_range = False
    if rng:
        m = re.match(r"bytes=(\d*)-(\d*)", rng)
        if m and (m.group(1) or m.group(2)):
            is_range = True
            if m.group(1):
                start = int(m.group(1))
            if m.group(2):
                end = min(int(m.group(2)), size - 1)
            # cap open-ended ranges so a seek returns quickly, not the
            # whole 200MB+ file (the browser requests the next slice next)
            elif start or not m.group(2):
                end = min(size - 1, start + 8 * 1024 * 1024 - 1)
    if start >= size or start > end:
        handler.send_response(416)
        handler.send_header("Content-Range", f"bytes */{size}")
        handler.send_header("Content-Length", "0")
        handler.end_headers()
        return
    length = end - start + 1
    handler.send_response(206 if is_range else 200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Accept-Ranges", "bytes")
    if is_range:
        handler.send_header("Content-Range", f"bytes {start}-{end}/{size}")
    handler.send_header("Content-Length", str(length))
    handler.end_headers()
    with open(p, "rb") as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            buf = f.read(min(remaining, 256 * 1024))
            if not buf:
                break
            try:
                handler.wfile.write(buf)
            except (ConnectionError, TimeoutError):
                handler.close_connection = True  # client seeked/closed
                return
            remaining -= len(buf)


class PreviewHandler(BaseHTTPRequestHandler):
    project_dir: Path = None  # set by serve()
    state: State = None
    run_id: str = None
    cfg: dict = None
    mode: str = "mix"

    def _video(self):
        """Resolve the preview per request, never once at startup.

        A board opened before the clips landed used to capture "no video" and
        report it forever, however much the pipeline produced afterwards."""
        try:
            return preview_video(self.project_dir, self._render_cfg(), self.mode)
        except Exception as e:                      # a failed draft must not 500
            print(f"preview build failed: {e}")
            return None

    def _render_cfg(self) -> dict:
        """config.yaml with the assemble stage's node parameters merged in.

        Without this the draft is built from the file defaults while the final
        is built from the stage's parameters — so a SPLIT project, whose
        template pins assemble to 1080x1920, was reviewed as a landscape frame
        and rendered as a portrait one. The reviewer must judge the shape they
        are going to get.
        """
        from .pipeline import merge_params
        cfg = self.cfg or {}
        if not (self.state and self.run_id):
            return cfg
        try:
            return merge_params(cfg, self.state.get_params(self.run_id, "assemble"))
        except Exception:                           # params are an optimisation
            return cfg
    # HTTP/1.0 (connection-close): a hand-rolled handler can't keep keep-alive
    # sockets in sync when the <video> element aborts range requests mid-seek;
    # closing per response is robust and Range/206 seeking still works.

    def handle_one_request(self):  # quiet client-abort resets (normal for video)
        try:
            super().handle_one_request()
        except (ConnectionError, TimeoutError):
            self.close_connection = True

    # ---- plumbing ----
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self._write(body)

    def _write(self, data: bytes) -> None:
        try:
            self.wfile.write(data)
        except (ConnectionError, TimeoutError):
            self.close_connection = True  # client went away; not an error

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode(), "application/json")

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    # ---- GET ----
    def do_GET(self):  # noqa: N802
        # Routes compare self.path exactly, so any query string 404s — "/?z=16",
        # a linkable timeline zoom, was "not found". The page reads its own
        # query client-side; the server only needs the path.
        self.path = self.path.split("?", 1)[0] or "/"
        if self.path == "/":
            page = (Path(__file__).parent / "review_ui.html").read_bytes()
            self._send(200, page, "text/html; charset=utf-8")
        elif self.path == "/state":
            tl = tlmod.load(self.project_dir)
            self._json({
                "timeline": tl,
                "mode": self.mode,
                "workbench": scene_workbench(self.project_dir),
                "review": load_review(self.project_dir),
                "video_ready": (lambda v: v is not None and Path(v).exists())(
                    self._video()),
                "project": self.project_dir.name,
            })
        elif self.path == "/timeline.json":  # legacy
            tl = tlmod.load(self.project_dir)
            self._json(tl if tl else {"error": "no timeline yet"})
        elif self.path == "/video":
            self._serve_video()
        elif self.path.startswith("/img/"):
            # a dropped still for a generated scene: /img/<scene_id>/<filename>
            parts = self.path.split("/")
            p = (self.project_dir / "imagery" / "incoming"
                 / parts[2] / parts[3]) if len(parts) == 4 else None
            if p and p.exists() and p.is_file():
                ct = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
                self._send(200, p.read_bytes(), ct)
            else:
                self._send(404, b"no image", "text/plain")
        elif self.path.startswith("/thumb/"):
            sid = self.path.rsplit("/", 1)[-1]
            p = self.project_dir / "timeline" / "thumbs" / f"{sid}.jpg"
            if p.exists():
                self._send(200, p.read_bytes(), "image/jpeg")
            else:
                self._send(404, b"no thumb", "text/plain")
        else:
            self._send(404, b"not found", "text/plain")

    def _serve_video(self) -> None:
        v = self._video()
        p = Path(v) if v else None
        if not p or not p.exists():
            self._send(404, b"no preview video", "text/plain")
            return
        send_file_range(self, p, "video/mp4")
    # ---- POST ----
    def do_POST(self):  # noqa: N802
        try:
            if self.path == "/edit":
                edit = self._body()
                tl = tlmod.load(self.project_dir)
                tl = tlmod.apply_edit(self.project_dir, tl, edit)
                log_history(self.project_dir, edit["scene_id"],
                            f"edit: {edit['action']}")
                self._json({"ok": True, "score": tl["score"]})
            elif self.path == "/comment":
                b = self._body()
                text = (b.get("text") or "").strip()
                if not text:
                    raise ValueError("empty comment")
                review = load_review(self.project_dir)
                entry = {"t": _ts(), "text": text}
                if b.get("scene_id"):
                    _scene_review(review, b["scene_id"])["comments"].append(entry)
                else:
                    review["project_comments"].append(entry)
                save_review(self.project_dir, review)
                self._json({"ok": True})
            elif self.path == "/flag":
                b = self._body()
                review = load_review(self.project_dir)
                sr = _scene_review(review, b["scene_id"])
                flag = b.get("flag")
                if flag not in (None, "revision", "regen"):
                    raise ValueError(f"unknown flag: {flag}")
                sr["flag"] = flag
                sr["history"].append(
                    {"t": _ts(), "event": f"flag: {flag or 'cleared'}"})
                save_review(self.project_dir, review)
                self._json({"ok": True})
            elif self.path == "/submit":
                self._submit(self._body())
            elif self.path == "/approve":  # legacy
                approve_gate(self.state, self.run_id, "timeline_approval")
                self._json({"ok": True,
                            "message": "Approved — rerun `mixfix run` to render."})
            else:
                self._send(404, b"not found", "text/plain")
        except (tlmod.EditError, json.JSONDecodeError, KeyError, ValueError) as e:
            self._json({"error": str(e)}, 400)

    def _submit(self, body: dict) -> None:
        decision = body.get("decision")
        if decision not in ("approve", "changes"):
            raise ValueError("decision must be approve|changes")
        tl = tlmod.load(self.project_dir)
        review = load_review(self.project_dir)
        scenes = []
        blockers = []
        for s in tl["scenes"]:
            sr = review["scenes"].get(s["id"], {})
            scenes.append({
                "id": s["id"], "review": s["review"],
                "flag": sr.get("flag"),
                "comments": sr.get("comments", []),
            })
            if s["review"] == "rejected" or sr.get("flag"):
                blockers.append(s["id"])
        if decision == "approve" and blockers:
            raise ValueError(
                "cannot approve with rejected/flagged scenes: "
                + ", ".join(blockers))
        package = {
            "submitted_at": _ts(),
            "decision": decision,
            "project": self.project_dir.name,
            "scenes": scenes,
            "project_comments": review["project_comments"],
            "score": tl["score"],
        }
        (self.project_dir / "review_package.json").write_text(
            json.dumps(package, indent=2), encoding="utf-8")
        review["submitted"] = {"t": package["submitted_at"], "decision": decision}
        save_review(self.project_dir, review)
        if decision == "approve":
            approve_gate(self.state, self.run_id, "timeline_approval")
            msg = "Project approved — rerun `mixfix run` to render."
        else:
            msg = ("Change request saved to review_package.json — the operator "
                   "will action it and re-run the pipeline.")
        self._json({"ok": True, "message": msg})

    def log_message(self, *args):  # quiet
        pass


# ---- gates ----
def ensure_gate(state: State, run_id: str, name: str):
    row = state.conn.execute(
        "SELECT * FROM gates WHERE run_id=? AND name=? ORDER BY created_at DESC LIMIT 1",
        (run_id, name)).fetchone()
    if row is None:
        from .state import new_id
        gate_id = new_id("gate")
        with state.conn:
            state.conn.execute(
                "INSERT INTO gates (gate_id, run_id, name, created_at)"
                " VALUES (?,?,?,?)", (gate_id, run_id, name, now()))
        return state.conn.execute(
            "SELECT * FROM gates WHERE gate_id=?", (gate_id,)).fetchone()
    return row


def approve_gate(state: State, run_id: str, name: str) -> None:
    with state.conn:
        state.conn.execute(
            "UPDATE gates SET status='approved', decided_at=? "
            "WHERE run_id=? AND name=? AND status='pending'",
            (now(), run_id, name))


def serve(project_dir: Path, state: State, run_id: str, port: int = 8765,
          cfg: dict | None = None) -> None:
    run = state.get_run(run_id)
    handler = type("H", (PreviewHandler,), {
        "project_dir": project_dir, "state": state, "run_id": run_id,
        "cfg": cfg, "mode": run["mode"] if run else "mix"})
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"Review board: http://127.0.0.1:{port}/  (Ctrl+C to stop)")
    httpd.serve_forever()
