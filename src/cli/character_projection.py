"""Character markdown projections derived from Postgres rows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import Paths
from .constants import ATTRIBUTES
from .paths_resolve import display_path


def public_character_mirror_path(
    paths: Paths,
    campaign_id: str,
    character: dict[str, Any],
) -> Path:
    return (
        paths.campaigns
        / campaign_id
        / "players"
        / str(character["player_id"])
        / "public"
        / "character.md"
    )


def write_public_character_mirror(
    paths: Paths,
    campaign_id: str,
    character: dict[str, Any],
) -> dict[str, Any]:
    path = public_character_mirror_path(paths, campaign_id, character)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = render_public_character_mirror(character)
    path.write_text(body, encoding="utf-8")
    return {
        "path": display_path(path),
        "bytes": len(body.encode("utf-8")),
    }


def render_public_character_mirror(character: dict[str, Any]) -> str:
    lines = [
        "---",
        f"title: {character['name']}",
        "type: character-display",
        f"character_id: {character['character_id']}",
        f"player_id: {character['player_id']}",
        "---",
        "",
        f"# {character['name']}",
        "",
        f"- **Player:** {character['player_id']}",
        f"- **Species:** {character['species']}",
        f"- **Culture:** {character['culture']}",
        f"- **Archetype:** {character['archetype']}",
        f"- **Organization role:** {character['organization_role']}",
        f"- **Pronouns:** {character.get('pronouns') or 'unspecified'}",
        f"- **Primary drive:** {character.get('primary_drive') or 'unrecorded'}",
        f"- **Positive trait:** {character.get('positive_trait') or 'unrecorded'}",
        f"- **Table presence:** {character.get('table_presence') or 'unrecorded'}",
        f"- **Non-work want:** {character.get('non_work_want') or 'unrecorded'}",
        (
            "- **Opening social action:** "
            f"{character.get('opening_social_action') or 'unrecorded'}"
        ),
        f"- **Level:** {character['level']} ({character['xp']} XP)",
        f"- **HP:** {character['hp']['current']}/{character['hp']['max']}",
        (
            f"- **Momentum:** {character['momentum']['current']} "
            f"({character['momentum']['floor']} to {character['momentum']['ceiling']})"
        ),
        "",
        "## Bio",
        "",
        str(character["bio"]).strip(),
        "",
        "## Goals",
        "",
    ]
    lines.extend(f"- {goal}" for goal in character.get("goals", []))
    life_prompt_answers = list(character.get("life_prompt_answers") or [])
    if life_prompt_answers:
        lines.extend(["", "## Life Prompt Answers", ""])
        for prompt in life_prompt_answers:
            if isinstance(prompt, dict):
                lines.append(
                    f"- **{prompt.get('prompt', 'prompt')}:** {prompt.get('answer', '')}"
                )
            else:
                lines.append(f"- {prompt}")
    pull_note = str(character.get("pull_utilization_note") or "").strip()
    if pull_note:
        lines.extend(["", "## Non-Adjacent Pull Utilization", "", pull_note])
    lines.extend(["", "## Attributes", ""])
    for attribute in ATTRIBUTES:
        lines.append(f"- **{attribute}:** {character['attributes'].get(attribute, 'standard')}")
    lines.extend(["", "## Skills", ""])
    for skill, tier in sorted(character.get("skills", {}).items()):
        lines.append(f"- **{skill}:** {tier}")
    lines.extend(["", "## Inventory", ""])
    inventory = list(character.get("inventory") or [])
    if inventory:
        for item in inventory:
            item_line = f"- **{item.get('id', 'item')}:** x{int(item.get('qty', 1))}"
            effect_tags = item.get("effect_tags")
            if isinstance(effect_tags, list) and effect_tags:
                item_line += " — " + "; ".join(str(tag) for tag in effect_tags)
            lines.append(item_line)
    else:
        lines.append("- None recorded.")
    tags = list(character.get("tags") or [])
    if tags:
        lines.extend(["", "## Tags", ""])
        lines.append(", ".join(tags))
    return "\n".join(lines).rstrip() + "\n"
