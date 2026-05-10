from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from db import get_conn, new_conn

log = logging.getLogger(__name__)


def get_mcp_servers(range_days: int = 7) -> list[dict]:
    conn = get_conn()
    cutoff = _cutoff(range_days)

    # Combine OTEL events (precise) and JSONL tool_calls (fallback)
    # SQLite lacks PERCENTILE_CONT; use MAX as p95 approximation per server
    rows = conn.execute("""
        SELECT
            mcp_server_name as server,
            COUNT(*) as total_calls,
            AVG(tool_duration_ms) as avg_latency,
            MAX(tool_duration_ms) as p95,
            SUM(CASE WHEN tool_success=0 THEN 1 ELSE 0 END) as errors
        FROM otel_events
        WHERE event_name='tool_result'
          AND mcp_server_name IS NOT NULL
          AND received_at >= ?
        GROUP BY mcp_server_name
        ORDER BY total_calls DESC
    """, (cutoff,)).fetchall()

    # Fallback: parse mcp__ prefixed tool names from tool_calls
    if not rows:
        rows = conn.execute("""
            SELECT
                substr(tool_name, 6, instr(substr(tool_name, 6), '__') - 1) as server,
                COUNT(*) as total_calls,
                AVG(duration_ms) as avg_latency,
                MAX(duration_ms) as p95,
                SUM(error) as errors
            FROM tool_calls
            WHERE tool_name LIKE 'mcp__%'
              AND ts >= ?
            GROUP BY server
            HAVING server != ''
            ORDER BY total_calls DESC
        """, (cutoff,)).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d["avg_latency"] = round(d.get("avg_latency") or 0, 1)
        d["p95"] = round(d.get("p95") or 0, 1)
        result.append(d)
    return result


def get_mcp_server_tools(server: str, range_days: int = 7) -> list[dict]:
    conn = get_conn()
    cutoff = _cutoff(range_days)

    # Try OTEL first
    rows = conn.execute("""
        SELECT
            mcp_tool_name as tool,
            COUNT(*) as calls,
            AVG(tool_duration_ms) as p50,
            MAX(tool_duration_ms) as p95_max,
            MAX(tool_duration_ms) as max_ms,
            SUM(CASE WHEN tool_success=0 THEN 1 ELSE 0 END) as errors
        FROM otel_events
        WHERE event_name='tool_result'
          AND mcp_server_name=?
          AND received_at >= ?
        GROUP BY mcp_tool_name
        ORDER BY calls DESC
    """, (server, cutoff)).fetchall()

    if not rows:
        # Fallback: tool_calls with mcp__<server>__<tool> pattern
        prefix = f"mcp__{server}__"
        rows = conn.execute("""
            SELECT
                substr(tool_name, ?) as tool,
                COUNT(*) as calls,
                AVG(duration_ms) as p50,
                MAX(duration_ms) as max_ms,
                MAX(duration_ms) as p95_max,
                SUM(error) as errors
            FROM tool_calls
            WHERE tool_name LIKE ?
              AND ts >= ?
            GROUP BY tool
            ORDER BY calls DESC
        """, (len(prefix) + 1, prefix + "%", cutoff)).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d["p50"] = round(d.get("p50") or 0, 1)
        d["p95"] = round(d.get("p95_max") or d.get("max_ms") or 0, 1)
        d["max_ms"] = round(d.get("max_ms") or 0, 1)
        d["error_rate"] = round(d["errors"] / max(d["calls"], 1), 3)
        result.append(d)
    return result


def _cutoff(range_days: int) -> str:
    from datetime import timedelta
    dt = datetime.now(tz=timezone.utc) - timedelta(days=range_days)
    return dt.isoformat()
