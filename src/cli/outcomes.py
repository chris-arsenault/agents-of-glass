"""Helpers for structured scene and arc close outcomes."""

from __future__ import annotations

from collections.abc import Iterable

from .errors import GlassError, agent_instruction


def normalize_outcomes(values: Iterable[str], *, label: str = "--outcome") -> list[str]:
    """Return 1-2 clean outcome bullets from repeated CLI option values."""
    outcomes: list[str] = []
    for value in values:
        for line in str(value).splitlines():
            text = line.strip().lstrip("-*").strip()
            if text:
                outcomes.append(text)
    if not outcomes:
        raise GlassError(
            agent_instruction(
                f"{label} is required",
                "Provide 1-2 in-universe outcome bullets that state what changed because this scene or arc ended.",
            )
        )
    if len(outcomes) > 2:
        raise GlassError(
            agent_instruction(
                f"{label} accepts at most 2 outcome bullets",
                "Keep outcomes focused: choose the one or two durable consequences that matter most.",
            )
        )
    return outcomes


def outcome_section(outcomes: list[str]) -> str:
    bullets = "\n".join(f"- {outcome}" for outcome in outcomes)
    return f"## Outcomes\n\n{bullets}\n"


def append_outcome_section(body: str, outcomes: list[str]) -> str:
    stripped = body.rstrip()
    if stripped:
        return f"{stripped}\n\n{outcome_section(outcomes)}"
    return outcome_section(outcomes)


def clock_disposition_section(dispositions: list[dict[str, object]]) -> str:
    if not dispositions:
        return ""
    lines = ["## Scene Clock Dispositions", ""]
    for item in dispositions:
        label = str(item.get("label") or item.get("clock_id") or "clock")
        verb = str(item.get("disposition") or "")
        reason = str(item.get("reason") or "").strip()
        value = item.get("value")
        max_value = item.get("max")
        position = (
            f" ({int(value)}/{int(max_value)})"
            if isinstance(value, int) and isinstance(max_value, int) and max_value
            else ""
        )
        lines.append(f"- **{label}**{position} — {verb}: {reason}")
    return "\n".join(lines) + "\n"


def append_clock_disposition_section(
    body: str,
    dispositions: list[dict[str, object]],
) -> str:
    section = clock_disposition_section(dispositions)
    if not section:
        return body
    stripped = body.rstrip()
    if stripped:
        return f"{stripped}\n\n{section}"
    return section
