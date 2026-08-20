"""MCP adapter for the agent-facing Glass runtime.

The MCP server is intentionally a typed transport adapter. Tools expose
domain-shaped schemas and execute through local runtime services where those
services exist; they do not call the local HTTP API.
"""

from __future__ import annotations

import sys
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, TypeAdapter, ValidationError
from pydantic_core import PydanticCustomError

from .campaign import active_campaign_id
from .commands.arc import (
    activate_arc_service,
    close_arc_service,
    close_check_arc_service,
    create_arc_service,
    current_arc_service,
    list_arcs_service,
)
from .commands.beat import (
    close_beat_service,
    convert_beat_service,
    start_beat_service,
)
from .commands.character import (
    add_signature_move_service,
    add_consequence_service,
    award_xp_service,
    bulk_get_characters_service,
    create_character_service,
    declare_skill_service,
    get_character_service,
    inventory_add_service,
    inventory_remove_service,
    level_up_service,
    list_consequences_service,
    list_characters_service,
    resolve_consequence_service,
    set_hp_service,
    signature_status_service,
)
from .commands.clock import (
    list_clocks_service,
    set_clock_service,
    set_clock_status_service,
    show_clock_service,
    tick_clock_service,
)
from .commands.facade import check_service, done_service
from .commands.fact import (
    current_fact_scope,
    fact_pack_service,
    render_fact_pack_markdown,
)
from .commands.lore import (
    lore_list_service,
    lore_read_service,
    lore_search_service,
)
from .commands.mode import current_mode_service, end_mode_service, start_mode_service
from .commands.msg import read_messages_service, send_message_service
from .commands.quest import quest_beat_service
from .commands.roll import roll_service
from .commands.scene import (
    closing_down_scene_service,
    create_scene_service,
    current_scene_service,
    declare_scene_clock_service,
    end_scene_service,
    list_scene_trackers_service,
    list_scenes_service,
    pressure_scene_service,
    scene_transition_service,
    set_scene_tracker_service,
    tick_scene_clock_service,
    tick_scene_tracker_service,
)
from .commands.thread import advance_thread_service, current_thread_service
from .commands.turn import (
    append_turn_service,
    clear_handoff_turn_service,
    handoff_turn_service,
    housekeeping_round_turn_service,
    initiative_turn_service,
    rapid_round_turn_service,
    restart_order_turn_service,
)
from .errors import GlassError
from .facts import LOW_FACT_IMPORTANCE, FactSpec, set_fact_specs
from .local_env import load_repo_env
from .role import current_role
from .config import get_paths
from .state import append_audit, load_state
from .yaml_io import to_yaml


GlassResult = dict[str, Any]
FactAudience = Literal["continuity", "profile", "meta"]
FactImportance = Literal["high", "medium", "low", "minor"]
SceneStatus = Literal["active", "closing", "ending", "ended", "blocked"]


class FactUpdate(BaseModel):
    """One neutral durable continuity fact committed by a hard-state tool."""

    subject_id: Annotated[str, Field(description="Entity id the fact is about.")]
    predicate: Annotated[str, Field(description="Relationship or property name.")]
    text: Annotated[str, Field(description="Neutral factual statement.")]
    audience: Annotated[
        FactAudience,
        Field(
            description=(
                "Required read audience: continuity for playable state, "
                "profile for character texture, meta for process guidance."
            )
        ),
    ]
    importance: Annotated[
        FactImportance,
        Field(
            description=(
                "Required fact size. high/medium facts appear in fact-pack reads. "
                "low/minor facts are stored for audit/debug but omitted from fact-pack "
                "output and should not carry playable state."
            )
        ),
    ]
    object_id: Annotated[
        str,
        Field(description="Optional related entity id for relationship facts."),
    ] = ""


CharacterInitialFacts = Annotated[
    list[FactUpdate],
    Field(
        min_length=1,
        description=(
            "Initial character facts to commit atomically with character creation. "
            "Use continuity for playable sheet facts and profile for table texture."
        ),
    ),
]


CharacterGoals = Annotated[
    list[str],
    Field(
        min_length=2,
        max_length=3,
        description="Exactly 2-3 concrete character goals.",
    ),
]
AttributeName = Literal[
    "vitality",
    "finesse",
    "focus",
    "resolve",
    "attunement",
    "ingenuity",
    "presence",
]
AttributeTier = Literal[
    "rudimentary",
    "standard",
    "advanced",
    "superior",
    "transcendent",
]


class CharacterLifePrompt(BaseModel):
    """A concrete response to one character life prompt."""

    prompt: Annotated[str, Field(description="The life prompt being answered.")]
    answer: Annotated[
        str,
        Field(description="Concrete behavior that answers the prompt; not a mood label."),
    ]


CharacterLifePrompts = Annotated[
    list[CharacterLifePrompt],
    Field(min_length=2, max_length=3, description="Exactly 2-3 life-prompt answers."),
]


class CharacterAttribute(BaseModel):
    """One character attribute override."""

    name: AttributeName
    tier: AttributeTier


CharacterAttributes = Annotated[
    list[CharacterAttribute],
    Field(description="Optional attribute tier overrides."),
]


class CharacterSkillSeed(BaseModel):
    """One named starting skill."""

    name: Annotated[str, Field(description="Plain skill name.")]


class CharacterStartingSkills(BaseModel):
    """Starting trained skills: one artisan and exactly two apprentice skills."""

    artisan: CharacterSkillSeed
    apprentices: Annotated[list[CharacterSkillSeed], Field(min_length=2, max_length=2)]


class CharacterPullUtilization(BaseModel):
    """Typed non-adjacent pull used to prevent flat or samey characters."""

    source: Annotated[
        str,
        Field(description="The non-adjacent source/domain used as the character seed."),
    ]
    thesis: Annotated[
        str,
        Field(description="The identity thesis that makes the source playable."),
    ]


class CharacterStartingItem(BaseModel):
    """One starting inventory item committed with character creation."""

    item_id: Annotated[str, Field(description="Stable item id used by inventory tools.")]
    name: Annotated[str, Field(description="Public item name.")]
    descriptor: Annotated[str, Field(description="Plain prose descriptor for normal narration.")]
    qty: Annotated[int, Field(ge=1, description="Starting quantity.")]
    effect_tags: Annotated[
        list[str],
        Field(description="Short tags for concrete ways this item can matter."),
    ]


CharacterStartingItems = Annotated[
    list[CharacterStartingItem],
    Field(min_length=1, description="Starting inventory committed with the character row."),
]


class StateFactUpdate(BaseModel):
    """One neutral fact inside a batched state update."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["fact"]
    subject_id: Annotated[str, Field(description="Entity id the fact is about.")]
    predicate: Annotated[str, Field(description="Relationship or property name.")]
    text: Annotated[str, Field(description="Neutral factual statement.")]
    audience: FactAudience
    importance: Annotated[
        FactImportance,
        Field(
            description=(
                "Required fact size: high or medium for playable state; low/minor "
                "are stored but omitted from fact-pack output and will return a warning."
            )
        ),
    ]
    object_id: Annotated[str, Field(description="Optional related entity id.")] = ""
    scope_id: Annotated[str, Field(description="Optional explicit scope id.")] = ""


class StateInventoryAdd(BaseModel):
    """Add or increase one inventory item inside a batched state update."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["inventory_add"]
    character_id: str
    item_id: str
    name: str
    descriptor: str
    qty: Annotated[int, Field(ge=1)]
    effect_tags: list[str]


class StateInventoryRemove(BaseModel):
    """Remove quantity from one inventory item inside a batched state update."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["inventory_remove"]
    character_id: str
    item_id: str
    qty: Annotated[int, Field(ge=1)]


StateUpdate = Annotated[
    StateFactUpdate | StateInventoryAdd | StateInventoryRemove,
    Field(discriminator="kind"),
]


def _reject_string_state_updates(value: Any) -> Any:
    if isinstance(value, list) and any(isinstance(item, str) for item in value):
        raise PydanticCustomError(
            "state_update_object_required",
            "state updates must be typed objects, not strings; use "
            '{"kind": "fact", "audience": "continuity", "importance": "medium", '
            '"subject_id": "<entity-id>", "predicate": "<predicate>", '
            '"text": "<neutral fact>"}',
        )
    return value


StateUpdates = Annotated[
    list[StateUpdate],
    Field(
        min_length=1,
        description=(
            "Batched durable updates for this turn. Use one call for multiple "
            "facts and inventory changes."
        ),
    ),
    BeforeValidator(_reject_string_state_updates),
]
_STATE_UPDATES_ADAPTER = TypeAdapter(list[StateUpdate])


def _state_update_shape_error(exc: ValidationError) -> GlassError:
    return GlassError(
        "glass_state_update requires `updates` to be a non-empty list of typed "
        "objects, never strings. Use objects like "
        '`{"kind": "fact", "audience": "continuity", "importance": "medium", '
        '"scope_id": "<scene-id>", "subject_id": "<entity-id>", "predicate": '
        '"<predicate>", "text": "<neutral fact>"}`. '
        "For inventory changes use "
        '`{"kind": "inventory_add", "character_id": "<character-id>", '
        '"item_id": "<item-id>", "name": "<item name>", "descriptor": '
        '"<plain descriptor>", "qty": 1, "effect_tags": ["<tag>"]}` or '
        '`{"kind": "inventory_remove", "character_id": "<character-id>", '
        '"item_id": "<item-id>", "qty": 1}`.'
        f"\n\nValidation detail:\n{exc}"
    )


mcp = FastMCP(
    "Agents of Glass",
    instructions=(
        "Use these tools for Agents of Glass campaign state. They are typed "
        "wrappers over local Glass runtime services; do not write files or use "
        "prose as state. Use the MCP client's canonical tools/list request "
        "with no parameters for tool discovery, and use "
        'glass_help(command="<glass_tool_name>") for parameter help.'
    ),
)


def _mcp_mutation_requires_turn_role() -> None:
    role = current_role()
    if role.kind != "operator":
        return
    try:
        state = load_state(get_paths(), active_campaign_id())
    except GlassError:
        return
    if str(state.get("active_turn_id") or "").strip():
        raise GlassError(
            "Glass MCP mutation has no turn actor. Start the MCP server with "
            "GLASS_ROLE=dm or GLASS_ROLE=player:<id> for active agent turns; "
            "do not write active-turn state as operator."
        )


def _run_service(
    callable_,
    output_formatter=to_yaml,
    *,
    mutates: bool = False,
    tool_name: str | None = None,
    **kwargs: Any,
) -> GlassResult:
    response_tool = _response_tool_name(tool_name, kwargs)
    try:
        if mutates:
            _mcp_mutation_requires_turn_role()
        result = callable_(**kwargs)
        instructions = _response_instructions(response_tool, result=result, ok=True)
        output_result = result
        if output_formatter is to_yaml and isinstance(result, dict) and "instructions" not in result:
            output_result = {**result, "instructions": instructions}
        response: GlassResult = {
            "ok": True,
            "exit_code": 0,
            "output": output_formatter(output_result),
            "args": [],
            "instructions": instructions,
        }
        return response
    except GlassError as exc:
        instructions = _response_instructions(response_tool, ok=False)
        return {
            "ok": False,
            "exit_code": 77,
            "output": f"Error: {exc}\n",
            "args": [],
            "instructions": instructions,
        }
    except Exception as exc:
        instructions = _response_instructions(response_tool, ok=False)
        return {
            "ok": False,
            "exit_code": 70,
            "output": f"glass MCP internal error: {exc}\n",
            "args": [],
            "instructions": instructions,
        }


def _fact_spec(
    subject_id: str,
    predicate: str,
    text: str,
    *,
    object_id: str | None = None,
) -> str:
    subject = subject_id.strip()
    pred = predicate.strip()
    body = text.strip()
    obj = (object_id or "").strip()
    if obj:
        return f"{subject}.{pred} -> {obj} = {body}"
    return f"{subject}.{pred} = {body}"


def _compile_fact_updates(values: list[FactUpdate | dict[str, Any]] | None) -> list[FactSpec]:
    return [
        FactSpec(
            subject_id=update.subject_id,
            predicate=update.predicate,
            text=update.text,
            audience=update.audience,
            salience=update.importance,
            object_id=update.object_id,
        )
        for update in (
            value if isinstance(value, FactUpdate) else FactUpdate.model_validate(value)
            for value in values or []
        )
    ]


def _fact_update_texts(specs: list[FactSpec]) -> list[str]:
    return [
        _fact_spec(
            spec.subject_id,
            spec.predicate,
            spec.text,
            object_id=spec.object_id,
        )
        for spec in specs
    ]


def _compile_character_pull_utilization(value: CharacterPullUtilization | dict[str, Any]) -> str:
    pull = (
        value
        if isinstance(value, CharacterPullUtilization)
        else CharacterPullUtilization.model_validate(value)
    )
    return f"Source: {pull.source.strip()}; Thesis: {pull.thesis.strip()}"


def _compile_character_life_prompts(
    values: list[CharacterLifePrompt | dict[str, Any]],
) -> list[str]:
    prompts = [
        value
        if isinstance(value, CharacterLifePrompt)
        else CharacterLifePrompt.model_validate(value)
        for value in values
    ]
    return [f"{prompt.prompt.strip()}={prompt.answer.strip()}" for prompt in prompts]


def _compile_character_attributes(
    values: list[CharacterAttribute | dict[str, Any]] | None,
) -> list[str]:
    attributes = [
        value if isinstance(value, CharacterAttribute) else CharacterAttribute.model_validate(value)
        for value in values or []
    ]
    return [f"{attribute.name}={attribute.tier}" for attribute in attributes]


def _compile_character_starting_skills(
    value: CharacterStartingSkills | dict[str, Any],
) -> list[str]:
    skills = (
        value
        if isinstance(value, CharacterStartingSkills)
        else CharacterStartingSkills.model_validate(value)
    )
    return [
        f"{skills.artisan.name.strip()}=artisan",
        *[f"{skill.name.strip()}=apprentice" for skill in skills.apprentices],
    ]


def _compile_character_starting_items(
    values: list[CharacterStartingItem | dict[str, Any]],
) -> list[dict[str, Any]]:
    items = [
        value
        if isinstance(value, CharacterStartingItem)
        else CharacterStartingItem.model_validate(value)
        for value in values
    ]
    return [
        {
            "id": item.item_id.strip(),
            "name": item.name.strip(),
            "descriptor": item.descriptor.strip(),
            "qty": item.qty,
            "effect_tags": [tag.strip() for tag in item.effect_tags if tag.strip()],
        }
        for item in items
    ]


def _state_update_service(updates: list[StateUpdate | dict[str, Any]]) -> dict[str, Any]:
    try:
        normalized = _STATE_UPDATES_ADAPTER.validate_python(updates)
    except ValidationError as exc:
        raise _state_update_shape_error(exc) from exc
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    default_scope, active_scene = current_fact_scope(state)
    mode = str((state.get("mode_stack") or [{}])[-1].get("mode") or "") if state.get("mode_stack") else ""
    role = current_role()

    fact_specs: list[FactSpec] = []
    inventory_results: list[dict[str, Any]] = []
    for update in normalized:
        if isinstance(update, StateFactUpdate):
            fact_specs.append(
                FactSpec(
                    subject_id=update.subject_id,
                    predicate=update.predicate,
                    text=update.text,
                    audience=update.audience,
                    salience=update.importance,
                    object_id=update.object_id or None,
                    scope_id=update.scope_id or default_scope,
                )
            )
    fact_result = set_fact_specs(
        campaign_id=campaign_id,
        specs=fact_specs,
        actor=role.actor,
        turn_id=str(state.get("active_turn_id") or "") or None,
        mode=mode or None,
        scene_id=active_scene,
        require_available=bool(fact_specs),
    )

    for update in normalized:
        if isinstance(update, StateInventoryAdd):
            inventory_results.append(
                inventory_add_service(
                    command_path="glass_state_update",
                    emit_output=False,
                    character_id=update.character_id,
                    item_id=update.item_id,
                    prose_name=update.name,
                    descriptor=update.descriptor,
                    qty=update.qty,
                    effect_tags=tuple(update.effect_tags),
                )
            )
        elif isinstance(update, StateInventoryRemove):
            inventory_results.append(
                inventory_remove_service(
                    command_path="glass_state_update",
                    emit_output=False,
                    character_id=update.character_id,
                    item_id=update.item_id,
                    qty=update.qty,
                )
            )

    importance_warnings = _fact_importance_warnings(fact_result.get("facts") or [])
    result = {
        "count": len(normalized),
        "facts": fact_result,
        "inventory": inventory_results,
        "importance_warnings": importance_warnings,
    }
    append_audit(
        paths,
        state,
        "glass_state_update",
        "state.update",
        {"updates": [update.model_dump() for update in normalized]},
        result,
    )
    return result


def _fact_importance_warnings(facts: list[dict[str, Any]]) -> list[str]:
    low_facts = [
        fact
        for fact in facts
        if str(fact.get("importance") or fact.get("salience") or "").strip().lower()
        in LOW_FACT_IMPORTANCE
    ]
    if not low_facts:
        return []
    warnings = [
        "Low/minor facts were stored but are omitted from fact-pack output. These are usually not the right place for playable state; use high or medium for facts the next actor must see."
    ]
    if len(low_facts) == len(facts):
        warnings.append(
            "This update only added low/minor facts. Add at least one high or medium fact if the turn changed playable continuity; otherwise close without claiming a state change."
        )
    return warnings


_MCP_HELP_ARGS: dict[str, list[str]] = {
    "glass_check": ["check"],
    "glass_fact_pack": ["fact", "pack"],
    "glass_state_update": ["state", "update"],
    "glass_lore_search": ["lore", "search"],
    "glass_lore_read": ["lore", "read"],
    "glass_lore_list": ["lore", "list"],
    "glass_message_send": ["msg"],
    "glass_message_read": ["msg", "read"],
    "glass_character_new": ["character", "new"],
    "glass_character_bulk_get": ["character", "bulk-get"],
    "glass_character_get": ["character", "get"],
    "glass_character_list": ["character", "list"],
    "glass_character_signature_status": ["character", "signature-status"],
    "glass_character_signature_add": ["character", "signature-add"],
    "glass_character_skill_declare": ["character", "skill-declare"],
    "glass_character_set_hp": ["character", "set-hp"],
    "glass_character_award_xp": ["character", "award-xp"],
    "glass_character_level_up": ["character", "level-up"],
    "glass_character_consequence_add": ["character", "consequence-add"],
    "glass_character_consequence_list": ["character", "consequence-list"],
    "glass_character_consequence_resolve": ["character", "consequence-resolve"],
    "glass_roll": ["roll"],
    "glass_arc_create": ["arc", "create"],
    "glass_arc_current": ["arc", "current"],
    "glass_arc_list": ["arc", "list"],
    "glass_arc_activate": ["arc", "activate"],
    "glass_arc_close_check": ["arc", "close-check"],
    "glass_arc_close": ["arc", "close"],
    "glass_mode_end": ["mode", "end"],
    "glass_mode_start": ["mode", "start"],
    "glass_mode_current": ["mode", "current"],
    "glass_scene_create": ["scene", "create"],
    "glass_scene_current": ["scene", "current"],
    "glass_scene_list": ["scene", "list"],
    "glass_scene_end": ["scene", "end"],
    "glass_scene_transition": ["scene", "transition"],
    "glass_scene_closing_down": ["scene", "closing-down"],
    "glass_scene_clock_declare": ["scene", "clock", "declare"],
    "glass_scene_clock_tick": ["scene", "clock", "tick"],
    "glass_scene_tracker_set": ["scene", "tracker", "set"],
    "glass_scene_tracker_tick": ["scene", "tracker", "tick"],
    "glass_scene_tracker_list": ["scene", "tracker", "list"],
    "glass_scene_pressure": ["scene", "pressure"],
    "glass_beat_start": ["beat", "start"],
    "glass_beat_close": ["beat", "close"],
    "glass_beat_convert": ["beat", "convert"],
    "glass_clock_list": ["clock", "list"],
    "glass_clock_show": ["clock", "show"],
    "glass_clock_set": ["clock", "set"],
    "glass_clock_tick": ["clock", "tick"],
    "glass_clock_resolve": ["clock", "resolve"],
    "glass_clock_archive": ["clock", "archive"],
    "glass_thread_current": ["thread", "current"],
    "glass_thread_advance": ["thread", "advance"],
    "glass_turn_handoff": ["turn", "handoff"],
    "glass_turn_rapid_round": ["turn", "rapid-round"],
    "glass_turn_housekeeping_round": ["turn", "housekeeping-round"],
    "glass_turn_restart_order": ["turn", "restart-order"],
    "glass_turn_clear_handoff": ["turn", "clear-handoff"],
    "glass_turn_initiative": ["turn", "initiative"],
    "glass_quest_beat": ["quest", "beat"],
    "glass_done": ["done"],
    "glass_turn_append": ["turn", "append"],
}


_MCP_RESPONSE_INSTRUCTIONS: dict[str, list[str]] = {
    "glass_help": [
        "Use the returned schema to call the typed MCP tool directly; do not shell out or invent alternate parameters.",
    ],
    "glass_check": [
        "Read unread messages, hard_requirements, compact facts, scene_contract, character hard state, and pending_level_ups before choosing the next tool.",
    ],
    "glass_fact_pack": [
        "Use these facts as neutral continuity only. Low/minor facts are omitted from fact-pack output; if important playable state is missing or wrong, commit it as high or medium with glass_state_update rather than relying on prose.",
    ],
    "glass_state_update": [
        "State updates are stored. Continue with any remaining mechanical tools for the turn; when durable state is complete, close with glass_done.",
        "If you created or changed scene, mode, clock, tracker, or beat state after the last glass_check(), call glass_check() before glass_done.",
    ],
    "glass_lore_search": [
        "Use lore search results as reference only. Promote anything that becomes campaign reality with glass_state_update.",
    ],
    "glass_lore_read": [
        "Use this lore entry as reference only. If it matters now, write one neutral continuity fact with glass_state_update.",
    ],
    "glass_lore_list": [
        "Choose a lore entry only if the current decision needs reference material; otherwise return to the active turn workflow.",
    ],
    "glass_message_send": [
        "Message sent. Continue the current turn unless the message was the only needed action; then close with glass_done.",
    ],
    "glass_message_read": [
        "Respond to any blocking messages with the appropriate state tool or glass_message_send, then continue the turn workflow.",
    ],
    "glass_character_new": [
        "Character row, starting inventory, and initial facts are recorded. Next add the character's signature move with glass_character_signature_add.",
        "After the signature move and any required setup facts/messages are complete, close with glass_done.",
    ],
    "glass_character_bulk_get": [
        "Use these sheets to choose concrete relationships, roles, or handoffs. Record commitments with glass_state_update or the relevant character tool.",
    ],
    "glass_character_get": [
        "Use this sheet as hard character state. If the turn changes HP, inventory, consequences, XP, or facts, use the matching MCP tool before glass_done.",
    ],
    "glass_character_list": [
        "Use these ids for exact recipients, ownership checks, and character tool calls; do not guess character ids.",
    ],
    "glass_character_signature_status": [
        "If a signature slot is open and the methodology requires it, add the move with glass_character_signature_add.",
    ],
    "glass_character_signature_add": [
        "Signature move recorded. If character build requirements are otherwise complete, close with glass_done; otherwise add the missing character facts or messages.",
    ],
    "glass_character_skill_declare": [
        "Skill declared. Use it in a future glass_roll when fiction calls for it, then close or continue with the current turn's required state work.",
    ],
    "glass_character_set_hp": [
        "HP changed. Carry the visible injury or recovery into glass_done state/pressure and public prose.",
    ],
    "glass_character_award_xp": [
        "XP changed. If a level-up is now pending, resolve it with glass_character_level_up before ending the upkeep flow.",
    ],
    "glass_character_level_up": [
        "Level-up resolved. Check whether more pending level-ups remain; otherwise continue the turn or close with glass_done.",
    ],
    "glass_character_consequence_add": [
        "Consequence recorded. Carry it into glass_done state/pressure and public prose; do not wait for the DM to restate it.",
    ],
    "glass_character_consequence_list": [
        "Use this list to choose whether to add, resolve, or reference a concrete consequence with the matching character tool.",
    ],
    "glass_character_consequence_resolve": [
        "Consequence resolved. Record any visible aftermath in facts or closeout if it changes current continuity.",
    ],
    "glass_roll": [
        "Follow the roll-specific instructions returned by this call. Do not reroll the same action under a new skill or angle.",
    ],
    "glass_arc_create": [
        "Arc created. Add required arc/campaign facts and clocks, then activate or stage the first scene as the methodology requires.",
    ],
    "glass_arc_current": [
        "Use the active arc id for scene, clock, and thread decisions; if no arc is active, create or activate one before scene prep.",
    ],
    "glass_arc_list": [
        "Use these arc ids to activate, close-check, close, or stage scenes; do not create duplicate arcs for the same live focus.",
    ],
    "glass_arc_activate": [
        "Arc activated. Stage the next scene, clock, beat, or planning facts for this arc before closing the turn.",
    ],
    "glass_arc_close_check": [
        "If the check says the arc is ready, close it with glass_arc_close; otherwise follow the returned blockers by adding scenes, clocks, outcomes, or facts.",
    ],
    "glass_arc_close": [
        "Arc closed. Create or activate the next arc, enter intermission, or close the turn according to the active methodology.",
    ],
    "glass_mode_end": [
        "Mode ended. Start the next required mode if the methodology calls for it; otherwise close with glass_done.",
        "If this changed the active scene board you will close from, call glass_check() before glass_done so the audit validates the current clocks and beats.",
    ],
    "glass_mode_start": [
        "Mode started. Establish its required facts, scene, clock, beat, or handoff before glass_done.",
        "If this started scene-play or action, call glass_check() again after the scene clock and opening beat exist, before glass_done.",
    ],
    "glass_mode_current": [
        "Use the active mode stack to select the next methodology and tool path; do not mutate state based only on prose.",
    ],
    "glass_scene_create": [
        "Scene created. DM must declare an objective scene clock and start an opening beat before handing play to players.",
        "After scene clocks and beats are staged, call glass_check() before glass_done so closeout sees the current scene contract.",
    ],
    "glass_scene_current": [
        "Use this scene id for scene clocks, beats, trackers, facts, and transitions.",
    ],
    "glass_scene_list": [
        "Use these scene ids to avoid duplicate scenes and to choose whether to transition, return, or close existing scene state.",
    ],
    "glass_scene_end": [
        "Scene ended. Run arc close-check or stage the next scene/transition before ending the DM turn.",
        "If you changed the scene boundary this turn, call glass_check() before glass_done unless the active methodology explicitly says the turn is rapid-only.",
    ],
    "glass_scene_transition": [
        "Transition recorded. Confirm the new scene has a clear objective clock and opening beat, then close with glass_done.",
        "After the new scene board is staged, call glass_check() before glass_done so closeout validates the current clocks and beats.",
    ],
    "glass_scene_closing_down": [
        "Closing pressure is active. Push beats and clocks toward resolution; do not extend the scene with a renamed version of the same obstacle.",
    ],
    "glass_scene_clock_declare": [
        "Scene clock declared on the active play scene. Start or update the active beat that points at this clock, then continue or close with glass_done.",
        "Call glass_check() before glass_done if this clock declaration is part of the board you are closing on.",
    ],
    "glass_scene_clock_tick": [
        "Scene clock moved. If this resolves the beat or scene objective, close/convert the beat or transition the scene; otherwise carry the changed pressure into glass_done.",
        "Call glass_check() before glass_done if clock movement changed which beats or scene choices are live.",
    ],
    "glass_scene_tracker_set": [
        "Pressure tracker is available. Players can now use glass_scene_pressure against it instead of separate roll plus manual tracker updates.",
        "Call glass_check() before glass_done if this tracker is part of the active scene board for the next actor.",
    ],
    "glass_scene_tracker_tick": [
        "Tracker changed. If it is resolved or exhausted, close/convert the related beat or update the scene direction before glass_done.",
        "Call glass_check() before glass_done if tracker movement changed the active scene board.",
    ],
    "glass_scene_tracker_list": [
        "Use an existing public tracker for pressure actions when possible; create a tracker only if the scene lacks the needed target.",
    ],
    "glass_scene_pressure": [
        "Carry this roll-and-pressure outcome forward. If the tracker resolves or the beat changes, close/convert the beat or update scene state before glass_done.",
        "Call glass_check() before glass_done if this pressure result changed the active beat, tracker, or scene board.",
    ],
    "glass_beat_start": [
        "Beat started. Players should target this beat on ordinary glass_roll calls until it closes, converts, or the DM reframes it.",
        "Call glass_check() before glass_done so closeout sees this active beat.",
    ],
    "glass_beat_close": [
        "Beat closed and clock movement applied. Start the next beat, transition the scene, or close the turn if the current action is complete.",
        "Call glass_check() before glass_done if closing this beat changed the active scene board.",
    ],
    "glass_beat_convert": [
        "Beat converted into longer pressure. Start a fresh beat or hand play forward; do not keep playing the converted beat as if still active.",
        "Call glass_check() before glass_done if converting this beat changed the active scene board.",
    ],
    "glass_clock_list": [
        "Use these durable clocks to choose whether to tick, resolve, archive, or carry them into scene/arc closeout.",
    ],
    "glass_clock_show": [
        "Use this clock's scope, value, and status to decide whether to tick, resolve, archive, or reference it in current state.",
    ],
    "glass_clock_set": [
        "Durable clock set. Tick it only when visible fiction advances it; otherwise continue the current workflow.",
    ],
    "glass_clock_tick": [
        "Durable clock moved. If its value reaches a terminal state, resolve or archive it instead of leaving ambiguous pressure.",
    ],
    "glass_clock_resolve": [
        "Clock resolved. Carry the outcome into scene/arc closeout or continuity facts if it changes what agents need to know.",
    ],
    "glass_clock_archive": [
        "Clock archived. Do not use it as active pressure unless it is deliberately recreated.",
    ],
    "glass_thread_current": [
        "Use current threads only when the scene or arc visibly advances one; otherwise keep the turn focused on immediate state.",
    ],
    "glass_thread_advance": [
        "Thread advanced. Continue scene/arc work or close with glass_done; do not over-explain the thread in prose.",
    ],
    "glass_turn_handoff": [
        "Handoff queued. Finish any required state updates, then close with glass_done.",
    ],
    "glass_turn_rapid_round": [
        "Rapid round queued. Close the DM turn after any required state updates; rapid responders should answer only the prompt.",
    ],
    "glass_turn_housekeeping_round": [
        "Housekeeping round queued. Close the current transition/upkeep turn when scene and arc state are complete.",
    ],
    "glass_turn_restart_order": [
        "Turn order restarted. Close with glass_done unless another required state mutation remains.",
    ],
    "glass_turn_clear_handoff": [
        "Handoff overrides cleared. Continue normal rotation or action order, then close the current turn.",
    ],
    "glass_turn_initiative": [
        "Initiative order is set. Start the action beat/clock if needed, then close or hand off to the first actor.",
        "Call glass_check() before glass_done if initiative setup also changed active scene clocks or beats.",
    ],
    "glass_quest_beat": [
        "Quest beat recorded. If it changes playable continuity, add or update a neutral fact before glass_done.",
    ],
    "glass_done": [
        "If valid is true, immediately call glass_turn_append with the public prose. If valid is false, fix the listed problems and call glass_done again.",
    ],
    "glass_turn_append": [
        "Public prose submitted. End this invocation; do not make more state changes for this turn.",
    ],
}


def _response_tool_name(tool_name: str | None, kwargs: dict[str, Any]) -> str:
    if tool_name:
        return tool_name
    command_path = kwargs.get("command_path")
    if isinstance(command_path, str) and command_path.startswith("glass_"):
        return command_path
    return ""


def _response_instructions(
    tool_name: str,
    *,
    result: Any | None = None,
    ok: bool,
) -> list[str]:
    if not ok:
        return _error_response_instructions(tool_name)
    if isinstance(result, dict) and "instructions" in result:
        return _coerce_instructions(result["instructions"])
    dynamic = _dynamic_response_instructions(tool_name, result)
    if dynamic:
        return dynamic
    return list(
        _MCP_RESPONSE_INSTRUCTIONS.get(
            tool_name,
            [
                "Read the returned state, then continue with the next required MCP tool or close with glass_done.",
            ],
        )
    )


def _coerce_instructions(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _error_response_instructions(tool_name: str) -> list[str]:
    if tool_name:
        return [
            "Do not work around this failed tool call with files, shell commands, direct DB/API calls, or prose-only state.",
            f"Use the error text and glass_help(command=\"{tool_name}\") to correct the typed MCP call, then retry or close with a clear blocker.",
        ]
    return [
        "Do not work around this failed tool call with files, shell commands, direct DB/API calls, or prose-only state.",
        "Use the error text and canonical tools/list discovery to choose the correct typed MCP call.",
    ]


def _dynamic_response_instructions(tool_name: str, result: Any | None) -> list[str]:
    if not isinstance(result, dict):
        return []
    if tool_name == "glass_check":
        hard_requirements = result.get("hard_requirements") or []
        scene_contract = result.get("scene_contract")
        landing_guidance = (
            str(scene_contract.get("landing_guidance") or "").strip()
            if isinstance(scene_contract, dict)
            else ""
        )
        action_guidance = (
            str(scene_contract.get("action_guidance") or "").strip()
            if isinstance(scene_contract, dict)
            else ""
        )
        prefix = [item for item in (landing_guidance, action_guidance) if item]
        if hard_requirements:
            return prefix + [
                "Satisfy hard_requirements with the relevant MCP tools before glass_done.",
                "Use scene_contract.next_actions as the current board; do not proceed from prose memory alone.",
            ]
        return prefix + [
            "Check is clean. Choose from scene_contract.next_actions when present, then use the relevant MCP tool or call glass_done if no state change remains.",
        ]
    if tool_name == "glass_state_update":
        instructions = list(_MCP_RESPONSE_INSTRUCTIONS["glass_state_update"])
        warnings = _coerce_instructions(result.get("importance_warnings") or [])
        return warnings + instructions
    if tool_name == "glass_character_new":
        instructions = list(_MCP_RESPONSE_INSTRUCTIONS["glass_character_new"])
        fact_result = result.get("facts")
        if isinstance(fact_result, dict):
            warnings = _fact_importance_warnings(list(fact_result.get("facts") or []))
            return warnings + instructions
        return instructions
    if tool_name == "glass_done":
        if result.get("valid") is True:
            soft_considerations = [
                str(item)
                for item in result.get("soft_considerations") or []
                if str(item).strip()
            ]
            low_fact_warnings = [
                item for item in soft_considerations if "Only low/minor facts" in item
            ]
            if low_fact_warnings:
                return low_fact_warnings + [
                    "Closeout is valid but the fact set is weak. If playable state changed, add a high or medium fact with glass_state_update and run glass_done again; if no playable state changed, call glass_turn_append."
                ]
            return [
                "Closeout is valid. Now call glass_turn_append(body=\"<public prose>\") and then stop this invocation.",
            ]
        return [
            "Closeout is not valid. Do not call glass_turn_append yet; fix the listed problems with MCP tools or corrected closeout fields, then call glass_done again.",
        ]
    return []


_CLI_HELP_ALIASES: dict[tuple[str, ...], list[str]] = {
    ("message",): ["msg"],
    ("messages",): ["msg"],
    ("fact", "set"): ["state", "update"],
    ("character", "inventory_add"): ["state", "update"],
    ("character", "inventory-add"): ["state", "update"],
    ("character", "inventory_remove"): ["state", "update"],
    ("character", "inventory-remove"): ["state", "update"],
    ("scene", "clock_declare"): ["scene", "clock", "declare"],
    ("scene", "clock-declare"): ["scene", "clock", "declare"],
    ("scene", "clock_tick"): ["scene", "clock", "tick"],
    ("scene", "clock-tick"): ["scene", "clock", "tick"],
}


def _normalize_help_args(command: str, subcommand: str) -> list[str]:
    command_text = command.strip()
    subcommand_text = subcommand.strip()
    if command_text in _MCP_HELP_ARGS and not subcommand_text:
        return list(_MCP_HELP_ARGS[command_text])

    raw_parts = [part for part in (command_text, subcommand_text) if part]
    parts: list[str] = []
    for raw_part in raw_parts:
        parts.extend(piece for piece in raw_part.split() if piece)
    alias = _CLI_HELP_ALIASES.get(tuple(parts))
    if alias is not None:
        return list(alias)
    return [part.replace("_", "-") for part in parts]


def _help_service(command: str = "", subcommand: str = "") -> dict[str, Any]:
    command_text = command.strip()
    subcommand_text = subcommand.strip()
    tool_name = command_text if command_text in mcp._tool_manager._tools else ""
    if not tool_name:
        normalized = _normalize_help_args(command, subcommand)
        for candidate, args in _MCP_HELP_ARGS.items():
            if args == normalized:
                tool_name = candidate
                break
    if not tool_name:
        available = sorted(mcp._tool_manager._tools)
        return {
            "status": "unknown",
            "requested": [part for part in (command_text, subcommand_text) if part],
            "detail": "Use canonical MCP tools/list for the complete tool catalog.",
            "available_tools": available,
        }
    tool = mcp._tool_manager._tools[tool_name]
    return {
        "tool": tool.name,
        "description": tool.description,
        "input_schema": tool.parameters,
    }


@mcp.tool()
def glass_help(command: str = "", subcommand: str = "") -> GlassResult:
    """Show parameter help for a typed MCP tool or underlying Glass tool area."""

    return _run_service(
        _help_service,
        tool_name="glass_help",
        command=command,
        subcommand=subcommand,
    )


@mcp.tool()
def glass_check(no_mark: bool = False) -> GlassResult:
    """Run compact turn-start check: messages, facts, scene contract, hard state, and upkeep."""

    return _run_service(
        check_service,
        command_path="glass_check",
        emit_output=False,
        no_mark=no_mark,
        mutates=True,
    )


@mcp.tool()
def glass_fact_pack(
    audience: Literal["continuity", "profile", "meta", "all"],
    output_format: Literal["markdown", "yaml"] = "markdown",
    scene_id: str = "",
    actor: str = "",
    limit: int = 80,
) -> GlassResult:
    """Read scoped continuity facts for the required audience."""

    formatter = render_fact_pack_markdown if output_format == "markdown" else to_yaml
    return _run_service(
        fact_pack_service,
        output_formatter=formatter,
        tool_name="glass_fact_pack",
        scene_id=scene_id or None,
        actor=actor or None,
        audience=audience,
        limit=limit,
    )


@mcp.tool()
def glass_state_update(updates: StateUpdates) -> GlassResult:
    """Apply typed fact/inventory objects in one call; strings are invalid."""

    return _run_service(
        _state_update_service,
        tool_name="glass_state_update",
        updates=updates,
        mutates=True,
    )


@mcp.tool()
def glass_lore_search(query: str, limit: int = 5) -> GlassResult:
    """Search DB-backed reference lore. Promote useful lore into facts separately."""

    return _run_service(
        lore_search_service,
        tool_name="glass_lore_search",
        query=query,
        limit=limit,
    )


@mcp.tool()
def glass_lore_read(entry_id: str) -> GlassResult:
    """Read one DB-backed lore entry by id."""

    return _run_service(
        lore_read_service,
        tool_name="glass_lore_read",
        lore_id=entry_id,
    )


@mcp.tool()
def glass_lore_list() -> GlassResult:
    """List available DB-backed lore entries."""

    return _run_service(lore_list_service, tool_name="glass_lore_list")


@mcp.tool()
def glass_message_send(message_type: str, recipient: str, body: str) -> GlassResult:
    """Send a durable typed message to another agent or the DM."""

    return _run_service(
        send_message_service,
        command_path="glass_message_send",
        emit_output=False,
        message_type=message_type,
        recipient=recipient,
        body=body,
        mutates=True,
    )


@mcp.tool()
def glass_message_read(
    since_checkpoint: bool = False,
    sender: str = "",
    message_type: str = "",
    no_mark: bool = False,
) -> GlassResult:
    """Read durable messages visible to this turn actor."""

    return _run_service(
        read_messages_service,
        command_path="glass_message_read",
        emit_output=False,
        since_checkpoint=since_checkpoint,
        sender=sender or None,
        message_type=message_type or None,
        no_mark=no_mark,
        mutates=not no_mark,
    )


@mcp.tool()
def glass_character_new(
    character_id: str,
    player_id: str,
    name: str,
    species: str,
    culture: str,
    archetype: str,
    organization_role: str,
    bio: str,
    primary_drive: str,
    positive_trait: str,
    table_presence: str,
    non_work_want: str,
    opening_social_action: str,
    pull_utilization: CharacterPullUtilization,
    starting_items: CharacterStartingItems,
    facts: CharacterInitialFacts,
    goals: CharacterGoals,
    life_prompts: CharacterLifePrompts,
    skills: CharacterStartingSkills,
    attributes: CharacterAttributes | None = None,
    tags: list[str] | None = None,
    pronouns: str = "",
    hp: int = 10,
) -> GlassResult:
    """Create a character row during character creation."""

    compiled_pull = _compile_character_pull_utilization(pull_utilization)
    compiled_life_prompts = _compile_character_life_prompts(life_prompts)
    compiled_attributes = _compile_character_attributes(attributes)
    compiled_skills = _compile_character_starting_skills(skills)
    compiled_items = _compile_character_starting_items(starting_items)
    fact_specs = _compile_fact_updates(facts)
    return _run_service(
        create_character_service,
        command_path="glass_character_new",
        emit_output=False,
        character_id=character_id,
        player_id=player_id,
        name=name,
        species=species,
        culture=culture,
        archetype=archetype,
        organization_role=organization_role,
        pronouns=pronouns,
        bio=bio,
        goals=tuple(goals),
        primary_drive=primary_drive,
        positive_trait=positive_trait,
        table_presence=table_presence,
        non_work_want=non_work_want,
        opening_social_action=opening_social_action,
        life_prompts=tuple(compiled_life_prompts),
        pull_utilization=compiled_pull,
        hp_max=hp,
        attribute_values=tuple(compiled_attributes),
        skill_values=tuple(compiled_skills),
        starting_items=tuple(compiled_items),
        fact_specs=tuple(fact_specs),
        tags=tuple(tags or []),
        mutates=True,
    )


@mcp.tool()
def glass_character_bulk_get(all_characters: bool = True) -> GlassResult:
    """Read character sheets available to the current actor."""

    return _run_service(
        bulk_get_characters_service,
        command_path="glass_character_bulk_get",
        character_ids=(),
        include_all=all_characters,
        agent_projection=True,
    )


@mcp.tool()
def glass_character_get(character_id: str) -> GlassResult:
    """Read one character sheet."""

    return _run_service(
        get_character_service,
        command_path="glass_character_get",
        character_id=character_id,
        agent_projection=True,
    )


@mcp.tool()
def glass_character_list() -> GlassResult:
    """List character ids and owners."""

    return _run_service(list_characters_service, command_path="glass_character_list")


@mcp.tool()
def glass_character_signature_status(character_id: str) -> GlassResult:
    """Inspect a character's signature move slots and existing moves."""

    return _run_service(
        signature_status_service,
        command_path="glass_character_signature_status",
        character_id=character_id,
    )


@mcp.tool()
def glass_character_signature_add(
    character_id: str,
    name: str,
    descriptor: str,
    body: str = "",
    look: str = "",
    use: str = "",
    tell: str = "",
) -> GlassResult:
    """Add one public typed signature move to a character."""

    return _run_service(
        add_signature_move_service,
        command_path="glass_character_signature_add",
        emit_output=False,
        character_id=character_id,
        name=name,
        descriptor=descriptor,
        body=body,
        look=look,
        usual_use=use,
        tell=tell,
        mutates=True,
    )


@mcp.tool()
def glass_character_skill_declare(
    character_id: str,
    skill_id: str,
    prose_name: str,
    descriptor: str,
) -> GlassResult:
    """Declare one new character skill at fool tier."""

    return _run_service(
        declare_skill_service,
        command_path="glass_character_skill_declare",
        emit_output=False,
        character_id=character_id,
        skill=skill_id,
        prose_name=prose_name,
        descriptor=descriptor,
        mutates=True,
    )


@mcp.tool()
def glass_character_set_hp(character_id: str, delta: int) -> GlassResult:
    """Adjust a character's HP by a signed delta."""

    return _run_service(
        set_hp_service,
        command_path="glass_character_set_hp",
        emit_output=False,
        character_id=character_id,
        delta=delta,
        mutates=True,
    )


@mcp.tool()
def glass_character_award_xp(
    character_id: str,
    delta: int,
    reason: str = "",
) -> GlassResult:
    """Award or revoke character XP."""

    return _run_service(
        award_xp_service,
        command_path="glass_character_award_xp",
        emit_output=False,
        character_id=character_id,
        delta=delta,
        reason=reason or None,
        mutates=True,
    )


@mcp.tool()
def glass_character_level_up(character_id: str, attribute: str = "") -> GlassResult:
    """Resolve one pending character level-up."""

    return _run_service(
        level_up_service,
        command_path="glass_character_level_up",
        emit_output=False,
        character_id=character_id,
        attribute_name=attribute or None,
        mutates=True,
    )


@mcp.tool()
def glass_character_consequence_add(
    character_id: str,
    label: str,
    description: str = "",
    severity: Literal["minor", "serious", "critical"] = "minor",
    scope: Literal["scene", "arc", "campaign"] = "scene",
    public: bool = True,
) -> GlassResult:
    """Add a lasting consequence. Players may add public consequences to their own character."""

    return _run_service(
        add_consequence_service,
        command_path="glass_character_consequence_add",
        emit_output=False,
        character_id=character_id,
        label=label,
        description=description,
        severity=severity,
        scope=scope,
        public=public,
        mutates=True,
    )


@mcp.tool()
def glass_character_consequence_list(
    character_id: str,
    include_resolved: bool = False,
    include_hidden: bool = False,
) -> GlassResult:
    """List lasting consequences for one character."""

    return _run_service(
        list_consequences_service,
        command_path="glass_character_consequence_list",
        character_id=character_id,
        include_resolved=include_resolved,
        include_hidden=include_hidden,
    )


@mcp.tool()
def glass_character_consequence_resolve(
    character_id: str,
    consequence_id: str,
    note: str = "",
) -> GlassResult:
    """Resolve one lasting consequence. Players may resolve public consequences on their own character."""

    return _run_service(
        resolve_consequence_service,
        command_path="glass_character_consequence_resolve",
        emit_output=False,
        character_id=character_id,
        consequence_id=consequence_id,
        note=note,
        mutates=True,
    )


@mcp.tool()
def glass_roll(
    character_id: str,
    skill: str,
    attribute: str,
    risk: Literal["controlled", "standard", "risky", "desperate"],
    target_id: str = "",
    save_skill: bool = False,
) -> GlassResult:
    """Resolve an ordinary character roll.

    In active scene play, set target_id to the active beat id from glass_check().
    A stall/regress/collapse roll ticks that beat's failed-roll pressure; the
    second failed roll closes the beat and queues the DM to reframe the route
    toward the same scene goal.
    """

    return _run_service(
        roll_service,
        command_path="glass_roll",
        emit_output=False,
        skill=skill,
        attribute=attribute,
        risk=risk,
        character_id=character_id,
        target_id=target_id or None,
        save_skill=save_skill,
        mutates=True,
    )


@mcp.tool()
def glass_arc_create(arc_id: str, pull_source: str, pull_utilization: str) -> GlassResult:
    """Create the active playable arc during planning or intermission."""

    return _run_service(
        create_arc_service,
        command_path="glass_arc_create",
        emit_output=False,
        arc_id=arc_id,
        pull_source=pull_source,
        pull_utilization=pull_utilization,
        mutates=True,
    )


@mcp.tool()
def glass_arc_current() -> GlassResult:
    """Show the active arc."""

    return _run_service(current_arc_service, command_path="glass_arc_current")


@mcp.tool()
def glass_arc_list() -> GlassResult:
    """List campaign arcs."""

    return _run_service(list_arcs_service, command_path="glass_arc_list")


@mcp.tool()
def glass_arc_activate(arc_id: str) -> GlassResult:
    """Set the active campaign arc."""

    return _run_service(
        activate_arc_service,
        command_path="glass_arc_activate",
        emit_output=False,
        arc_id=arc_id,
        mutates=True,
    )


@mcp.tool()
def glass_arc_close_check(arc_id: str = "") -> GlassResult:
    """Check whether an arc is ready to close."""

    return _run_service(
        close_check_arc_service,
        command_path="glass_arc_close_check",
        arc_id=arc_id or None,
    )


@mcp.tool()
def glass_arc_close(
    arc_id: str = "",
    summary: str = "",
    outcomes: list[str] | None = None,
    carry_clocks: list[str] | None = None,
    retire_clocks: list[str] | None = None,
) -> GlassResult:
    """Close an arc after scenes and arc clocks have dispositions."""

    return _run_service(
        close_arc_service,
        command_path="glass_arc_close",
        emit_output=False,
        arc_id=arc_id or None,
        summary=summary or None,
        outcome_values=tuple(outcomes or []),
        carry_clock_specs=tuple(carry_clocks or []),
        retire_clock_specs=tuple(retire_clocks or []),
        mutates=True,
    )


@mcp.tool()
def glass_mode_end() -> GlassResult:
    """End the active mode after required state and facts are committed."""

    return _run_service(
        end_mode_service,
        command_path="glass_mode_end",
        emit_output=False,
        mutates=True,
    )


@mcp.tool()
def glass_mode_start(mode_name: str, scene_id: str) -> GlassResult:
    """Start a DM-controlled mode frame."""

    return _run_service(
        start_mode_service,
        command_path="glass_mode_start",
        emit_output=False,
        mode_name=mode_name,
        scene_id=scene_id,
        mutates=True,
    )


@mcp.tool()
def glass_mode_current() -> GlassResult:
    """Read the active mode stack."""

    return _run_service(current_mode_service, command_path="glass_mode_current")


@mcp.tool()
def glass_scene_create(scene_id: str, scene_type: str, arc_id: str = "") -> GlassResult:
    """Create a scene under the active or specified arc."""

    return _run_service(
        create_scene_service,
        command_path="glass_scene_create",
        emit_output=False,
        scene_id=scene_id,
        scene_type=scene_type,
        arc_id=arc_id or None,
        mutates=True,
    )


@mcp.tool()
def glass_scene_current() -> GlassResult:
    """Read the active scene."""

    return _run_service(current_scene_service, tool_name="glass_scene_current")


@mcp.tool()
def glass_scene_list(arc_id: str = "") -> GlassResult:
    """List scenes, optionally filtered to one arc."""

    return _run_service(
        list_scenes_service,
        tool_name="glass_scene_list",
        arc_id=arc_id or None,
    )


@mcp.tool()
def glass_scene_end(
    summary: str = "",
    beats: str = "",
    outcomes: list[str] | None = None,
    xp: str = "",
    carry_clocks: list[str] | None = None,
    retire_clocks: list[str] | None = None,
) -> GlassResult:
    """End the active scene and bundle scene closeout state."""

    return _run_service(
        end_scene_service,
        command_path="glass_scene_end",
        emit_output=False,
        summary=summary or None,
        beats=beats or None,
        outcome_values=tuple(outcomes or []),
        xp_spec=xp or None,
        carry_clock_specs=tuple(carry_clocks or []),
        retire_clock_specs=tuple(retire_clocks or []),
        mutates=True,
    )


@mcp.tool()
def glass_scene_transition(
    next_scene_id: str,
    kind: Literal["new", "nested", "return"],
    close_parent: bool = False,
    scene_type: str = "",
    arc_id: str = "",
    new_mode: Literal["scene-play", "action"] = "scene-play",
    summary: str = "",
    outcomes: list[str] | None = None,
    beats: str = "",
    xp: str = "",
    carry_clocks: list[str] | None = None,
    retire_clocks: list[str] | None = None,
    parent_summary: str = "",
    parent_outcomes: list[str] | None = None,
    parent_beats: str = "",
    parent_carry_clocks: list[str] | None = None,
    parent_retire_clocks: list[str] | None = None,
    force: bool = False,
) -> GlassResult:
    """Transition from the active scene to another scene frame."""

    return _run_service(
        scene_transition_service,
        command_path="glass_scene_transition",
        emit_output=False,
        next_scene_id=next_scene_id,
        kind=kind,
        close_parent=close_parent,
        scene_type=scene_type or None,
        arc_id_override=arc_id or None,
        new_mode=new_mode,
        summary=summary or None,
        outcome_values=tuple(outcomes or []),
        beats=beats or None,
        xp_spec=xp or None,
        carry_clock_specs=tuple(carry_clocks or []),
        retire_clock_specs=tuple(retire_clocks or []),
        parent_summary=parent_summary or None,
        parent_outcome_values=tuple(parent_outcomes or []),
        parent_beats=parent_beats or None,
        parent_carry_clock_specs=tuple(parent_carry_clocks or []),
        parent_retire_clock_specs=tuple(parent_retire_clocks or []),
        force=force,
        mutates=True,
    )


@mcp.tool()
def glass_scene_closing_down(rounds: int = 4, turns: int | None = None) -> GlassResult:
    """Declare that the active scene is entering closing pressure."""

    return _run_service(
        closing_down_scene_service,
        command_path="glass_scene_closing_down",
        emit_output=False,
        round_budget=rounds,
        turn_budget=turns,
        mutates=True,
    )


@mcp.tool()
def glass_scene_clock_declare(
    clock_id: str,
    label: str,
    goal: str,
    max_value: int,
    direction: Literal["progress", "countdown"],
    value: int = 0,
    polarity: Literal["objective", "threat", "timer", ""] = "",
    visibility: Literal["public", "dm"] = "public",
) -> GlassResult:
    """Declare or replace a scene-local active-play clock."""

    return _run_service(
        declare_scene_clock_service,
        command_path="glass_scene_clock_declare",
        emit_output=False,
        clock_id=clock_id,
        label=label,
        goal=goal,
        value=value,
        max_value=max_value,
        direction=direction,
        polarity=polarity or None,
        visibility=visibility,
        mutates=True,
    )


@mcp.tool()
def glass_scene_clock_tick(clock_id: str, delta: int, outcome: str) -> GlassResult:
    """Move a scene clock when a turn creates concrete progress or consequence."""

    return _run_service(
        tick_scene_clock_service,
        command_path="glass_scene_clock_tick",
        emit_output=False,
        clock_id=clock_id,
        delta=delta,
        outcome=outcome,
        mutates=True,
    )


@mcp.tool()
def glass_scene_tracker_set(
    tracker_id: str,
    max_value: int,
    label: str = "",
    value: int = 0,
    resistance: int = 0,
    impact_resistance: int = 0,
    public: bool = True,
) -> GlassResult:
    """Create or replace a scene-local pressure tracker."""

    return _run_service(
        set_scene_tracker_service,
        command_path="glass_scene_tracker_set",
        emit_output=False,
        tracker_id=tracker_id,
        label=label or None,
        value=value,
        max_value=max_value,
        resistance=resistance,
        impact_resistance=impact_resistance,
        public=public,
        mutates=True,
    )


@mcp.tool()
def glass_scene_tracker_tick(tracker_id: str, delta: int = 1) -> GlassResult:
    """Advance or reduce a scene-local pressure tracker."""

    return _run_service(
        tick_scene_tracker_service,
        command_path="glass_scene_tracker_tick",
        emit_output=False,
        tracker_id=tracker_id,
        delta=delta,
        mutates=True,
    )


@mcp.tool()
def glass_scene_tracker_list(all_scenes: bool = False) -> GlassResult:
    """List scene-local pressure trackers visible to this actor."""

    return _run_service(
        list_scene_trackers_service,
        command_path="glass_scene_tracker_list",
        all_scenes=all_scenes,
    )


@mcp.tool()
def glass_scene_pressure(
    target_id: str,
    character_id: str,
    skill: str,
    attribute: str,
    risk: Literal["controlled", "standard", "risky", "desperate"],
    impact: Literal["d6", "d8", "d10"],
    bonus: int = 0,
    save_skill: bool = False,
    because: str = "",
    note: str = "",
) -> GlassResult:
    """Roll and apply impact to a scene-local pressure tracker."""

    return _run_service(
        pressure_scene_service,
        command_path="glass_scene_pressure",
        emit_output=False,
        target_id=target_id,
        skill=skill,
        attribute=attribute,
        risk=risk,
        character_id=character_id,
        impact_die=impact,
        bonus=bonus,
        save_skill=save_skill,
        because=because or None,
        note=note or None,
        mutates=True,
    )


@mcp.tool()
def glass_beat_start(
    beat_id: str,
    clock_id: str,
    label: str,
    question: str,
) -> GlassResult:
    """Start a dramatic beat in the active scene."""

    return _run_service(
        start_beat_service,
        command_path="glass_beat_start",
        emit_output=False,
        beat_id=beat_id,
        clock_id=clock_id,
        label=label,
        question=question,
        mutates=True,
    )


@mcp.tool()
def glass_beat_close(beat_id: str, outcome: str, clock_delta: int) -> GlassResult:
    """Close an active beat and apply scene-clock movement."""

    return _run_service(
        close_beat_service,
        command_path="glass_beat_close",
        emit_output=False,
        beat_id=beat_id,
        outcome=outcome,
        clock_delta=clock_delta,
        mutates=True,
    )


@mcp.tool()
def glass_beat_convert(beat_id: str, to_clock_id: str, reason: str) -> GlassResult:
    """Convert an active beat into longer-running clock pressure."""

    return _run_service(
        convert_beat_service,
        command_path="glass_beat_convert",
        emit_output=False,
        beat_id=beat_id,
        to_clock_id=to_clock_id,
        reason=reason,
        mutates=True,
    )


@mcp.tool()
def glass_clock_list(
    scope: str = "",
    anchor_id: str = "",
    public_only: bool = False,
    include_archived: bool = False,
) -> GlassResult:
    """List durable cross-scene clocks."""

    return _run_service(
        list_clocks_service,
        command_path="glass_clock_list",
        scope=scope or None,
        anchor_id=anchor_id or None,
        public_only=public_only,
        include_archived=include_archived,
    )


@mcp.tool()
def glass_clock_show(clock_id: str) -> GlassResult:
    """Show one durable cross-scene clock."""

    return _run_service(
        show_clock_service,
        command_path="glass_clock_show",
        clock_id=clock_id,
    )


@mcp.tool()
def glass_clock_set(
    clock_id: str,
    max_value: int,
    scope: str = "campaign",
    anchor_id: str = "",
    label: str = "",
    description: str = "",
    value: int = 0,
    direction: Literal["fills", "drains"] = "fills",
    public: bool = False,
) -> GlassResult:
    """Create or replace a durable cross-scene clock."""

    return _run_service(
        set_clock_service,
        command_path="glass_clock_set",
        emit_output=False,
        clock_id=clock_id,
        scope=scope,
        anchor_id=anchor_id or None,
        label=label or None,
        description=description,
        value=value,
        max_value=max_value,
        direction=direction,
        public=public,
        mutates=True,
    )


@mcp.tool()
def glass_clock_tick(clock_id: str, delta: int = 1, note: str = "") -> GlassResult:
    """Advance or reduce a durable cross-scene clock."""

    return _run_service(
        tick_clock_service,
        command_path="glass_clock_tick",
        emit_output=False,
        clock_id=clock_id,
        delta=delta,
        note=note,
        mutates=True,
    )


@mcp.tool()
def glass_clock_resolve(clock_id: str, note: str = "") -> GlassResult:
    """Mark a durable cross-scene clock resolved."""

    return _run_service(
        set_clock_status_service,
        command_path="glass_clock_resolve",
        emit_output=False,
        clock_id=clock_id,
        status="resolved",
        note=note,
        mutates=True,
    )


@mcp.tool()
def glass_clock_archive(clock_id: str, note: str = "") -> GlassResult:
    """Archive a durable cross-scene clock."""

    return _run_service(
        set_clock_status_service,
        command_path="glass_clock_archive",
        emit_output=False,
        clock_id=clock_id,
        status="archived",
        note=note,
        mutates=True,
    )


@mcp.tool()
def glass_thread_current() -> GlassResult:
    """Read current long-game threads."""

    return _run_service(current_thread_service, command_path="glass_thread_current")


@mcp.tool()
def glass_thread_advance(thread_id: str, note: str = "") -> GlassResult:
    """Advance or create a long-game thread beat."""

    return _run_service(
        advance_thread_service,
        command_path="glass_thread_advance",
        emit_output=False,
        thread_id=thread_id,
        note=note,
        mutates=True,
    )


@mcp.tool()
def glass_turn_handoff(agent_id: str) -> GlassResult:
    """Queue a one-off next-speaker handoff."""

    return _run_service(
        handoff_turn_service,
        command_path="glass_turn_handoff",
        emit_output=False,
        agent_id=agent_id,
        mutates=True,
    )


@mcp.tool()
def glass_turn_rapid_round(prompt: str, players: str = "") -> GlassResult:
    """Queue rapid response turns for players."""

    return _run_service(
        rapid_round_turn_service,
        command_path="glass_turn_rapid_round",
        emit_output=False,
        prompt=prompt,
        players_csv=players or None,
        mutates=True,
    )


@mcp.tool()
def glass_turn_housekeeping_round(
    players: str = "",
    previous_scene: str = "",
    next_scene: str = "",
    next_actor: str = "tev",
) -> GlassResult:
    """Queue non-plot housekeeping turns at a scene boundary."""

    return _run_service(
        housekeeping_round_turn_service,
        command_path="glass_turn_housekeeping_round",
        emit_output=False,
        players_csv=players or None,
        previous_scene=previous_scene,
        next_scene=next_scene,
        next_actor=next_actor,
        mutates=True,
    )


@mcp.tool()
def glass_turn_restart_order(agent_id: str) -> GlassResult:
    """Clear pending handoffs and restart rotation from one agent."""

    return _run_service(
        restart_order_turn_service,
        command_path="glass_turn_restart_order",
        emit_output=False,
        agent_id=agent_id,
        mutates=True,
    )


@mcp.tool()
def glass_turn_clear_handoff() -> GlassResult:
    """Clear pending handoff overrides."""

    return _run_service(
        clear_handoff_turn_service,
        command_path="glass_turn_clear_handoff",
        emit_output=False,
        mutates=True,
    )


@mcp.tool()
def glass_turn_initiative(players: str = "", label: str = "initiative") -> GlassResult:
    """Roll and persist action-scene initiative order."""

    return _run_service(
        initiative_turn_service,
        command_path="glass_turn_initiative",
        emit_output=False,
        participants_csv=players or None,
        label=label,
        mutates=True,
    )


@mcp.tool()
def glass_quest_beat(text: str, scene_id: str = "", arc_id: str = "") -> GlassResult:
    """Record one public story-shifting quest beat."""

    return _run_service(
        quest_beat_service,
        command_path="glass_quest_beat",
        emit_output=False,
        text=text,
        scene_id=scene_id or None,
        arc_id=arc_id or None,
        mutates=True,
    )


@mcp.tool()
def glass_done(
    summary: str,
    state: list[str],
    rolls: str,
    scene_status: SceneStatus,
    next_speaker: str = "default",
    turn_type: Literal["act", "answer", "support", "pass", ""] = "",
    open_questions: list[str] | None = None,
    position: str = "",
    pressure: str = "",
) -> GlassResult:
    """Run turn audit and stage closeout. Follow with glass_turn_append."""

    return _run_service(
        done_service,
        command_path="glass_done",
        emit_output=False,
        summary=summary,
        state_changes=tuple(state),
        rolls=rolls,
        turn_type=turn_type,
        next_speaker=next_speaker,
        scene_status=scene_status,
        open_questions=tuple(open_questions or []),
        position=position,
        pressure=pressure,
        mutates=True,
    )


@mcp.tool()
def glass_turn_append(body: str) -> GlassResult:
    """Submit viewer-facing public prose after glass_done succeeds."""

    return _run_service(
        append_turn_service,
        command_path="glass_turn_append",
        emit_output=False,
        body=body,
        source="mcp",
        mutates=True,
    )


def main(argv: list[str] | None = None) -> None:
    """Run the Glass MCP server over stdio."""

    args = list(sys.argv[1:] if argv is None else argv)
    if any(arg in {"-h", "--help"} for arg in args):
        sys.stdout.write(
            "Usage: glass-mcp\n\n"
            "Run the Agents of Glass MCP server over stdio. The server expects "
            "GLASS_API_GRANT in the environment.\n"
        )
        return
    load_repo_env()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
