# Scene Play Character

Goal: act from inside the character while using facts and hard state as continuity.

1. Call `glass_check()`.
2. Read facts, messages, scene clocks, scene trackers, and `scene_contract.next_actions` from MCP tool output.
3. Choose one concrete character action, answer, support move, or pass from the current scene board.
4. Use `glass_scene_pressure(...)` when the action both rolls and reduces a public scene tracker; use `glass_roll(..., target_id="<active-beat-id>")` only when no tracker should change.
5. Update character/mechanical state through `glass_character_*`, beat, clock, pressure, or message MCP tools.
6. Record durable continuity with `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "scope_id": "<scene-id>", "subject_id": "<entity-id>", "predicate": "<predicate>", "text": "<neutral fact>"}])`.
7. Close with `glass_done(turn_type="act|answer|support|pass", scene_status="active")`.
8. Submit public scene prose with `glass_turn_append(body="...")`.

If your roll stalls, regresses, or collapses, finish this turn with a visible setback or cost. The same beat can take one more failed attempt before it closes, but the next attempt must be a concrete action that changes table position, not another layer of diagnosis or method explanation.

Do not write files. Character texture should color action, not replace action.
