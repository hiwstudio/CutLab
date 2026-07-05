"""LLM backends for the director (P2), pluggable per config.LLM_BACKEND.

- manual: no synchronous completion — the director writes the prompt to a file
  and a human (or Claude) drops an answer back; free, no key, crash-resumable.
  Represented here by MANUAL (a sentinel), handled specially in director.py.
- openrouter / anthropic: automatic HTTP calls; the key comes from the env and is
  never stored or logged by CutLab.
- fake: returns a canned completion (tests).

Plan parsing tolerates the model wrapping JSON in prose or ```json fences.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Protocol

from .. import config


class LLMError(Exception):
    pass


class LLMBackend(Protocol):
    manual: bool

    def complete(self, system: str, user: str) -> str: ...


class ManualBackend:
    """Sentinel backend: the director splits into write-prompt / accept-answer."""

    manual = True

    def complete(self, system: str, user: str) -> str:  # pragma: no cover
        raise LLMError("manual backend has no synchronous completion")


class FakeBackend:
    """Injectable test backend: returns a fixed string (or a callable's result)."""

    manual = False

    def __init__(self, response: str | Callable[[str, str], str]):
        self._response = response

    def complete(self, system: str, user: str) -> str:
        return self._response(system, user) if callable(self._response) else self._response


class OpenRouterBackend:
    manual = False

    def __init__(self, api_key: str, model: str, base_url: str):
        if not api_key:
            raise LLMError("OPENROUTER_API_KEY is not set")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def complete(self, system: str, user: str) -> str:
        import httpx

        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
            },
            timeout=120,
        )
        if resp.status_code != 200:
            raise LLMError(f"OpenRouter {resp.status_code}: {resp.text[:300]}")
        return resp.json()["choices"][0]["message"]["content"]


class AnthropicBackend:
    manual = False

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        self.api_key = api_key
        # Map an openrouter-style id to a bare Anthropic model id if needed.
        self.model = model.split("/")[-1] if "/" in model else model

    def complete(self, system: str, user: str) -> str:
        import httpx

        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 1500,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=120,
        )
        if resp.status_code != 200:
            raise LLMError(f"Anthropic {resp.status_code}: {resp.text[:300]}")
        return resp.json()["content"][0]["text"]


def make_backend(backend: str | None = None) -> LLMBackend:
    backend = (backend or config.LLM_BACKEND).lower()
    if backend == "manual":
        return ManualBackend()
    if backend == "openrouter":
        return OpenRouterBackend(config.OPENROUTER_API_KEY, config.LLM_MODEL,
                                 config.OPENROUTER_BASE_URL)
    if backend == "anthropic":
        return AnthropicBackend(config.ANTHROPIC_API_KEY, config.LLM_MODEL)
    raise LLMError(f"unknown LLM backend '{backend}'")


_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def parse_plan(raw: str) -> tuple[list[dict[str, Any]], str]:
    """Extract (ops, note) from an LLM completion. Accepts a bare JSON object or
    one wrapped in a ```json fence / surrounding prose. Raises LLMError on
    anything that isn't a JSON object with an `ops` list."""
    text = raw.strip()
    obj = None
    # 1. bare JSON object.
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        pass
    # 2. fenced JSON.
    if obj is None:
        m = _FENCE_RE.search(text)
        if m:
            try:
                obj = json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
    # 3. first {...} span.
    if obj is None:
        start, end = text.find("{"), text.rfind("}")
        if 0 <= start < end:
            try:
                obj = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    if not isinstance(obj, dict) or not isinstance(obj.get("ops"), list):
        raise LLMError("could not parse an ops plan from the model output")
    ops = obj["ops"]
    if not all(isinstance(o, dict) and "op" in o for o in ops):
        raise LLMError("plan contains an entry that is not an op object")
    return ops, str(obj.get("note", ""))
