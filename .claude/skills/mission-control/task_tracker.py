from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from db import get_conn, new_conn


def create_task(
    title: str,
    description: str | None = None,
    priority: int = 50,
    assigned_skill: str | None = None,
    scheduled_for: str | None = None,
    model: str | None = None,
    execution_mode: str = "stream",
    quadrant: str = "do",
    requires_approval: bool = False,
    risk_level: str = "low",
    dry_run: bool = False,
) -> int:
    conn = new_conn()
    now = datetime.now(tz=timezone.utc).isoformat()
    try:
        with conn:
            cur = conn.execute("""
                INSERT INTO ops_tasks (
                    title, description, priority, assigned_skill, scheduled_for,
                    model, execution_mode, quadrant, requires_approval, risk_level,
                    dry_run, status, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'pending',?)
            """, (
                title, description, priority, assigned_skill, scheduled_for,
                model, execution_mode, quadrant,
                1 if requires_approval else 0, risk_level,
                1 if dry_run else 0, now,
            ))
            return cur.lastrowid
    finally:
        conn.close()


def claim_pending(task_id: int) -> dict | None:
    conn = new_conn()
    try:
        with conn:
            cur = conn.execute("""
                UPDATE ops_tasks SET status='running', started_at=?
                WHERE id=? AND status='pending'
            """, (datetime.now(tz=timezone.utc).isoformat(), task_id))
            if cur.rowcount == 0:
                return None
            row = conn.execute("SELECT * FROM ops_tasks WHERE id=?", (task_id,)).fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def update_task(task_id: int, **kwargs) -> None:
    conn = new_conn()
    allowed = {"status", "output_summary", "error_message", "session_id",
               "started_at", "completed_at", "duration_ms", "cost_usd", "pid"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k}=?" for k in updates)
    try:
        with conn:
            conn.execute(f"UPDATE ops_tasks SET {set_clause} WHERE id=?", list(updates.values()) + [task_id])
    finally:
        conn.close()


def complete_task(task_id: int, output: str | None = None, cost_usd: float | None = None) -> None:
    conn = new_conn()
    now = datetime.now(tz=timezone.utc).isoformat()
    row = conn.execute("SELECT started_at FROM ops_tasks WHERE id=?", (task_id,)).fetchone()
    dur = None
    if row and row["started_at"]:
        try:
            start_dt = datetime.fromisoformat(row["started_at"].replace("Z", "+00:00"))
            dur = int((datetime.now(tz=timezone.utc) - start_dt).total_seconds() * 1000)
        except Exception:
            pass
    try:
        with conn:
            conn.execute("""
                UPDATE ops_tasks SET status='done', completed_at=?, duration_ms=?, output_summary=?, cost_usd=?
                WHERE id=?
            """, (now, dur, output, cost_usd, task_id))
    finally:
        conn.close()


def fail_task(task_id: int, error: str) -> None:
    conn = new_conn()
    now = datetime.now(tz=timezone.utc).isoformat()
    try:
        with conn:
            conn.execute("""
                UPDATE ops_tasks
                SET status='failed', error_message=?, completed_at=?,
                    consecutive_failures=consecutive_failures+1
                WHERE id=?
            """, (error, now, task_id))
    finally:
        conn.close()


def get_pending_tasks(limit: int = 10) -> list[dict]:
    conn = new_conn()
    try:
        rows = conn.execute("""
            SELECT * FROM ops_tasks
            WHERE status IN ('pending')
              AND (scheduled_for IS NULL OR scheduled_for <= datetime('now'))
            ORDER BY priority DESC, created_at ASC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
