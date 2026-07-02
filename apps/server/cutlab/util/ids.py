"""ID generation. All entity ids are prefix_[a-z0-9]{n} per the EDL spec."""
from __future__ import annotations

import secrets
import uuid

_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


def _token(n: int) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def new_project_id() -> str:
    return f"proj_{_token(8)}"


def new_asset_id() -> str:
    return f"ast_{_token(8)}"


def new_track_id() -> str:
    return f"trk_{_token(8)}"


def new_clip_id() -> str:
    return f"clp_{_token(8)}"


def new_job_id() -> str:
    return f"job_{uuid.uuid4()}"
