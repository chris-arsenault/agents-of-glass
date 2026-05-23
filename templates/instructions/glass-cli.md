# Glass MCP Tools

Native MCP tools named `glass_*` are the only agent interaction mode for
campaign state. They are typed wrappers over local Glass runtime services and
run under the current turn grant. Do not call `glass` in a shell when a
matching `glass_*` tool exists.

Use the canonical MCP `tools/list` request for tool discovery. It is a
client-to-server request, takes no parameters, and returns the structured
`tools/list` response containing each tool's name, description, and input
schema. It is not a Glass tool and must not be called through `glass_help` or a
shell command.

Use `glass_help(command="<glass_tool_name>")` only when syntax or a parameter
contract is unclear. For example:

- `glass_help(command="glass_state_update")`
- `glass_help(command="glass_scene_clock_declare")`
- `glass_help(command="glass_done")`

After reading help, return to the typed MCP tool named by the injected prompt or
the methodology.

Canonical turn sequence:

1. `glass_check()`
2. `glass_fact_pack(audience="continuity", output_format="markdown")` when you need to refresh continuity
3. purpose-built state tools such as `glass_message_send(...)`, `glass_roll(...)`, `glass_scene_*`, `glass_character_*`, `glass_beat_*`, `glass_clock_*`
4. `glass_lore_search(query="<query>")` only for DB-backed reference prose, when needed
5. `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "<entity-id>", "predicate": "<predicate>", "text": "<neutral fact>"}, {"kind": "inventory_add", "character_id": "<character-id>", "item_id": "<item-id>", "name": "<item name>", "descriptor": "<plain descriptor>", "qty": 1, "effect_tags": ["<tag>"]}, {"kind": "inventory_remove", "character_id": "<character-id>", "item_id": "<item-id>", "qty": 1}])` for durable facts and inventory changes
6. `glass_done(..., scene_status="active")`
7. `glass_turn_append(body="<public prose>")`

Fact audience contract:

- `glass_fact_pack(...)` requires an `audience`; choose `continuity` for the normal turn-state feed.
- Every fact object must include `importance="high|medium|low|minor"`. Use `high` for campaign/scene facts the next actor must use and `medium` for ordinary durable state. `low` and `minor` are stored but omitted from fact-pack output; tool responses will warn because they are usually not the right place for playable state.
- Use `glass_state_update(updates=[{"kind": "fact", "audience": "profile", "importance": "medium", "subject_id": "<character-id>", "predicate": "social-texture", "text": "<table-facing texture>"}])` only for character texture, table presence, voice, habits, and non-load-bearing personal color.
- `audience="meta"` is for process guidance. It is not campaign reality.
- `glass_done(...)` requires `scene_status`; use exactly one enum value from `tools/list`.

MCP return contract:

- Tool results include an `instructions` field even when `ok` is true. Read it before deciding the next action; it is current-turn guidance from the runtime system.

Forbidden during agent turns:

- shelling out to `glass` when a typed MCP tool exists
- file creation or edits
- scratch files
- campaign markdown edits
- markdown sync tools
- retired lore file workflows
- table/summary/note maintenance tools
- source, test, migration, template, or config edits
- direct local API or database calls

If a needed state operation has no typed MCP tool, close with a clear blocker or
message the DM/operator. Do not invent a file, API, shell, or stdout workaround.
