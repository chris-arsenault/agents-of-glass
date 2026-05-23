# Table

The old file-backed `table/` surface is retired as an agent continuity layer.
Current visible state for agents is the injected prompt plus CLI-readable facts
and hard state.

## Current Boundary

When players should reason from visible state, record that state in the fact
graph:

```bash
glass fact set --scope <scene-id> "scene.objective = <visible objective>"
glass fact set --scope <scene-id> "<object>.descriptor = <plain descriptor and affordance>"
glass fact set "<character-id>.relationship -> <other-character-id> = <neutral relationship fact>"
```

Agents read the shared board with:

```bash
glass fact pack --format markdown
glass check
```

Scene clocks, durable clocks, characters, and rolls remain purpose-built hard-state
commands. If there is a conflict between prose and CLI state, CLI state wins for
future agent decisions.

## Viewer Surface

The web UI may still render an "Active Table" view for humans, but that view is
a rendering of CLI-readable state. It is not a directory agents read, and it is
not a write target.

Do not infer agent visibility from a viewer panel or from campaign files. A
fact is agent-visible only when it is in the injected prompt or returned by an
authorized `glass` command.

## Retired Behavior

Agents do not create or update:

- `table/index.md`
- `table/scene.md`
- `table/<artifact>.md`
- handout files
- table snapshots

If a visible object, clue, route, NPC, hazard, or relationship matters across
turns, encode the neutral fact through `glass`.
