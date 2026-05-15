"""Mechanical constants for the glass CLI."""

from __future__ import annotations


CHECK_DICE_COUNT = 1
CHECK_DIE_SIDES = 10

RISK_THRESHOLDS = {
    "controlled": 5,
    "standard": 6,
    "risky": 7,
    "desperate": 8,
}

ATTRIBUTE_TIERS = {
    "rudimentary": -2,
    "standard": 0,
    "advanced": 1,
    "superior": 2,
    "transcendent": 4,
}

SKILL_TIERS = {
    "fool": -2,
    "apprentice": 0,
    "artisan": 1,
    "virtuoso": 2,
    "legend": 4,
}

ATTRIBUTES = (
    "vitality",
    "finesse",
    "focus",
    "resolve",
    "attunement",
    "ingenuity",
    "presence",
)

STARTER_MESSAGE_TYPES = {
    "table-talk",
    "banter",
    "instruction",
    "plot-hint",
    "secret",
}
