# Scene Transition DM

Goal: close the old scene and stage the next scene through hard-state MCP tools.

1. Call `glass_check()`.
2. Close or transition the current scene with `glass_scene_transition(...)` or the explicit scene/arc MCP tools named in the prompt.
3. Dispose of clocks and beats explicitly.
4. Create the next scene, declare objective/threat/timer clocks, and start the opening beat.
5. Record neutral facts with `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "scope_id": "<next-scene-id>", "subject_id": "scene", "predicate": "objective", "text": "<visible objective>"}, {"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "<closed-scene-id>", "predicate": "outcome", "text": "<neutral closed outcome>"}])` for the closed outcome and the next scene's visible board.
6. Queue housekeeping or the next handoff only through `glass_turn_*` when needed.
7. Close with `glass_done(scene_status="ended")`.
8. Submit public transition prose with `glass_turn_append(body="...")`.

Do not write files.
