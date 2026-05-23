# Closeout

Closeout is not a file-authoring phase.

Before closing:

1. Call or confirm `glass_check()`.
2. Make required hard-state updates through the owning `glass_*` MCP tools.
3. Record neutral durable facts with `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "<entity-id>", "predicate": "<predicate>", "text": "<neutral fact>"}])` for every meaningful state change.
4. Run `glass_done(summary="...", state=[...], rolls="...", scene_status="active", next_speaker="default")`.
5. Submit public prose with `glass_turn_append(body="...")`.

If no state changed, use `state=["no state change"]` and `rolls="none"`. If state changed, commit a neutral fact before closeout. Do not use prose as the only record of a change.
