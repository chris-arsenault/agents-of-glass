# Action Scene DM

Goal: keep action order moving while recording consequences in hard state.

1. Call `glass_check()`.
2. Read `scene_contract.next_actions`, action order, facts, scene clocks, scene trackers, durable clocks, and messages from MCP tool output.
3. Resolve pending uncertainty or make one concrete pressure move.
4. Use `glass_scene_tracker_set(...)` to establish pressure targets, `glass_scene_pressure(...)` for roll-mediated tracker reduction, and clock/beat/consequence/message/handoff MCP tools for their own hard state.
5. Record durable continuity with `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "scope_id": "<scene-id>", "subject_id": "<entity-id>", "predicate": "<predicate>", "text": "<neutral fact>"}])` when state changed.
6. Close with `glass_done(..., scene_status="active")`.
7. Submit public action prose with `glass_turn_append(body="...")`.

Keep the opposing will acting — and moving forward: its move each DM turn
closes distance, forces a decision, takes something, or changes the ground.
A move that only adds another standing complication to the current standoff
is not a move. When a beat's question is answered, its set piece is finished;
do not restage it or route the next complication back through it.

Do not write files.
