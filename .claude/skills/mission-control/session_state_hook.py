from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))


def main():
    try:
        event = json.loads(sys.stdin.read())
    except Exception:
        return

    session_id = event.get("session_id") or os.environ.get("CLAUDE_SESSION_ID")
    hook_event = event.get("hook_type", "")

    if not session_id:
        return

    state_map = {
        "PreToolUse": "running",
        "PostToolUse": "running",
        "Notification": "waiting",
        "Stop": "stopped",
    }
    state = state_map.get(hook_event, "running")
    tool = event.get("tool_name")

    try:
        import urllib.request
        data = json.dumps({"state": state, "current_tool": tool}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:8765/api/sessions/live/{session_id}/state",
            data=data,
            method="PUT",
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass


if __name__ == "__main__":
    main()
