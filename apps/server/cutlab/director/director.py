"""Director orchestration (P2): natural-language command -> ops plan -> proposal.

The plan is always applied in `propose` mode, so the human accepts or rejects it
(A2.3) — the director can never silently commit an edit. Backends:
  - automatic (openrouter/anthropic/fake): command() calls the LLM and proposes.
  - manual: command() writes the prompt to a file and returns AwaitingAnswer;
    answer() parses the dropped-in answer and proposes. Request state lives in
    `director/{request_id}.prompt.txt` (and .answer.txt), so it survives a crash.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from ..edl.engine import Engine, Rejected
from ..edl.schema import EDL
from ..understanding.schema import Understanding
from . import backends
from .backends import LLMBackend, LLMError, parse_plan
from .context import SYSTEM_PROMPT, build_prompt


@dataclass
class Proposed:
    status: str  # "proposed"
    rev: int
    summary: str
    note: str


@dataclass
class AwaitingAnswer:
    status: str  # "awaiting_answer"
    request_id: str
    prompt: str
    prompt_path: str


@dataclass
class PlanRejected:
    status: str  # "rejected"
    issues: list[dict]
    note: str


DirectorResult = Proposed | AwaitingAnswer | PlanRejected

_RID_RE = re.compile(r"^dir_[a-z0-9]{8,32}$")


class Director:
    def __init__(self, engine: Engine, projects_dir: Path, backend: LLMBackend | None = None):
        self.engine = engine
        self.projects_dir = projects_dir
        self.backend = backend or backends.make_backend()

    # -- public ---------------------------------------------------------------

    def command(self, project_id: str, text: str) -> DirectorResult:
        if not text.strip():
            raise LLMError("empty command")
        edl, understanding = self._load(project_id)
        prompt = build_prompt(edl, understanding, text)

        if getattr(self.backend, "manual", False):
            rid = "dir_" + uuid.uuid4().hex[:16]
            path = self._prompt_path(project_id, rid)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(SYSTEM_PROMPT + "\n\n---\n\n" + prompt, encoding="utf-8")
            return AwaitingAnswer("awaiting_answer", rid, prompt, str(path))

        raw = self.backend.complete(SYSTEM_PROMPT, prompt)
        ops, note = parse_plan(raw)
        return self._propose(project_id, ops, note)

    def answer(self, project_id: str, request_id: str, answer_text: str) -> DirectorResult:
        if not _RID_RE.match(request_id):
            raise LLMError("invalid request id")
        # Persist the answer next to the prompt (provenance / crash-resume).
        apath = self._answer_path(project_id, request_id)
        if apath.parent.exists():
            apath.write_text(answer_text, encoding="utf-8")
        ops, note = parse_plan(answer_text)
        return self._propose(project_id, ops, note)

    # -- internals ------------------------------------------------------------

    def _propose(self, project_id: str, ops: list[dict], note: str) -> DirectorResult:
        head = self.engine.get_project(project_id)["head_rev"]
        try:
            result = self.engine.apply(project_id, head, ops, mode="propose")
        except Rejected as e:
            return PlanRejected("rejected", [i.to_dict() for i in e.issues], note)
        return Proposed("proposed", result["rev"], result["summary"], note)

    def _load(self, project_id: str) -> tuple[EDL, dict[str, Understanding]]:
        edl = EDL.model_validate(self.engine.get_edl(project_id))
        understanding: dict[str, Understanding] = {}
        base = self.projects_dir / project_id
        for aid, asset in edl.assets.items():
            if not asset.understanding:
                continue
            p = base / asset.understanding
            if p.is_file():
                try:
                    understanding[aid] = Understanding.model_validate_json(
                        p.read_text(encoding="utf-8")
                    )
                except Exception:
                    pass
        return edl, understanding

    def _dir(self, project_id: str) -> Path:
        return self.projects_dir / project_id / "director"

    def _prompt_path(self, project_id: str, rid: str) -> Path:
        return self._dir(project_id) / f"{rid}.prompt.txt"

    def _answer_path(self, project_id: str, rid: str) -> Path:
        return self._dir(project_id) / f"{rid}.answer.txt"
