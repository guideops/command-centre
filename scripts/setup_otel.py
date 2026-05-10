from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

SETTINGS_PATH = Path.home() / ".claude" / "settings.json"

REQUIRED = {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:8765",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/json",
    "OTEL_METRICS_EXPORTER": "otlp",
    "OTEL_LOGS_EXPORTER": "otlp",
    "OTEL_LOG_TOOL_DETAILS": "1",
}


def main(yes: bool = False):
    import sys as _sys
    _sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if not SETTINGS_PATH.exists():
        print(f"Creating {SETTINGS_PATH}")
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        settings = {}
    else:
        try:
            settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error reading settings.json: {e}")
            sys.exit(1)

    env = settings.get("env", {})
    missing = {k: v for k, v in REQUIRED.items() if env.get(k) != v}

    if not missing:
        print("All OTEL settings already configured.")
        return

    print("Missing or incorrect OTEL settings:")
    for k, v in missing.items():
        current = env.get(k, "<not set>")
        print(f"  {k}: {current!r} -> {v!r}")

    if not yes:
        resp = input("\nApply these settings? [Y/n] ").strip().lower()
        if resp in ("n", "no"):
            print("Aborted.")
            return

    # Backup
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = SETTINGS_PATH.with_name(f"settings.json.bak.{ts}")
    shutil.copy2(SETTINGS_PATH, backup)
    print(f"Backed up to {backup}")

    # Merge
    if "env" not in settings:
        settings["env"] = {}
    for k, v in missing.items():
        settings["env"][k] = v

    SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    print("settings.json updated.")
    print("\nIMPORTANT: Quit and restart Claude Code for OTEL to take effect.")


if __name__ == "__main__":
    main(yes="--yes" in sys.argv)
