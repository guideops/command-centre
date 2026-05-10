from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

INSTALL_DIR = Path(__file__).parent.parent
ENV_FILE = INSTALL_DIR / ".env"
REFS_DIR = INSTALL_DIR / ".claude" / "skills" / "telegram" / "references"


def main():
    print("=== Telegram Setup Wizard ===\n")
    print("Step 1: Create a Telegram bot via @BotFather")
    print("  1. Open Telegram and search for @BotFather")
    print("  2. Send /newbot and follow prompts")
    print("  3. Copy the token (format: 123456:ABC-DEF...)\n")

    token = input("Bot token: ").strip()
    if not token:
        print("Token required. Aborted.")
        sys.exit(1)

    # Validate token
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        if not data.get("ok"):
            print("Invalid token.")
            sys.exit(1)
        bot_name = data["result"].get("username")
        print(f"Bot validated: @{bot_name}")
    except Exception as e:
        print(f"Token validation failed: {e}")
        sys.exit(1)

    print("\nStep 2: Get your Telegram chat_id")
    print("  Open Telegram, search for @userinfobot and send /start")
    print("  It will reply with your user ID\n")

    chat_id = input("Your chat_id (numeric): ").strip()
    if not chat_id:
        print("chat_id required. Aborted.")
        sys.exit(1)

    # Test send
    try:
        payload = json.dumps({"chat_id": chat_id, "text": "Command Centre is wired up."}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
        if not result.get("ok"):
            print(f"Test message failed: {result}")
            sys.exit(1)
        print("Test message sent successfully!")
    except Exception as e:
        print(f"Failed to send test message: {e}")
        sys.exit(1)

    # Write .env
    env_content = ""
    if ENV_FILE.exists():
        env_content = ENV_FILE.read_text(encoding="utf-8")

    lines = [l for l in env_content.splitlines() if not l.startswith("TELEGRAM_")]
    lines.extend([
        f"TELEGRAM_BOT_TOKEN={token}",
        f"TELEGRAM_DASH_CHAT_ID={chat_id}",
    ])
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        import stat
        ENV_FILE.chmod(0o600)
    except Exception:
        pass
    print(f"Written to {ENV_FILE}")

    # Write references/messaging.yaml
    REFS_DIR.mkdir(parents=True, exist_ok=True)
    yaml_content = f"""allowed_user_ids:
  - {chat_id}
"""
    (REFS_DIR / "messaging.yaml").write_text(yaml_content)
    print(f"Allowed users saved to {REFS_DIR}/messaging.yaml")

    print("\nSetup complete! Restart the Command Centre server to apply.")


if __name__ == "__main__":
    main()
