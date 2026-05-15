# Glass Command Surface

Audit of the `glass` CLI command paths registered in `src/cli/main.py` and
`src/cli/commands/*.py`.

## Agent-Facing Design

Agents should not learn or remember the full `glass` CLI. The runner now
injects the command surface into each TURN_START from the current situation:
role, mode, turn type, active arc, active scene, player/character surface, and
pending level-up state.

The effective agent-facing surface is:

1. Core facade on nearly every full turn:
   `glass check`, `glass done`, and `glass find`.
2. Situation-specific lower-level commands injected only when relevant:
   active-play roll/beat/pressure commands, character-creation commands,
   pending level-up commands, scene-prep commands, and scene-transition
   commands. DM scene-prep and scene-transition turns also inject long-game
   thread commands when callbacks or recurring campaign handles are in play.
3. An explicit out-of-surface rule: if TURN_START and the current methodology
   do not name a command, the agent should not browse the full CLI or source
   to discover one.

This matters most for scene and arc management. `glass arc close-check`,
`glass scene create --type <problem-family>`, scene clocks, beats, and scene
closeout are injected into DM scene-prep / scene-transition turns directly.
They are no longer discoverable only by reading methodology prose.

Source of truth: `ContextBuilder._turn_command_surface()` in
`src/orchestrator/context.py`.

## Counting Rule

- Counted: static Click leaf commands reachable as `glass ...`.
- Not counted: pure grouping commands such as `glass`, `glass arc`, or
  `glass scene tracker`.
- Counted once: hidden `glass msg send`.
- Not counted separately: the shorthand `glass msg <type> <recipient> <body>`.
  That spelling is implemented by `MessageGroup.resolve_command()` and
  dispatches to the hidden `glass msg send`.
- This is a command-path audit, not an option/argument audit.

**Distinct static leaf commands: 124.**

The static CLI is intentionally larger than the agent-facing command surface.
The facade commands are:

1. `glass check`
2. `glass done`
3. `glass find`
4. `glass next`

Those facade commands collapse common turn-start, closeout, search, and
turn-queue actions. The lower-level commands below remain available to the CLI,
but campaign agents should see them through TURN_START injection rather than a
static catalog.

## Counts By Group

| Group | Count |
|---|---:|
| `api` | 5 |
| `arc` | 6 |
| `beat` | 4 |
| `campaign` | 1 |
| `character` | 18 |
| `check` | 1 |
| `clock` | 6 |
| `db` | 2 |
| `done` | 1 |
| `entity` | 14 |
| `find` | 1 |
| `lore` | 6 |
| `mode` | 3 |
| `msg` | 2 |
| `next` | 1 |
| `note` | 4 |
| `quest` | 1 |
| `roll` | 1 |
| `scene` | 11 |
| `search` | 3 |
| `session` | 3 |
| `summary` | 3 |
| `sync` | 1 |
| `table` | 7 |
| `tarot` | 3 |
| `thread` | 3 |
| `turn` | 10 |
| `turns` | 2 |
| `web-api` | 1 |

## Command Paths

### `api` (5)

1. `glass api daemon restart`
2. `glass api daemon start`
3. `glass api daemon status`
4. `glass api daemon stop`
5. `glass api serve`

### `arc` (6)

1. `glass arc activate`
2. `glass arc close`
3. `glass arc close-check`
4. `glass arc create`
5. `glass arc current`
6. `glass arc list`

### `beat` (4)

1. `glass beat check`
2. `glass beat close`
3. `glass beat convert`
4. `glass beat start`

### `campaign` (1)

1. `glass campaign pull-note`

### `character` (18)

1. `glass character award-xp`
2. `glass character bulk-get`
3. `glass character bulk-update`
4. `glass character consequence-add`
5. `glass character consequence-list`
6. `glass character consequence-resolve`
7. `glass character get`
8. `glass character inventory-add`
9. `glass character inventory-rm`
10. `glass character level-up`
11. `glass character list`
12. `glass character mirror`
13. `glass character new`
14. `glass character set-hp`
15. `glass character set-momentum`
16. `glass character signature-add`
17. `glass character signature-status`
18. `glass character skill-declare`

### `check` (1)

1. `glass check`

### `clock` (6)

1. `glass clock archive`
2. `glass clock list`
3. `glass clock resolve`
4. `glass clock set`
5. `glass clock show`
6. `glass clock tick`

### `db` (2)

1. `glass db migrate`
2. `glass db status`

### `done` (1)

1. `glass done`

### `entity` (14)

1. `glass entity between`
2. `glass entity claim`
3. `glass entity edges`
4. `glass entity find`
5. `glass entity link`
6. `glass entity neighborhood`
7. `glass entity query`
8. `glass entity ratify-claim`
9. `glass entity relations`
10. `glass entity similar`
11. `glass entity stance`
12. `glass entity stats`
13. `glass entity unlink`
14. `glass entity upsert`

### `find` (1)

1. `glass find`

### `lore` (6)

1. `glass lore import`
2. `glass lore list`
3. `glass lore new`
4. `glass lore promote`
5. `glass lore search`
6. `glass lore upsert`

### `mode` (3)

1. `glass mode current`
2. `glass mode end`
3. `glass mode start`

### `msg` (2)

1. `glass msg read`
2. `glass msg send` hidden; preferred spelling is
   `glass msg <type> <recipient> <body>`.

### `next` (1)

1. `glass next`

### `note` (4)

1. `glass note propose`
2. `glass note ratify`
3. `glass note reject`
4. `glass note write`

### `quest` (1)

1. `glass quest beat`

### `roll` (1)

1. `glass roll`

### `scene` (11)

1. `glass scene clock declare`
2. `glass scene clock tick`
3. `glass scene closing-down`
4. `glass scene create`
5. `glass scene current`
6. `glass scene end`
7. `glass scene list`
8. `glass scene pressure`
9. `glass scene tracker list`
10. `glass scene tracker set`
11. `glass scene tracker tick`

### `search` (3)

1. `glass search reindex`
2. `glass search semantic`
3. `glass search text`

### `session` (3)

1. `glass session new`
2. `glass session show`
3. `glass session wrap`

### `summary` (3)

1. `glass summary append`
2. `glass summary show`
3. `glass summary write`

### `sync` (1)

1. `glass sync apply`

### `table` (7)

1. `glass table append`
2. `glass table archive`
3. `glass table current`
4. `glass table show`
5. `glass table snapshot`
6. `glass table use`
7. `glass table write`

### `tarot` (3)

1. `glass tarot current`
2. `glass tarot draw`
3. `glass tarot list`

### `thread` (3)

1. `glass thread advance`
2. `glass thread beat`
3. `glass thread current`

### `turn` (10)

1. `glass turn append`
2. `glass turn audit`
3. `glass turn begin`
4. `glass turn clear-handoff`
5. `glass turn end`
6. `glass turn handoff`
7. `glass turn housekeeping-round`
8. `glass turn initiative`
9. `glass turn rapid-round`
10. `glass turn restart-order`

### `turns` (2)

1. `glass turns feed`
2. `glass turns find`

### `web-api` (1)

1. `glass web-api serve`
