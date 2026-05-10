from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))


def pick_skill(title: str, description: str, skill_descriptions: list[dict]) -> str | None:
    if not skill_descriptions:
        return None

    try:
        import anthropic
        client = anthropic.Anthropic()
        skill_list = "\n".join(
            f"- {s['name']}: {s.get('description', '')}" for s in skill_descriptions
        )
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=50,
            messages=[{
                "role": "user",
                "content": (
                    f"Pick the best skill for this task. Reply with ONLY the skill name.\n\n"
                    f"Task: {title}\n{description or ''}\n\nSkills:\n{skill_list}"
                )
            }]
        )
        skill_name = msg.content[0].text.strip()
        valid = {s["name"] for s in skill_descriptions}
        if skill_name in valid:
            return skill_name
        # fuzzy match
        for s in valid:
            if s.lower() in skill_name.lower() or skill_name.lower() in s.lower():
                return s
    except Exception:
        pass

    return skill_descriptions[0]["name"] if skill_descriptions else None
