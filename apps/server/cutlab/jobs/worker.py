"""Job worker: claims queued jobs and executes registered handlers.

Runs either as a daemon thread inside the server process (normal mode) or as
a standalone process (`python -m cutlab.jobs.worker`) so crash-resume tests
can SIGKILL it.
"""
from __future__ import annotations

import logging
import threading
import time
import traceback
from typing import Any, Callable

from ..db import Database
from .queue import JobCancelled, JobContext, JobQueue

log = logging.getLogger("cutlab.worker")

# A handler receives a JobContext and drives its stages via ctx.run_stage().
Handler = Callable[[JobContext], None]


class Worker:
    def __init__(self, db: Database, queue: JobQueue, poll_interval: float = 0.25):
        self.db = db
        self.queue = queue
        self.poll_interval = poll_interval
        self.handlers: dict[str, Handler] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def register(self, kind: str, handler: Handler) -> None:
        self.handlers[kind] = handler

    def start(self) -> None:
        self.queue.recover_on_start()
        self._thread = threading.Thread(target=self.run_forever, daemon=True, name="cutlab-worker")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)

    def run_forever(self) -> None:
        while not self._stop.is_set():
            if not self.run_one():
                self._stop.wait(self.poll_interval)

    def run_one(self) -> bool:
        """Claim and execute a single job. Returns True if a job was processed."""
        job = self.queue.claim()
        if job is None:
            return False
        handler = self.handlers.get(job["kind"])
        if handler is None:
            self.queue.finish(job["id"], "failed", f"no handler for kind '{job['kind']}'")
            return True
        ctx = JobContext(self.queue, job)
        try:
            handler(ctx)
            self.queue.finish(job["id"], "done")
        except JobCancelled:
            self.queue.finish(job["id"], "cancelled")
        except Exception as e:  # noqa: BLE001 - job isolation boundary
            tail = "".join(traceback.format_exception(e))[-2000:]
            log.error("job %s failed: %s", job["id"], tail)
            self.queue.fail_or_requeue(job["id"], tail)
        return True


def main() -> None:
    """Standalone worker process (used by crash-resume tests and dev)."""
    import argparse

    from .. import config
    from .ingest import ingest_handler
    from ..render.runner import render_handler

    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(config.DB_PATH))
    parser.add_argument("--once", action="store_true", help="drain the queue then exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    db = Database(args.db)
    queue = JobQueue(db)
    worker = Worker(db, queue)
    worker.register("ingest", ingest_handler)
    worker.register("render", render_handler)
    queue.recover_on_start()
    if args.once:
        while worker.run_one():
            pass
    else:
        worker.run_forever()


if __name__ == "__main__":
    main()
