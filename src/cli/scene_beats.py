"""Shared helpers for scene-local clocks and dramatic beats."""

from __future__ import annotations

from typing import Any

from . import db as _db


ACTIVE_PLAY_TURN_KINDS = {"active-play", "active-play-dm"}
BEAT_WARNING_AGE = 8
BEAT_MAX_AGE = 10
BEAT_MAX_ACTIVE = 3


def beat_check_required_for_turn(turn_context: dict[str, Any] | None) -> bool:
    if not isinstance(turn_context, dict):
        return False
    return str(turn_context.get("kind") or "").strip() in ACTIVE_PLAY_TURN_KINDS


def turn_number_from_id(turn_id: str | None) -> int | None:
    raw = str(turn_id or "").strip()
    if "-t" not in raw:
        return None
    suffix = raw.rsplit("-t", 1)[-1]
    if not suffix.isdigit():
        return None
    return int(suffix)


def clock_progress_text(clock: dict[str, Any]) -> str:
    value = int(clock.get("value", 0) or 0)
    max_value = int(clock.get("max", 0) or 0)
    direction = str(clock.get("direction") or "progress")
    return f"{value}/{max_value} {direction}"


def beat_status_note(age: int) -> str | None:
    if age >= BEAT_MAX_AGE:
        return (
            "must resolve, convert, or end the scene before another non-pass turn."
        )
    if age >= BEAT_WARNING_AGE:
        return (
            "close soon; do not add another diagnostic layer unless it resolves this beat."
        )
    return None


def scene_close_note(completed_beats: int) -> str | None:
    if completed_beats >= 5:
        return (
            "this scene has ample resolved material; when the current scene clock "
            "lands, close or transition unless a genuinely new scene question "
            "needs its own clock."
        )
    if completed_beats >= 4:
        return (
            "this scene has enough resolved material to close when the current "
            "scene clock lands; keep any next clock choice deliberate."
        )
    return None


def scene_contract_snapshot(
    conn: "Any",
    *,
    campaign_id: str,
    scene_id: str,
    role_kind: str,
    reference_turn_number: int | None = None,
) -> dict[str, Any]:
    active_clocks = _db.scene_clock_list(
        conn,
        campaign_id=campaign_id,
        scene_id=scene_id,
        include_inactive=False,
    )
    all_clocks = _db.scene_clock_list(
        conn,
        campaign_id=campaign_id,
        scene_id=scene_id,
        include_inactive=True,
    )
    all_beats = _db.scene_beat_list(
        conn,
        campaign_id=campaign_id,
        scene_id=scene_id,
        include_inactive=True,
    )
    clock_by_id = {str(clock["clock_id"]): clock for clock in all_clocks}
    visible_clocks = [
        clock
        for clock in active_clocks
        if role_kind != "player" or clock.get("visibility") == "public"
    ]
    active_beats_raw = [beat for beat in all_beats if beat.get("status") == "active"]
    active_beats: list[dict[str, Any]] = []
    for beat in active_beats_raw:
        clock = clock_by_id.get(str(beat.get("clock_id") or ""))
        clock_visible = role_kind != "player" or (
            isinstance(clock, dict) and clock.get("visibility") == "public"
        )
        age = int(beat.get("non_pass_turns", 0) or 0)
        active_beats.append(
            {
                **beat,
                "age_text": f"{age}/{BEAT_MAX_AGE}",
                "clock_label": clock.get("label") if clock_visible and clock else None,
                "clock_visible": bool(clock_visible),
                "status_note": beat_status_note(age),
            }
        )

    recent_beats: list[dict[str, Any]] = []
    if reference_turn_number is not None:
        threshold = max(reference_turn_number - 1, 0)
        for beat in all_beats:
            if beat.get("status") == "active":
                continue
            closed_turn_number = turn_number_from_id(str(beat.get("closed_turn_id") or ""))
            if closed_turn_number is None or closed_turn_number < threshold:
                continue
            clock = clock_by_id.get(str(beat.get("clock_id") or ""))
            clock_visible = role_kind != "player" or (
                isinstance(clock, dict) and clock.get("visibility") == "public"
            )
            recent_beats.append(
                {
                    **beat,
                    "clock_label": clock.get("label") if clock_visible and clock else None,
                }
            )

    completed_beats = sum(1 for beat in all_beats if beat.get("status") == "closed")
    hidden_clock_count = max(len(active_clocks) - len(visible_clocks), 0)
    return {
        "scene_id": scene_id,
        "active_clock_count": len(active_clocks),
        "visible_clock_count": len(visible_clocks),
        "hidden_clock_count": hidden_clock_count,
        "clocks": [
            {
                **clock,
                "progress_text": clock_progress_text(clock),
            }
            for clock in visible_clocks
        ],
        "active_beat_count": len(active_beats),
        "active_beats": active_beats,
        "recent_beats": recent_beats,
        "completed_beats": completed_beats,
        "warning_beats": [
            beat for beat in active_beats if int(beat.get("non_pass_turns", 0) or 0) >= BEAT_WARNING_AGE
        ],
        "expired_beats": [
            beat for beat in active_beats if int(beat.get("non_pass_turns", 0) or 0) >= BEAT_MAX_AGE
        ],
        "scene_note": scene_close_note(completed_beats),
    }


def scene_contract_failures(snapshot: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if int(snapshot.get("active_clock_count", 0) or 0) <= 0:
        failures.append("this active scene has 0 scene clocks")
    if int(snapshot.get("active_beat_count", 0) or 0) <= 0:
        failures.append("this active scene has 0 active beats")
    if int(snapshot.get("active_beat_count", 0) or 0) > BEAT_MAX_ACTIVE:
        failures.append(
            f"this active scene has more than {BEAT_MAX_ACTIVE} active beats"
        )
    for beat in snapshot.get("active_beats", []):
        if int(beat.get("non_pass_turns", 0) or 0) > BEAT_MAX_AGE:
            failures.append(
                f"beat `{beat.get('beat_id')}` exceeds {BEAT_MAX_AGE}/{BEAT_MAX_AGE}"
            )
    return failures
