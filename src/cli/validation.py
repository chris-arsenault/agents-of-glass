"""Mechanical validators (attributes, skills, dice math)."""

from __future__ import annotations

from .constants import ATTRIBUTES
from .errors import GlassError, agent_instruction


ITEM_STATUS_SUFFIXES: tuple[str, ...] = ("-spent", "-broken", "-lost", "-sealed")


def validate_key_values(
    values: tuple[str, ...],
    valid_values: dict[str, int],
    label: str,
) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise GlassError(
                agent_instruction(
                    f"invalid {label} {value!r}",
                    "Use `name=tier` format for each value.",
                )
            )
        name, tier = value.split("=", 1)
        name = name.strip()
        tier = tier.strip()
        if not name:
            raise GlassError(
                agent_instruction(
                    f"invalid {label}: name cannot be empty",
                    "Put a name before the equals sign, for example `resolve=advanced`.",
                )
            )
        if tier not in valid_values:
            options = ", ".join(sorted(valid_values))
            raise GlassError(
                agent_instruction(
                    f"invalid {label} tier {tier!r}",
                    f"Use one of: {options}.",
                )
            )
        parsed[name] = tier
    return parsed


def assert_attribute_name(attribute: str) -> None:
    if attribute not in ATTRIBUTES:
        raise GlassError(
            agent_instruction(
                f"unknown attribute {attribute!r}",
                f"Use one of: {', '.join(ATTRIBUTES)}.",
            )
        )


def assert_valid_item_id(item_id: str) -> None:
    if not item_id:
        return
    lowered = item_id.lower()
    for suffix in ITEM_STATUS_SUFFIXES:
        if lowered.endswith(suffix):
            raise GlassError(
                agent_instruction(
                    f"item id {item_id!r} encodes transient status in its identity",
                    "Drop the status suffix from the id "
                    f"({', '.join(ITEM_STATUS_SUFFIXES)}).",
                    "Use `glass character consequence-add <character> <label>` to "
                    "record unavailability, expended charges, damage, jammed gear, "
                    "or other conditional state. Reserve `glass character inventory-rm` "
                    "for permanent removal.",
                )
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


def momentum_narrative_effect(momentum: int) -> tuple[str, str]:
    if momentum > 2:
        return (
            "additional_good",
            "momentum > 2: add one extra good visible consequence",
        )
    if momentum <= 0:
        return (
            "additional_complication",
            "momentum <= 0: add one extra visible complication",
        )
    return "none", "momentum 1-2: no extra momentum rider"
