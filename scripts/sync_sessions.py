from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from db import get_conn, init_db, new_conn

log = logging.getLogger(__name__)

CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"
MAX_TOOL_DURATION_MS = 10 * 60 * 1000  # 10 minutes cap


def _ts_to_epoch(ts: str) -> float | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return None


def _local_date(ts: str) -> str | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        local = dt.astimezone()
        return local.strftime("%Y-%m-%d")
    except Exception:
        return None


def _project_cwd_from_hash(project_dir: Path) -> str | None:
    name = project_dir.name
    # Decode C--Users-pawar-... back to C:\Users\pawar\...
    if name.startswith("C--"):
        decoded = name.replace("--", ":\\", 1).replace("-", "\\")
        # fix double backslash issues
        return decoded
    # fallback: replace double-dash with / for unix paths
    return "/" + name.replace("-", "/").lstrip("/")


def _extract_title(messages: list[dict]) -> str | None:
    for m in messages:
        if m.get("type") == "user":
            msg = m.get("message", {})
            content = msg.get("content", "")
            if isinstance(content, str) and content and not content.startswith("<"):
                return content[:120].strip()
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text = part.get("text", "")
                        if text and not text.startswith("<"):
                            return text[:120].strip()
    return None


def sync_session(jsonl_path: Path, conn=None) -> None:
    close_after = conn is None
    if conn is None:
        conn = new_conn()

    try:
        mtime = os.path.getmtime(jsonl_path)
        mtime_str = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

        # Check if we need to re-sync
        row = conn.execute(
            "SELECT synced_at, ended_at FROM sessions WHERE session_id=?",
            (jsonl_path.stem,),
        ).fetchone()
        if row and row["synced_at"] and row["ended_at"]:
            # Already complete sync — skip if file hasn't changed
            if row["synced_at"] >= mtime_str:
                return

        _parse_and_store(jsonl_path, conn, mtime_str)
        if close_after:
            conn.commit()
    except Exception as e:
        log.warning("Failed to sync %s: %s", jsonl_path, e)
    finally:
        if close_after:
            conn.close()


def _parse_and_store(jsonl_path: Path, conn: Any, mtime_str: str) -> None:
    session_id = jsonl_path.stem
    project_dir = jsonl_path.parent

    # Detect source
    source = "ide"
    if "cowork" in str(jsonl_path).lower():
        source = "cowork"

    # State tracking
    tool_starts: dict[str, dict] = {}  # tool_use_id -> {name, ts}
    messages: list[dict] = []
    cwd: str | None = None
    git_branch: str | None = None
    model: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    cost_usd = 0.0
    duration_ms: int | None = None
    stop_reason: str | None = None
    is_error = False
    error_count = 0
    rate_limit_hit = 0

    # Token accumulators (by model for daily rollup)
    token_by_model: dict[str, dict[str, int]] = {}

    total_input = 0
    total_output = 0
    total_cache_read = 0
    total_cache_create = 0

    try:
        with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
            raw_lines = f.readlines()
    except Exception as e:
        log.warning("Cannot read %s: %s", jsonl_path, e)
        return

    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        etype = obj.get("type", "")

        if etype == "user":
            if not started_at:
                started_at = obj.get("timestamp")
            if not cwd and obj.get("cwd"):
                cwd = obj.get("cwd")
            if not git_branch and obj.get("gitBranch"):
                git_branch = obj.get("gitBranch")
            messages.append(obj)

            # tool_result in content
            msg = obj.get("message", {})
            content = msg.get("content", [])
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "tool_result":
                        tuid = part.get("tool_use_id")
                        ts_result = obj.get("timestamp", "")
                        is_err = 1 if part.get("is_error") else 0
                        if tuid and tuid in tool_starts:
                            start_info = tool_starts[tuid]
                            dur = _calc_duration(start_info["ts"], ts_result)
                            _upsert_tool_call(
                                conn, session_id, tuid,
                                start_info["name"], start_info["ts"],
                                dur, is_err
                            )
                            if is_err:
                                error_count += 1

        elif etype == "assistant":
            msg = obj.get("message", {})
            if not model and msg.get("model"):
                model = msg.get("model")

            usage = msg.get("usage", {})
            inp = usage.get("input_tokens", 0) or 0
            out = usage.get("output_tokens", 0) or 0
            cr = usage.get("cache_read_input_tokens", 0) or 0
            cc = usage.get("cache_creation_input_tokens", 0) or 0

            total_input += inp
            total_output += out
            total_cache_read += cr
            total_cache_create += cc

            # Track by model for daily rollup
            m = msg.get("model") or model or "unknown"
            date_key = _local_date(obj.get("timestamp", "")) or "unknown"
            bucket_key = f"{date_key}|{m}"
            if bucket_key not in token_by_model:
                token_by_model[bucket_key] = {
                    "date": date_key, "model": m,
                    "input": 0, "output": 0, "cr": 0, "cc": 0
                }
            token_by_model[bucket_key]["input"] += inp
            token_by_model[bucket_key]["output"] += out
            token_by_model[bucket_key]["cr"] += cr
            token_by_model[bucket_key]["cc"] += cc

            content = msg.get("content", [])
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "tool_use":
                        tuid = part.get("id")
                        tname = part.get("name", "")
                        tts = obj.get("timestamp", "")
                        if tuid:
                            tool_starts[tuid] = {"name": tname, "ts": tts}

        elif etype == "result":
            ended_at = obj.get("timestamp") or ended_at
            cost_usd = obj.get("total_cost_usd") or 0.0
            duration_ms = obj.get("duration_ms")
            stop_reason = obj.get("stop_reason")
            is_error = bool(obj.get("is_error"))

        elif etype == "system" and obj.get("subtype") == "turn_duration":
            if not cwd and obj.get("cwd"):
                cwd = obj.get("cwd")
            if not git_branch and obj.get("gitBranch"):
                git_branch = obj.get("gitBranch")

    # Compute started_at from first user message timestamp if not set
    if not started_at and messages:
        started_at = messages[0].get("timestamp")

    title = _extract_title(messages)
    effective_tokens = total_input + total_output  # exclude cache overhead

    # Upsert session
    conn.execute("""
        INSERT INTO sessions (
            session_id, source, cwd, git_branch, model,
            started_at, ended_at,
            input_tokens, output_tokens, cache_read_tokens, cache_create_tokens,
            total_tokens, effective_tokens, cost_usd, duration_ms,
            error_count, rate_limit_hit, stop_reason, title, synced_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(session_id) DO UPDATE SET
            source=excluded.source, cwd=excluded.cwd, git_branch=excluded.git_branch,
            model=excluded.model, started_at=excluded.started_at, ended_at=excluded.ended_at,
            input_tokens=excluded.input_tokens, output_tokens=excluded.output_tokens,
            cache_read_tokens=excluded.cache_read_tokens, cache_create_tokens=excluded.cache_create_tokens,
            total_tokens=excluded.total_tokens, effective_tokens=excluded.effective_tokens,
            cost_usd=excluded.cost_usd, duration_ms=excluded.duration_ms,
            error_count=excluded.error_count, rate_limit_hit=excluded.rate_limit_hit,
            stop_reason=excluded.stop_reason, title=excluded.title, synced_at=excluded.synced_at
    """, (
        session_id, source, cwd, git_branch, model,
        started_at, ended_at,
        total_input, total_output, total_cache_read, total_cache_create,
        total_input + total_output + total_cache_read + total_cache_create,
        effective_tokens, cost_usd, duration_ms,
        error_count, rate_limit_hit, stop_reason, title, mtime_str
    ))

    # Token usage daily rollup
    for bucket in token_by_model.values():
        conn.execute("""
            INSERT INTO token_usage (date, model, source, input_tokens, output_tokens, cache_read_tokens, cache_create_tokens)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(date, model, source) DO UPDATE SET
                input_tokens=input_tokens+excluded.input_tokens,
                output_tokens=output_tokens+excluded.output_tokens,
                cache_read_tokens=cache_read_tokens+excluded.cache_read_tokens,
                cache_create_tokens=cache_create_tokens+excluded.cache_create_tokens
        """, (
            bucket["date"], bucket["model"], source,
            bucket["input"], bucket["output"], bucket["cr"], bucket["cc"]
        ))


def _calc_duration(ts_start: str, ts_end: str) -> int | None:
    s = _ts_to_epoch(ts_start)
    e = _ts_to_epoch(ts_end)
    if s is None or e is None:
        return None
    dur_ms = int((e - s) * 1000)
    if dur_ms < 0:
        return None
    return min(dur_ms, MAX_TOOL_DURATION_MS)


def _upsert_tool_call(conn, session_id, tool_use_id, tool_name, ts, duration_ms, error):
    conn.execute("""
        INSERT INTO tool_calls (session_id, tool_use_id, tool_name, ts, duration_ms, error)
        VALUES (?,?,?,?,?,?)
        ON CONFLICT(session_id, tool_use_id) DO UPDATE SET
            duration_ms=excluded.duration_ms, error=excluded.error
    """, (session_id, tool_use_id, tool_name, ts, duration_ms, error))


def scan_all(conn=None) -> int:
    close_after = conn is None
    if conn is None:
        conn = new_conn()

    count = 0
    try:
        if not CLAUDE_PROJECTS.exists():
            log.warning("~/.claude/projects not found at %s", CLAUDE_PROJECTS)
            return 0

        for project_dir in CLAUDE_PROJECTS.iterdir():
            if not project_dir.is_dir():
                continue
            for jsonl_file in project_dir.glob("*.jsonl"):
                try:
                    sync_session(jsonl_file, conn)
                    count += 1
                except Exception as e:
                    log.warning("Error syncing %s: %s", jsonl_file, e)
            # Also handle subagent dirs
            for sub_dir in project_dir.iterdir():
                if sub_dir.is_dir() and sub_dir.name.startswith("subagents"):
                    for jsonl_file in sub_dir.glob("*.jsonl"):
                        try:
                            sync_session(jsonl_file, conn)
                            count += 1
                        except Exception as e:
                            log.warning("Error syncing subagent %s: %s", jsonl_file, e)

        conn.commit()
        log.info("Synced %d sessions", count)
    except Exception as e:
        log.error("scan_all failed: %s", e)
    finally:
        if close_after:
            conn.close()

    return count


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    init_db()
    n = scan_all()
    print(f"Synced {n} sessions")
