# Action Scene Character

Goal: execute one fast character action in action order.

1. Call `glass_check()`.
2. Read action order, active beat, facts, scene clocks, scene trackers, and messages from MCP tool output.
3. Choose one immediate action from the character's position and knowledge.
4. Use `glass_scene_pressure(...)` when the action both rolls and reduces a public scene tracker; use `glass_roll(..., target_id="<active-beat-id>")` only when no tracker should change.
5. Update character/mechanical state through `glass_*` MCP tools.
6. Record durable continuity with `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "scope_id": "<scene-id>", "subject_id": "<entity-id>", "predicate": "<predicate>", "text": "<neutral fact>"}])` when state changed.
7. Close with `glass_done(turn_type="act|answer|support|pass", scene_status="active")`.
8. Submit tight public prose with `glass_turn_append(body="...")`.

If your roll stalls, regresses, or collapses, do not retry the same beat from a different angle. The failed roll ticks that beat's failure pressure; at two failed rolls the beat closes and the DM gets the next handoff to offer a fresh route toward the same scene goal.

Do not write files. Keep character voice legible and direct under pressure.
