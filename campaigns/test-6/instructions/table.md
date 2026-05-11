---
title: Public Table Instructions
target: executing-agent
authority: binding
---

# Public Table Instructions

The public table is the current short-term visible scene state. It exists to
reduce clarification turns.

The table root is `table/`:

- `table/index.md` — at-a-glance visible state.
- `table/scene.md` — scene kickoff description.
- `table/handouts/` — in-game handouts.
- Any other markdown file at table root — freeform visible references created
  because this scene needs them.

## Players

Read the table before asking the DM to repeat visible information: room
descriptions, NPC posture, monster condition, routes, public stakes, handouts,
and public trackers.

Ask the DM only when the table is absent, ambiguous, newly relevant, or secret.

## DM

Update the table before ending your turn when visible short-term state changed.
Do not put secrets in `table/`.

Use:

```bash
glass table current
glass table show [path]
glass sync apply table/index.md
glass sync apply table/scene.md table/<reference>.md
glass sync apply table
glass table snapshot
```

Edit table markdown in place in `table/`, then commit the changed files or the
whole table directory with one `glass sync apply`.

Hard state remains in Postgres and the CLI: rolls, HP, inventory, action order,
scene trackers, durable clocks, consequences, and turns.
