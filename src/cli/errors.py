"""Glass CLI error type."""

from __future__ import annotations

import click


class GlassError(click.ClickException):
    """Agent-friendly CLI error."""
