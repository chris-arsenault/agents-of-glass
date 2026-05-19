# Table

The table is the campaign's player-agent-visible short-term working memory.
In this project, "public table" means "present in the player agents' projected
CWD," not "everything a human web viewer may inspect."

It exists to minimize avoidable actor transitions. Players should not need to
spend turns asking the DM to repeat visible information they have already been
given: room descriptions, obvious monster condition, scene stakes, where the
exits are, what the duke's public posture is, or what handout was just shown.

Human viewers of the web UI can inspect DM notes, lore, hooks, graph state, and
other debug surfaces elsewhere. Those surfaces do **not** become table content
unless the DM explicitly writes or links them under `campaigns/<id>/table/`.

## Shape

The live table is always at:

```text
campaigns/<id>/table/
  scene.md
  <meaningful-slug>.md
  handouts/
```

Only two names are reserved:

- `scene.md` — the current visible situation.
- `handouts/` — optional in-game handouts: notices, letters, pictures, maps,
  diagrams, evidence, generated images, and similar player-visible artifacts.

Everything else at `table/` root is arbitrary markdown. There is no authored
`table/index.md`. The DM creates named files only when they help the table:
`ossa-treen.md`, `ref-0042-sr.md`, `sable-side-waystation.md`,
`broken-elevator.md`, or whatever the scene needs. These names are examples,
not a type system or allow list.

Table artifacts are intentionally close to durable lore shape. A table artifact
can be promoted into `shared/lore/` when it becomes lasting public canon, and an
existing `shared/lore/` entry can be copied onto the table when it becomes
scene-relevant.

## Boundary

The table is player-agent-visible and immediate. It is not:

- durable campaign lore
- a transcript
- a journal
- a character sheet
- canonical numeric state
- a DM secret notebook
- a graph-derived list of "active" entities
- a mirror of DM notes, hooks, NPC files, or monster files
- a catch-all for everything the human viewer can browse

Hard state still lives in the CLI/DB: rolls, HP, momentum, inventory, XP,
action order, scene trackers, durable clocks, and character consequences. The
table may summarize or link those values for readability, but hard state wins
if there is a conflict.

Secrets stay out of `table/` until they become visible. Use `dm/secret/`,
`dm/notes/`, hidden trackers, or the message bus for hidden state.

The web UI's **Active Table** panel must render only `table/**` from the live
campaign root. If a viewer wants to know which NPCs, monsters, routes, hooks, or
handouts the player agents could see, the answer must be legible from
`table/scene.md`, `table/handouts/**`, or another named artifact in `table/`.
Do not infer table visibility from graph rows or DM notes.

## Lifecycle

`glass scene create` snapshots any still-active previous table, then creates a
fresh live table for the new top-level scene.

Nested modes and subscene protocols keep the existing table. An `action`
subscene typed as combat, chase, or social-pressure should update the table, not
replace it.

`glass scene end --outcome` archives the final live table into the scene
directory and replaces the live table with an inactive pointer.

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
glass table show [path]
glass table write <path> --body <markdown>
glass table append <path> --body <markdown>
glass table use <campaign-markdown-path> --as <table-artifact>.md
glass lore promote table/<artifact>.md --to shared/lore/<path>.md
glass table snapshot [--label <text>]
glass table archive
```

Players read the table. The DM writes it. This keeps public visible state
authoritative without creating a second player-authored lore surface. `glass
table current` exists only as an operator/debug listing command; normal agent
turns read the projected files named in TURN_START directly.
