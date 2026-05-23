# Campaign Planning

Goal: establish campaign planning state through MCP tools and neutral facts.

1. Call `glass_check()`.
2. Create or activate the first playable arc with `glass_arc_create(arc_id="<arc-id>", pull_source="<source>", pull_utilization="<note>")` or `glass_arc_activate(arc_id="<arc-id>")`.
3. Commit the required campaign and active-arc facts in one `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "campaign", "predicate": "opening", "text": "<plain opening situation>"}, {"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "campaign", "predicate": "premise", "text": "<plain campaign premise>"}, {"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "<arc-id>", "predicate": "focus", "text": "<plain active arc focus>"}])` call:
   - campaign opening
   - campaign premise or constraint
   - one active arc focus, direction, or status fact using the actual arc id
5. Call `glass_arc_current()`, `glass_arc_list()`, and `glass_fact_pack(audience="continuity", output_format="markdown")` to verify the arc and facts exist.
6. Call `glass_mode_end()` only after the arc and required graph facts exist.
7. Close with `glass_done(summary="...", state=["..."], rolls="none", scene_status="active", next_speaker="default")`.
8. Submit a short public planning summary with `glass_turn_append(body="...")`.

Do not write files.
