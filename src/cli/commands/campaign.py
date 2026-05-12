"""Campaign-level planning commands."""

from __future__ import annotations

from pathlib import Path

import click

from ..campaign import active_campaign_id, active_campaign_root
from ..config import get_paths
from ..errors import GlassError, agent_instruction
from ..ids import now_iso
from ..paths_resolve import display_path
from ..persistence import CampaignPersistence
from ..role import require_dm
from ..state import commit, load_state, queue_event
from ..yaml_io import command_params


@click.group()
def campaign() -> None:
    """Campaign-level durable planning commands."""


@campaign.command("pull-note")
@click.option(
    "--source",
    required=True,
    help="Non-adjacent real-world source/domain used in campaign planning.",
)
@click.option(
    "--used-in",
    "used_in",
    multiple=True,
    required=True,
    help="Repeat for each campaign surface changed by the pull.",
)
@click.option(
    "--note",
    required=True,
    help="Concrete utilization note naming what was borrowed and where it appears.",
)
@click.pass_context
def campaign_pull_note(
    ctx: click.Context,
    source: str,
    used_in: tuple[str, ...],
    note: str,
) -> None:
    """Record the campaign's non-adjacent pull utilization."""

    role = require_dm()
    source = _require_text(source, "--source")
    used_in_values = [_require_text(value, "--used-in") for value in used_in]
    note = _require_concrete_note(
        note,
        "--note",
        "Name the concrete detail borrowed and the campaign surface it changed.",
    )
    paths = get_paths()
    campaign_id = active_campaign_id()
    root = active_campaign_root()
    state = load_state(paths, campaign_id)
    destination = root / "dm" / "notes" / "pulls" / "campaign-non-adjacent.md"
    body = _campaign_pull_note_body(
        destination,
        source=source,
        used_in=used_in_values,
        note=note,
    )
    persistence = CampaignPersistence(
        paths=paths,
        campaign_id=campaign_id,
        campaign_root=root,
    )
    persisted = persistence.write_markdown(
        destination,
        body,
        state=state,
        graph=False,
        search=False,
    )
    queue_event(state, role.actor, f"campaign pull-note: {source}")
    result = {
        "campaign_id": campaign_id,
        "path": display_path(destination),
        "source": source,
        "used_in": used_in_values,
        "persistence": persisted.to_dict(),
    }
    commit(
        paths,
        state,
        ctx,
        "campaign.pull-note",
        command_params(source=source, used_in=used_in_values, note=note),
        result,
    )


def _campaign_pull_note_body(
    destination: Path,
    *,
    source: str,
    used_in: list[str],
    note: str,
) -> str:
    entry = "\n".join(
        [
            f"## Pull Recorded {now_iso()}",
            "",
            f"- **Source/domain:** {source}",
            "- **Used in:** " + "; ".join(used_in),
            f"- **Utilization:** {note}",
            "",
        ]
    )
    if destination.exists():
        existing = destination.read_text(encoding="utf-8").rstrip()
        return existing + "\n\n" + entry
    return "\n".join(
        [
            "---",
            "title: Campaign Non-Adjacent Pulls",
            "status: authored",
            "audience: dm",
            "type: campaign-pull-utilization",
            "---",
            "",
            "# Campaign Non-Adjacent Pulls",
            "",
            entry,
        ]
    )


def _require_text(value: str, option_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise GlassError(
            agent_instruction(
                f"{option_name} is required",
                f"Provide a non-empty value for `{option_name}`.",
            )
        )
    return cleaned


def _require_concrete_note(value: str, option_name: str, instruction: str) -> str:
    cleaned = _require_text(value, option_name)
    if len(cleaned.split()) < 6:
        raise GlassError(
            agent_instruction(
                f"{option_name} is too vague",
                instruction,
            )
        )
    return cleaned
