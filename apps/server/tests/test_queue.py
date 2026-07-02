"""B3.1 tests: durable queue — enqueue/claim/checkpoint/recover."""
from __future__ import annotations

from pathlib import Path

from cutlab.db import Database
from cutlab.jobs.queue import JobContext, JobQueue, artifacts_valid
from cutlab.jobs.worker import Worker


def make_4stage_handler(workdir: Path, executed: list[str]):
    """A handler with 4 checkpointed stages, each writing one artifact file."""

    def handler(ctx: JobContext) -> None:
        for i in range(1, 5):
            name = f"stage{i}"

            def run(name=name) -> str:
                executed.append(name)
                p = workdir / f"{name}.bin"
                p.write_bytes(b"artifact-" + name.encode())
                return str(p)

            ctx.run_stage(name, run)
            ctx.set_progress(i / 4)

    return handler


def test_enqueue_claim_done(db: Database, queue: JobQueue, tmp_path: Path):
    executed: list[str] = []
    worker = Worker(db, queue)
    worker.register("test", make_4stage_handler(tmp_path, executed))

    job_id = queue.enqueue("test", {"x": 1}, project_id=None)
    assert queue.get(job_id)["state"] == "queued"
    assert worker.run_one() is True
    job = queue.get(job_id)
    assert job["state"] == "done"
    assert job["progress"] == 1.0
    assert executed == ["stage1", "stage2", "stage3", "stage4"]
    assert set(job["artifacts"]) == {"stage1", "stage2", "stage3", "stage4"}


def test_claim_order_and_empty(db: Database, queue: JobQueue):
    assert queue.claim() is None
    a = queue.enqueue("test", {"n": "a"})
    b = queue.enqueue("test", {"n": "b"})
    assert queue.claim()["id"] == a
    assert queue.claim()["id"] == b
    assert queue.claim() is None


def test_recovery_resumes_at_first_missing_stage(db: Database, queue: JobQueue, tmp_path: Path):
    """The spec's recovery test: job crashed 'running' with 2 of 4 stage
    artifacts on disk; after restart only stages 3-4 execute."""
    executed: list[str] = []
    handler = make_4stage_handler(tmp_path, executed)

    # Simulate a crashed run: stages 1-2 checkpointed, then process died.
    job_id = queue.enqueue("test", {})
    job = queue.claim()
    assert job["id"] == job_id
    for i in (1, 2):
        p = tmp_path / f"stage{i}.bin"
        p.write_bytes(b"pre-crash")
        queue.checkpoint(job_id, f"stage{i}", str(p))
    assert queue.get(job_id)["state"] == "running"  # died here

    # Restart: fresh worker recovers, then processes.
    worker = Worker(db, queue)
    worker.register("test", handler)
    recovered = queue.recover_on_start()
    assert recovered == [job_id]
    job = queue.get(job_id)
    assert job["state"] == "queued"
    assert job["attempts"] == 1

    assert worker.run_one() is True
    job = queue.get(job_id)
    assert job["state"] == "done"
    assert executed == ["stage3", "stage4"]
    # Pre-crash artifacts untouched.
    assert (tmp_path / "stage1.bin").read_bytes() == b"pre-crash"


def test_recovery_reruns_stage_with_corrupt_artifact(db: Database, queue: JobQueue, tmp_path: Path):
    executed: list[str] = []
    job_id = queue.enqueue("test", {})
    queue.claim()
    good = tmp_path / "stage1.bin"
    good.write_bytes(b"ok")
    queue.checkpoint(job_id, "stage1", str(good))
    empty = tmp_path / "stage2.bin"
    empty.write_bytes(b"")  # size 0 -> fails integrity check
    queue.checkpoint(job_id, "stage2", str(empty))

    queue.recover_on_start()
    worker = Worker(db, queue)
    worker.register("test", make_4stage_handler(tmp_path, executed))
    worker.run_one()
    assert executed == ["stage2", "stage3", "stage4"]


def test_max_attempts_fail(db: Database, queue: JobQueue):
    job_id = queue.enqueue("test", {})
    # Crash-recover repeatedly; third attempt exhausts the budget.
    queue.claim()
    queue.recover_on_start()
    assert queue.get(job_id)["attempts"] == 1
    queue.claim()
    queue.recover_on_start()
    assert queue.get(job_id)["attempts"] == 2
    queue.claim()
    queue.recover_on_start()
    job = queue.get(job_id)
    assert job["attempts"] == 3
    assert job["state"] == "failed"


def test_handler_exception_requeues_then_fails(db: Database, queue: JobQueue):
    worker = Worker(db, queue)

    def boom(ctx: JobContext) -> None:
        raise RuntimeError("stage exploded")

    worker.register("test", boom)
    job_id = queue.enqueue("test", {})
    for expected_state in ("queued", "queued", "failed"):
        worker.run_one()
        job = queue.get(job_id)
        assert job["state"] == expected_state
    assert "stage exploded" in job["error"]


def test_cancel(db: Database, queue: JobQueue, tmp_path: Path):
    job_id = queue.enqueue("test", {})
    assert queue.cancel(job_id) is True
    assert queue.get(job_id)["state"] == "cancelled"
    assert queue.claim() is None
    # Cancelling a finished job is a no-op.
    assert queue.cancel(job_id) is False


def test_artifacts_valid(tmp_path: Path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"x")
    assert artifacts_valid(str(f)) is True
    assert artifacts_valid([str(f)]) is True
    assert artifacts_valid({"out": str(f), "cmd": "not-a-path"}) is True
    assert artifacts_valid(str(tmp_path / "missing.bin")) is False
    empty = tmp_path / "e.bin"
    empty.write_bytes(b"")
    assert artifacts_valid(str(empty)) is False
    assert artifacts_valid([]) is False


def test_events_emitted(db: Database, tmp_path: Path):
    events: list[str] = []
    queue = JobQueue(db, on_event=lambda job: events.append(job["state"]))
    worker = Worker(db, queue)
    worker.register("test", make_4stage_handler(tmp_path, []))
    queue.enqueue("test", {})
    worker.run_one()
    assert events[0] == "queued"
    assert events[-1] == "done"
    assert "running" in events
