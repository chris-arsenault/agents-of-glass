# Action Scene DM

Goal: keep action order moving while recording consequences in hard state.

1. Call `glass_check()`.
2. Read `scene_contract.next_actions`, action order, facts, scene clocks, scene trackers, durable clocks, and messages from MCP tool output.
3. Resolve pending uncertainty or make one concrete pressure move.
4. Use `glass_scene_tracker_set(...)` to establish pressure targets, `glass_scene_pressure(...)` for roll-mediated tracker reduction, and clock/beat/consequence/message/handoff MCP tools for their own hard state.
5. Record durable continuity with `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "scope_id": "<scene-id>", "subject_id": "<entity-id>", "predicate": "<predicate>", "text": "<neutral fact>"}])` when state changed.
6. Close with `glass_done(..., scene_status="active")`.
7. Submit public action prose with `glass_turn_append(body="...")`.

Keep the opposing will acting: every DM turn, the scene's antagonist or
pressure makes or advances a move the players can see or feel.

Do not write files.
