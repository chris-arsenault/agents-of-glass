# Table

The table is the campaign's public short-term working memory.

It exists to minimize avoidable actor transitions. Players should not need to
spend turns asking the DM to repeat visible information they have already been
given: room descriptions, obvious monster condition, scene stakes, where the
exits are, what the duke's public posture is, or what handout was just shown.

## Shape

The live table is always at:

```text
campaigns/<id>/table/
  index.md
  scene.md
  handouts/
  <freeform-root-files>.md
```

Only three names are reserved:

- `index.md` — at-a-glance board for the current visible state.
- `scene.md` — the DM's scene kickoff description.
- `handouts/` — in-game handouts: notices, letters, pictures, maps, diagrams,
  evidence, generated images, and similar player-visible artifacts.

Everything else at `table/` root is freeform markdown. The DM creates files
only when they help the table: `npc-korth.md`, `west-balcony.md`,
`the-dukes-mental-state.md`, `broken-elevator.md`, or whatever the scene needs.

Do not introduce typed table schemas unless play shows a concrete drift problem
that prose files cannot solve.

## Boundary

The table is public and immediate. It is not:

- durable campaign lore
- a transcript
- a journal
- a character sheet
- canonical numeric state
- a DM secret notebook

Hard state still lives in the CLI/DB: rolls, HP, momentum, inventory, XP,
action order, scene trackers, durable clocks, and character consequences. The
table may summarize or link those values for readability, but hard state wins
if there is a conflict.

Secrets stay out of `table/` until they become visible. Use `dm/secret/`,
`dm/notes/`, `dm/scratchpad.md`, hidden trackers, or the message bus for hidden
state.

## Lifecycle

`glass scene create` snapshots any still-active previous table, then creates a
fresh live table for the new top-level scene.

Nested modes and subscene protocols keep the existing table. A combat, chase,
or social-pressure exchange that erupts inside a scene should update the table,
not replace it.

`glass scene end` archives the final live table into the scene directory and
replaces the live table with an inactive pointer.

Snapshots live under:

```text
arcs/<arc>/scenes/<scene>/table/snapshots/
```

The final archived table lives under:

```text
arcs/<arc>/scenes/<scene>/table/final/
```

## CLI

```bash
glass table current
glass table show [path]
glass table write <path> --body <markdown>
glass table append <path> --body <markdown>
glass table snapshot [--label <text>]
glass table archive
```

Players read the table. The DM writes it. This keeps public visible state
authoritative without creating a second player-authored lore surface.
