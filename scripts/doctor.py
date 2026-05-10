from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

INSTALL_DIR = Path(__file__).parent.parent
REQUIRED_OTEL = {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:8765",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/json",
    "OTEL_METRICS_EXPORTER": "otlp",
    "OTEL_LOGS_EXPORTER": "otlp",
    "OTEL_LOG_TOOL_DETAILS": "1",
}

PORT = int(os.environ.get("CC_PORT", "8765"))

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(label: str, detail: str = ""):
    print(f"  {GREEN}[OK]{RESET} {label}" + (f"  {YELLOW}{detail}{RESET}" if detail else ""))


def fail(label: str, detail: str = ""):
    print(f"  {RED}[FAIL]{RESET} {label}" + (f"  {YELLOW}{detail}{RESET}" if detail else ""))
    return False


def warn(label: str, detail: str = ""):
    print(f"  {YELLOW}[WARN]{RESET} {label}" + (f"  {detail}" if detail else ""))


errors = 0


def check(condition: bool, label: str, ok_detail: str = "", fail_detail: str = "") -> bool:
    global errors
    if condition:
        ok(label, ok_detail)
        return True
    else:
        fail(label, fail_detail)
        errors += 1
        return False


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    global errors
    print(f"\n{BOLD}Command Centre Doctor{RESET}\n")

    # Python version
    v = sys.version_info
    check(v >= (3, 9), f"Python {v.major}.{v.minor}.{v.micro}", fail_detail="Need Python 3.9+")
    if v < (3, 10):
        warn("Python 3.10+ recommended for best compatibility")

    # claude CLI
    claude_path = shutil.which("claude")
    check(claude_path is not None, "claude CLI in PATH", ok_detail=claude_path or "", fail_detail="Install Claude Code CLI")

    # settings.json
    settings_path = Path.home() / ".claude" / "settings.json"
    settings_ok = check(settings_path.exists(), "~/.claude/settings.json exists")
    if settings_ok:
        try:
            settings = json.loads(settings_path.read_text())
            env = settings.get("env", {})
            all_otel = all(env.get(k) == v for k, v in REQUIRED_OTEL.items())
            check(all_otel, "OTEL keys configured", fail_detail="Run: cc setup otel")
            if not all_otel:
                missing = [k for k, v in REQUIRED_OTEL.items() if env.get(k) != v]
                for k in missing:
                    warn(f"  Missing: {k}")
        except Exception as e:
            fail(f"settings.json parse error: {e}")

    # Session files
    projects_dir = Path.home() / ".claude" / "projects"
    if projects_dir.exists():
        count = sum(1 for _ in projects_dir.rglob("*.jsonl"))
        check(True, f"Session files found", ok_detail=f"{count} JSONL files")
    else:
        warn("~/.claude/projects not found")

    # CC_PROJECT_ROOT
    root = os.environ.get("CC_PROJECT_ROOT")
    check(bool(root), "CC_PROJECT_ROOT set", ok_detail=root or "", fail_detail="Set CC_PROJECT_ROOT in .env")

    # Port reachable
    try:
        s = socket.socket()
        s.settimeout(2)
        s.connect(("127.0.0.1", PORT))
        s.close()
        port_ok = True
    except Exception:
        port_ok = False
    check(port_ok, f"Dashboard reachable (port {PORT})", fail_detail="Start with: cc start")

    if port_ok:
        try:
            import urllib.request
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/system/health", timeout=5) as resp:
                data = json.loads(resp.read())
            ok(f"  Uptime: {data.get('uptime_s', '?')}s")
            if data.get('last_otel_age_s'):
                age = data['last_otel_age_s']
                if age < 120:
                    ok(f"  Last OTEL event: {age:.0f}s ago")
                else:
                    warn(f"  Last OTEL event: {age:.0f}s ago (stale)")
            if data.get('daemon_age_s'):
                age = data['daemon_age_s']
                if age < 300:
                    ok(f"  Daemon heartbeat: {age:.0f}s ago")
                else:
                    warn(f"  Daemon heartbeat: {age:.0f}s ago (stale)")
        except Exception as e:
            warn(f"Health check error: {e}")

    # Windows Task Scheduler
    try:
        result = subprocess.run(
            ["schtasks", "/query", "/tn", "CommandCentre\\Server"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            ok("Windows Task Scheduler: Server task found")
        else:
            warn("Windows Task Scheduler: Server task not found (run install.ps1)")
    except Exception:
        warn("Could not check Task Scheduler")

    # Telegram
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if telegram_token:
        try:
            import urllib.request
            with urllib.request.urlopen(
                f"https://api.telegram.org/bot{telegram_token}/getMe", timeout=5
            ) as resp:
                data = json.loads(resp.read())
            if data.get("ok"):
                ok(f"Telegram bot: @{data['result']['username']}")
            else:
                fail("Telegram bot: invalid token")
        except Exception as e:
            warn(f"Telegram not reachable: {e}")
    else:
        warn("Telegram not configured (optional)")

    print()
    if errors == 0:
        print(f"{GREEN}{BOLD}All checks passed!{RESET}")
        sys.exit(0)
    else:
        print(f"{RED}{BOLD}{errors} check(s) failed.{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
