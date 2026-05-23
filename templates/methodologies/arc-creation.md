# Arc Creation

Goal: create or activate an arc through hard-state MCP tools and neutral facts.

1. Call `glass_check()`.
2. Create or activate the arc with `glass_arc_*`.
3. Set required arc clocks with `glass_clock_*`.
4. Advance recurring threads only with `glass_thread_advance(...)`.
5. Record premise, stakes, antagonist pressure, and visible direction with `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "<arc-id>", "predicate": "premise", "text": "<neutral premise>"}, {"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "<arc-id>", "predicate": "stakes", "text": "<neutral stakes>"}])`.
6. Close with `glass_done(..., scene_status="active")`.
7. Submit public arc readiness prose with `glass_turn_append(body="...")`.

Do not write plan files.
