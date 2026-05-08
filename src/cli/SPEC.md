# `glass` CLI — Spec

The in-session tool surface. Used by both the orchestrator and the agents. The single choke point for state mutation.

For the role this CLI plays in the system, see [`../../docs/design/architecture.md`](../../docs/design/architecture.md). For when agents call it, see [`../../docs/design/turn-loop.md`](../../docs/design/turn-loop.md).

This is a **spec, not an implementation**. We fill in details as we build. Aligned with [`tracking-immediate-decisions.md`](../../tracking-immediate-decisions.md) — most flag-level details are organic.

## Conventions

- **Output is YAML on stdout** for machine-readable returns. Errors go to stderr with a non-zero exit code.
- **Permissions are role-enforced via env var.** The orchestrator sets `GLASS_ROLE=dm` or `GLASS_ROLE=player:tev` (etc.) when spawning each agent's subprocess. The CLI checks the role on each subcommand and rejects calls outside that role's allowlist.
- **Errors are agent-friendly.** When an agent's call fails (unknown type, missing field, permission denied), the error message names what went wrong and lists valid options. The agent can retry inline.
- **Audit log everywhere.** Every successful call appends to `content/sessions/<active-session>/audit.jsonl`.

## Subcommands

### Session lifecycle

```
glass session new --campaign <name>
glass session show
glass session wrap                  # DM only — produces session summary, ends loop
glass session list                  # operator-friendly
```

### Mode lifecycle

```
glass mode start <mode-name> <scene-id>     # DM only
glass mode end                              # DM only — pops the mode stack
glass mode current                          # show current mode + stack
```

### Dice

```
glass roll <skill> <attribute> --risk <level> --character <id> [--target <id>]
```

Returns a structured roll record (dice, modifiers, total, target, margin, outcome tier, momentum delta). Logged to Postgres `dice_event` and the audit log. The orchestrator inlines a one-line summary into the transcript at the right point.

### Characters

```
glass character new <id> --player <player-id>           # creates from interactive prose? TBD
glass character get <id>
glass character set-hp <id> <delta>                     # DM, or own
glass character set-momentum <id> <value>               # DM, or own
glass character inventory-add <id> <item-id> [--qty N]
glass character inventory-rm <id> <item-id> [--qty N]
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
glass entity similar <section-id>   # read — vector search
```

### Threads (DM scaffolding)

```
glass thread current
glass thread beat <thread-id>       # show current beat
glass thread advance <thread-id>    # DM only — advances the beat
```

### Messaging

See [`../../docs/design/messaging.md`](../../docs/design/messaging.md).

```
glass msg <type> <recipient> <body>
glass msg read [--since-checkpoint] [--from <sender>] [--type <type>]
```

### Turns (corpus access)

```
glass turn append <markdown-file>           # called at end of agent turn (orchestrator handles header)
glass turns find [--scene X] [--speaker Y] [--mode Z] [--turn-id N]
```

## Environment

The CLI reads:

- `GLASS_ROLE` — `dm` or `player:<id>`. Set by the orchestrator.
- `GLASS_SESSION_ID` — active session. Set by the orchestrator.
- `GLASS_CONFIG` — path to `agents-of-glass.toml`. Defaults to repo root.

If `GLASS_ROLE` is unset, the CLI assumes operator and allows everything. (The operator CLI `aog` is the friendlier interface for humans; `glass` from the shell is for debugging.)

## What's not in this spec

- Exact flag names for every subcommand
- Exit codes
- Full output schemas

These get pinned as we build. See [`tracking-immediate-decisions.md`](../../tracking-immediate-decisions.md) — the CLI surface is held for organic resolution.
