"""Retired character markdown display helper."""

from __future__ import annotations

from typing import Any

from .config import Paths


def write_public_character_mirror(
    paths: Paths,
    campaign_id: str,
    character: dict[str, Any],
) -> dict[str, Any]:
    del paths, campaign_id, character
    return {
        "status": "retired",
        "detail": "character markdown mirrors are not written; use character commands",
    }
