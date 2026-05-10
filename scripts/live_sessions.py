from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from db import get_conn

CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"
ACTIVE_WINDOW_MINUTES = 5


def get_live_sessions() -> list[dict]:
    conn = get_conn()
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(minutes=ACTIVE_WINDOW_MINUTES)).isoformat()

    rows = conn.execute("""
        SELECT s.session_id, s.title, s.cwd, s.model, s.started_at,
               s.total_tokens, s.ended_at,
               ls.state, ls.current_tool, ls.updated_at as state_updated_at
        FROM sessions s
        LEFT JOIN live_session_state ls ON s.session_id = ls.session_id
        WHERE s.started_at >= ? OR s.ended_at IS NULL
        ORDER BY s.started_at DESC
        LIMIT 20
    """, (cutoff,)).fetchall()

    results = []
    for r in rows:
        results.append(dict(r))
    return results


def get_session_state(session_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM live_session_state WHERE session_id=?", (session_id,)
    ).fetchone()
    return dict(row) if row else None


def write_session_state(session_id: str, state: str, current_tool: str | None = None) -> None:
    conn = get_conn()
    now = datetime.now(tz=timezone.utc).isoformat()
    with conn:
        conn.execute("""
            INSERT INTO live_session_state (session_id, state, current_tool, updated_at)
            VALUES (?,?,?,?)
            ON CONFLICT(session_id) DO UPDATE SET
                state=excluded.state, current_tool=excluded.current_tool, updated_at=excluded.updated_at
        """, (session_id, state, current_tool, now))


def get_tool_timeline(session_id: str) -> list[dict]:
    jsonl_path = _find_jsonl(session_id)
    if not jsonl_path:
        return []

    tool_starts: dict[str, dict] = {}
    timeline = []

    try:
        with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue

                etype = obj.get("type", "")
                if etype == "assistant":
                    content = obj.get("message", {}).get("content", [])
                    if isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "tool_use":
                                tuid = part["id"]
                                tool_starts[tuid] = {
                                    "id": tuid,
                                    "name": part.get("name"),
                                    "input_preview": json.dumps(part.get("input", {}))[:200],
                                    "started_at": obj.get("timestamp"),
                                }

                elif etype == "user":
                    content = obj.get("message", {}).get("content", [])
                    if isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "tool_result":
                                tuid = part.get("tool_use_id")
                                if tuid and tuid in tool_starts:
                                    entry = dict(tool_starts[tuid])
                                    entry["ended_at"] = obj.get("timestamp")
                                    entry["is_error"] = bool(part.get("is_error"))
                                    out = part.get("content", "")
                                    if isinstance(out, list):
                                        out = " ".join(p.get("text", "") for p in out if isinstance(p, dict))
                                    entry["output_preview"] = str(out)[:300]
                                    timeline.append(entry)
    except Exception:
        pass

    return timeline


def _find_jsonl(session_id: str) -> Path | None:
    if not CLAUDE_PROJECTS.exists():
        return None
    for project_dir in CLAUDE_PROJECTS.iterdir():
        f = project_dir / f"{session_id}.jsonl"
        if f.exists():
            return f
    return None
