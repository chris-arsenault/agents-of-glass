---
title: Public Table Instructions
target: executing-agent
authority: binding
---

# Public Table Instructions

`table/` is the shared visible board. If players should reason from a visible
fact in the current scene, it must appear in `table/` or another
player-readable file.

There is no authored `table/index.md`. Do not create one. The table is made of
`table/scene.md` plus named markdown artifacts such as `vel-hasken.md`,
`ref-0042-sr.md`, or any other meaningful slug the scene needs. These names are
examples, not a taxonomy or allow list.

## Player Sequence

1. Read `table/scene.md` and the named table artifacts relevant to your action.
2. Use `glass table show [path]` when a table file needs command-visible output.
3. Ask the DM only when the table is absent, ambiguous, or newly relevant.
4. Do not edit `table/`.

## DM Sequence

1. Update `table/scene.md` before ending any turn that changes the current
   visible situation.
2. Create or update a named table artifact for every reusable visible NPC,
   locale, ship, document, faction, clue, object, relationship, or other lore
   item players are expected to reason from.
3. When existing durable lore enters the scene, put the visible portion on the
   table with `glass table use` or a named table artifact that links to the
   durable lore.
4. When a table artifact becomes durable canon, promote or copy it into
   `shared/lore/` with `glass lore promote` or the `glass lore new` /
   `glass lore upsert` sequence.
5. Use command writes for table state:

```bash
glass table write scene.md --body "<visible scene description>"
glass table write <meaningful-slug>.md --body "<visible artifact>"
glass table append <meaningful-slug>.md --body "<new visible detail>"
glass table use shared/lore/<path>.md --as <meaningful-slug>.md
glass lore promote table/<meaningful-slug>.md --to shared/lore/<path>.md
glass table snapshot --label "<reason>"
```

6. Use `glass sync apply table` only for table files already edited directly.
7. Mention table updates and lore promotions in `glass done --state`.

## Boundary

Only `table/` is the active table. DM notes, graph entities, hooks, NPC files,
lore, messages, and human-visible UI panels are separate surfaces unless the
DM puts their visible content into `table/`.

## CLI Encoding Opportunities

These are not commands yet:

- `glass table check` for stale scene state, missing named artifacts, unpromoted
  durable lore, and stale table snapshots.
