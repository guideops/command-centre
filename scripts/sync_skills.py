from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from db import get_conn, new_conn

SKILL_DIRS = [
    Path.home() / ".claude" / "skills",
    Path(__file__).parent.parent / ".claude" / "skills",
]


def _read_frontmatter(skill_file: Path) -> dict:
    try:
        text = skill_file.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if not m:
            return {}
        fm = {}
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip()
        return fm
    except Exception:
        return {}


def sync_skills(conn=None) -> int:
    close_after = conn is None
    if conn is None:
        conn = new_conn()

    count = 0
    try:
        seen = set()
        for base_dir in SKILL_DIRS:
            if not base_dir.exists():
                continue
            for skill_dir in base_dir.iterdir():
                if not skill_dir.is_dir():
                    continue
                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    skill_file = skill_dir / "README.md"
                if not skill_file.exists():
                    continue

                name = skill_dir.name
                fm = _read_frontmatter(skill_file)
                description = fm.get("description", "")
                autonomy = fm.get("autonomy", "review")
                user_invocable = 1 if fm.get("user_invocable", "").lower() in ("true", "yes", "1") else 0

                scripts = list(skill_dir.glob("*.py")) + list(skill_dir.glob("scripts/*.py"))
                script_count = len(scripts)

                mtime = max(
                    (f.stat().st_mtime for f in skill_dir.rglob("*") if f.is_file()),
                    default=0
                )
                last_modified = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat() if mtime else None

                env = "ide:global" if base_dir == Path.home() / ".claude" / "skills" else "ide:project"

                conn.execute("""
                    INSERT INTO skills (name, environment, description, path, autonomy_level, user_invocable, script_count, last_modified)
                    VALUES (?,?,?,?,?,?,?,?)
                    ON CONFLICT(name) DO UPDATE SET
                        environment=excluded.environment, description=excluded.description,
                        path=excluded.path, autonomy_level=excluded.autonomy_level,
                        user_invocable=excluded.user_invocable, script_count=excluded.script_count,
                        last_modified=excluded.last_modified
                """, (name, env, description, str(skill_dir), autonomy, user_invocable, script_count, last_modified))
                seen.add(name)
                count += 1

        conn.commit()
    finally:
        if close_after:
            conn.close()

    return count


if __name__ == "__main__":
    from db import init_db
    init_db()
    n = sync_skills()
    print(f"Synced {n} skills")
