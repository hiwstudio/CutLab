"""HTTP + WebSocket API (A7). Base: /api/v1, JSON everywhere.

Errors: {error: {code, message, issues?}}. Optimistic locking on apply
(409 when base_rev != head). A per-project asyncio lock enforces single
writer per project.
"""
from __future__ import annotations

import asyncio
import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Request, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from . import config
from .db import Database, utcnow
from .edl.engine import Conflict, Engine, NotFound, Rejected
from .edl.schema import LEGAL_FPS
from .jobs.ingest import ingest_handler
from .jobs.queue import JobQueue
from .jobs.understanding import understanding_handler
from .jobs.worker import Worker
from .render.runner import render_handler
from .util import paths
from .util.ids import new_asset_id
from .ws import WsHub

MEDIA_EXT_KIND = {
    ".mp4": "video", ".mov": "video", ".mkv": "video", ".webm": "video",
    ".avi": "video", ".m4v": "video", ".mts": "video",
    ".mp3": "audio", ".wav": "audio", ".m4a": "audio", ".aac": "audio",
    ".flac": "audio", ".ogg": "audio", ".opus": "audio",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image",
    ".bmp": "image", ".gif": "image",
}


def error_response(status: int, code: str, message: str, issues: list | None = None) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if issues is not None:
        body["error"]["issues"] = issues
    return JSONResponse(status_code=status, content=body)


class CanvasIn(BaseModel):
    width: int
    height: int
    fps: float


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    canvas: CanvasIn


class ApplyIn(BaseModel):
    base_rev: int
    ops: list[dict[str, Any]]
    mode: str = "commit"


class AssetPathIn(BaseModel):
    path: str


class RenderIn(BaseModel):
    rev: int | None = None
    output: str | None = None


class AppState:
    def __init__(self, data_dir: Path, start_worker: bool = True):
        self.data_dir = data_dir
        self.projects_dir = data_dir / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.hub = WsHub()
        self.db = Database(data_dir / "cutlab.db")
        self.queue = JobQueue(self.db, on_event=self.hub.job_event)
        self.engine = Engine(self.db, projects_dir=self.projects_dir,
                             on_revision=self.hub.revision_event)
        self.worker = Worker(self.db, self.queue)
        self.worker.register("ingest", ingest_handler)
        self.worker.register("render", render_handler)
        self.worker.register("understanding", understanding_handler)
        self._start_worker = start_worker
        self.locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def startup(self, loop: asyncio.AbstractEventLoop) -> None:
        self.hub.set_loop(loop)
        if self._start_worker:
            self.worker.start()

    def shutdown(self) -> None:
        if self._start_worker:
            self.worker.stop()
        self.db.close()


def create_app(data_dir: Path | None = None, start_worker: bool = True,
               verify_ffmpeg: bool = True) -> FastAPI:
    if verify_ffmpeg:
        config.verify_ffmpeg()
    from contextlib import asynccontextmanager

    state = AppState(data_dir or config.DATA_DIR, start_worker=start_worker)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        state.startup(asyncio.get_running_loop())
        yield
        state.shutdown()

    app = FastAPI(title="CutLab", version="0.1.0", lifespan=lifespan)
    app.state.cutlab = state
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["*"], allow_headers=["*"],
    )

    @app.exception_handler(NotFound)
    async def _nf(request: Request, exc: NotFound):
        return error_response(404, "E_NOT_FOUND", str(exc))

    @app.exception_handler(Conflict)
    async def _conflict(request: Request, exc: Conflict):
        r = error_response(409, "E_CONFLICT", str(exc))
        r.headers["X-Head-Rev"] = str(exc.head_rev)
        return r

    @app.exception_handler(Rejected)
    async def _rejected(request: Request, exc: Rejected):
        return error_response(422, "E_VALIDATION", str(exc),
                              issues=[i.to_dict() for i in exc.issues])

    api = APIRouter(prefix="/api/v1")

    # -- projects -------------------------------------------------------------

    @api.post("/projects")
    async def create_project(body: ProjectIn):
        if body.canvas.fps not in LEGAL_FPS:
            return error_response(422, "E_VALIDATION", f"fps must be one of {LEGAL_FPS}")
        project = state.engine.create_project(body.name, body.canvas.model_dump())
        paths.ensure_project_layout(state.projects_dir / project["id"])
        return project

    @api.get("/projects")
    async def list_projects():
        return state.engine.list_projects()

    @api.get("/projects/{project_id}")
    async def get_project(project_id: str):
        return state.engine.get_project(project_id)

    @api.get("/projects/{project_id}/edl")
    async def get_edl(project_id: str, rev: int | None = None):
        return state.engine.get_edl(project_id, rev)

    @api.post("/projects/{project_id}/apply")
    async def apply(project_id: str, body: ApplyIn):
        async with state.locks[project_id]:
            return state.engine.apply(project_id, body.base_rev, body.ops, body.mode)

    @api.post("/projects/{project_id}/undo")
    async def undo(project_id: str):
        async with state.locks[project_id]:
            return {"rev": state.engine.undo(project_id)}

    @api.post("/projects/{project_id}/redo")
    async def redo(project_id: str):
        async with state.locks[project_id]:
            return {"rev": state.engine.redo(project_id)}

    @api.get("/projects/{project_id}/revisions")
    async def revisions(project_id: str):
        return state.engine.revisions(project_id)

    # -- proposals (P2) --------------------------------------------------------

    @api.get("/projects/{project_id}/proposals")
    async def proposals(project_id: str):
        return state.engine.proposals(project_id)

    @api.post("/projects/{project_id}/proposals/{rev}/accept")
    async def accept_proposal(project_id: str, rev: int):
        async with state.locks[project_id]:
            return {"rev": state.engine.accept_proposal(project_id, rev)}

    @api.post("/projects/{project_id}/proposals/{rev}/reject")
    async def reject_proposal(project_id: str, rev: int):
        async with state.locks[project_id]:
            return {"rev": state.engine.reject_proposal(project_id, rev)}

    # -- assets ---------------------------------------------------------------

    @api.post("/projects/{project_id}/assets")
    async def upload_asset(project_id: str, file: UploadFile | None = None,
                           request: Request = None):
        state.engine.get_project(project_id)  # 404 if missing
        project_dir = state.projects_dir / project_id
        media = paths.media_dir(project_dir)
        media.mkdir(parents=True, exist_ok=True)

        if file is not None:
            filename = Path(file.filename or "upload.bin").name
            dest = _unique_path(media / filename)
            with dest.open("wb") as f:
                while chunk := await file.read(1 << 20):
                    f.write(chunk)
        else:
            try:
                body = AssetPathIn(**(await request.json()))
            except Exception:
                return error_response(422, "E_VALIDATION",
                                      "provide a multipart 'file' or JSON {path}")
            src = Path(body.path)
            if not src.exists():
                return error_response(422, "E_VALIDATION", f"path not found: {body.path}")
            dest = _unique_path(media / src.name)
            await asyncio.to_thread(shutil.copy2, src, dest)

        kind = MEDIA_EXT_KIND.get(dest.suffix.lower())
        if kind is None:
            dest.unlink(missing_ok=True)
            return error_response(422, "E_VALIDATION",
                                  f"unsupported media extension '{dest.suffix}'")

        asset_id = new_asset_id()
        src_rel = f"media/{dest.name}"
        state.db.execute(
            "INSERT INTO assets (project_id, asset_id, kind, src, status)"
            " VALUES (?, ?, ?, ?, 'ingesting')",
            (project_id, asset_id, kind, src_rel),
        )
        job_id = state.queue.enqueue("ingest", {
            "project_id": project_id, "asset_id": asset_id, "kind": kind,
            "src": src_rel, "project_dir": str(project_dir),
        }, project_id=project_id)
        return {"asset_id": asset_id, "kind": kind, "src": src_rel,
                "status": "ingesting", "job_id": job_id}

    @api.get("/projects/{project_id}/assets")
    async def list_assets(project_id: str):
        state.engine.get_project(project_id)
        rows = state.db.query(
            "SELECT project_id, asset_id, kind, src, proxy, duration_ms, width,"
            " height, understanding, status FROM assets WHERE project_id=? ORDER BY rowid",
            (project_id,),
        )
        return rows

    # -- understanding (P1) -----------------------------------------------------

    @api.post("/projects/{project_id}/assets/{asset_id}/analyze")
    async def analyze_asset(project_id: str, asset_id: str):
        state.engine.get_project(project_id)
        row = state.db.query_one(
            "SELECT kind, src, status FROM assets WHERE project_id=? AND asset_id=?",
            (project_id, asset_id),
        )
        if row is None:
            return error_response(404, "E_NOT_FOUND", f"asset {asset_id} not found")
        if row["status"] != "ready":
            return error_response(409, "E_NOT_READY", "asset is still ingesting")
        job_id = state.queue.enqueue("understanding", {
            "project_id": project_id, "asset_id": asset_id, "kind": row["kind"],
            "src": row["src"], "project_dir": str(state.projects_dir / project_id),
        }, project_id=project_id)
        return {"asset_id": asset_id, "job_id": job_id, "status": "analyzing"}

    @api.get("/projects/{project_id}/assets/{asset_id}/understanding")
    async def get_understanding(project_id: str, asset_id: str):
        state.engine.get_project(project_id)
        row = state.db.query_one(
            "SELECT understanding FROM assets WHERE project_id=? AND asset_id=?",
            (project_id, asset_id),
        )
        if row is None:
            return error_response(404, "E_NOT_FOUND", f"asset {asset_id} not found")
        if not row["understanding"]:
            return error_response(404, "E_NOT_ANALYZED", "asset has no understanding yet")
        path = paths.safe_join(state.projects_dir / project_id, row["understanding"])
        if not path.is_file():
            return error_response(404, "E_NOT_FOUND", "understanding artifact missing")
        return json.loads(path.read_text(encoding="utf-8"))

    # -- render / jobs ----------------------------------------------------------

    @api.post("/projects/{project_id}/render")
    async def render(project_id: str, body: RenderIn | None = None):
        project = state.engine.get_project(project_id)
        body = body or RenderIn()
        rev = body.rev if body.rev is not None else project["head_rev"]
        state.engine.get_edl(project_id, rev)  # 404 if rev unknown
        if body.output and (
            not body.output.replace("-", "").replace("_", "").isalnum()
        ):
            return error_response(422, "E_VALIDATION", "output name must be alphanumeric -_")
        job_id = state.queue.enqueue("render", {
            "project_id": project_id, "rev": rev,
            "project_dir": str(state.projects_dir / project_id),
            "output": body.output,
        }, project_id=project_id)
        return {"job_id": job_id, "rev": rev}

    @api.get("/jobs/{job_id}")
    async def get_job(job_id: str):
        job = state.queue.get(job_id)
        if job is None:
            return error_response(404, "E_NOT_FOUND", f"job {job_id} not found")
        job.pop("input_json", None)
        job.pop("artifacts_json", None)
        return job

    @api.post("/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str):
        if state.queue.get(job_id) is None:
            return error_response(404, "E_NOT_FOUND", f"job {job_id} not found")
        return {"ok": state.queue.cancel(job_id)}

    app.include_router(api)

    # -- media files ------------------------------------------------------------

    @app.get("/media/{project_id}/{file_path:path}")
    async def media_file(project_id: str, file_path: str):
        root = state.projects_dir / project_id
        try:
            target = paths.safe_join(root, file_path)
        except ValueError:
            return error_response(403, "E_FORBIDDEN", "path escapes project dir")
        if not target.is_file():
            return error_response(404, "E_NOT_FOUND", file_path)
        return FileResponse(target)

    # -- websocket ---------------------------------------------------------------

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await state.hub.handle(ws)

    return app


def _unique_path(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem, suffix = dest.stem, dest.suffix
    for i in range(1, 1000):
        candidate = dest.with_name(f"{stem}_{i}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError("could not find unique filename")
