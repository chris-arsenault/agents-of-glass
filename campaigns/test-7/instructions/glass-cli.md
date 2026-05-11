---
title: Glass CLI Instructions
target: executing-agent
authority: binding
---

# Glass CLI Instructions

`glass` is the only persistent state mutation surface. Do not write raw SQL or
raw Cypher. Read normal workspace-relative paths, edit writable document paths
in place, and use `glass` to commit those edits or mutate hard state. Do not
invent mechanical state in prose when a `glass` command owns it.

Use `glass --help` and command-specific `--help` when unsure. Do not spend
turn time reading the CLI source; if a command still fails after one clear
usage correction, continue the turn and let the operator-visible logs carry the
tooling problem.

Prefer bulk commands when you have several related mutations. For authored
markdown, write files at their real workspace paths and commit them with one
`glass sync apply`.

The usual mutation workflow is:

1. Read normal workspace files directly.
2. Edit writable markdown files directly at their intended relative paths.
3. Use one purpose-built `glass` command for hard state, or one
   `glass sync apply` for several document writes.
4. After the command succeeds, read the same relative path if you need to verify it.

## Common Read Commands

```bash
glass character bulk-get <id>... [--all]
glass character get <id>
glass clock list
glass summary show campaign
glass summary show scene
glass table current
glass turns find --text "<query>"
glass search text "<query>"
glass search semantic "<query>"
glass entity relations <id>
glass tarot current
```

## Common Mutation Commands

Players may mutate only their own character state and private notes. The DM may
mutate campaign, scene, lore, clock, tracker, and graph state.

```bash
glass roll <skill> <attribute> --risk <level> --character <id>
glass scene pressure <target> <skill> <attribute> --risk <level> --character <id> --impact <d6|d8|d10>
glass character bulk-update --json '<payload>'
glass character mirror <id>
glass character signature-status <id>
glass character signature-add <id> <name>
glass character set-hp <id> <delta>
glass character inventory-add <id> <item-id>
glass turn end --summary "<what changed>" --state "<durable updates or no state change>" --rolls "<rolls or none>" --next default
glass msg <type> <recipient> <body>
glass note propose <path>
glass sync apply [path-or-directory ...]
```

If a command fails, read the error, adjust, and retry only when the correction
is clear.

## Workspace Sync

Use `glass sync apply` to commit authored markdown from the workspace. Pass
files or directories:

```bash
glass sync apply players/tev/public players/tev/secrets
glass sync apply arcs/prelude table
glass sync apply
```

With no paths, `glass sync apply` commits changed writable markdown files.
Directory arguments recurse over markdown files.

Do not sync turn artifact paths such as `dm/turns/<n>/TURN.md` or
`players/<id>/turns/<n>/TURN.md`; the runner collects the current turn prose
and `glass turn end` closeout automatically.

Player syncs can commit only their own writable player document paths. Players
may also append to the active scene summary with `glass summary append scene`
when durable scene-level truth changes. Per-turn continuity for the next actor
belongs in `glass turn end --summary ...`.
DM syncs can commit DM, arc, table, shared lore, and campaign summary/context
document paths. Use `--dry-run` to validate without writing.

## Turn End

Every agent turn closes with `glass turn end`. The command records the compact
context block future turns receive and optionally queues a next actor:

```bash
glass turn end \
  --summary "Tev commits to opening the rack while Sumi keeps Drova talking." \
  --state "table/index.md updated with the exposed service panel" \
  --rolls "none" \
  --next default
```

Use `--next dm`, `--next tev`, `--next sumi`, `--next renno`, or `--next kit`
only when normal rotation or action order should be overridden.
