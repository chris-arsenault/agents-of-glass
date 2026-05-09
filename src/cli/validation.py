"""Mechanical validators (attributes, skills, dice math)."""

from __future__ import annotations

from .constants import ATTRIBUTES
from .errors import GlassError


def validate_key_values(
    values: tuple[str, ...],
    valid_values: dict[str, int],
    label: str,
) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise GlassError(f"invalid {label}: expected name=tier, got {value!r}")
        name, tier = value.split("=", 1)
        name = name.strip()
        tier = tier.strip()
        if not name:
            raise GlassError(f"invalid {label}: name cannot be empty")
        if tier not in valid_values:
            options = ", ".join(sorted(valid_values))
            raise GlassError(f"invalid {label} tier {tier!r}; valid tiers: {options}")
        parsed[name] = tier
    return parsed


def assert_attribute_name(attribute: str) -> None:
    if attribute not in ATTRIBUTES:
        raise GlassError(
            f"unknown attribute {attribute!r}; valid attributes: {', '.join(ATTRIBUTES)}"
        )


def clamp(value: int, floor: int, ceiling: int) -> int:
    return max(floor, min(ceiling, value))


def outcome_for_margin(margin: int) -> tuple[str, int]:
    if margin >= 2:
        return "breakthrough", 2
    if margin >= 0:
        return "advance", 1
    if margin == -1:
        return "stall", 0
    if margin >= -3:
        return "regress", -1
    return "collapse", -2
