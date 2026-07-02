from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cutlab.db import Database  # noqa: E402
from cutlab.jobs.queue import JobQueue  # noqa: E402


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    d = Database(tmp_path / "test.db")
    yield d
    d.close()


@pytest.fixture()
def queue(db: Database) -> JobQueue:
    return JobQueue(db)
