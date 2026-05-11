"""Turn commands."""

from __future__ import annotations

import json
import os
import random
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click

from .. import db as _db
from .. import embeddings as _embeddings
from .. import workspace as _workspace
from ..campaign import (
    active_campaign_id,
    active_campaign_root,
    lookup_player_character_id,
    pg_connection,
    resolve_active_campaign_workspace,
)
from ..config import REPO_ROOT, Paths, get_paths
from ..constants import (
    ATTRIBUTE_TIERS,
    ATTRIBUTES,
    RISK_THRESHOLDS,
    SKILL_TIERS,
    STARTER_MESSAGE_TYPES,
)
from ..entities import (
    markdown_title,
    parse_frontmatter,
    parse_sections,
    upsert_entity_from_path,
)
from ..errors import GlassError
from ..ids import new_id, now_iso, slugify
from ..messages import (
    infer_player_from_path,
    load_message_types,
    message_visible_to,
    player_dirs,
    require_message_type,
    require_recipient,
    roster,
)
from ..paths_resolve import (
    clean_relative_path,
    display_path,
    ensure_under,
    ensure_under_any,
    resolve_content_path,
    resolve_note_write_path,
)
from ..role import (
    Role,
    actor_for_turn,
    assert_character_writable,
    current_role,
    require_dm,
    require_player,
    role_label_for_turn,
)
from ..state import (
    append_audit,
    audit_path,
    commit,
    current_mode_record,
    default_state,
    inline_event_lines,
    load_state,
    normalize_state,
    queue_event,
    save_state,
    state_path,
    state_summary,
    transcript_path,)
from ..validation import (
    assert_attribute_name,
    clamp,
    outcome_for_margin,
    validate_key_values,
)
from ..yaml_io import (
    command_params,
    emit,
    make_jsonable,
    read_body,
    to_yaml,
    yaml_scalar,
)


_TURN_END_NEXT_CHOICES = ("default", "dm", "tev", "sumi", "renno", "kit")
_TURN_END_SCENE_STATUS_CHOICES = (
    "active",
    "closing",
    "ending",
    "ended",
    "blocked",
)


@click.group()
def turn() -> None:
    """Turn lifecycle commands."""


@turn.command("append")
@click.argument("markdown_file")
@click.option("--speaker")
@click.option("--role", "turn_role", type=click.Choice(["dm", "player", "operator"]))
@click.option("--mode", "mode_name")
@click.option("--scene", "scene_id")
@click.option("--character", "character_id")
@click.option("--end-file", "end_file")
@click.pass_context
def turn_append(
    ctx: click.Context,
    markdown_file: str,
    speaker: str | None,
    turn_role: str | None,
    mode_name: str | None,
    scene_id: str | None,
    character_id: str | None,
    end_file: str | None,
) -> None:
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    source = Path(markdown_file).expanduser()
    if not source.is_absolute():
        source = Path.cwd() / source
    if not source.exists():
        raise GlassError(f"turn markdown not found: {markdown_file}")
    body = source.read_text(encoding="utf-8").strip()
    turn_end = _load_turn_end_metadata(end_file)
    role = current_role()
    speaker_id = actor_for_turn(role, speaker)
    resolved_role = role_label_for_turn(role, turn_role)
    current = current_mode_record(state)
    resolved_mode = mode_name or (current["mode"] if current else "none")
    resolved_scene = scene_id or (current["scene_id"] if current else "none")
    export_info = _turn_export_info(resolved_scene)
    arc_id = export_info.get("arc_id")
    scene_type = export_info.get("scene_type") or resolved_mode
    state["turn_counter"] = int(state.get("turn_counter", 0)) + 1
    turn_id = state["turn_counter"]

    flushed: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    for event in state.get("pending_events", []):
        if event.get("actor") == speaker_id or role.can_do_anything:
            flushed.append(event)
        else:
            remaining.append(event)
    state["pending_events"] = remaining

    header = (
        f"## Turn {turn_id} - {speaker_id} ({resolved_role}) - "
        f"{resolved_mode}, {resolved_scene}"
    )
    parts = [header, "", body]
    event_lines = inline_event_lines(flushed)
    if event_lines:
        parts.extend(["", *event_lines])
    turn_markdown = "\n".join(parts).rstrip() + "\n\n"
    ts = now_iso()
    turn_number_in_scene = _fallback_turn_number_in_scene(
        state, scene_id=resolved_scene
    )

    record = {
        "turn_id": turn_id,
        "campaign_id": state["campaign"],
        "session_id": state["campaign"],
        "scene_id": resolved_scene,
        "mode": resolved_mode,
        "speaker": speaker_id,
        "role": resolved_role,
        "character_id": character_id,
        "source_path": str(source),
        "prose": body,
        "event_summaries": [event["summary"] for event in flushed],
        "events": flushed,
        "markdown": turn_markdown,
        "created_at": ts,
        "ts": ts,
        "arc_id": arc_id,
        "scene_type": scene_type,
        "turn_number_in_scene": turn_number_in_scene,
        "visibility": "public",
        **_turn_end_record_fields(turn_end),
    }
    search_title = (
        f"Turn {turn_id} - {speaker_id} "
        f"({resolved_mode}, {resolved_scene})"
    )
    search_body = _turn_search_body(body, turn_end)
    embedded = _embeddings.embed_text(
        _embeddings.embedding_text(title=search_title, body=search_body),
        kind="document",
    )
    with pg_connection() as conn:
        turn_number_in_scene = (
            _db.turn_count(
                conn,
                campaign_id=state["campaign"],
                scene=resolved_scene,
            )
            + 1
        )
        record = _db.turn_insert(
            conn,
            campaign_id=state["campaign"],
            turn_id=turn_id,
            session_id=state["campaign"],
            scene_id=resolved_scene,
            mode=resolved_mode,
            speaker=speaker_id,
            role=resolved_role,
            character_id=character_id,
            source_path=str(source),
            prose=body,
            event_summaries=[event["summary"] for event in flushed],
            events=flushed,
            markdown=turn_markdown,
            created_at=ts,
            arc_id=arc_id,
            scene_type=scene_type,
            turn_number_in_scene=turn_number_in_scene,
            visibility="public",
            **_turn_end_db_fields(turn_end),
        )
        _db.event_insert_many(
            conn,
            campaign_id=state["campaign"],
            scene_id=resolved_scene,
            turn_id=turn_id,
            events=flushed,
        )
        _db.search_chunk_upsert(
            conn,
            chunk_id=f"{state['campaign']}:turn:{turn_id}",
            campaign_id=state["campaign"],
            source_type="turn",
            source_id=str(turn_id),
            visibility="public",
            owner_actor=None,
            path=str(source),
            title=search_title,
            body=search_body,
            metadata={
                "turn_id": turn_id,
                "speaker": speaker_id,
                "role": resolved_role,
                "mode": resolved_mode,
                "scene_id": resolved_scene,
                "arc_id": arc_id,
            },
            embedding=embedded.vectors[0],
            embedding_model=embedded.model,
            embedding_provider=embedded.provider,
        )
        conn.commit()

    # Derived compatibility export. The structured row above is the canonical
    # communication surface for queries and the future viewer UI.
    root_transcript = transcript_path(paths, state["campaign"])
    root_transcript.parent.mkdir(parents=True, exist_ok=True)
    with root_transcript.open("a", encoding="utf-8") as handle:
        handle.write(turn_markdown)
    scene_transcript_path = export_info.get("scene_transcript_path")
    if isinstance(scene_transcript_path, Path):
        with scene_transcript_path.open("a", encoding="utf-8") as handle:
            handle.write(turn_markdown)

    state["turns"].append(record)
    result = {
        "turn": {key: value for key, value in record.items() if key != "markdown"},
        "events_flushed": flushed,
        "transcript_export_path": display_path(root_transcript),
        "scene_transcript_export_path": (
            display_path(scene_transcript_path)
            if isinstance(scene_transcript_path, Path)
            else None
        ),
    }
    commit(
        paths,
        state,
        ctx,
        "turn.append",
        command_params(markdown_file=markdown_file, speaker=speaker_id, end_file=end_file),
        result,
    )


@turn.command("end")
@click.option("--summary", required=True, help="1-3 sentence compact continuity for the next actor.")
@click.option(
    "--next",
    "next_speaker",
    type=click.Choice(_TURN_END_NEXT_CHOICES),
    default="default",
    show_default=True,
    help="Next actor override. Use default to keep normal rotation/action order.",
)
@click.option(
    "--state",
    "state_changes",
    multiple=True,
    required=True,
    help="Durable state/table/lore/message update, or 'no state change'. Repeat as needed.",
)
@click.option(
    "--rolls",
    required=True,
    help="Rolls/checks/pressure commands used, or 'none'.",
)
@click.option("--open-question", "open_questions", multiple=True)
@click.option(
    "--scene-status",
    type=click.Choice(_TURN_END_SCENE_STATUS_CHOICES),
    default="active",
    show_default=True,
)
@click.option("--position", default="", help="Position/leverage change, or unchanged.")
@click.option("--pressure", default="", help="Tracker/clock/HP/pressure change, or none.")
@click.option("--to", "end_file", default=None, hidden=True)
@click.pass_context
def turn_end(
    ctx: click.Context,
    summary: str,
    next_speaker: str,
    state_changes: tuple[str, ...],
    rolls: str,
    open_questions: tuple[str, ...],
    scene_status: str,
    position: str,
    pressure: str,
    end_file: str | None,
) -> None:
    """Record the required end-of-turn closeout block.

    The orchestrator commits public prose separately with `glass turn append`.
    This command records the compact context block that future TURN_START files
    embed, and optionally queues a next-speaker override.
    """
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    summary_text = _required_text(summary, "--summary")
    rolls_text = _required_text(rolls, "--rolls")
    state_items = [_required_text(item, "--state") for item in state_changes]
    open_items = [item.strip() for item in open_questions if item.strip()]
    target = _turn_end_target_path(end_file=end_file)
    target.parent.mkdir(parents=True, exist_ok=True)

    current = current_mode_record(state) or {}
    payload = {
        "summary": summary_text,
        "next": next_speaker,
        "state": state_items,
        "rolls": rolls_text,
        "open_questions": open_items,
        "scene_status": scene_status,
        "position": position.strip(),
        "pressure": pressure.strip(),
        "campaign_id": campaign_id,
        "turn_id": os.environ.get("GLASS_TURN_ID", ""),
        "actor": role.actor,
        "role": role.kind,
        "mode": current.get("mode"),
        "scene_id": current.get("scene_id"),
        "created_at": now_iso(),
    }
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if next_speaker != "default":
        state["next_speakers"].append({"agent": next_speaker, "source": "turn.end"})
        queue_event(state, role.actor, f"turn end handoff -> {next_speaker}")

    result = {
        "turn_closeout_path": display_path(target),
        "summary": summary_text,
        "next": next_speaker,
        "state": state_items,
        "rolls": rolls_text,
        "open_questions": open_items,
        "scene_status": scene_status,
        "queue": list(state.get("next_speakers", [])),
    }
    commit(
        paths,
        state,
        ctx,
        "turn.end",
        command_params(
            summary=summary_text,
            next=next_speaker,
            state=state_items,
            rolls=rolls_text,
            open_questions=open_items,
            scene_status=scene_status,
            position=position.strip(),
            pressure=pressure.strip(),
        ),
        result,
    )


def _load_turn_end_metadata(end_file: str | None) -> dict[str, Any]:
    if not end_file:
        return {}
    path = Path(end_file).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GlassError(f"turn end metadata not found: {end_file}") from exc
    except json.JSONDecodeError as exc:
        raise GlassError(f"invalid turn end metadata: {end_file}: {exc}") from exc
    if not isinstance(payload, dict):
        raise GlassError("turn end metadata must be a JSON object")
    summary = str(payload.get("summary") or "").strip()
    if not summary:
        raise GlassError("turn end metadata is missing summary")
    return payload


def _turn_end_record_fields(turn_end: dict[str, Any]) -> dict[str, Any]:
    return {
        "turn_summary": str(turn_end.get("summary") or ""),
        "next_speaker": str(turn_end.get("next") or "default"),
        "scene_status": str(turn_end.get("scene_status") or "active"),
        "state_changes": list(turn_end.get("state") or []),
        "rolls": str(turn_end.get("rolls") or ""),
        "open_questions": list(turn_end.get("open_questions") or []),
        "position": str(turn_end.get("position") or ""),
        "pressure": str(turn_end.get("pressure") or ""),
        "turn_end": dict(turn_end),
    }


def _turn_end_db_fields(turn_end: dict[str, Any]) -> dict[str, Any]:
    return _turn_end_record_fields(turn_end)


def _turn_search_body(body: str, turn_end: dict[str, Any]) -> str:
    parts = [body]
    summary = str(turn_end.get("summary") or "").strip()
    if summary:
        parts.append(summary)
    for key in ("state", "rolls", "open_questions", "position", "pressure"):
        value = turn_end.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value if str(item).strip())
        elif value:
            parts.append(str(value))
    return "\n\n".join(part for part in parts if part)


def _required_text(value: str, label: str) -> str:
    text = value.strip()
    if not text:
        raise GlassError(f"{label} cannot be empty")
    return text


def _turn_end_target_path(*, end_file: str | None) -> Path:
    raw = end_file or os.environ.get("AOG_TURN_CLOSEOUT")
    if raw:
        path = Path(raw).expanduser()
        return path if path.is_absolute() else Path.cwd() / path
    raise GlassError("turn end needs AOG_TURN_CLOSEOUT or --to")


def _turn_export_info(scene_id: str) -> dict[str, Any]:
    try:
        workspace = resolve_active_campaign_workspace()
        current = _workspace.current_scene(workspace)
    except GlassError:
        return {}
    if not current or current.get("scene_id") != scene_id:
        return {}
    arc_id = current.get("arc_id")
    transcript: Path | None = None
    if arc_id:
        transcript = workspace.scene_dir(str(arc_id), scene_id) / "transcript.md"
        transcript.parent.mkdir(parents=True, exist_ok=True)
        if not transcript.exists():
            transcript.write_text(f"# Scene: {scene_id}\n\n", encoding="utf-8")
    return {
        "arc_id": arc_id,
        "scene_type": current.get("scene_type"),
        "scene_transcript_path": transcript,
    }


def _fallback_turn_number_in_scene(state: dict[str, Any], *, scene_id: str) -> int:
    return (
        sum(1 for turn in state.get("turns", []) if turn.get("scene_id") == scene_id)
        + 1
    )


_HANDOFF_AGENT_IDS = ("dm", "tev", "sumi", "renno", "kit")
_PLAYER_AGENT_IDS = ("tev", "sumi", "renno", "kit")
_ACTION_PARTICIPANT_IDS = ("dm", "tev", "sumi", "renno", "kit")


@turn.command("handoff")
@click.argument("agent_id")
@click.pass_context
def turn_handoff(ctx: click.Context, agent_id: str) -> None:
    """Append a one-off override to the next-speaker queue.

    Each call appends; multiple calls in a single turn queue up multiple
    redirects in the order called. The orchestrator pops one off per
    turn. After the queue is drained, round-robin resumes from the last
    redirected agent.

    Example: a DM in their turn calls `glass turn handoff sumi` then
    `glass turn handoff dm`. Sumi runs next, then the DM, then rotation
    continues from the DM (dm -> next-in-rotation).
    """
    if agent_id not in _HANDOFF_AGENT_IDS:
        raise GlassError(
            f"unknown agent id {agent_id!r}; valid: {', '.join(_HANDOFF_AGENT_IDS)}"
        )
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    state["next_speakers"].append({"agent": agent_id})
    queue_event(state, role.actor, f"handoff -> {agent_id}")
    result = {"queue": list(state["next_speakers"])}
    commit(
        paths, state, ctx, "turn.handoff",
        command_params(agent_id=agent_id), result,
    )


@turn.command("initiative")
@click.option(
    "--participants",
    "participants_csv",
    default=None,
    help="Comma-separated agent ids. Defaults to dm,tev,sumi,renno,kit.",
)
@click.option("--label", default="initiative", show_default=True)
@click.pass_context
def turn_initiative(
    ctx: click.Context, participants_csv: str | None, label: str
) -> None:
    """DM-only: roll and persist action-scene turn order.

    Use this after the DM's opening layout for quickfire action scenes.
    The DM is a participant by default, so their next turn after the
    opening layout can land wherever the initiative roll puts it.
    """
    role = require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    current = current_mode_record(state)
    if not current or current.get("mode") == "none":
        raise GlassError("cannot roll initiative without an active mode")

    if participants_csv:
        participants = [
            entry.strip() for entry in participants_csv.split(",") if entry.strip()
        ]
    else:
        participants = list(_ACTION_PARTICIPANT_IDS)
    if not participants:
        raise GlassError("initiative needs at least one participant")

    seen: set[str] = set()
    for participant in participants:
        if participant not in _ACTION_PARTICIPANT_IDS:
            raise GlassError(
                f"unknown participant {participant!r}; valid: "
                f"{', '.join(_ACTION_PARTICIPANT_IDS)}"
            )
        if participant in seen:
            raise GlassError(f"duplicate initiative participant {participant!r}")
        seen.add(participant)

    rng = random.SystemRandom()
    rolls: list[dict[str, Any]] = []
    for participant in participants:
        dice = [rng.randint(1, 6), rng.randint(1, 6)]
        rolls.append(
            {
                "agent": participant,
                "dice": dice,
                "total": sum(dice),
                "tiebreaker": rng.randint(1, 1_000_000),
            }
        )
    ordered_rolls = sorted(
        rolls,
        key=lambda item: (int(item["total"]), int(item["tiebreaker"])),
        reverse=True,
    )
    order = [str(item["agent"]) for item in ordered_rolls]
    public_rolls = [
        {
            "agent": item["agent"],
            "dice": item["dice"],
            "total": item["total"],
        }
        for item in ordered_rolls
    ]
    state["action_order"] = {
        "mode": current["mode"],
        "scene_id": current["scene_id"],
        "label": label,
        "round": 1,
        "cursor": 0,
        "order": order,
        "rolls": public_rolls,
        "created_at": now_iso(),
        "created_by": role.actor,
    }
    with pg_connection() as conn:
        persisted = _db.action_order_upsert(
            conn,
            campaign_id=campaign_id,
            mode=str(current["mode"]),
            scene_id=str(current["scene_id"]),
            label=label,
            order=order,
            rolls=public_rolls,
            actor=role.actor,
        )
    state["action_order"] = {
        key: persisted[key]
        for key in ("mode", "scene_id", "label", "round", "cursor", "order", "rolls")
    } | {"created_at": persisted["created_at"], "created_by": role.actor}

    order_summary = ", ".join(
        f"{item['agent']}({item['total']})" for item in public_rolls
    )
    queue_event(
        state,
        role.actor,
        f"{label} order @ {current['scene_id']}: {order_summary}",
    )
    result = {
        "action_order": state["action_order"],
    }
    commit(
        paths,
        state,
        ctx,
        "turn.initiative",
        command_params(participants=participants, label=label),
        result,
    )


@turn.command("rapid-round")
@click.argument("prompt_parts", nargs=-1, required=True)
@click.option("--players", "players_csv", default=None,
              help="Comma-separated player ids (subset of tev,sumi,renno,kit). "
                   "Order matters. Defaults to all four in declaration order.")
@click.pass_context
def turn_rapid_round(
    ctx: click.Context, prompt_parts: tuple[str, ...], players_csv: str | None,
) -> None:
    """DM-only: queue a single-shot rapid response from each player.

    Each queued turn sees the prompt in TURN_START.md and is told to give
    a brief reactive narration only — no rolls, no full menu, no handoff.
    Use this when the DM needs each player's character to react to the
    same stimulus quickly without spending a full per-player turn.
    """
    require_dm()
    if players_csv:
        targets = [p.strip() for p in players_csv.split(",") if p.strip()]
    else:
        targets = list(_PLAYER_AGENT_IDS)
    for player in targets:
        if player not in _PLAYER_AGENT_IDS:
            raise GlassError(
                f"unknown player {player!r}; valid: {', '.join(_PLAYER_AGENT_IDS)}"
            )
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    prompt = " ".join(prompt_parts).strip()
    if not prompt:
        raise GlassError("rapid-round prompt cannot be empty")
    for player in targets:
        state["next_speakers"].append({
            "agent": player,
            "rapid_prompt": prompt,
        })
    queue_event(
        state, role.actor,
        f"rapid-round queued for {','.join(targets)}: {prompt[:60]}",
    )
    result = {"queue": list(state["next_speakers"]), "prompt": prompt}
    commit(
        paths, state, ctx, "turn.rapid-round",
        command_params(prompt=prompt, players=targets), result,
    )


@turn.command("housekeeping-round")
@click.option(
    "--players",
    "players_csv",
    default=None,
    help="Comma-separated player ids. Defaults to tev,sumi,renno,kit.",
)
@click.option(
    "--previous-scene",
    default="",
    help="Scene that just closed. Used only for TURN_START context.",
)
@click.option(
    "--next-scene",
    default="",
    help="Scene being staged next. Used only for TURN_START context.",
)
@click.option(
    "--next",
    "next_actor",
    type=click.Choice(_TURN_END_NEXT_CHOICES),
    default="tev",
    show_default=True,
    help="Actor queued after housekeeping. Use default to leave rotation alone.",
)
@click.pass_context
def turn_housekeeping_round(
    ctx: click.Context,
    players_csv: str | None,
    previous_scene: str,
    next_scene: str,
    next_actor: str,
) -> None:
    """DM-only: queue one non-plot housekeeping turn for each player.

    Use this at a scene boundary after the DM has wrapped the old scene,
    staged the next scene, and started the next scene's play mode. The queued
    player turns are for notes, journals, sheet cleanup, and private requests;
    they must not introduce new in-fiction action or mid/long-term plot design.
    """
    require_dm()
    if players_csv:
        targets = [p.strip() for p in players_csv.split(",") if p.strip()]
    else:
        targets = list(_PLAYER_AGENT_IDS)
    seen: set[str] = set()
    for player in targets:
        if player not in _PLAYER_AGENT_IDS:
            raise GlassError(
                f"unknown player {player!r}; valid: {', '.join(_PLAYER_AGENT_IDS)}"
            )
        if player in seen:
            raise GlassError(f"duplicate player {player!r}")
        seen.add(player)

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    previous = previous_scene.strip()
    upcoming = next_scene.strip()

    for player in targets:
        state["next_speakers"].append(
            {
                "agent": player,
                "housekeeping": True,
                "previous_scene": previous,
                "next_scene": upcoming,
                "source": "turn.housekeeping-round",
            }
        )
    if next_actor != "default":
        state["next_speakers"].append(
            {
                "agent": next_actor,
                "after_housekeeping": True,
                "previous_scene": previous,
                "next_scene": upcoming,
                "source": "turn.housekeeping-round",
            }
        )
    queue_event(
        state,
        role.actor,
        (
            f"housekeeping-round queued for {','.join(targets)}"
            f"; next scene actor: {next_actor}"
        ),
    )
    result = {
        "queue": list(state["next_speakers"]),
        "players": targets,
        "previous_scene": previous,
        "next_scene": upcoming,
        "next": next_actor,
    }
    commit(
        paths,
        state,
        ctx,
        "turn.housekeeping-round",
        command_params(
            players=targets,
            previous_scene=previous,
            next_scene=upcoming,
            next=next_actor,
        ),
        result,
    )


@turn.command("restart-order")
@click.argument("agent_id")
@click.pass_context
def turn_restart_order(ctx: click.Context, agent_id: str) -> None:
    """DM-only: clear any pending handoff queue + redirect to AGENT_ID.

    Use this when the rotation needs a hard reset — e.g., a player went
    out of order and you want to restart from a specific PC. Round-robin
    resumes from the new agent on subsequent turns.
    """
    require_dm()
    if agent_id not in _HANDOFF_AGENT_IDS:
        raise GlassError(
            f"unknown agent id {agent_id!r}; valid: {', '.join(_HANDOFF_AGENT_IDS)}"
        )
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    cleared = list(state["next_speakers"])
    state["next_speakers"] = [{"agent": agent_id}]
    queue_event(state, role.actor, f"restart turn order -> {agent_id}")
    result = {"cleared": cleared, "queue": list(state["next_speakers"])}
    commit(
        paths, state, ctx, "turn.restart-order",
        command_params(agent_id=agent_id), result,
    )


@turn.command("clear-handoff")
@click.pass_context
def turn_clear_handoff(ctx: click.Context) -> None:
    """DM-only: wipe any pending handoff queue (rare — usually the
    orchestrator consumes entries automatically on each turn)."""
    require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    previous = list(state.get("next_speakers", []))
    state["next_speakers"] = []
    result = {"cleared": previous}
    commit(paths, state, ctx, "turn.clear-handoff", {}, result)
