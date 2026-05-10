from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_DASH_CHAT_ID")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://127.0.0.1:8765")


def tick():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        from db import new_conn
        conn = new_conn()
        try:
            _check_decisions(conn)
            _check_approvals(conn)
            _check_failed_tasks(conn)
            _check_overdue_schedules(conn)
            _check_inbox(conn)
            conn.commit()
            _log_heartbeat(conn)
        finally:
            conn.close()
    except Exception as e:
        log.warning("Notifier tick error: %s", e)


def _check_decisions(conn):
    rows = conn.execute(
        "SELECT id, prompt FROM ops_decisions WHERE status='pending'"
    ).fetchall()
    for r in rows:
        key = f"decision_{r['id']}"
        if _already_notified(conn, "decision_pending", key):
            continue
        text = f"Decision waiting:\n{r['prompt'][:300]}"
        buttons = [
            [{"text": "Mark answered", "callback_data": f"dash:dec_answer:{r['id']}"}],
            [{"text": "Snooze 30m", "callback_data": f"dash:snooze:decision_pending:{key}"}],
        ]
        msg_id = _send_message(text, buttons)
        _record_notification(conn, "decision_pending", key, msg_id)


def _check_approvals(conn):
    rows = conn.execute(
        "SELECT id, title FROM ops_tasks WHERE status='awaiting_approval'"
    ).fetchall()
    for r in rows:
        key = f"task_{r['id']}"
        if _already_notified(conn, "task_approval", key):
            continue
        text = f"Approval needed:\n{r['title']}"
        buttons = [
            [{"text": "Approve", "callback_data": f"dash:task_approve:{r['id']}"}],
            [{"text": "Dismiss", "callback_data": f"dash:dismiss:task_approval:{key}"}],
        ]
        msg_id = _send_message(text, buttons)
        _record_notification(conn, "task_approval", key, msg_id)


def _check_failed_tasks(conn):
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(hours=24)).isoformat()
    rows = conn.execute(
        "SELECT id, title, error_message FROM ops_tasks WHERE status='failed' AND completed_at >= ?",
        (cutoff,)
    ).fetchall()
    for r in rows:
        key = f"task_{r['id']}_failed"
        if _already_notified(conn, "task_failed", key):
            continue
        text = f"Task failed: {r['title']}\n{(r['error_message'] or '')[:200]}"
        buttons = [
            [{"text": "Re-run", "callback_data": f"dash:task_rerun:{r['id']}"}],
            [{"text": "Dismiss", "callback_data": f"dash:dismiss:task_failed:{key}"}],
        ]
        msg_id = _send_message(text, buttons)
        _record_notification(conn, "task_failed", key, msg_id)


def _check_overdue_schedules(conn):
    rows = conn.execute("""
        SELECT id, name FROM ops_schedules
        WHERE enabled=1 AND next_run_at IS NOT NULL AND next_run_at < datetime('now', '-5 minutes')
    """).fetchall()
    for r in rows:
        key = f"sched_{r['id']}"
        if _already_notified(conn, "schedule_overdue", key):
            continue
        text = f"Schedule overdue: {r['name']}"
        buttons = [
            [{"text": "Disable", "callback_data": f"dash:sched_disable:{r['id']}"}],
            [{"text": "Dismiss", "callback_data": f"dash:dismiss:schedule_overdue:{key}"}],
        ]
        msg_id = _send_message(text, buttons)
        _record_notification(conn, "schedule_overdue", key, msg_id)


def _check_inbox(conn):
    rows = conn.execute(
        "SELECT id, body FROM ops_inbox WHERE read=0 AND direction='agent_to_user'"
    ).fetchall()
    for r in rows:
        key = f"inbox_{r['id']}"
        if _already_notified(conn, "inbox_unread", key):
            continue
        text = f"Inbox: {r['body'][:300]}"
        buttons = [
            [{"text": "Mark read", "callback_data": f"dash:inbox_read:{r['id']}"}],
        ]
        msg_id = _send_message(text, buttons)
        _record_notification(conn, "inbox_unread", key, msg_id)


def _already_notified(conn, event_type: str, event_key: str) -> bool:
    row = conn.execute("""
        SELECT snoozed_until FROM notification_log
        WHERE event_type=? AND event_key=? AND chat_id=?
    """, (event_type, event_key, TELEGRAM_CHAT_ID)).fetchone()
    if not row:
        return False
    snooze = row["snoozed_until"]
    if snooze:
        try:
            snooze_dt = datetime.fromisoformat(snooze.replace("Z", "+00:00"))
            if datetime.now(tz=timezone.utc) < snooze_dt:
                return True  # Still snoozed
        except Exception:
            pass
    return True  # Already notified, not snoozed


def _record_notification(conn, event_type: str, event_key: str, msg_id: int | None):
    now = datetime.now(tz=timezone.utc).isoformat()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO notification_log (event_type, event_key, chat_id, telegram_message_id, sent_at)
            VALUES (?,?,?,?,?)
        """, (event_type, event_key, TELEGRAM_CHAT_ID, msg_id, now))
    except Exception as e:
        log.warning("Failed to record notification: %s", e)


def _send_message(text: str, buttons: list | None = None) -> int | None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return None
    try:
        import urllib.request
        payload: dict = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
        if buttons:
            payload["reply_markup"] = {"inline_keyboard": buttons}
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            return result.get("result", {}).get("message_id")
    except Exception as e:
        log.warning("Telegram send failed: %s", e)
        return None


def _log_heartbeat(conn):
    now = datetime.now(tz=timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO activities (event_type, detail, created_at) VALUES ('notifier_heartbeat', 'tick', ?)",
        (now,)
    )
