from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from db import new_conn, init_db
from task_tracker import create_task
import dispatcher

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(os.environ.get("CC_PROJECT_ROOT", Path(__file__).parent.parent.parent.parent))


def _parse_cron_simple(expr: str, now: datetime) -> datetime | None:
    """Very basic cron parser: minute hour dom month dow."""
    try:
        parts = expr.strip().split()
        if len(parts) != 5:
            return None
        minute, hour, dom, month, dow = parts
        # Find next run — simple: try next 10080 minutes (1 week)
        from datetime import timedelta
        candidate = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        for _ in range(10080):
            if _matches(candidate, minute, hour, dom, month, dow):
                return candidate
            candidate += timedelta(minutes=1)
    except Exception:
        pass
    return None


def _matches(dt: datetime, minute: str, hour: str, dom: str, month: str, dow: str) -> bool:
    def _check(val: int, spec: str) -> bool:
        if spec == "*":
            return True
        try:
            return val == int(spec)
        except ValueError:
            pass
        if "/" in spec:
            _, step = spec.split("/", 1)
            return val % int(step) == 0
        if "," in spec:
            return str(val) in spec.split(",")
        if "-" in spec:
            lo, hi = spec.split("-", 1)
            return int(lo) <= val <= int(hi)
        return False

    return (
        _check(dt.minute, minute)
        and _check(dt.hour, hour)
        and _check(dt.day, dom)
        and _check(dt.month, month)
        and _check(dt.weekday(), dow)  # Mon=0..Sun=6
    )


def _materialize_schedules(conn) -> None:
    now = datetime.now(tz=timezone.utc)
    rows = conn.execute("""
        SELECT * FROM ops_schedules
        WHERE enabled=1 AND (next_run_at IS NULL OR next_run_at <= ?)
    """, (now.isoformat(),)).fetchall()

    for row in rows:
        try:
            # BEGIN IMMEDIATE prevents double-materialization
            conn.execute("BEGIN IMMEDIATE")
            # Re-check inside transaction
            r2 = conn.execute(
                "SELECT next_run_at FROM ops_schedules WHERE id=? AND enabled=1 AND (next_run_at IS NULL OR next_run_at <= ?)",
                (row["id"], now.isoformat())
            ).fetchone()
            if not r2:
                conn.execute("ROLLBACK")
                continue

            task_id = create_task(
                title=row["task_title"] or row["name"],
                description=row["task_description"],
                assigned_skill=row["assigned_skill"],
            )

            # Update next_run_at
            next_run = _parse_cron_simple(row["cron_expression"] or "0 9 * * 1-5", now)
            next_run_str = next_run.isoformat() if next_run else None

            conn.execute("""
                UPDATE ops_schedules SET last_run_at=?, next_run_at=? WHERE id=?
            """, (now.isoformat(), next_run_str, row["id"]))
            conn.execute("COMMIT")
            log.info("Materialized schedule '%s' → task %d", row["name"], task_id)
        except Exception as e:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            log.warning("Failed to materialize schedule %d: %s", row["id"], e)


def tick(once: bool = False) -> None:
    init_db()
    conn = new_conn()
    try:
        _materialize_schedules(conn)
        conn.commit()
        dispatcher.run_once()

        now = datetime.now(tz=timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO activities (event_type, detail, created_at) VALUES ('heartbeat', 'tick', ?)",
            (now,)
        )
        conn.commit()
        log.info("Heartbeat tick complete")
    except Exception as e:
        log.error("Heartbeat error: %s", e)
    finally:
        conn.close()


def run_loop() -> None:
    logging.basicConfig(level=logging.INFO)
    log.info("Mission Control heartbeat started")
    while True:
        tick()
        time.sleep(120)


if __name__ == "__main__":
    if "--once" in sys.argv:
        logging.basicConfig(level=logging.INFO)
        tick(once=True)
    else:
        run_loop()
