# Scene Play Player

Goal: take one grounded player turn that changes or clarifies the scene.

1. Call `glass_check()`.
2. Read facts, messages, scene clocks, scene trackers, and the active beat from MCP tool output.
3. Choose one clear action, answer, support move, or pass.
4. Use `glass_scene_pressure(...)` when the action both rolls and reduces a public scene tracker; use `glass_roll(..., target_id="<active-beat-id>")` only when no tracker should change.
5. Update hard state with the specific `glass_*` MCP tool that owns it.
6. Record any durable new continuity with `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "scope_id": "<scene-id>", "subject_id": "<entity-id>", "predicate": "<predicate>", "text": "<neutral fact>"}])`.
7. Close with `glass_done(turn_type="act|answer|support|pass", scene_status="active")`.
8. Submit public scene prose with `glass_turn_append(body="...")`.

If your roll stalls, regresses, or collapses, do not retry the same beat from a different angle. The failed roll ticks that beat's failure pressure; at two failed rolls the beat closes and the DM gets the next handoff to offer a fresh route toward the same scene goal.

Do not write files. Do not turn character tics, object labels, or prior phrasing into the subject of the scene unless the concrete situation makes them load-bearing.
