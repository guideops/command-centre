from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, AsyncGenerator

import psutil
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).parent))
from db import get_conn, init_db, new_conn
from sync_sessions import scan_all
from sync_skills import sync_skills
from live_sessions import get_live_sessions, get_session_state, write_session_state, get_tool_timeline
from mcp_analyzer import get_mcp_servers, get_mcp_server_tools

log = logging.getLogger(__name__)

PORT = int(os.environ.get("CC_PORT", "8765"))
PROJECT_ROOT = Path(os.environ.get("CC_PROJECT_ROOT", Path(__file__).parent.parent))
UI_DIST = PROJECT_ROOT / "ui" / "dist"
QUEUE_DIR = PROJECT_ROOT / ".tmp" / "mission-control-queue"
MAX_RETRIES = int(os.environ.get("CLAUDE_CODE_MAX_RETRIES", "10"))

_start_time = time.time()
_last_otel_event: float | None = None
_last_sync: float | None = None
_last_notifier: float | None = None


# ─── Lifespan ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log.info("DB initialized")

    # Initial sync
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _do_sync)

    # Background loops
    sync_task = asyncio.create_task(_sync_loop())
    notifier_task = asyncio.create_task(_notifier_loop())

    yield

    sync_task.cancel()
    notifier_task.cancel()


def _do_sync():
    global _last_sync
    try:
        conn = new_conn()
        scan_all(conn)
        sync_skills(conn)
        _last_sync = time.time()
    except Exception as e:
        log.error("Sync error: %s", e)


async def _sync_loop():
    global _last_sync
    while True:
        await asyncio.sleep(120)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _do_sync)


async def _notifier_loop():
    global _last_notifier
    while True:
        await asyncio.sleep(30)
        try:
            notifier_path = PROJECT_ROOT / "scripts" / "notifier.py"
            if notifier_path.exists():
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, _run_notifier_tick)
            _last_notifier = time.time()
        except Exception as e:
            log.warning("Notifier tick error: %s", e)


def _run_notifier_tick():
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("notifier", PROJECT_ROOT / "scripts" / "notifier.py")
        if spec:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "tick"):
                mod.tick()
    except Exception as e:
        log.warning("Notifier module error: %s", e)


app = FastAPI(title="Command Centre", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── OTEL ingest ─────────────────────────────────────────────────────────────

@app.post("/v1/logs")
async def ingest_logs(request: Request):
    global _last_otel_event
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"status": "ok", "dropped": 0})

    drops = 0
    conn = new_conn()
    try:
        resource_logs = body.get("resourceLogs", [])
        now = datetime.now(tz=timezone.utc).isoformat()
        for rl in resource_logs:
            for sl in rl.get("scopeLogs", []):
                for lr in sl.get("logRecords", []):
                    try:
                        _ingest_log_record(conn, lr, now)
                        _last_otel_event = time.time()
                    except Exception as e:
                        log.debug("Drop log record: %s", e)
                        drops += 1
        conn.commit()
    finally:
        conn.close()

    return JSONResponse({"status": "ok", "dropped": drops})


def _parse_attributes(attrs: list) -> dict:
    result = {}
    for a in attrs:
        k = a.get("key", "")
        v = a.get("value", {})
        if "stringValue" in v:
            result[k] = v["stringValue"]
        elif "intValue" in v:
            result[k] = int(v["intValue"])
        elif "doubleValue" in v:
            result[k] = float(v["doubleValue"])
        elif "boolValue" in v:
            result[k] = bool(v["boolValue"])
    return result


def _ingest_log_record(conn, lr: dict, now: str):
    attrs = _parse_attributes(lr.get("attributes", []))
    event_name = attrs.get("event.name", "")
    ts_ns = lr.get("timeUnixNano", "0")
    try:
        ts_s = int(ts_ns) / 1e9
        ts_iso = datetime.fromtimestamp(ts_s, tz=timezone.utc).isoformat()
    except Exception:
        ts_iso = now

    # Parse tool_parameters for MCP tools
    mcp_server_name = attrs.get("mcp_server_name")
    mcp_tool_name = attrs.get("mcp_tool_name")
    if not mcp_server_name and attrs.get("tool_name") == "mcp_tool":
        try:
            tp = json.loads(attrs.get("tool_parameters", "{}"))
            mcp_server_name = tp.get("mcp_server_name")
            mcp_tool_name = tp.get("mcp_tool_name")
        except Exception:
            pass
    if not mcp_server_name:
        tn = attrs.get("tool_name", "")
        if tn.startswith("mcp__"):
            parts = tn.split("__", 2)
            if len(parts) == 3:
                mcp_server_name = parts[1]
                mcp_tool_name = parts[2]

    conn.execute("""
        INSERT INTO otel_events (
            event_name, session_id, prompt_id, timestamp, model,
            tool_name, tool_success, tool_duration_ms, tool_error,
            cost_usd, api_duration_ms, input_tokens, output_tokens,
            cache_read_tokens, cache_create_tokens, speed,
            error_message, status_code, attempt_count,
            skill_name, skill_source, prompt_length,
            decision, decision_source, request_id, tool_result_size_bytes,
            mcp_server_scope, plugin_name, plugin_version, marketplace_name,
            install_trigger, mcp_server_name, mcp_tool_name, received_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        event_name,
        attrs.get("session_id"),
        attrs.get("prompt_id"),
        ts_iso,
        attrs.get("model"),
        attrs.get("tool_name"),
        _int(attrs.get("tool_success")),
        _float(attrs.get("tool_duration_ms")),
        attrs.get("tool_error"),
        _float(attrs.get("cost_usd")),
        _float(attrs.get("api_duration_ms")),
        _int(attrs.get("input_tokens")),
        _int(attrs.get("output_tokens")),
        _int(attrs.get("cache_read_tokens")),
        _int(attrs.get("cache_create_tokens")),
        attrs.get("speed"),
        attrs.get("error_message"),
        _int(attrs.get("status_code")),
        _int(attrs.get("attempt_count")),
        attrs.get("skill_name"),
        attrs.get("skill_source"),
        _int(attrs.get("prompt_length")),
        attrs.get("decision"),
        attrs.get("decision_source"),
        attrs.get("request_id"),
        _int(attrs.get("tool_result_size_bytes")),
        attrs.get("mcp_server_scope"),
        attrs.get("plugin_name"),
        attrs.get("plugin_version"),
        attrs.get("marketplace_name"),
        attrs.get("install_trigger"),
        mcp_server_name,
        mcp_tool_name,
        now,
    ))


@app.post("/v1/metrics")
async def ingest_metrics(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"status": "ok"})

    conn = new_conn()
    try:
        now = datetime.now(tz=timezone.utc).isoformat()
        for rm in body.get("resourceMetrics", []):
            attrs_resource = _parse_attributes(rm.get("resource", {}).get("attributes", []))
            for sm in rm.get("scopeMetrics", []):
                for metric in sm.get("metrics", []):
                    name = metric.get("name", "")
                    mtype = "gauge"
                    data_points = []
                    if "sum" in metric:
                        mtype = "counter"
                        data_points = metric["sum"].get("dataPoints", [])
                    elif "gauge" in metric:
                        mtype = "gauge"
                        data_points = metric["gauge"].get("dataPoints", [])

                    for dp in data_points:
                        attrs = _parse_attributes(dp.get("attributes", []))
                        value = dp.get("asDouble") or dp.get("asInt") or 0
                        ts_ns = dp.get("timeUnixNano", "0")
                        try:
                            ts_s = int(ts_ns) / 1e9
                            ts_iso = datetime.fromtimestamp(ts_s, tz=timezone.utc).isoformat()
                        except Exception:
                            ts_iso = now

                        conn.execute("""
                            INSERT INTO otel_metrics (metric_name, metric_type, value, session_id, model, timestamp)
                            VALUES (?,?,?,?,?,?)
                        """, (
                            name, mtype, float(value),
                            attrs.get("session_id") or attrs_resource.get("session_id"),
                            attrs.get("model"),
                            ts_iso
                        ))
        conn.commit()
    finally:
        conn.close()

    return JSONResponse({"status": "ok"})


# ─── System / Health ─────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "uptime_s": int(time.time() - _start_time)}


@app.get("/api/system/health")
async def system_health():
    import psutil as ps
    proc = ps.Process()
    mem_mb = proc.memory_info().rss / 1024 / 1024

    conn = get_conn()
    last_otel_row = conn.execute(
        "SELECT received_at FROM otel_events ORDER BY id DESC LIMIT 1"
    ).fetchone()
    last_activity = conn.execute(
        "SELECT created_at FROM activities WHERE event_type='heartbeat' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    last_sync_activity = conn.execute(
        "SELECT created_at FROM activities WHERE event_type='sync_loop_heartbeat' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    last_notifier_activity = conn.execute(
        "SELECT created_at FROM activities WHERE event_type='notifier_heartbeat' ORDER BY id DESC LIMIT 1"
    ).fetchone()

    now = time.time()
    tz_name = datetime.now().astimezone().tzname()

    return {
        "uptime_s": int(now - _start_time),
        "memory_mb": round(mem_mb, 1),
        "last_otel_event": last_otel_row["received_at"] if last_otel_row else None,
        "last_otel_age_s": _age_s(last_otel_row["received_at"] if last_otel_row else None),
        "daemon_last_tick": last_activity["created_at"] if last_activity else None,
        "daemon_age_s": _age_s(last_activity["created_at"] if last_activity else None),
        "sync_last_tick": last_sync_activity["created_at"] if last_sync_activity else None,
        "sync_age_s": _age_s(last_sync_activity["created_at"] if last_sync_activity else None),
        "notifier_last_tick": last_notifier_activity["created_at"] if last_notifier_activity else None,
        "notifier_age_s": _age_s(last_notifier_activity["created_at"] if last_notifier_activity else None),
        "tzname": tz_name,
    }


@app.get("/api/system/state")
async def system_state():
    conn = get_conn()
    rows = conn.execute("SELECT key, value FROM system_state").fetchall()
    return {r["key"]: r["value"] for r in rows}


@app.post("/api/system/emergency-stop")
async def emergency_stop():
    conn = get_conn()
    # Set emergency flag
    now = datetime.now(tz=timezone.utc).isoformat()
    with conn:
        conn.execute("""
            INSERT INTO system_state (key, value, updated_at) VALUES ('emergency_stop', '1', ?)
            ON CONFLICT(key) DO UPDATE SET value='1', updated_at=?
        """, (now, now))

    killed = 0
    spared = 0
    pid_dir = QUEUE_DIR / "pids"

    if pid_dir.exists():
        for pid_file in pid_dir.glob("*"):
            try:
                pid = int(pid_file.name)
                # Verify process exists
                try:
                    proc = psutil.Process(pid)
                except psutil.NoSuchProcess:
                    pid_file.unlink(missing_ok=True)
                    continue

                # Verify it's a claude -p process
                cmdline = " ".join(proc.cmdline())
                if "claude" in cmdline and "-p" in cmdline:
                    proc.terminate()
                    killed += 1
                    pid_file.unlink(missing_ok=True)
                else:
                    spared += 1
            except Exception as e:
                log.warning("Emergency stop: error with pid %s: %s", pid_file.name, e)

    # Mark running tasks as failed
    with conn:
        conn.execute("""
            UPDATE ops_tasks SET status='failed', error_message='Emergency stop triggered'
            WHERE status='running'
        """)

    return {"stopped": True, "processes_killed": killed, "interactive_spared": spared}


@app.post("/api/system/emergency-resume")
async def emergency_resume():
    conn = get_conn()
    now = datetime.now(tz=timezone.utc).isoformat()
    with conn:
        conn.execute("""
            INSERT INTO system_state (key, value, updated_at) VALUES ('emergency_stop', '0', ?)
            ON CONFLICT(key) DO UPDATE SET value='0', updated_at=?
        """, (now, now))
    return {"resumed": True}


@app.get("/api/attention")
async def attention():
    conn = get_conn()
    issues = []

    # Pending decisions
    pending_dec = conn.execute(
        "SELECT COUNT(*) as n FROM ops_decisions WHERE status='pending'"
    ).fetchone()["n"]
    if pending_dec:
        issues.append({"type": "decisions_pending", "count": pending_dec, "message": f"{pending_dec} decision(s) waiting"})

    # Failed tasks in last 24h
    failed = conn.execute("""
        SELECT COUNT(*) as n FROM ops_tasks
        WHERE status='failed' AND completed_at >= datetime('now', '-24 hours')
    """).fetchone()["n"]
    if failed:
        issues.append({"type": "tasks_failed", "count": failed, "message": f"{failed} task(s) failed recently"})

    # Stale dispatcher (no heartbeat in 5 min)
    last_hb = conn.execute(
        "SELECT created_at FROM activities WHERE event_type='heartbeat' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if last_hb:
        age = _age_s(last_hb["created_at"])
        if age and age > 300:
            issues.append({"type": "dispatcher_stale", "age_s": age, "message": "Dispatcher heartbeat stale"})

    # Overdue schedules
    overdue = conn.execute("""
        SELECT COUNT(*) as n FROM ops_schedules
        WHERE enabled=1 AND next_run_at IS NOT NULL AND next_run_at < datetime('now', '-5 minutes')
    """).fetchone()["n"]
    if overdue:
        issues.append({"type": "schedules_overdue", "count": overdue, "message": f"{overdue} schedule(s) overdue"})

    # Loop detection (same tool >10 times in last 5 min for same session)
    loops = conn.execute("""
        SELECT session_id, tool_name, COUNT(*) as n
        FROM tool_calls
        WHERE ts >= datetime('now', '-5 minutes')
        GROUP BY session_id, tool_name
        HAVING n >= 10
    """).fetchall()
    for l in loops:
        issues.append({"type": "loop_detected", "session_id": l["session_id"],
                       "tool": l["tool_name"], "count": l["n"]})

    return {"issues": issues, "all_clear": len(issues) == 0}


@app.get("/api/firehose")
async def firehose(request: Request):
    async def event_stream() -> AsyncGenerator[str, None]:
        last_id = 0
        conn = new_conn()
        try:
            while True:
                if await request.is_disconnected():
                    break
                rows = conn.execute(
                    "SELECT id, event_name, session_id, timestamp, tool_name, received_at FROM otel_events WHERE id > ? ORDER BY id LIMIT 50",
                    (last_id,)
                ).fetchall()
                for r in rows:
                    last_id = r["id"]
                    data = json.dumps(dict(r))
                    yield f"data: {data}\n\n"
                await asyncio.sleep(2)
        finally:
            conn.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ─── Sessions ────────────────────────────────────────────────────────────────

@app.get("/api/sessions")
async def sessions(
    range: str = Query("7d"),
    source: str = Query(None),
    model: str = Query(None),
    page: int = Query(1),
    page_size: int = Query(50),
):
    conn = get_conn()
    cutoff = _range_cutoff(range)
    params: list[Any] = [cutoff]
    filters = ["s.started_at >= ?"]
    if source:
        filters.append("s.source=?")
        params.append(source)
    if model:
        filters.append("s.model LIKE ?")
        params.append(f"%{model}%")

    where = " AND ".join(filters)
    total = conn.execute(f"SELECT COUNT(*) as n FROM sessions s WHERE {where}", params).fetchone()["n"]
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"SELECT * FROM sessions s WHERE {where} ORDER BY started_at DESC LIMIT ? OFFSET ?",
        params + [page_size, offset]
    ).fetchall()

    return {"total": total, "page": page, "page_size": page_size, "sessions": [dict(r) for r in rows]}


@app.get("/api/sessions/live")
async def live_sessions():
    return {"sessions": get_live_sessions()}


@app.get("/api/sessions/live/{sid}/state")
async def live_session_state(sid: str):
    state = get_session_state(sid)
    if not state:
        raise HTTPException(404, "Session not found")
    return state


@app.get("/api/sessions/live/{sid}/stream")
async def live_session_stream(sid: str, request: Request):
    jsonl_path = _find_session_jsonl(sid)
    if not jsonl_path:
        raise HTTPException(404, "Session JSONL not found")

    async def stream() -> AsyncGenerator[str, None]:
        try:
            with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
                while True:
                    if await request.is_disconnected():
                        break
                    line = f.readline()
                    if line:
                        yield f"data: {line.strip()}\n\n"
                    else:
                        await asyncio.sleep(0.5)
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/sessions/live/{sid}/message")
async def send_live_message(sid: str, request: Request):
    import re as _re
    if not _re.match(r"^[0-9a-f-]{36}$", sid):
        raise HTTPException(400, "Invalid session_id")
    body = await request.json()
    msg = body.get("message", "")
    if not msg:
        raise HTTPException(400, "message required")

    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    queue_file = QUEUE_DIR / f"{sid}.jsonl"
    with open(queue_file, "a", encoding="utf-8") as f:
        f.write(json.dumps({"message": msg, "ts": datetime.now(tz=timezone.utc).isoformat()}) + "\n")
    return {"queued": True}


@app.get("/api/sessions/outcomes")
async def session_outcomes(range: str = Query("7d")):
    conn = get_conn()
    cutoff = _range_cutoff(range)
    rows = conn.execute("""
        SELECT
            DATE(started_at, 'localtime') as date,
            SUM(CASE WHEN error_count > 0 THEN 1 ELSE 0 END) as errored,
            SUM(CASE WHEN rate_limit_hit > 0 THEN 1 ELSE 0 END) as rate_limited,
            SUM(CASE WHEN stop_reason='max_tokens' THEN 1 ELSE 0 END) as truncated,
            SUM(CASE WHEN ended_at IS NULL THEN 1 ELSE 0 END) as unfinished,
            COUNT(*) as total
        FROM sessions
        WHERE started_at >= ?
        GROUP BY date
        ORDER BY date ASC
    """, (cutoff,)).fetchall()
    return {"data": [dict(r) for r in rows]}


@app.get("/api/sessions/by-project")
async def sessions_by_project(range: str = Query("7d")):
    conn = get_conn()
    cutoff = _range_cutoff(range)
    rows = conn.execute("""
        SELECT cwd, COUNT(*) as sessions, SUM(effective_tokens) as effective_tokens,
               SUM(
                   (SELECT COUNT(*) FROM tool_calls tc WHERE tc.session_id=s.session_id)
               ) as tool_count
        FROM sessions s
        WHERE started_at >= ?
        GROUP BY cwd
        ORDER BY sessions DESC
        LIMIT 50
    """, (cutoff,)).fetchall()
    return {"data": [dict(r) for r in rows]}


@app.get("/api/sessions/{sid}/details")
async def session_details(sid: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE session_id=?", (sid,)).fetchone()
    if not row:
        raise HTTPException(404, "Session not found")

    tools = conn.execute(
        "SELECT * FROM tool_calls WHERE session_id=? ORDER BY ts ASC", (sid,)
    ).fetchall()
    timeline = get_tool_timeline(sid)

    return {
        "session": dict(row),
        "tools": [dict(t) for t in tools],
        "timeline": timeline,
    }


@app.get("/api/summary")
async def summary():
    conn = get_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    sessions_today = conn.execute(
        "SELECT COUNT(*) as n FROM sessions WHERE DATE(started_at,'localtime')=?", (today,)
    ).fetchone()["n"]
    tokens_today = conn.execute("""
        SELECT COALESCE(SUM(input_tokens+output_tokens),0) as n FROM sessions
        WHERE DATE(started_at,'localtime')=?
    """, (today,)).fetchone()["n"]
    tools_today = conn.execute("""
        SELECT COUNT(*) as n FROM tool_calls
        WHERE DATE(ts,'localtime')=?
    """, (today,)).fetchone()["n"]
    errors_today = conn.execute("""
        SELECT COALESCE(SUM(error_count),0) as n FROM sessions
        WHERE DATE(started_at,'localtime')=?
    """, (today,)).fetchone()["n"]

    return {
        "sessions_today": sessions_today,
        "tokens_today": tokens_today,
        "tools_today": tools_today,
        "errors_today": errors_today,
    }


@app.post("/api/sync")
async def manual_sync():
    loop = asyncio.get_event_loop()
    n = await loop.run_in_executor(None, _do_sync)
    return {"synced": True}


# ─── Observability ───────────────────────────────────────────────────────────

@app.get("/api/usage/tokens")
async def usage_tokens(range: str = Query("7d")):
    conn = get_conn()
    cutoff = _range_cutoff(range)
    rows = conn.execute("""
        SELECT date, model, source,
               SUM(input_tokens) as input_tokens,
               SUM(output_tokens) as output_tokens,
               SUM(cache_read_tokens) as cache_read_tokens,
               SUM(cache_create_tokens) as cache_create_tokens
        FROM token_usage
        WHERE date >= ?
        GROUP BY date, model, source
        ORDER BY date ASC
    """, (_local_date_str(cutoff),)).fetchall()

    totals = conn.execute("""
        SELECT SUM(input_tokens) as input, SUM(output_tokens) as output,
               SUM(cache_read_tokens) as cache_read, SUM(cache_create_tokens) as cache_create
        FROM token_usage WHERE date >= ?
    """, (_local_date_str(cutoff),)).fetchone()

    return {"data": [dict(r) for r in rows], "totals": dict(totals) if totals else {}}


@app.get("/api/usage/cache")
async def usage_cache(range: str = Query("7d")):
    conn = get_conn()
    cutoff_date = _local_date_str(_range_cutoff(range))
    rows = conn.execute("""
        SELECT date,
               SUM(cache_read_tokens) as cache_read,
               SUM(input_tokens) as input,
               SUM(cache_create_tokens) as cache_create
        FROM token_usage
        WHERE date >= ?
        GROUP BY date
        ORDER BY date ASC
    """, (cutoff_date,)).fetchall()

    total_read = sum(r["cache_read"] or 0 for r in rows)
    total_input = sum(r["input"] or 0 for r in rows)
    total_create = sum(r["cache_create"] or 0 for r in rows)
    billable = total_input + total_read + total_create
    hit_rate = total_read / max(billable, 1)
    low_sample = billable < 10_000

    return {
        "hit_rate": round(hit_rate, 4),
        "low_sample": low_sample,
        "billable_tokens": billable,
        "data": [dict(r) for r in rows],
    }


@app.get("/api/tools/latency")
async def tool_latency(range: str = Query("7d")):
    conn = get_conn()
    cutoff = _range_cutoff(range)
    rows = conn.execute("""
        SELECT tool_name,
               COUNT(*) as calls,
               AVG(duration_ms) as p50,
               MAX(duration_ms) as max_ms,
               SUM(error) as errors
        FROM tool_calls
        WHERE ts >= ? AND duration_ms IS NOT NULL
        GROUP BY tool_name
        ORDER BY max_ms DESC
        LIMIT 50
    """, (cutoff,)).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d["p50"] = round(d["p50"] or 0, 1)
        d["p95"] = d["max_ms"]  # approximate
        d["error_rate"] = round((d["errors"] or 0) / max(d["calls"], 1), 3)
        result.append(d)
    return {"data": result}


@app.get("/api/hooks/activity")
async def hook_activity(range: str = Query("7d")):
    conn = get_conn()
    cutoff = _range_cutoff(range)
    # Pair start/complete events
    rows = conn.execute("""
        SELECT
            DATE(received_at,'localtime') as date,
            COUNT(CASE WHEN event_name='hook_execution_start' THEN 1 END) as fires,
            COUNT(CASE WHEN event_name='hook_execution_complete' THEN 1 END) as completions
        FROM otel_events
        WHERE event_name IN ('hook_execution_start', 'hook_execution_complete')
          AND received_at >= ?
        GROUP BY date
        ORDER BY date ASC
    """, (cutoff,)).fetchall()
    total_fires = sum(r["fires"] or 0 for r in rows)
    return {"data": [dict(r) for r in rows], "total_fires": total_fires}


@app.get("/api/tools/agent-fanout")
async def agent_fanout(range: str = Query("7d")):
    conn = get_conn()
    cutoff = _range_cutoff(range)
    rows = conn.execute("""
        SELECT tc.session_id, s.title, COUNT(*) as agent_calls
        FROM tool_calls tc
        LEFT JOIN sessions s ON s.session_id=tc.session_id
        WHERE tc.tool_name='Agent' AND tc.ts >= ?
        GROUP BY tc.session_id
        ORDER BY agent_calls DESC
        LIMIT 30
    """, (cutoff,)).fetchall()
    return {"data": [dict(r) for r in rows]}


@app.get("/api/tools/edit-decisions")
async def edit_decisions(range: str = Query("7d")):
    conn = get_conn()
    cutoff = _range_cutoff(range)
    rows = conn.execute("""
        SELECT decision, COUNT(*) as count
        FROM otel_events
        WHERE event_name='tool_decision'
          AND tool_name IN ('Edit', 'MultiEdit', 'Write', 'NotebookEdit')
          AND received_at >= ?
        GROUP BY decision
    """, (cutoff,)).fetchall()
    total = sum(r["count"] for r in rows)
    return {"data": [dict(r) for r in rows], "total": total, "low_sample": total < 10}


@app.get("/api/activity/productivity")
async def productivity(range: str = Query("7d")):
    conn = get_conn()
    cutoff = _range_cutoff(range)
    metrics = ["claude_code.commit.count", "claude_code.pull_request.count",
               "claude_code.lines_of_code.count"]
    result = {}
    for m in metrics:
        total = conn.execute(
            "SELECT SUM(value) as n FROM otel_metrics WHERE metric_name=? AND timestamp >= ?",
            (m, cutoff)
        ).fetchone()["n"] or 0
        result[m] = total

    daily = conn.execute("""
        SELECT DATE(timestamp,'localtime') as date, metric_name, SUM(value) as total
        FROM otel_metrics
        WHERE metric_name IN ('claude_code.commit.count','claude_code.pull_request.count','claude_code.lines_of_code.count')
          AND timestamp >= ?
        GROUP BY date, metric_name
        ORDER BY date ASC
    """, (cutoff,)).fetchall()

    return {"totals": result, "daily": [dict(r) for r in daily]}


@app.get("/api/system/pressure")
async def system_pressure(range: str = Query("7d")):
    conn = get_conn()
    cutoff = _range_cutoff(range)
    # Retry exhaustion: events where attempt_count >= MAX_RETRIES
    exhausted = conn.execute("""
        SELECT COUNT(*) as n FROM otel_events
        WHERE event_name='api_error' AND attempt_count >= ? AND received_at >= ?
    """, (MAX_RETRIES, cutoff)).fetchone()["n"]

    compactions = conn.execute("""
        SELECT COUNT(*) as n FROM otel_events
        WHERE event_name='compaction' AND received_at >= ?
    """, (cutoff,)).fetchone()["n"]

    errors = conn.execute("""
        SELECT timestamp, error_message, status_code, attempt_count
        FROM otel_events
        WHERE event_name='api_error' AND received_at >= ?
        ORDER BY id DESC LIMIT 10
    """, (cutoff,)).fetchall()

    return {
        "retry_exhaustion_count": exhausted,
        "compaction_count": compactions,
        "retry_threshold": MAX_RETRIES,
        "recent_errors": [dict(r) for r in errors],
    }


# ─── MCP ─────────────────────────────────────────────────────────────────────

@app.get("/api/mcp")
async def mcp_list(range: str = Query("7d")):
    days = _range_to_days(range)
    return {"servers": get_mcp_servers(days)}


@app.get("/api/mcp/{server}/tools")
async def mcp_server_tools(server: str, range: str = Query("7d")):
    days = _range_to_days(range)
    return {"tools": get_mcp_server_tools(server, days)}


@app.post("/api/mcp/sync")
async def mcp_sync():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _do_sync)
    return {"synced": True}


@app.post("/api/mcp/measure")
async def mcp_measure():
    return {"status": "not_implemented", "message": "Schema measurement requires MCP server access"}


# ─── Skills ──────────────────────────────────────────────────────────────────

@app.get("/api/skills")
async def skills_list(environment: str = Query(None), user_invocable: bool = Query(None)):
    conn = get_conn()
    filters = []
    params = []
    if environment:
        filters.append("environment=?")
        params.append(environment)
    if user_invocable is not None:
        filters.append("user_invocable=?")
        params.append(1 if user_invocable else 0)
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    rows = conn.execute(f"SELECT * FROM skills {where} ORDER BY name", params).fetchall()
    return {"skills": [dict(r) for r in rows]}


@app.post("/api/skills/sync")
async def skills_sync():
    loop = asyncio.get_event_loop()
    n = await loop.run_in_executor(None, sync_skills)
    return {"synced": n}


@app.patch("/api/skills/{name}/autonomy")
async def update_skill_autonomy(name: str, request: Request):
    body = await request.json()
    level = body.get("autonomy_level")
    if level not in ("auto", "review", "manual"):
        raise HTTPException(400, "autonomy_level must be auto|review|manual")
    conn = get_conn()
    with conn:
        conn.execute("UPDATE skills SET autonomy_level=? WHERE name=?", (level, name))
    return {"updated": True}


# ─── Decisions ───────────────────────────────────────────────────────────────

@app.get("/api/decisions")
async def decisions_list(status: str = Query("pending")):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM ops_decisions WHERE status=? ORDER BY created_at DESC LIMIT 100",
        (status,)
    ).fetchall()
    return {"decisions": [dict(r) for r in rows]}


@app.post("/api/decisions")
async def create_decision(request: Request):
    body = await request.json()
    prompt = body.get("prompt", "")
    task_id = body.get("task_id")
    session_id = body.get("session_id")
    if not prompt:
        raise HTTPException(400, "prompt required")

    conn = get_conn()
    now = datetime.now(tz=timezone.utc).isoformat()
    try:
        with conn:
            conn.execute("""
                INSERT OR IGNORE INTO ops_decisions (task_id, session_id, prompt, status, created_at)
                VALUES (?,?,?,?,?)
            """, (task_id, session_id, prompt, "pending", now))
        row = conn.execute(
            "SELECT id FROM ops_decisions WHERE session_id=? AND prompt=?",
            (session_id, prompt)
        ).fetchone()
        created = conn.execute(
            "SELECT changes() as n"
        ).fetchone()
        return {"id": row["id"] if row else None, "created": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/decisions/{did}/answer")
async def answer_decision(did: int, request: Request):
    body = await request.json()
    answer = body.get("answer", "")
    if not answer:
        raise HTTPException(400, "answer required")

    conn = get_conn()
    row = conn.execute("SELECT * FROM ops_decisions WHERE id=?", (did,)).fetchone()
    if not row:
        raise HTTPException(404, "Decision not found")

    now = datetime.now(tz=timezone.utc).isoformat()
    with conn:
        conn.execute(
            "UPDATE ops_decisions SET answer=?, status='answered', answered_at=? WHERE id=?",
            (answer, now, did)
        )

    # Write to queue file for dispatcher to inject
    if row["session_id"]:
        QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        qfile = QUEUE_DIR / f"{row['session_id']}.jsonl"
        with open(qfile, "a") as f:
            f.write(json.dumps({"decision_id": did, "answer": answer, "ts": now}) + "\n")

    return {"answered": True}


# ─── Inbox ───────────────────────────────────────────────────────────────────

@app.get("/api/inbox")
async def inbox_list(unread: int = Query(0), max_age_days: int = Query(30)):
    conn = get_conn()
    cutoff = (datetime.now() - timedelta(days=max_age_days)).isoformat()
    filters = ["created_at >= ?"]
    params = [cutoff]
    if unread:
        filters.append("read=0")
    filters.append("direction='agent_to_user'")
    where = " AND ".join(filters)
    rows = conn.execute(
        f"SELECT * FROM ops_inbox WHERE {where} ORDER BY created_at DESC LIMIT 100",
        params
    ).fetchall()
    return {"messages": [dict(r) for r in rows]}


@app.post("/api/inbox")
async def create_inbox(request: Request):
    body = await request.json()
    conn = get_conn()
    now = datetime.now(tz=timezone.utc).isoformat()
    with conn:
        conn.execute("""
            INSERT INTO ops_inbox (task_id, session_id, direction, body, created_at)
            VALUES (?,?,?,?,?)
        """, (body.get("task_id"), body.get("session_id"), "agent_to_user", body.get("body", ""), now))
    return {"created": True}


@app.post("/api/inbox/{mid}/read")
async def mark_read(mid: int):
    conn = get_conn()
    with conn:
        conn.execute("UPDATE ops_inbox SET read=1 WHERE id=?", (mid,))
    return {"read": True}


@app.post("/api/inbox/{mid}/reply")
async def reply_inbox(mid: int, request: Request):
    body = await request.json()
    msg_body = body.get("body", "")
    conn = get_conn()
    row = conn.execute("SELECT * FROM ops_inbox WHERE id=?", (mid,)).fetchone()
    if not row:
        raise HTTPException(404)
    now = datetime.now(tz=timezone.utc).isoformat()
    with conn:
        conn.execute("""
            INSERT INTO ops_inbox (task_id, session_id, direction, body, created_at)
            VALUES (?,?,?,?,?)
        """, (row["task_id"], row["session_id"], "user_to_agent", msg_body, now))

    if row["session_id"]:
        QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        qfile = QUEUE_DIR / f"{row['session_id']}.jsonl"
        with open(qfile, "a") as f:
            f.write(json.dumps({"message": msg_body, "ts": now}) + "\n")

    return {"replied": True}


# ─── Tasks ───────────────────────────────────────────────────────────────────

@app.get("/api/tasks")
async def tasks_list(status: str = Query(None), quadrant: str = Query(None)):
    conn = get_conn()
    filters = []
    params = []
    if status:
        filters.append("status=?")
        params.append(status)
    if quadrant:
        filters.append("quadrant=?")
        params.append(quadrant)
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    rows = conn.execute(
        f"SELECT * FROM ops_tasks {where} ORDER BY created_at DESC LIMIT 200",
        params
    ).fetchall()
    return {"tasks": [dict(r) for r in rows]}


@app.post("/api/tasks")
async def create_task(request: Request):
    body = await request.json()
    conn = get_conn()
    now = datetime.now(tz=timezone.utc).isoformat()
    with conn:
        conn.execute("""
            INSERT INTO ops_tasks (
                title, description, priority, quadrant, requires_approval,
                risk_level, dry_run, model, execution_mode, assigned_skill,
                scheduled_for, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            body.get("title", "Untitled"),
            body.get("description"),
            body.get("priority", 50),
            body.get("quadrant", "do"),
            1 if body.get("requires_approval") else 0,
            body.get("risk_level", "low"),
            1 if body.get("dry_run") else 0,
            body.get("model"),
            body.get("execution_mode", "stream"),
            body.get("assigned_skill"),
            body.get("scheduled_for"),
            now,
        ))
    return {"created": True}


@app.patch("/api/tasks/{tid}")
async def update_task(tid: int, request: Request):
    body = await request.json()
    conn = get_conn()
    allowed_fields = {"title", "description", "priority", "quadrant", "status",
                      "risk_level", "assigned_skill", "model", "execution_mode"}
    updates = {k: v for k, v in body.items() if k in allowed_fields}
    if not updates:
        raise HTTPException(400, "No valid fields to update")
    set_clause = ", ".join(f"{k}=?" for k in updates)
    with conn:
        conn.execute(f"UPDATE ops_tasks SET {set_clause} WHERE id=?", list(updates.values()) + [tid])
    return {"updated": True}


@app.delete("/api/tasks/{tid}")
async def delete_task(tid: int):
    conn = get_conn()
    with conn:
        conn.execute("DELETE FROM ops_tasks WHERE id=?", (tid,))
    return {"deleted": True}


@app.post("/api/tasks/{tid}/approve")
async def approve_task(tid: int):
    conn = get_conn()
    now = datetime.now(tz=timezone.utc).isoformat()
    with conn:
        conn.execute(
            "UPDATE ops_tasks SET status='pending', approved_at=? WHERE id=? AND status='awaiting_approval'",
            (now, tid)
        )
    return {"approved": True}


@app.post("/api/tasks/{tid}/rerun")
async def rerun_task(tid: int):
    conn = get_conn()
    row = conn.execute("SELECT status FROM ops_tasks WHERE id=?", (tid,)).fetchone()
    if not row:
        raise HTTPException(404)
    if row["status"] != "failed":
        raise HTTPException(400, "Task must be in failed status to rerun")
    with conn:
        conn.execute("""
            UPDATE ops_tasks SET status='pending', error_message=NULL,
            completed_at=NULL, started_at=NULL, duration_ms=NULL,
            output_summary=NULL, session_id=NULL
            WHERE id=?
        """, (tid,))
    return {"rerun": True, "task_id": tid}


@app.post("/api/dispatcher/trigger")
async def dispatcher_trigger():
    heartbeat_path = PROJECT_ROOT / ".claude" / "skills" / "mission-control" / "heartbeat.py"
    if not heartbeat_path.exists():
        raise HTTPException(404, "Mission Control not installed")

    async def _run():
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(heartbeat_path), "--once",
            env={**os.environ, "CC_PROJECT_ROOT": str(PROJECT_ROOT)},
        )
        await proc.wait()

    asyncio.create_task(_run())
    return {"triggered": True}


# ─── Schedules ───────────────────────────────────────────────────────────────

@app.get("/api/schedules")
async def schedules_list():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM ops_schedules ORDER BY created_at DESC").fetchall()
    return {"schedules": [dict(r) for r in rows]}


@app.post("/api/schedules")
async def create_schedule(request: Request):
    body = await request.json()
    conn = get_conn()
    now = datetime.now(tz=timezone.utc).isoformat()
    with conn:
        conn.execute("""
            INSERT INTO ops_schedules (name, cron_expression, task_title, task_description, assigned_skill, enabled, created_at)
            VALUES (?,?,?,?,?,?,?)
        """, (
            body.get("name", "Schedule"),
            body.get("cron_expression"),
            body.get("task_title"),
            body.get("task_description"),
            body.get("assigned_skill"),
            1 if body.get("enabled", True) else 0,
            now,
        ))
    return {"created": True}


@app.patch("/api/schedules/{sid}")
async def update_schedule(sid: int, request: Request):
    body = await request.json()
    conn = get_conn()
    allowed = {"name", "cron_expression", "task_title", "task_description", "assigned_skill", "enabled"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if "cron_expression" in updates:
        updates["next_run_at"] = None  # force recompute
    if not updates:
        raise HTTPException(400, "No valid fields")
    set_clause = ", ".join(f"{k}=?" for k in updates)
    with conn:
        conn.execute(f"UPDATE ops_schedules SET {set_clause} WHERE id=?", list(updates.values()) + [sid])
    return {"updated": True}


@app.delete("/api/schedules/{sid}")
async def delete_schedule(sid: int):
    conn = get_conn()
    with conn:
        conn.execute("DELETE FROM ops_schedules WHERE id=?", (sid,))
    return {"deleted": sid}


@app.get("/api/schedules/{sid}/runs")
async def schedule_runs(sid: int, limit: int = Query(10)):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM ops_tasks WHERE assigned_skill IS NOT NULL ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    return {"runs": [dict(r) for r in rows]}


@app.post("/api/schedules/parse-nl")
async def parse_nl_schedule(request: Request):
    body = await request.json()
    text = body.get("text", "")
    if not text:
        raise HTTPException(400, "text required")

    try:
        import anthropic
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": f"Convert this schedule to a cron expression. Reply with ONLY the cron expression (5 fields), nothing else:\n\n{text}"
            }]
        )
        cron = msg.content[0].text.strip()
    except Exception:
        cron = "0 9 * * 1-5"  # fallback: weekdays 9am

    return {"cron": cron}


# ─── Context health ──────────────────────────────────────────────────────────

@app.get("/api/context/health")
async def context_health():
    settings_path = Path.home() / ".claude" / "settings.json"
    claude_md = Path.home() / ".claude" / "CLAUDE.md"

    result = {
        "settings_exists": settings_path.exists(),
        "claude_md_exists": claude_md.exists(),
    }

    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
            result["mcp_server_count"] = len(settings.get("mcpServers", {}))
            result["hook_count"] = len(settings.get("hooks", []))
            result["settings_size_bytes"] = settings_path.stat().st_size
        except Exception:
            pass

    if claude_md.exists():
        try:
            text = claude_md.read_text(encoding="utf-8")
            result["claude_md_lines"] = len(text.splitlines())
            result["claude_md_size_bytes"] = claude_md.stat().st_size
        except Exception:
            pass

    return result


# ─── Static files ─────────────────────────────────────────────────────────────

if UI_DIST.exists():
    app.mount("/", StaticFiles(directory=str(UI_DIST), html=True), name="static")
else:
    @app.get("/")
    async def root():
        return JSONResponse({
            "message": "Command Centre API running. Build the UI with: cd ui && npm install && npm run build",
            "api_docs": "/docs"
        })


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _int(v) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None


def _float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def _range_cutoff(range: str) -> str:
    now = datetime.now(tz=timezone.utc)
    if range == "today":
        d = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif range == "30d":
        d = now - timedelta(days=30)
    else:
        d = now - timedelta(days=7)
    return d.isoformat()


def _local_date_str(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d")
    except Exception:
        return iso[:10]


def _range_to_days(range: str) -> int:
    return {"today": 1, "7d": 7, "30d": 30}.get(range, 7)


def _age_s(ts_str: str | None) -> float | None:
    if not ts_str:
        return None
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return time.time() - dt.timestamp()
    except Exception:
        return None


def _find_session_jsonl(session_id: str) -> Path | None:
    from pathlib import Path as P
    projects = P.home() / ".claude" / "projects"
    if not projects.exists():
        return None
    for d in projects.iterdir():
        f = d / f"{session_id}.jsonl"
        if f.exists():
            return f
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")
