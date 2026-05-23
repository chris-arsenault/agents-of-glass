# Intermission

Goal: make between-scene or between-arc decisions through MCP tools, messages, and facts.

1. Call `glass_check()`.
2. Inspect arcs, threads, clocks, and facts through MCP tools.
3. Send concrete requests or offers with messages.
4. Create, close, or activate arcs only through `glass_arc_*`.
5. Record durable decisions with `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "<entity-id>", "predicate": "<predicate>", "text": "<neutral fact>"}])`.
6. Close with `glass_done(..., scene_status="active")`.
7. Submit public intermission prose with `glass_turn_append(body="...")`.

Do not write files.
