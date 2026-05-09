"""Mechanical constants for the glass CLI."""

from __future__ import annotations


RISK_THRESHOLDS = {
    "controlled": 7,
    "standard": 8,
    "risky": 9,
    "desperate": 10,
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
