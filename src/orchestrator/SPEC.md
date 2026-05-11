# Orchestrator — Spec

The Python loop that drives a scene: picks the next agent, builds their per-turn context package, spawns `claude -p --dangerously-skip-permissions`, and processes their output. Plus the campaign/arc/scene lifecycle that runs around scenes.

For the full role this plays in the system, see [`../../docs/design/architecture.md`](../../docs/design/architecture.md). For the turn shape it implements, see [`../../docs/design/turn-loop.md`](../../docs/design/turn-loop.md). For the context it builds per turn, see [`../../docs/design/context-packages.md`](../../docs/design/context-packages.md). For the campaign/arc/scene hierarchy this drives, see [`../../docs/design/game-start.md`](../../docs/design/game-start.md).

This started as a spec. The current implementation is a v0 bootstrap predating the full hierarchy — paths get migrated as the build catches up:

- runtime state in Postgres, with scene prose and operator artifacts on disk;
- transcript, scene context, and audit files at `campaigns/<id>/arcs/<arc>/scenes/<scene>/`;
- per-turn artifacts (`TURN_START.md`, `TURN.md`, closeout JSON, agent stdout/stderr) under `dm/turns/<NNNN>/` or `players/<id>/turns/<NNNN>/`;
- agents are spawned inside per-turn read-only campaign-shaped projections (`cwd = .glass-cwd/<campaign>/<turn>-<agent>/`);
- agent stdout/stderr is streamed line-by-line to the operator's terminal with `[<agent-id>]` prefix, plus captured to disk;
- real turns invoke `claude -p ...`; `--dry-run` commits synthetic turns for
  wiring checks without spending model time.

There are no "sessions" — scenes are the unit of play. Sessions were a human-time-management artifact; the agents play as long as the operator runs the orchestrator.

## Two binaries

The orchestrator package exposes two scripts:

- **`aog`** — the operator CLI. Create campaigns, list campaigns, run/resume/clear scenes, advance phase. The human-facing surface.
- **(internal)** — the actual orchestrator loop. Started by `aog scene run`. Foreground process for v1; the operator monitors stdout and ctrl-C's to interrupt.

## `aog` surface

Campaign management (see [`/docs/design/game-start.md`](../../docs/design/game-start.md) for the bootstrap flow):

```
aog campaign run [<id>]                     # IMPLEMENTED — phase-aware lifecycle driver:
                                            #   1. create campaigns/<id>/ from templates/
                                            #   2. invoke DM in campaign-planning mode (foundation + opening arc)
                                            #   3. run character creation
                                            #   4. run two-scene prelude shakedown
                                            #   5. advance/run active play
                                            # flags: --max-planning-turns N, --max-creation-turns N,
                                            #        --max-prelude-turns N, --max-turns N,
                                            #        --skip-prelude, --dry-run
aog campaign show <id>                      # IMPLEMENTED — print runtime state summary
aog campaign list                           # IMPLEMENTED — list all campaigns with phase
aog campaign clear <id> [--yes]             # IMPLEMENTED — wipe campaign workspace
aog campaign checkpoint <id> [--label text] # IMPLEMENTED — snapshot filesystem + Postgres + FalkorDB
aog campaign checkpoints <id>               # IMPLEMENTED — list available checkpoints
aog campaign restore <id> <checkpoint>      # IMPLEMENTED — restore all persistence surfaces
aog campaign reconcile <id> [--repair]      # IMPLEMENTED — inspect/refresh disposable projections
```

Scenes (regular play, after bootstrap):

```
aog scene run [<scene-slug>]                # run the orchestrator loop for the active or named scene (foreground)
aog scene resume [<scene-slug>]             # resume from last consistent state
aog scene list [--arc <arc-slug>]
aog scene show [<scene-slug>]
aog scene prepare-turn [<scene-slug>]       # build next context package without committing
aog clear scene <scene-slug>                # clear a scene's state (drops transcript, audit, prep, context)
aog clear arc <arc-slug>                    # clear an arc and all its scenes
```

Note: scenes are *created* by the DM via `glass scene create` (in-play CLI), not by the operator. The operator runs scenes that the DM has already scaffolded.

Operator concerns only — no agent ever calls `aog`.

## What the orchestrator loop does, per turn (within an active scene)

1. **Pick the next agent.** Handoff/rapid-response/housekeeping queue first,
   then persisted action-scene initiative order if present, otherwise the mode
   default (round-robin, DM-only, travel order, etc.).
2. **Generate `TURN_START.md`** under the spawning agent's canonical campaign turn directory. Contains pointers (relative to the projected campaign workspace) to persona, the methodology for this role + turn type, the player-agent-visible public table, scene framing, campaign-level context, instruction surfaces, recent-turn summary snapshot, actual-play creative influence when applicable, plus the path where the agent must write prose (`TURN.md` in the same relative turn dir).
   The turn-type switch is programmatic here: queued rapid-response turns,
   queued player housekeeping, action-order turns, DM action openings, and DM
   scene transitions each point at their own methodology document. Actual-play
   methodologies must not branch to other actual-play turn types.
   Continuity compression lives in authored summary files (`summary.md` at
   campaign, arc/act, and scene levels); TURN_START points at those surfaces
   but does not generate its own summary prose.
3. **Build the per-turn projection** under `.glass-cwd/<campaign>/<turn>-<agent>/`. It mirrors canonical relative paths but contains only actor-visible files. The projection is chowned to the spawned actor; role-authorized document surfaces and the current turn dir are writable.
4. **Probe workspace permissions.** Before Claude starts, run as the spawned actor and prove the current turn dir supports arbitrary create, edit, and delete operations. Fail fast if ownership, ACLs, or modes are wrong.
5. **Mint a role-scoped `glass` grant**. The local API writes to the canonical campaign root while using the projection as cwd, so `glass sync apply` can commit projected document edits by their real relative paths.
6. **Spawn `claude -p --dangerously-skip-permissions`** with `cwd` set to the projection. Set env vars: `GLASS_ROLE`, `GLASS_CAMPAIGN_ID`, `GLASS_CONFIG`, `GLASS_TURN_ID`, `AOG_TURN_START`, `AOG_TURN_PROSE`, `AOG_TURN_CLOSEOUT`, `GLASS_API_URL`, and `GLASS_API_GRANT`/grant file as available. The prompt is short — it says to read TURN_START, write public prose, run `glass turn end`, and exit.
7. **Stream stdout/stderr** to the operator's terminal line-by-line, prefixed with `[<agent-id>]`. Full captures saved beside the agent's canonical turn files.
8. **Wait** for the subprocess to exit (with timeout from `claude.turn_timeout_seconds`, default 3600s).
9. **Copy turn artifacts back to canonical storage.** `TURN.md`, `turn-closeout.json`, and debug logs generated in the actor-owned projection are copied to the canonical turn dir.
10. **Process the agent's prose.** The agent must write public turn prose to
   `TURN.md` at `AOG_TURN_PROSE`. If that file is missing or empty,
   the turn fails; stdout/stderr are operational debug captures, not public
   corpus. The agent must also complete `glass turn end`, which writes compact
   closeout metadata. The orchestrator then calls `glass turn append`, which commits
   `turns.prose` plus closeout metadata in Postgres, links/inlines pending
   events, and refreshes campaign and scene markdown transcript exports.
10. **Update orchestrator state** (turn number, mode budgets, last speaker). State persists to Postgres so resume works.
11. **Evaluate scene-end** conditions. Hard turn caps + DM voluntary
    `glass scene end` for v1. If a DM scene-play/action turn leaves an open act
    with no active mode, the turn fails; ordinary scene boundaries must stage
    the next scene and queue player housekeeping in the same DM turn. No-mode
    active lifecycle starts intermission only after prelude or an act close,
    and starts scene prep after intermission or as recovery inside an open act.
12. **Loop.**

## Failure handling

When an agent fails (claude error, timeout, malformed output):

- Stop the loop.
- Log to stderr with the failing turn id.
- The scene state in Postgres is at the last consistent boundary (last fully-committed turn).
- The operator inspects, fixes, and runs `aog scene resume` — or `aog clear scene` and continues.

No automatic retries. No automatic recovery. See [`../../docs/design/architecture.md`](../../docs/design/architecture.md#resumability).

## Resumability requirements

- Mode stack, turn number, last speaker, current speaker queue → all in Postgres.
- Markdown content (transcript, framing, lore, journals) → all on disk, git-tracked.
- Graph state → in FalkorDB.
- Vector recall state → in Postgres `search_chunks`, including persisted embeddings.
- Per-agent turn artifacts (`dm/turns/*`, `players/<id>/turns/*`) → discardable after commit; rebuilt on resume as needed.

Operator checkpoints capture and restore all four durable surfaces: campaign
filesystem, Postgres runtime/search/vector rows, FalkorDB graph nodes/edges,
and disposable projections/permissions.

`aog session resume <id>` should be idempotent — running it on a clean session is a no-op.

## What the orchestrator does NOT do

- Make narrative decisions.
- Override agent prose.
- Parse agent prose for "intent" or "next speaker hints" (see [`../../docs/principles/codify-only-what-drifts.md`](../../docs/principles/codify-only-what-drifts.md)).
- Write to Postgres or FalkorDB except via the `glass` CLI (same rule that applies to agents).

## Open after the v0 build

See [`docs/backlog.md`](../../docs/backlog.md) for the broader list.
