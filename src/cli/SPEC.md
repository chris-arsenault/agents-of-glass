# `glass` CLI — Spec

The in-session tool surface. Used by both the orchestrator and the agents. It is the only agent interaction mode and the single choke point for state mutation.

For the role this CLI plays in the system, see [`../../docs/design/architecture.md`](../../docs/design/architecture.md). For when agents call it, see [`../../docs/design/turn-loop.md`](../../docs/design/turn-loop.md).

This is a **spec, not an implementation**. We fill in details as we build. Aligned with [`docs/backlog.md`](../../docs/backlog.md) — most flag-level details are organic.

## Conventions

- **Command results are YAML on stdout** for machine-readable returns. Errors go to stderr with a non-zero exit code. CLI stdout is command return only; public prose and durable state never use raw provider stdout as an interaction channel.
- **Permissions are role-enforced via env var.** The orchestrator sets `GLASS_ROLE=dm` or `GLASS_ROLE=player:tev` (etc.) when spawning each agent's subprocess. The CLI checks the role on each subcommand and rejects calls outside that role's allowlist.
- **Errors are agent-friendly.** When an agent's call fails (unknown type, missing field, permission denied), the error message names what went wrong and lists valid options. The agent can retry inline.
- **Audit log everywhere.** Every successful call appends to the active scene's `audit.jsonl` (`campaigns/<id>/arcs/<arc>/scenes/<scene>/audit.jsonl`). Calls outside an active scene (e.g. during campaign planning) append to a campaign-level audit.

## Subcommands

### Arc and scene lifecycle (DM only)

The DM changes active arc/scene state through the CLI. Any backing files or exports created by these commands are implementation details for operator inspection. Orchestrated agents do not hand-edit those files.

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
glass scene transition <next-scene-id> --new|--nested|--return [--close-parent]
                                               # canonical scene-boundary command.
                                               # --new closes current + opens next at same stack level.
                                               # --nested pushes a sub-scene on top without closing.
                                               # --return <parent-id> closes nested + pops to parent.
                                               # required clock dispositions for any scene that closes.
glass scene end --outcome <text>               # low-level: closes current scene without a successor.
                                               # use only when no next scene is being staged
                                               # (e.g. immediately before glass arc close).
                                               # --outcome is repeatable, max 2 bullets
glass table current                            # optional/debug; table files are not agent continuity
glass table show [path]                        # optional/debug; prefer glass fact pack
```

### Mode lifecycle (within a scene)

A scene has a primary protocol/toolkit label (set at creation via `--type`).
Modes can be pushed for nested situations (an action scene inside town play).

```
glass mode push <mode-name>           # DM only — push a nested mode
glass mode pop                        # DM only — pop back to parent
glass mode current                    # show current mode + stack
glass scene clock declare <id> --label <text> --goal <text> --max N \
  --direction progress|countdown --polarity objective|threat|timer
glass scene clock tick <id> [delta] --outcome <text>
glass scene tracker set <id> --max N  # DM only — scene-local pressure target
  [--value N] [--resistance N] [--impact-resistance N]
glass scene tracker tick <id> [delta] # DM only — direct tracker adjustment
glass scene tracker list              # visible pressure targets
glass scene pressure <tracker-id> <skill> <attribute> \
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
added to the total. Logged to SQLite `dice_event` and the audit log. The
orchestrator inlines a one-line summary into the transcript at the right point.
Undeclared skills roll at `fool` and do not gain skill XP unless `--save-skill`
declares them before the roll.

Use `glass scene pressure <tracker-id> ...` when a character action both rolls
and reduces an established scene pressure tracker. Use `glass scene clock tick`
for direct non-roll objective/threat/timer movement, `glass character set-hp`
for HP changes, and `glass character consequence-add` for lasting character
fallout.

### Characters

Items, skills, and signature moves each carry three labels: a **slug**
(CLI handle), a **prose name** (used only when a character names the
thing aloud), and a **generic descriptor** (used in ordinary turn
prose). The CLI requires all three on every authoring flow; turn
prose should reach for the descriptor by default.

Worked examples:

| Surface | Slug | Prose name | Descriptor (prose default) |
|---|---|---|---|
| Item | `mirror-baton` | `Mirror Baton` | `baton` |
| Item | `forged-route-seal` | `Forged Route Seal` | `a forged dock pass` |
| Skill | `read-parallel-resonance-bands` | `Read Parallel Resonance Bands` | `reading the bands` |
| Skill | `talk-down-crowds` | `Talk Down Crowds` | `talking the crowd down` |
| Move | `ride-the-line-down` | `Ride The Line Down` | `the fall-line ride` |
| Move | `quiet-door` | `Quiet Door` | `her old lockpick trick` |

Concrete CLI invocations:

```bash
glass character inventory-add vel forged-route-seal \
  --name 'Forged Route Seal' \
  --descriptor 'a forged dock pass' \
  --effect-tag 'passes casual inspection'

glass character skill-declare doruth read-parallel-resonance-bands \
  --name 'Read Parallel Resonance Bands' \
  --descriptor 'reading the bands'

glass character signature-add mox 'Ride The Line Down' \
  --descriptor 'the fall-line ride' \
  --look 'Mox plants her feet on the fall line and rides the wreck down.' \
  --use 'When a beam is going to come down and someone is in the fall pocket.' \
  --tell 'One chance to read the line right.'
```

In `glass character bulk-update --from update.json`, the same three
labels must appear in the payload:

```json
{
  "characters": [{
    "character_id": "vel",
    "inventory_add": [
      {
        "id": "forged-route-seal",
        "name": "Forged Route Seal",
        "descriptor": "a forged dock pass",
        "qty": 1,
        "effect_tags": ["passes casual inspection"]
      }
    ],
    "set": {
      "skills": {
        "read-parallel-resonance-bands": {
          "tier": "artisan",
          "name": "Read Parallel Resonance Bands",
          "descriptor": "reading the bands"
        }
      }
    },
    "signature_moves": [
      {
        "name": "Ride The Line Down",
        "descriptor": "the fall-line ride",
        "look": "Mox plants her feet on the fall line.",
        "use": "When a beam is going to come down anyway.",
        "tell": "One chance to read the line right."
      }
    ],
    "mirror": true
  }]
}
```

```
glass character new <id> --player <player-id> \
  --primary-drive <drive> --positive-trait <text> \
  --table-presence <text> --non-work-want <text> \
  --opening-social-action <text> \
  --life-prompt "<prompt>=<answer>" --life-prompt "<prompt>=<answer>" \
  --pull-utilization "Source: <source>; Thesis: <identity thesis>."
glass character get <id>
glass character bulk-get <id>... [--all]
glass character bulk-update --from update.json          # set fields, inventory, signatures, mirror, hp/momentum
glass character set-hp <id> <delta>                     # DM, or own
glass character set-momentum <id> <value>               # DM, or own
glass character inventory-add <id> <item-id> [--qty N] [--name TEXT] [--descriptor TEXT] [--effect-tag TEXT ...]
glass character inventory-rm <id> <item-id> [--qty N]
glass character skill-declare <id> <skill-slug> [--name TEXT] [--descriptor TEXT]
glass character signature-status <id>
glass character signature-add <id> <name> [--descriptor TEXT] [--body TEXT | --look TEXT --use TEXT --tell TEXT]
glass character consequence-add <id> <label> [--severity minor|serious|critical]
glass character consequence-list <id> [--all]
glass character consequence-resolve <id> <consequence-id> [--note TEXT]
```

### Notes (operator/admin and legacy prose surfaces)

The old note/draft flow is not part of the orchestrated agent turn contract.
Agent turns use neutral continuity facts and purpose-built state commands; the
operator may curate durable prose outside the turn loop. See
[`../../docs/design/agents.md`](../../docs/design/agents.md).

### Lore curation

Reference lore is prose source material stored in embedded SQLite. It is not
continuity, and it is not copied into campaign markdown. If a reference detail
becomes true or visible in play, commit the usable portion as a neutral fact.

```
glass lore put <id> --body <text>      # DM only — upsert DB-backed prose reference
glass lore ingest <path-or-dir>        # DM only — load existing markdown into DB; no campaign copy
glass lore search <query>              # search DB-backed reference lore
glass lore read <id>                   # read one DB-backed reference entry
glass lore list                        # list DB-backed reference entries
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
glass check                                  # combined messages/facts/clocks/beat contract
glass fact pack --audience continuity|profile|meta|all --format yaml|markdown
glass fact set --audience continuity|profile|meta [--scope S] "subject.predicate = value"
glass done --summary S --state S --rolls S [--turn-type act|answer|support|pass] [--next default|agent]
glass lore search <query>                    # reference prose only; promote with facts
glass next <handoff|rapid-round|housekeeping-round|restart-order|clear> [...]
```

### Turns (corpus access)

```
glass turn append --body <public-prose>      # required after glass done in agent turns
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
glass summary show campaign|arc|act|scene [id]
```

Markdown sync commands are retired. Agent turns mutate durable state through
purpose-built Glass commands and graph facts only.

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
