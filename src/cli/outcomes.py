"""Helpers for structured scene and arc close outcomes."""

from __future__ import annotations

from collections.abc import Iterable

from .errors import GlassError


def normalize_outcomes(values: Iterable[str], *, label: str = "--outcome") -> list[str]:
    """Return 1-2 clean outcome bullets from repeated CLI option values."""
    outcomes: list[str] = []
    for value in values:
        for line in str(value).splitlines():
            text = line.strip().lstrip("-*").strip()
            if text:
                outcomes.append(text)
    if not outcomes:
        raise GlassError(f"{label} is required; provide 1-2 in-universe outcome bullets")
    if len(outcomes) > 2:
        raise GlassError(f"{label} accepts at most 2 outcome bullets")
    return outcomes


def outcome_section(outcomes: list[str]) -> str:
    bullets = "\n".join(f"- {outcome}" for outcome in outcomes)
    return f"## Outcomes\n\n{bullets}\n"


def append_outcome_section(body: str, outcomes: list[str]) -> str:
    stripped = body.rstrip()
    if stripped:
        return f"{stripped}\n\n{outcome_section(outcomes)}"
    return outcome_section(outcomes)
