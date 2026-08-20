"""Neutral continuity fact commands."""

from __future__ import annotations

import click

from ..campaign import active_campaign_id
from ..errors import GlassError, agent_instruction
from ..facts import (
    FACT_IMPORTANCE,
    FactSpec,
    default_fact_scope_for_mode,
    fact_pack,
    normalize_fact_audience,
    parse_fact_spec,
    render_fact_pack_markdown,
    set_fact,
)
from ..role import current_role
from ..state import current_mode_record, load_state
from ..config import get_paths
from ..yaml_io import emit


@click.group()
def fact() -> None:
    """Read and write neutral continuity facts."""


@fact.command("set")
@click.argument("spec", nargs=-1, required=True)
@click.option(
    "--scope", "scope_id", default=None, help="Fact scope id. Defaults to active scene or campaign."
)
@click.option(
    "--visibility",
    default="public",
    type=click.Choice(["public", "dm", "private"]),
    show_default=True,
)
@click.option(
    "--importance",
    "salience",
    default="medium",
    type=click.Choice(list(FACT_IMPORTANCE)),
    show_default=True,
)
@click.option(
    "--audience",
    required=True,
    type=click.Choice(["continuity", "profile", "meta"]),
    help="Required fact audience: continuity, profile, or meta.",
)
def fact_set(
    spec: tuple[str, ...],
    scope_id: str | None,
    visibility: str,
    salience: str,
    audience: str,
) -> None:
    """Set one current fact.

    Example:

        glass fact set "mox.status = Mox is pinned in the second pipe"

        glass fact set "mera.trusts -> mox = Mera trusts Mox after plain speech"
    """

    state = load_state(get_paths(), active_campaign_id())
    default_scope, _active_scene = current_fact_scope(state, scope_id)
    raw = " ".join(spec).strip()
    try:
        parsed = parse_fact_spec(
            raw,
            default_scope_id=default_scope,
            visibility=visibility,
            salience=salience,
            audience=audience,
        )
    except ValueError as exc:
        raise GlassError(
            agent_instruction(
                "invalid fact",
                "Use `subject.predicate = neutral text` or "
                "`subject.predicate -> object = neutral text`.",
                str(exc),
            )
        ) from exc
    emit(set_fact_service(parsed))


def current_fact_scope(
    state: dict,
    scope_id: str | None = None,
) -> tuple[str, str | None]:
    mode = current_mode_record(state) or {}
    mode_name = str(mode.get("mode") or "").strip()
    active_scene = str(mode.get("scene_id") or "").strip() or None
    default_scope = scope_id or default_fact_scope_for_mode(mode_name, active_scene)
    return default_scope, active_scene


def set_fact_service(spec: FactSpec) -> dict:
    """Persist one structured fact for the current turn context."""

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    mode = current_mode_record(state) or {}
    role = current_role()
    active_scene = str(mode.get("scene_id") or "").strip() or None
    return set_fact(
        campaign_id=campaign_id,
        spec=spec,
        actor=role.actor,
        turn_id=str(state.get("active_turn_id") or "") or None,
        mode=str(mode.get("mode") or "") or None,
        scene_id=active_scene,
    )


def set_fact_structured_service(
    *,
    subject_id: str,
    predicate: str,
    text: str,
    audience: str,
    object_id: str | None = None,
    scope_id: str | None = None,
    visibility: str = "public",
    salience: str = "medium",
) -> dict:
    """Persist one structured fact for the current turn context."""

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    default_scope, active_scene = current_fact_scope(state, scope_id)
    mode = current_mode_record(state) or {}
    role = current_role()
    return set_fact(
        campaign_id=campaign_id,
        spec=FactSpec(
            subject_id=subject_id,
            predicate=predicate,
            text=text,
            object_id=object_id or None,
            scope_id=default_scope,
            visibility=visibility,
            salience=salience,
            audience=normalize_fact_audience(audience),
        ),
        actor=role.actor,
        turn_id=str(state.get("active_turn_id") or "") or None,
        mode=str(mode.get("mode") or "") or None,
        scene_id=active_scene,
    )


@fact.command("pack")
@click.option(
    "--scene", "scene_id", default=None, help="Scene id. Defaults to the active mode scene."
)
@click.option("--actor", default=None, help="Actor id. Defaults to current role actor.")
@click.option("--limit", type=int, default=80, show_default=True)
@click.option(
    "--audience",
    required=True,
    type=click.Choice(["continuity", "profile", "meta", "all"]),
    help="Required fact audience to read.",
)
@click.option("--format", "output_format", type=click.Choice(["yaml", "markdown"]), default="yaml")
def fact_pack_command(
    scene_id: str | None,
    actor: str | None,
    limit: int,
    audience: str,
    output_format: str,
) -> None:
    """Print the current fact pack for this turn scope."""

    pack = fact_pack_service(scene_id=scene_id, actor=actor, audience=audience, limit=limit)
    if output_format == "markdown":
        click.echo(render_fact_pack_markdown(pack))
    else:
        emit(pack)


def fact_pack_service(
    *,
    audience: str,
    scene_id: str | None = None,
    actor: str | None = None,
    limit: int = 80,
) -> dict:
    """Read the current fact pack for this turn scope."""

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    mode = current_mode_record(state) or {}
    role = current_role()
    return fact_pack(
        campaign_id=campaign_id,
        scene_id=scene_id or str(mode.get("scene_id") or "") or None,
        actor=actor or role.actor,
        visibility="dm" if role.kind in {"dm", "operator"} else "public",
        audience=audience,
        limit=limit,
    )
