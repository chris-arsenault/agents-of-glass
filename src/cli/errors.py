"""Glass CLI error type."""

from __future__ import annotations

import click


class GlassError(click.ClickException):
    """Agent-friendly CLI error."""


def agent_instruction(problem: str, *steps: str) -> str:
    """Format a CLI error as a concrete instruction for the current agent."""
    message = problem.strip()
    clean_steps = [step.strip() for step in steps if step and step.strip()]
    if not clean_steps:
        return message
    lines = [message, "", "Do this:"]
    lines.extend(f"- {step}" for step in clean_steps)
    return "\n".join(lines)
