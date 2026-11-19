"""Optional Telegram approval surface (P4) for CutLab proposals.

Follows the owner's telegram-gate conventions: the pipeline never blocks on a
human — a compaction job proposes a revision and (when Telegram is configured)
sends ONE gate request; tapping Approve/Reject calls the same engine
accept_proposal/reject_proposal the Studio uses. The bot stays thin: the
engine owns what a decision means. Idempotent: the second tap on a decided
gate gets "already decided". Unauthorized taps are ignored silently.

callback_data: g|<project_id>:<rev>|<gate>|<decision>   (fits Telegram's 64B)

Transport is injected so the full round-trip is unit-testable without a live
bot token; production uses httpx against api.telegram.org.

Config (env): CUTLAB_TELEGRAM_TOKEN, CUTLAB_TELEGRAM_CHAT_ID,
CUTLAB_TELEGRAM_APPROVERS (comma-separated user ids).

Standalone poller: `python -m cutlab.gates.telegram`
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Callable

from ..edl.engine import Conflict, Engine, NotFound, Rejected

log = logging.getLogger("cutlab.telegram")

TOKEN = os.environ.get("CUTLAB_TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CUTLAB_TELEGRAM_CHAT_ID", "")
APPROVERS = {
    int(x) for x in os.environ.get("CUTLAB_TELEGRAM_APPROVERS", "").split(",")
    if x.strip().isdigit()
}

Transport = Callable[[str, dict[str, Any]], dict[str, Any]]


def configured() -> bool:
    return bool(TOKEN and CHAT_ID)


def _http_transport(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    import httpx

    resp = httpx.post(
        f"https://api.telegram.org/bot{TOKEN}/{method}", json=payload, timeout=30
    )
    data = resp.json()
    if not data.get("ok"):
        log.warning("telegram %s failed: %s", method, str(data)[:200])
    return data


class TelegramGate:
    def __init__(self, engine: Engine, transport: Transport | None = None,
                 chat_id: str | None = None, approvers: set[int] | None = None):
        self.engine = engine
        self.transport = transport or _http_transport
        self.chat_id = chat_id if chat_id is not None else CHAT_ID
        self.approvers = approvers if approvers is not None else APPROVERS

    # -- outbound -------------------------------------------------------------

    def send_proposal_gate(self, project_id: str, rev: int, gate: str,
                           summary: str, evidence: str) -> dict[str, Any]:
        """Gate request per the house format: outcome first, real evidence,
        one decision per message."""
        project = self.engine.get_project(project_id)
        text = (
            f"🔶 GATE — {project['name']} / {gate}\n"
            f"Run: {project_id} r{rev}\n"
            f"{summary}\n{evidence}"
        )
        cb = f"g|{project_id}:{rev}|{gate}"
        return self.transport("sendMessage", {
            "chat_id": self.chat_id,
            "text": text,
            "reply_markup": {"inline_keyboard": [[
                {"text": "✅ Approve", "callback_data": f"{cb}|approve"},
                {"text": "❌ Reject", "callback_data": f"{cb}|reject"},
            ]]},
        })

    def send_report(self, text: str) -> None:
        """Informational stage report (no buttons)."""
        self.transport("sendMessage", {"chat_id": self.chat_id, "text": text})

    # -- inbound --------------------------------------------------------------

    def handle_update(self, update: dict[str, Any]) -> str:
        """Process one getUpdates entry. Returns a short outcome string
        (for logs/tests): applied | already-decided | unauthorized | ignored."""
        cq = update.get("callback_query")
        if not cq:
            return "ignored"
        data = str(cq.get("data", ""))
        parts = data.split("|")
        if len(parts) != 4 or parts[0] != "g":
            return "ignored"
        _, run_ref, gate, decision = parts
        from_id = int(cq.get("from", {}).get("id", 0))
        if self.approvers and from_id not in self.approvers:
            return "unauthorized"  # silently ignored per convention

        # Ack immediately, always.
        self.transport("answerCallbackQuery", {"callback_query_id": cq.get("id", "")})

        project_id, _, rev_s = run_ref.partition(":")
        rev = int(rev_s)
        try:
            if decision == "approve":
                self.engine.accept_proposal(project_id, rev)
                outcome = f"✅ Approved r{rev}"
            else:
                self.engine.reject_proposal(project_id, rev)
                outcome = f"❌ Rejected r{rev}"
            result = "applied"
        except Rejected as e:
            # E_STATE: someone (Studio or an earlier tap) already decided.
            if e.issues and e.issues[0].code == "E_STATE":
                outcome = f"already decided (r{rev})"
                result = "already-decided"
            else:
                outcome = f"⚠ {e.issues[0].message if e.issues else 'rejected'}"
                result = "error"
        except Conflict:
            outcome = f"⚠ stale proposal r{rev} (head moved)"
            result = "error"
        except NotFound:
            outcome = f"⚠ unknown proposal r{rev}"
            result = "error"

        # Edit the original message: decision state shown, buttons removed.
        msg = cq.get("message", {})
        if msg.get("message_id"):
            who = cq.get("from", {}).get("first_name", "approver")
            self.transport("editMessageText", {
                "chat_id": msg.get("chat", {}).get("id", self.chat_id),
                "message_id": msg["message_id"],
                "text": f"{msg.get('text', '')}\n\n{outcome} by {who}",
            })
        return result

    # -- polling runner ---------------------------------------------------------

    def run_polling(self, stop: Callable[[], bool] = lambda: False) -> None:
        offset = 0
        while not stop():
            data = self.transport("getUpdates", {"offset": offset, "timeout": 25})
            for upd in data.get("result", []):
                offset = max(offset, upd.get("update_id", 0) + 1)
                try:
                    self.handle_update(upd)
                except Exception:  # noqa: BLE001 - keep polling
                    log.exception("update handling failed")
            time.sleep(0.5)


def main() -> None:  # pragma: no cover - standalone entry
    from .. import config
    from ..db import Database

    logging.basicConfig(level=logging.INFO)
    if not configured():
        raise SystemExit(
            "Set CUTLAB_TELEGRAM_TOKEN and CUTLAB_TELEGRAM_CHAT_ID to run the gate poller."
        )
    db = Database(config.DB_PATH)
    engine = Engine(db, projects_dir=config.PROJECTS_DIR)
    TelegramGate(engine).run_polling()


if __name__ == "__main__":  # pragma: no cover
    main()
