---
title: Public Table Instructions
target: executing-agent
authority: binding
---

# Public Table Instructions

`table/` is retired as the agent continuity layer. The graph fact pack is the
shared visible board for agent decisions, and agents read it through the MCP tool surface:

```text
glass_fact_pack(audience="continuity", output_format="markdown")
```

When called with `audience="continuity"`, `glass_fact_pack` returns only continuity facts:
usable world state, obligations, scene affordances, relationships, clues, and
other facts agents should act on. Character profile material and table-facing
guidance are separate audiences; do not treat them as the normal state feed.
Facts marked `importance="low"` or `importance="minor"` are stored for audit/debug
but omitted from fact-pack output.

If players should reason from a visible fact in current play, record it with
`glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "<entity-id>", "predicate": "<predicate>", "text": "<neutral fact>"}])`. Public prose is submitted with
`glass_turn_append(body="...")`; it is not a state transport layer.

Do not create or update `table/index.md`, `table/scene.md`, or named table
artifacts. Do not use files as a substitute for graph facts.

## Player Sequence

1. Read `glass_fact_pack(audience="continuity", output_format="markdown")`.
2. Ask the DM only when the fact graph or hard-state MCP tool output is absent,
   ambiguous, or newly relevant.
3. Do not edit `table/`.

## DM Sequence

1. Update graph facts before ending any turn that changes the current visible
   situation.
2. Create or update a fact for every reusable visible NPC, locale, ship,
   document, faction, clue, object, relationship, or other lore item players are
   expected to reason from.
3. When existing durable lore enters the scene, record the visible portion as a
   scoped graph fact.
4. Use graph facts for continuity state:

```text
glass_state_update(updates=[
  {"kind": "fact", "audience": "continuity", "importance": "medium", "scope_id": "<scene-id>", "subject_id": "scene", "predicate": "objective", "text": "<visible objective>"},
  {"kind": "fact", "audience": "continuity", "importance": "medium", "scope_id": "<scene-id>", "subject_id": "<object>", "predicate": "descriptor", "text": "<plain descriptor and affordance>"},
  {"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "<character-id>", "predicate": "relationship", "object_id": "<other-character-id>", "text": "<neutral relationship fact>"},
  {"kind": "fact", "audience": "profile", "importance": "medium", "subject_id": "<character-id>", "predicate": "social-texture", "text": "<table-facing texture>"}
])
```

5. Mention already-committed fact updates in `glass_done(state=[...])`.

## Boundary

Only the fact graph is active continuity. Reference lore, messages, old table
files, transcripts, summaries, and human-visible UI panels are separate surfaces
unless their visible content is recorded as graph facts.
