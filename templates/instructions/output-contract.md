# Output Contract

There are two runtime outputs, and only two. Both go through typed MCP tools.
No file, stdout, shell command, API, database, or final chat response is a valid
substitute.

1. Durable state updates before closeout through the owning MCP tool.

Use `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "<entity-id>", "predicate": "<predicate>", "text": "<neutral fact>"}])` for neutral facts and inventory deltas that do not have a more specific hard-state tool. Use purpose-built `glass_*` tools for clocks, beats, rolls, scenes, messages, and character mechanics.

2. Closeout through `glass_done`:

```text
glass_done(
  summary="<1-3 sentence compact continuity>",
  state=["<durable update or no state change>"],
  rolls="<rolls/checks used or none>",
  scene_status="active",
  next_speaker="default",
)
```

3. Public prose through `glass_turn_append` after `glass_done` succeeds:

```text
glass_turn_append(body="<public prose>")
```

Do not write prose, closeout, notes, summaries, or scratch material to files. Do
not rely on stdout as a state channel. Do not include literal tool-call syntax in
public prose.
