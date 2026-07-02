"""WebSocket hub: job and revision events.

Clients connect to /ws and send {"project_id": "..."} to subscribe (multiple
subscriptions per socket are fine). Job events are throttled to >=250ms per
job unless the state changed; state transitions always go out immediately.

Events originate on the worker thread; broadcasts are marshalled onto the
server's event loop with run_coroutine_threadsafe.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

log = logging.getLogger("cutlab.ws")

JOB_THROTTLE_S = 0.25


class WsHub:
    def __init__(self) -> None:
        self._subs: dict[WebSocket, set[str]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._last_job_sent: dict[str, tuple[float, str]] = {}  # job_id -> (t, state)
        self._lock = asyncio.Lock()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def handle(self, ws: WebSocket) -> None:
        await ws.accept()
        self._subs[ws] = set()
        try:
            while True:
                msg = await ws.receive_text()
                try:
                    data = json.loads(msg)
                except json.JSONDecodeError:
                    continue
                pid = data.get("project_id")
                if isinstance(pid, str):
                    self._subs[ws].add(pid)
        except WebSocketDisconnect:
            pass
        finally:
            self._subs.pop(ws, None)

    # -- broadcast (called from any thread) -----------------------------------

    def job_event(self, job: dict[str, Any]) -> None:
        now = time.monotonic()
        last = self._last_job_sent.get(job["id"])
        if last and last[1] == job["state"] and now - last[0] < JOB_THROTTLE_S:
            return  # throttle progress-only updates
        self._last_job_sent[job["id"]] = (now, job["state"])
        payload = {"type": "job", "job": {
            "id": job["id"], "kind": job["kind"], "project_id": job["project_id"],
            "state": job["state"], "stage": job["stage"], "progress": job["progress"],
            "error": job["error"], "artifacts": job.get("artifacts", {}),
        }}
        self._send_threadsafe(job.get("project_id"), payload)

    def revision_event(self, project_id: str, rev: int, summary: str, state: str) -> None:
        self._send_threadsafe(project_id, {
            "type": "revision", "project_id": project_id,
            "rev": rev, "summary": summary, "state": state,
        })

    def _send_threadsafe(self, project_id: str | None, payload: dict[str, Any]) -> None:
        if self._loop is None or self._loop.is_closed():
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        coro = self._broadcast(project_id, payload)
        if running is self._loop:
            self._loop.create_task(coro)
        else:
            asyncio.run_coroutine_threadsafe(coro, self._loop)

    async def _broadcast(self, project_id: str | None, payload: dict[str, Any]) -> None:
        text = json.dumps(payload)
        for ws, pids in list(self._subs.items()):
            if project_id is not None and project_id not in pids:
                continue
            try:
                await ws.send_text(text)
            except Exception:
                self._subs.pop(ws, None)
