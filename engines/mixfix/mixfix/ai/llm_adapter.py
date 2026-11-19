"""LLM API adapter — the Autonomous System Mode brain (stdlib urllib, no SDK).

Implements the same task contract as the operator: given a request.json payload,
produce a result dict. Provider-pluggable; Anthropic Messages API by default.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


class LLMError(RuntimeError):
    pass


class LLMAdapter:
    def __init__(self, cfg: dict, api_key: str):
        self.cfg = cfg["llm"]
        self.api_key = api_key
        self.calls_made = 0

    def run_task(self, request: dict) -> dict:
        """Fulfill one AI task via the LLM API. Returns the result dict."""
        budget = self.cfg.get("max_calls_per_run", 200)
        if self.calls_made >= budget:
            raise LLMError(
                f"per-run API budget exhausted ({budget} calls) — pausing run")
        prompt = (
            f"{request['instructions']}\n\n"
            f"INPUT:\n{json.dumps(request['payload'], indent=2)}\n\n"
            "Respond with ONLY the JSON object, no prose, no code fences."
        )
        body = {
            "model": self.cfg["model"],
            "max_tokens": 8192,
            "messages": [{"role": "user", "content": prompt}],
        }
        req = urllib.request.Request(
            ANTHROPIC_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "content-type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise LLMError(f"LLM API error {e.code}: {e.read().decode()[:500]}") from e
        except urllib.error.URLError as e:
            raise LLMError(f"LLM API unreachable: {e.reason}") from e
        self.calls_made += 1
        text = "".join(b.get("text", "") for b in data.get("content", []))
        return _extract_json(text)


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        text = text[4:] if text.startswith("json") else text
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise LLMError(f"no JSON object in LLM response: {text[:200]}")
    return json.loads(text[start:end + 1])
