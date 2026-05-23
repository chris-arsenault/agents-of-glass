# Scene Housekeeping Player

Goal: perform local cleanup without advancing plot.

1. Call `glass_check()`.
2. Update hard state only when there is an actual mechanical cleanup MCP tool to run.
3. Send messages for concrete requests or coordination before the next scene.
4. Record a neutral fact with `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "<entity-id>", "predicate": "<predicate>", "text": "<neutral fact>"}])` only if durable state changed.
5. Close with `glass_done(summary="housekeeping only: <cleanup>", state=["<update or no state change>"], rolls="none", scene_status="ended")`.
6. Submit a short process-only public note with `glass_turn_append(body="...")`.

Do not write notes, journals, scratch files, or markdown.
