# Lore And Notes

Agent turns do not maintain lore or notes files.

Use neutral graph facts for continuity that future agents must read. Use purpose-built Glass MCP tools for mechanical state, messages, clocks, beats, rolls, and character data.

Reference lore is database-backed prose source material. Agents may read injected
reference excerpts or use `glass_lore_search(query="<query>")` when a methodology explicitly
needs source prose. Reference lore is not campaign reality until the visible or
load-bearing portion is committed with `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "<entity-id>", "predicate": "<predicate>", "text": "<neutral fact>"}])`.

Do not create, edit, import, promote, or sync markdown lore/notes as a state
path.
