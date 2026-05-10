from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from db import new_conn
from task_tracker import claim_pending, complete_task, fail_task, get_pending_tasks, update_task

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(os.environ.get("CC_PROJECT_ROOT", Path(__file__).parent.parent.parent.parent))
QUEUE_DIR = PROJECT_ROOT / ".tmp" / "mission-control-queue"
PID_DIR = QUEUE_DIR / "pids"
MAX_CONCURRENT = int(os.environ.get("MC_MAX_CONCURRENT", "3"))
TASK_TIMEOUT_SECONDS = int(os.environ.get("MC_TASK_TIMEOUT", "1800"))
DEFAULT_MODEL = os.environ.get("MISSION_CONTROL_DEFAULT_MODEL", "claude-sonnet-4-6")


def run_once():
    conn = new_conn()
    try:
        # Check emergency stop
        row = conn.execute("SELECT value FROM system_state WHERE key='emergency_stop'").fetchone()
        if row and row["value"] == "1":
            log.info("Emergency stop active — skipping dispatch")
            return

        _sweep_stale_pids()
        tasks = get_pending_tasks(MAX_CONCURRENT)
        for task in tasks:
            claimed = claim_pending(task["id"])
            if not claimed:
                continue
            try:
                _dispatch(claimed, conn)
            except Exception as e:
                log.error("Dispatch error for task %d: %s", task["id"], e)
                fail_task(task["id"], str(e))
    finally:
        conn.close()


def _dispatch(task: dict, conn) -> None:
    task_id = task["id"]
    skill = task.get("assigned_skill")

    # Autonomy check
    if skill:
        skill_row = conn.execute("SELECT autonomy_level FROM skills WHERE name=?", (skill,)).fetchone()
        if skill_row:
            autonomy = skill_row["autonomy_level"]
            if autonomy in ("manual", "review"):
                with conn:
                    conn.execute(
                        "UPDATE ops_tasks SET status='awaiting_approval' WHERE id=?", (task_id,)
                    )
                return

    model = _resolve_model(task, conn)
    prompt = _build_prompt(task)
    env = _build_env()

    mode = task.get("execution_mode", "stream")
    if mode == "classic":
        _run_classic(task_id, prompt, model, env)
    else:
        _run_stream(task_id, prompt, model, env)


def _run_classic(task_id: int, prompt: str, model: str, env: dict) -> None:
    PID_DIR.mkdir(parents=True, exist_ok=True)
    args = ["claude", "-p", prompt, "--model", model, "--output-format", "text"]

    try:
        proc = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, text=True
        )
        _mark_pid(proc.pid)
        update_task(task_id, pid=proc.pid)
        try:
            stdout, stderr = proc.communicate(timeout=TASK_TIMEOUT_SECONDS)
            if proc.returncode == 0:
                complete_task(task_id, output=stdout[:5000] if stdout else None)
            else:
                fail_task(task_id, stderr[:1000] if stderr else f"Exit code {proc.returncode}")
        except subprocess.TimeoutExpired:
            proc.kill()
            fail_task(task_id, "Task timed out")
    except FileNotFoundError:
        fail_task(task_id, "claude CLI not found in PATH")
    finally:
        _unmark_pid(proc.pid if "proc" in dir() else None)


def _run_stream(task_id: int, prompt: str, model: str, env: dict) -> None:
    PID_DIR.mkdir(parents=True, exist_ok=True)
    args = ["claude", "-p", prompt, "--model", model, "--output-format", "stream-json",
            "--verbose"]

    try:
        proc = subprocess.Popen(
            args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, text=True, bufsize=1
        )
        _mark_pid(proc.pid)
        update_task(task_id, pid=proc.pid)

        session_id = None
        output_parts = []
        decision_queue: list[dict] = []
        cost_usd = None

        stdout_lines = []
        stop_event = threading.Event()

        def _read_stdout():
            for line in proc.stdout:
                stdout_lines.append(line)
            stop_event.set()

        reader = threading.Thread(target=_read_stdout, daemon=True)
        reader.start()

        start = time.time()
        last_queue_check = 0
        in_fence = False

        while not stop_event.is_set():
            # Process buffered lines
            while stdout_lines:
                line = stdout_lines.pop(0)
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue

                otype = obj.get("type", "")
                if otype == "system" and obj.get("subtype") == "init":
                    session_id = obj.get("session_id")
                    if session_id:
                        update_task(task_id, session_id=session_id)

                elif otype == "assistant":
                    content = obj.get("message", {}).get("content", [])
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            text = part.get("text", "")
                            output_parts.append(text)
                            # Parse DECISION: / INBOX: markers
                            _parse_markers(text, task_id, session_id, proc, decision_queue, in_fence)

                elif otype == "result":
                    cost_usd = obj.get("total_cost_usd")

            # Poll queue file for user messages
            now = time.time()
            if session_id and now - last_queue_check > 2:
                last_queue_check = now
                _inject_queued_messages(session_id, proc)

            # Timeout check
            if time.time() - start > TASK_TIMEOUT_SECONDS:
                proc.kill()
                fail_task(task_id, "Task timed out")
                return

            if proc.poll() is not None:
                break
            time.sleep(0.2)

        stop_event.wait(timeout=5)
        proc.wait()

        output = "".join(output_parts)[-5000:]
        if proc.returncode == 0:
            complete_task(task_id, output=output, cost_usd=cost_usd)
        else:
            stderr_out = proc.stderr.read(1000) if proc.stderr else ""
            fail_task(task_id, stderr_out or f"Exit code {proc.returncode}")

    except FileNotFoundError:
        fail_task(task_id, "claude CLI not found in PATH")
    finally:
        _unmark_pid(proc.pid if "proc" in dir() else None)


def _parse_markers(text: str, task_id: int, session_id: str | None, proc, decisions: list, in_fence: bool):
    lines = text.splitlines()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        if stripped.startswith("DECISION:"):
            prompt_text = stripped[9:].strip()
            _handle_decision(task_id, session_id, prompt_text, proc)
        elif stripped.startswith("INBOX:"):
            msg = stripped[6:].strip()
            _handle_inbox(task_id, session_id, msg)


def _handle_decision(task_id: int, session_id: str | None, prompt: str, proc) -> None:
    try:
        import urllib.request
        data = json.dumps({
            "task_id": task_id,
            "session_id": session_id,
            "prompt": prompt,
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:8765/api/decisions",
            data=data, headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        log.warning("Failed to post decision: %s", e)

    # Poll for answer
    timeout = 300  # 5 min
    start = time.time()
    while time.time() - start < timeout:
        try:
            import urllib.request
            with urllib.request.urlopen(
                f"http://127.0.0.1:8765/api/decisions?status=answered", timeout=5
            ) as resp:
                data = json.loads(resp.read())
                for d in data.get("decisions", []):
                    if d.get("session_id") == session_id and d.get("prompt") == prompt:
                        answer = d.get("answer", "")
                        if answer and proc.stdin:
                            proc.stdin.write(answer + "\n")
                            proc.stdin.flush()
                        return
        except Exception:
            pass
        time.sleep(2)


def _handle_inbox(task_id: int, session_id: str | None, msg: str) -> None:
    try:
        import urllib.request
        data = json.dumps({
            "task_id": task_id,
            "session_id": session_id,
            "body": msg,
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:8765/api/inbox",
            data=data, headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        log.warning("Failed to post inbox message: %s", e)


def _inject_queued_messages(session_id: str, proc) -> None:
    queue_file = QUEUE_DIR / f"{session_id}.jsonl"
    if not queue_file.exists():
        return

    offset_file = QUEUE_DIR / f"{session_id}.offset"
    offset = 0
    if offset_file.exists():
        try:
            offset = int(offset_file.read_text().strip())
        except Exception:
            pass

    try:
        with open(queue_file, "r", encoding="utf-8") as f:
            f.seek(offset)
            new_lines = f.readlines()
            new_offset = f.tell()

        for line in new_lines:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                msg = obj.get("message", "")
                if msg and proc.stdin:
                    proc.stdin.write(msg + "\n")
                    proc.stdin.flush()
            except Exception:
                pass

        if new_offset > offset:
            offset_file.write_text(str(new_offset))
    except Exception:
        pass


def _resolve_model(task: dict, conn) -> str:
    if task.get("model"):
        return task["model"]
    if task.get("assigned_skill"):
        row = conn.execute("SELECT autonomy_level FROM skills WHERE name=?", (task["assigned_skill"],)).fetchone()
    return DEFAULT_MODEL


def _build_prompt(task: dict) -> str:
    parts = [task.get("title", "")]
    if task.get("description"):
        parts.append(task["description"])
    if task.get("dry_run"):
        parts.append("\n[DRY RUN: Describe what you would do but do not make changes]")
    return "\n\n".join(parts)


def _build_env() -> dict:
    env = {**os.environ}
    env["CLAUDE_CODE_ENABLE_TELEMETRY"] = "1"
    env["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://127.0.0.1:8765"
    env["OTEL_EXPORTER_OTLP_PROTOCOL"] = "http/json"
    env["OTEL_METRICS_EXPORTER"] = "otlp"
    env["OTEL_LOGS_EXPORTER"] = "otlp"
    env["ATOMICOPS_DISPATCHED"] = "1"
    return env


def _mark_pid(pid: int) -> None:
    PID_DIR.mkdir(parents=True, exist_ok=True)
    (PID_DIR / str(pid)).touch()


def _unmark_pid(pid: int | None) -> None:
    if pid is None:
        return
    pid_file = PID_DIR / str(pid)
    pid_file.unlink(missing_ok=True)


def _sweep_stale_pids() -> None:
    if not PID_DIR.exists():
        return
    for pid_file in PID_DIR.iterdir():
        try:
            pid = int(pid_file.name)
            if not psutil.pid_exists(pid):
                pid_file.unlink(missing_ok=True)
        except Exception:
            pid_file.unlink(missing_ok=True)
