"""Per-actor system prompt assembly for claude-provider agent turns.

The system prompt fully replaces Claude Code's default (coding-agent) system
prompt via `claude -p --system-prompt-file`. It is assembled from three
authored inputs under ``templates/``:

- the per-role base document (``templates/prompts/{dm,player}-base.md``) —
  role identity frame, craft principles, and relocated durable guards;
- the actor's persona (``templates/dm/persona.md`` or
  ``templates/players/<id>/persona.md``) — who this person is at the table;
- the persona's assigned narrative style (``templates/styles/<style>.md``) —
  how this actor's prose moves on the page.

Persona and style *contents* are inlined; the running agent is never pointed
at these files. A missing base document disables the flag for that role so
older checkouts and tests keep working. A missing persona or style degrades to
whatever inputs exist.

Assembled prompts are runtime artifacts, written under
``<campaigns_dir>/.system-prompts/<campaign>/<actor>.md`` — not under
``templates/`` (authored input only) and not inside the campaign tree agents
can see.
"""

from __future__ import annotations

import re
from pathlib import Path

from .config import AogConfig
from .state import Agent

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_STYLE_KEY_RE = re.compile(r"^narrative_style:\s*(\S+)\s*$", re.MULTILINE)


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter, body); frontmatter is empty when absent."""

    match = _FRONTMATTER_RE.match(text)
    if not match:
        return "", text
    return match.group(1), text[match.end() :]


def _read_optional(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def persona_path_for(config: AogConfig, agent: Agent) -> Path:
    if agent.role == "dm":
        return config.templates_dir / "dm" / "persona.md"
    return config.templates_dir / "players" / agent.id / "persona.md"


def assemble_system_prompt(config: AogConfig, agent: Agent) -> str | None:
    """Build the full system prompt text for one actor, or None if disabled."""

    base_text = _read_optional(config.prompts.base_for_role(agent.role))
    if base_text is None:
        return None

    sections = [base_text.strip()]

    persona_raw = _read_optional(persona_path_for(config, agent))
    style_body = None
    if persona_raw is not None:
        frontmatter, persona_body = _split_frontmatter(persona_raw)
        style_match = _STYLE_KEY_RE.search(frontmatter)
        if style_match:
            style_raw = _read_optional(
                config.templates_dir / "styles" / f"{style_match.group(1)}.md"
            )
            if style_raw is not None:
                _, style_body = _split_frontmatter(style_raw)
        sections.append(
            "# Who you are at the table\n\n"
            "This is you. It is not a reference document; it is your own "
            "personality, taste, and table behavior.\n\n" + persona_body.strip()
        )
    if style_body:
        sections.append(
            "# How your prose moves\n\n"
            "Your narration on the page follows this register. It is what "
            "makes your turns read differently from everyone else's.\n\n"
            + style_body.strip()
        )

    return "\n\n".join(sections) + "\n"


def materialize_system_prompt(
    config: AogConfig,
    *,
    campaign_id: str,
    agent: Agent,
) -> Path | None:
    """Write the assembled prompt to its runtime location and return the path.

    Rewritten on every invocation so authored-template edits between turns are
    picked up; the write is small and idempotent.
    """

    content = assemble_system_prompt(config, agent)
    if content is None:
        return None
    prompt_dir = config.campaigns_dir / ".system-prompts" / campaign_id
    prompt_dir.mkdir(parents=True, exist_ok=True)
    path = prompt_dir / f"{agent.id}.md"
    path.write_text(content, encoding="utf-8")
    return path
