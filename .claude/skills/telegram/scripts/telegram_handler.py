"""
Telegram polling handler — long-polls for updates, routes commands and
inline-keyboard callbacks to the dashboard REST API.

Run standalone:  python telegram_handler.py
Or import and call run_forever() from a supervisor.

Env vars required:
  TELEGRAM_BOT_TOKEN    Bot token from @BotFather
  TELEGRAM_DASH_CHAT_ID Allowed chat_id (others are rejected)

Optional:
  DASHBOARD_URL         default http://127.0.0.1:8765
  CC_PROJECT_ROOT       project root (for messaging.yaml allow-list)
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_CHAT = os.environ.get("TELEGRAM_DASH_CHAT_ID", "")
DASHBOARD = os.environ.get("DASHBOARD_URL", "http://127.0.0.1:8765")
INSTALL_DIR = Path(__file__).parent.parent.parent.parent.parent  # project root heuristic

# Attempt to load allow-list from messaging.yaml
def _load_allowed_ids() -> set[str]:
    ids = set()
    if ALLOWED_CHAT:
        ids.add(str(ALLOWED_CHAT))
    yaml_path = Path(__file__).parent.parent / "references" / "messaging.yaml"
    if yaml_path.exists():
        try:
            for line in yaml_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("- "):
                    ids.add(line[2:].strip())
        except Exception:
            pass
    return ids


# ─── Telegram API helpers ────────────────────────────────────────────────────

def _tg(method: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/{method}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _send(chat_id: str, text: str, buttons: list | None = None):
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    try:
        _tg("sendMessage", payload)
    except Exception as e:
        log.warning("sendMessage failed: %s", e)


def _answer_callback(callback_id: str, text: str = ""):
    try:
        _tg("answerCallbackQuery", {"callback_id": callback_id, "text": text})
    except Exception:
        pass


# ─── Dashboard API helpers ───────────────────────────────────────────────────

def _dash_get(path: str) -> dict:
    with urllib.request.urlopen(f"{DASHBOARD}{path}", timeout=10) as resp:
        return json.loads(resp.read())


def _dash_post(path: str, body: dict | None = None) -> dict:
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(
        f"{DASHBOARD}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _dash_patch(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{DASHBOARD}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


# ─── Command handlers ────────────────────────────────────────────────────────

def handle_command(chat_id: str, text: str):
    cmd = text.split()[0].lower().lstrip("/")

    if cmd == "start":
        _send(chat_id,
              "<b>Command Centre</b>\n\n"
              "/status — system health\n"
              "/sessions — today's sessions\n"
              "/pending — pending decisions\n"
              "/tasks — task queue\n"
              "/stop — emergency stop\n"
              "/resume — resume after stop")

    elif cmd == "status":
        try:
            h = _dash_get("/api/system/health")
            s = _dash_get("/api/summary")
            lines = [
                f"<b>Command Centre</b>",
                f"Uptime: {h.get('uptime_s', '?')}s | Mem: {h.get('memory_mb', '?')}MB",
                f"Sessions today: {s.get('sessions_today', 0)}",
                f"Tokens today: {s.get('tokens_today', 0):,}",
                f"Tools today: {s.get('tools_today', 0)}",
            ]
            age = h.get("last_otel_age_s")
            if age:
                stale = " (stale)" if age > 120 else ""
                lines.append(f"Last OTEL: {int(age)}s ago{stale}")
            _send(chat_id, "\n".join(lines))
        except Exception as e:
            _send(chat_id, f"Error fetching status: {e}")

    elif cmd == "sessions":
        try:
            data = _dash_get("/api/sessions?range=today&page_size=5")
            rows = data.get("sessions", [])
            if not rows:
                _send(chat_id, "No sessions today.")
                return
            lines = [f"<b>Sessions today ({data.get('total', 0)} total)</b>"]
            for r in rows[:5]:
                title = (r.get("title") or "untitled")[:40]
                tokens = r.get("effective_tokens", 0) or 0
                lines.append(f"• {title} — {tokens:,} tokens")
            _send(chat_id, "\n".join(lines))
        except Exception as e:
            _send(chat_id, f"Error: {e}")

    elif cmd == "pending":
        try:
            data = _dash_get("/api/decisions?status=pending")
            decisions = data.get("decisions", [])
            if not decisions:
                _send(chat_id, "No pending decisions.")
                return
            for d in decisions[:3]:
                prompt = (d.get("prompt") or "")[:200]
                buttons = [[
                    {"text": "Mark answered", "callback_data": f"dash:dec_answer:{d['id']}"},
                ]]
                _send(chat_id, f"<b>Decision #{d['id']}</b>\n{prompt}", buttons)
        except Exception as e:
            _send(chat_id, f"Error: {e}")

    elif cmd == "tasks":
        try:
            data = _dash_get("/api/tasks")
            tasks = data.get("tasks", [])
            if not tasks:
                _send(chat_id, "No tasks.")
                return
            lines = [f"<b>Tasks ({len(tasks)})</b>"]
            for t in tasks[:8]:
                status = t.get("status", "?")
                title = (t.get("title") or "untitled")[:50]
                lines.append(f"• [{status}] {title}")
            _send(chat_id, "\n".join(lines))
        except Exception as e:
            _send(chat_id, f"Error: {e}")

    elif cmd == "stop":
        buttons = [[
            {"text": "CONFIRM STOP", "callback_data": "dash:emergency_stop:confirm"},
            {"text": "Cancel", "callback_data": "dash:emergency_stop:cancel"},
        ]]
        _send(chat_id,
              "<b>Emergency Stop</b>\nThis will terminate all running claude -p sessions. Confirm?",
              buttons)

    elif cmd == "resume":
        try:
            _dash_post("/api/system/emergency-resume")
            _send(chat_id, "Emergency stop cleared. Dispatcher can resume.")
        except Exception as e:
            _send(chat_id, f"Error: {e}")

    elif cmd == "attention":
        try:
            data = _dash_get("/api/attention")
            if data.get("all_clear"):
                _send(chat_id, "All clear — no issues.")
                return
            lines = ["<b>Attention required:</b>"]
            for issue in data.get("issues", []):
                lines.append(f"• {issue.get('message', issue.get('type', '?'))}")
            _send(chat_id, "\n".join(lines))
        except Exception as e:
            _send(chat_id, f"Error: {e}")

    else:
        _send(chat_id, f"Unknown command: /{cmd}\nType /start for help.")


# ─── Callback router ─────────────────────────────────────────────────────────

def handle_callback(chat_id: str, callback_id: str, data: str):
    _answer_callback(callback_id)

    parts = data.split(":")
    if len(parts) < 2 or parts[0] != "dash":
        return

    action = parts[1]

    if action == "task_approve" and len(parts) >= 3:
        task_id = parts[2]
        try:
            _dash_post(f"/api/tasks/{task_id}/approve")
            _send(chat_id, f"Task #{task_id} approved.")
        except Exception as e:
            _send(chat_id, f"Approve failed: {e}")

    elif action == "task_rerun" and len(parts) >= 3:
        task_id = parts[2]
        try:
            _dash_post(f"/api/tasks/{task_id}/rerun")
            _send(chat_id, f"Task #{task_id} queued for re-run.")
        except Exception as e:
            _send(chat_id, f"Re-run failed: {e}")

    elif action == "dec_answer" and len(parts) >= 3:
        dec_id = parts[2]
        _send(chat_id, f"Reply with the answer for decision #{dec_id}. Format:\n<code>answer:{dec_id}: your answer here</code>")

    elif action == "inbox_read" and len(parts) >= 3:
        msg_id = parts[2]
        try:
            _dash_post(f"/api/inbox/{msg_id}/read")
            _send(chat_id, "Message marked read.")
        except Exception as e:
            _send(chat_id, f"Error: {e}")

    elif action == "sched_disable" and len(parts) >= 3:
        sched_id = parts[2]
        try:
            _dash_patch(f"/api/schedules/{sched_id}", {"enabled": False})
            _send(chat_id, f"Schedule #{sched_id} disabled.")
        except Exception as e:
            _send(chat_id, f"Error: {e}")

    elif action == "emergency_stop":
        sub = parts[2] if len(parts) >= 3 else ""
        if sub == "confirm":
            try:
                result = _dash_post("/api/system/emergency-stop")
                killed = result.get("processes_killed", 0)
                _send(chat_id, f"Emergency stop executed. Killed {killed} process(es).")
            except Exception as e:
                _send(chat_id, f"Stop failed: {e}")
        else:
            _send(chat_id, "Cancelled.")

    elif action == "dismiss":
        _send(chat_id, "Dismissed.")

    else:
        _send(chat_id, f"Unknown action: {action}")


# ─── Inline text answers ─────────────────────────────────────────────────────

def handle_text(chat_id: str, text: str):
    # "answer:<decision_id>: <answer text>"
    if text.lower().startswith("answer:"):
        rest = text[7:].strip()
        if ":" in rest:
            dec_id_part, answer = rest.split(":", 1)
            dec_id = dec_id_part.strip()
            answer = answer.strip()
            if dec_id.isdigit() and answer:
                try:
                    _dash_post(f"/api/decisions/{dec_id}/answer", {"answer": answer})
                    _send(chat_id, f"Answer recorded for decision #{dec_id}.")
                except Exception as e:
                    _send(chat_id, f"Error: {e}")
                return
    # inbox reply: "reply:<session_id>: <message>"
    elif text.lower().startswith("reply:"):
        rest = text[6:].strip()
        if ":" in rest:
            msg_id_part, body = rest.split(":", 1)
            msg_id = msg_id_part.strip()
            body = body.strip()
            if msg_id.isdigit() and body:
                try:
                    _dash_post(f"/api/inbox/{msg_id}/reply", {"body": body})
                    _send(chat_id, f"Reply sent.")
                except Exception as e:
                    _send(chat_id, f"Error: {e}")
                return
    _send(chat_id, "Type /start for available commands.")


# ─── Update dispatcher ────────────────────────────────────────────────────────

def dispatch(update: dict, allowed: set[str]):
    msg = update.get("message") or update.get("edited_message")
    cb = update.get("callback_query")

    if cb:
        from_id = str(cb.get("from", {}).get("id", ""))
        if from_id not in allowed:
            log.debug("Rejected callback from %s", from_id)
            return
        chat_id = str(cb.get("message", {}).get("chat", {}).get("id", from_id))
        handle_callback(chat_id, cb["id"], cb.get("data", ""))
        return

    if msg:
        from_id = str(msg.get("from", {}).get("id", ""))
        chat_id = str(msg.get("chat", {}).get("id", ""))
        if from_id not in allowed:
            log.debug("Rejected message from %s", from_id)
            return
        text = msg.get("text", "")
        if text.startswith("/"):
            handle_command(chat_id, text)
        else:
            handle_text(chat_id, text)


# ─── Long-poll loop ───────────────────────────────────────────────────────────

def run_forever():
    if not TOKEN:
        log.error("TELEGRAM_BOT_TOKEN not set. Exiting.")
        return

    allowed = _load_allowed_ids()
    if not allowed:
        log.warning("No allowed chat IDs configured. All messages will be rejected.")

    log.info("Telegram handler starting. Allowed IDs: %s", allowed)
    offset = 0

    while True:
        try:
            result = _tg("getUpdates", {"timeout": 30, "offset": offset, "allowed_updates": ["message", "callback_query"]})
            for upd in result.get("result", []):
                offset = upd["update_id"] + 1
                try:
                    dispatch(upd, allowed)
                except Exception as e:
                    log.warning("Dispatch error: %s", e)
        except urllib.error.URLError as e:
            log.warning("Telegram poll error: %s", e)
            time.sleep(5)
        except Exception as e:
            log.error("Unexpected poll error: %s", e)
            time.sleep(10)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_forever()
