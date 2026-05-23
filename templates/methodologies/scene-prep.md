# Scene Prep

Goal: stage a playable scene with hard state and neutral facts.

1. Call `glass_check()`.
2. Confirm the active arc with `glass_arc_current()` or `glass_arc_close_check(arc_id="<arc-id>")`.
3. Create the scene with `glass_scene_create(scene_id="...", scene_type="...", arc_id="...")`.
4. End scene-prep if it is active, then start the play mode with `glass_mode_start(mode_name="scene-play|action", scene_id="<scene>")`.
5. Declare the objective clock and any needed threat/timer clocks with `glass_scene_clock_declare(...)`.
6. Start the opening beat with `glass_beat_start(...)`.
7. Record neutral facts with `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "scope_id": "<scene-id>", "subject_id": "scene", "predicate": "objective", "text": "<visible objective>"}, {"kind": "fact", "audience": "continuity", "importance": "medium", "scope_id": "<scene-id>", "subject_id": "<object-id>", "predicate": "descriptor", "text": "<plain descriptor and affordance>"}])` for objective, antagonist pressure, concrete physical danger, positions, and three interactable scene objects.
8. Close with `glass_done(..., scene_status="active")`.
9. Submit the visible scene opening with `glass_turn_append(body="...")`.

Do not write prep, summary, table, or lore files.
