# Character Branch Instructions

This file is the binding runtime contract for character-surface turns. Design
docs are not runtime instructions.

1. Read the injected prompt you were given at invocation.
2. Use `glass_check()` unless the injected prompt explicitly marks the turn as rapid and optional.
3. Read current continuity from `glass_fact_pack(audience="continuity", output_format="markdown")` or the facts embedded in the prompt.
4. Mutate durable state only through purpose-built `glass_*` MCP tools and `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "<entity-id>", "predicate": "<predicate>", "text": "<neutral fact>"}])`.
5. Read and follow any `instructions` returned by MCP tools; successful tool calls can still give binding next-step guidance.
6. Do not write files. Do not create scratch files. Do not edit campaign markdown. Do not use markdown sync tools. Do not shell out to `glass` when a typed MCP tool exists. Do not call local APIs or databases directly. Do not rely on stdout as state.
7. Close with `glass_done(..., scene_status="<enum from tools/list>")`.
8. Submit public prose with `glass_turn_append(body="...")`.

Stay inside the character's knowledge and agency. Use facts and hard-state MCP tool output as continuity, not prose echoes. Reference docs are not state and not an alternate interaction mode.
