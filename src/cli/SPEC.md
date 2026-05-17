# `glass` CLI — Spec

The in-session tool surface. Used by both the orchestrator and the agents. The single choke point for state mutation.

For the role this CLI plays in the system, see [`../../docs/design/architecture.md`](../../docs/design/architecture.md). For when agents call it, see [`../../docs/design/turn-loop.md`](../../docs/design/turn-loop.md).

This is a **spec, not an implementation**. We fill in details as we build. Aligned with [`docs/backlog.md`](../../docs/backlog.md) — most flag-level details are organic.

## Conventions

- **Output is YAML on stdout** for machine-readable returns. Errors go to stderr with a non-zero exit code.
- **Permissions are role-enforced via env var.** The orchestrator sets `GLASS_ROLE=dm` or `GLASS_ROLE=player:tev` (etc.) when spawning each agent's subprocess. The CLI checks the role on each subcommand and rejects calls outside that role's allowlist.
- **Errors are agent-friendly.** When an agent's call fails (unknown type, missing field, permission denied), the error message names what went wrong and lists valid options. The agent can retry inline.
- **Audit log everywhere.** Every successful call appends to the active scene's `audit.jsonl` (`campaigns/<id>/arcs/<arc>/scenes/<scene>/audit.jsonl`). Calls outside an active scene (e.g. during campaign planning) append to a campaign-level audit.

## Subcommands

### Arc and scene lifecycle (DM only — manages the dir hierarchy)

The DM scaffolds arcs and scenes through the CLI; the CLI creates the directory and stub files. The DM then writes content into the scaffolded files.

```
glass campaign pull-note --source <text> --used-in <surface> --note <text>
glass arc create <slug> --pull-source <text> --pull-utilization <text>
                                               # creates arcs/<slug>/ with plan.md, context.md, pulls.md, scenes/
glass arc activate <slug>                      # set active_arc for future scene creation
glass arc current                              # which arc is active
glass arc list
glass arc close-check [<slug>]                 # reports open scene, active arc clocks,
                                               # summary/done-criteria readiness
glass arc close [<slug>] --outcome <text>      # closes arc/act with 1-2 outcome bullets

glass scene create <slug> --type <label>       # creates arcs/<active-arc>/scenes/<slug>/
                                               # label is a protocol/toolkit slug; custom allowed
                                               #   with prep.md, context.md, transcript.md, audit.jsonl
                                               # resets campaigns/<id>/table/ for the new scene
                                               # use --arc <slug> to attach to a non-active arc
glass scene current
glass scene list [--arc <slug>]
glass scene end --outcome <text>               # archives table, ends the active scene
                                               # --outcome is repeatable, max 2 bullets
glass table current                            # optional/debug: list live player-agent-visible table files
glass table show [path]                        # read player-agent-visible table file/dir
glass table write <path> --body <md>           # DM only; replace table file
glass table append <path> --body <md>          # DM only; append table file
glass table use <campaign-md> --as <path>      # DM only; copy visible lore onto table
glass lore promote table/<path> --to <lore-md> # DM only; promote table artifact to lore
glass table snapshot [--label <text>]          # DM only; archive table snapshot
```

### Mode lifecycle (within a scene)

A scene has a primary protocol/toolkit label (set at creation via `--type`).
Modes can be pushed for nested situations (an action scene inside town play).

```
glass mode push <mode-name>           # DM only — push a nested mode
glass mode pop                        # DM only — pop back to parent
glass mode current                    # show current mode + stack
glass scene tracker set <id> --max N  # DM only — scene-local clock/progress tracker
  [--value N] [--resistance N] [--impact-resistance N]
glass scene tracker tick <id> [delta] # DM only — advance/reduce a tracker
glass scene tracker list              # visible tracker state
glass scene clock declare <id> --label <text> --goal <text> --max N \
  --direction progress|countdown --polarity objective|threat|timer
glass scene clock tick <id> [delta] --outcome <text>
glass scene pressure <target> <skill> <attribute> \
  --risk <level> --character <id> --impact <d6|d8|d10> \
  [--bonus N] [--save-skill] [--because <text>] [--note <text>]

glass clock set <id> --max N [--scope <scope>] [--anchor <id>] [--public]
glass clock tick <id> [delta] [--note <text>]
glass clock list [--scope <scope>] [--anchor <id>] [--public] [--all]
glass clock show <id>
glass clock resolve <id> [--note <text>]
```

### Dice

```
glass roll <skill> <attribute> --risk <level> --character <id> [--target <id>] [--save-skill]
```

Returns a structured roll record (dice, modifiers, total, target, margin,
outcome tier, momentum delta, and narrative momentum effect). Momentum is not
added to the total. Logged to Postgres `dice_event` and the audit log. The
orchestrator inlines a one-line summary into the transcript at the right point.
Undeclared skills roll at `fool` and do not gain skill XP unless `--save-skill`
declares them before the roll.

`glass scene pressure` uses the same hit-check math, then rolls an impact die
to reduce a scene tracker. It is generic: HP, resistance, distance, morale,
alert, and similar numeric targets all use the same command. `--note` records a
fictional effect but does not create a mechanical object.

### Characters

```
glass character new <id> --player <player-id> \
  --primary-drive <drive> --positive-trait <text> \
  --table-presence <text> --non-work-want <text> \
  --opening-social-action <text> \
  --life-prompt "<prompt>=<answer>" --life-prompt "<prompt>=<answer>" \
  --pull-utilization "Source: <source>; Thesis: <identity thesis>; Used in: archetype, drive, trait, table presence, non-work want, opening social action, item, skill, signature move, failure mode, voice."
glass character get <id>
glass character bulk-get <id>... [--all] [--no-signatures]
glass character bulk-update --from update.json          # set fields, inventory, signatures, mirror, hp/momentum
glass character set-hp <id> <delta>                     # DM, or own
glass character set-momentum <id> <value>               # DM, or own
glass character inventory-add <id> <item-id> [--qty N] [--effect-tag TEXT ...]
glass character inventory-rm <id> <item-id> [--qty N]
glass character signature-status <id>
glass character signature-add <id> <name> [--body TEXT | --from PATH]
glass character consequence-add <id> <label> [--severity minor|serious|critical]
glass character consequence-list <id> [--all]
glass character consequence-resolve <id> <consequence-id> [--note TEXT]
```

### Notes (lore drafts and journal entries)

```
glass note write <path>             # write a note. Path determines where: drafts/ vs journal/ vs canonical
glass note propose <path>           # player only — push a draft to DM intake
glass note ratify <intake-id>       # DM only — canonize a player draft into shared lore
glass note reject <intake-id>       # DM only — drop a player draft
```

Note: lore drafts are encyclopedia-shaped (frontmatter + sections); journal entries are journal-shaped (free-form prose). The CLI does not enforce this — it's a convention. See [`../../docs/design/agents.md`](../../docs/design/agents.md).

### Entities (graph)

```
glass entity upsert <path>          # DM only — markdown → FalkorDB
glass entity neighborhood <id>      # read — show typed edges
glass entity relations <id> [--type REL] [--direction out|in|both]
glass entity between <a> <b>
glass entity edges --type REL
glass entity stance <a> <b>
glass entity find [--query Q] [--type T]
glass entity claim <a> <REL> <b> --summary TEXT
glass entity ratify-claim <claim-id> # DM only
glass entity similar <section-id>   # read — section similarity fallback
```

`entity query` remains the DM-only arbitrary Cypher escape hatch. Player-facing
graph commands are bounded so players can ask relationship questions without
raw graph access.

### Lore curation

The world bible at `../the-glass-frontier-lore/` is the DM's reference. It is not bulk-copied into the campaign. The DM imports specific entries on demand. See [`/templates/methodologies/campaign-planning.md`](../../templates/methodologies/campaign-planning.md#curate-dont-copy).

```
glass lore import <world-bible-path> [--as <new-name>]   # DM only
                                       # copies world-bible entry into campaigns/<id>/shared/lore/,
                                       # preserves directory structure (or renames via --as),
                                       # tags frontmatter with `source: world-bible/<path>`,
                                       # calls glass entity upsert on the result
glass lore list                        # read — list imported entries (campaign canon)
glass lore search <query>              # DM only — search the world bible without importing
```

### Threads (DM scaffolding)

```
glass thread current
glass thread beat <thread-id>       # show current beat
glass thread advance <thread-id> --note <text>
                               # DM only — advances the beat or opens the thread
```

### Messaging

See [`../../docs/design/messaging.md`](../../docs/design/messaging.md).

```
glass msg <type> <recipient> <body>
glass msg read [--since-checkpoint] [--from <sender>] [--type <type>]
```

### Agent facade

```
glass check                                  # combined messages/table/clocks/beat contract
glass done --summary S --state S --rolls S [--turn-type act|answer|support|pass] [--next default|agent]
glass find <query> [--mode text|semantic|turns]
glass next <handoff|rapid-round|housekeeping-round|restart-order|clear> [...]
```

### Turns (corpus access)

```
glass turn append <markdown-file>           # called at end of agent turn (orchestrator handles header)
glass turn end --summary S --state S --rolls S [--scene-status active|ended] [--next default|agent]
                                                   # lower-level closeout; prefer glass done
glass turn initiative [--participants ...]  # DM only; roll/persist action-scene order
glass turn handoff <agent-id>               # one-off next-speaker override
glass turn rapid-round <prompt>             # DM only; short response from each player
glass turn housekeeping-round [--previous-scene X] [--next-scene Y] [--next agent]
                                                   # DM only; queue between-scene player cleanup
glass turns find [--scene X] [--speaker Y] [--mode Z] [--turn-id N] [--text Q]
glass turns feed [--after-turn N] [--limit N]   # structured public viewer feed
glass search text <query> [--type turn|markdown]
glass search semantic <query> [--type turn|markdown]  # vector search over embedded chunks
glass search reindex [--turns-only]             # DM only
glass tarot current [actor]
glass tarot list [--actor <actor>] [--all]
glass tarot draw <actor> [--turns N]             # DM only
glass summary show campaign|arc|act|scene [id]
glass summary write campaign|arc|act|scene [id] --body <markdown>
glass summary append campaign|arc|act|scene [id] --body <markdown>
glass sync apply [path-or-directory ...]          # commit projected markdown edits
```

`glass sync apply` commits markdown edits from the projected workspace to the
canonical campaign. With paths, files are committed directly and directories
recurse over markdown files:

```
glass sync apply players/tev/public/intro.md
glass sync apply arcs/prelude table
glass sync apply
```

With no paths, it commits changed writable markdown files from the current
projection. Successful markdown writes are registered with the persistence
facade, so searchable markdown and entity graph side effects stay centralized.
The legacy `--from scratch/sync.json` manifest form remains supported for rare
generated batches.

## Environment

The CLI reads:

- `GLASS_ROLE` — `dm` or `player:<id>`. Set by the orchestrator.
- `GLASS_CAMPAIGN_ID` — active campaign. Set by the orchestrator.
- `GLASS_ARC_ID` — active arc, if any.
- `GLASS_SCENE_ID` — active scene, if any.
- `GLASS_CONFIG` — path to `agents-of-glass.toml`. Defaults to repo root.

If `GLASS_ROLE` is unset, the CLI assumes operator and allows everything. (The operator CLI `aog` is the friendlier interface for humans; `glass` from the shell is for debugging.)

## What's not in this spec

- Exact flag names for every subcommand
- Exit codes
- Full output schemas

These get pinned as we build. See [`docs/backlog.md`](../../docs/backlog.md) — the CLI surface is held for organic resolution.
