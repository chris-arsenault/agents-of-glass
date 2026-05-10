# Orchestrator — Spec

The Python loop that drives a scene: picks the next agent, builds their per-turn context package, spawns `claude -p --dangerously-skip-permissions`, and processes their output. Plus the campaign/arc/scene lifecycle that runs around scenes.

For the full role this plays in the system, see [`../../docs/design/architecture.md`](../../docs/design/architecture.md). For the turn shape it implements, see [`../../docs/design/turn-loop.md`](../../docs/design/turn-loop.md). For the context it builds per turn, see [`../../docs/design/context-packages.md`](../../docs/design/context-packages.md). For the campaign/arc/scene hierarchy this drives, see [`../../docs/design/game-start.md`](../../docs/design/game-start.md).

This started as a spec. The current implementation is a v0 bootstrap predating the full hierarchy — paths get migrated as the build catches up:

- target shape: scene state at `campaigns/<id>/arcs/<arc>/scenes/<scene>/state.json`;
- transcript, scene context, and audit files at `campaigns/<id>/arcs/<arc>/scenes/<scene>/`;
- per-turn artifacts (TURN_START.md, TURN.md, agent stdout/stderr) under `dm/turns/<NNNN>/` or `players/<id>/turns/<NNNN>/`;
- agents are spawned directly inside the campaign workspace (`cwd = campaigns/<id>/`); no per-turn ephemeral CWD;
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
aog campaign bootstrap <id>                 # IMPLEMENTED — full bootstrap end-to-end:
                                            #   1. create campaigns/<id>/ from templates/
                                            #   2. invoke DM in campaign-planning mode (foundation + opening arc)
                                            #   3. [STUB] character creation
                                            #   4. [STUB] active scene play
                                            # flags: --max-planning-turns N, --dry-run, --keep-cwd
aog campaign show <id>                      # IMPLEMENTED — print state.json
aog campaign list                           # IMPLEMENTED — list all campaigns with phase
aog campaign clear <id> [--yes]             # IMPLEMENTED — wipe campaign workspace

aog campaign plan [<id>]                    # planned — run the campaign_planning phase only
aog campaign character-create [<id>]        # planned — run the character_creation phase only
aog campaign run [<id>]                     # planned — advance from current phase
aog campaign resume [<id>]                  # planned — alias for `run`, failure recovery
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

1. **Pick the next agent.** Handoff/rapid-response queue first, then persisted action-scene initiative order if present, otherwise the mode default (round-robin, DM-only, travel order, etc.).
2. **Generate `TURN_START.md`** under the spawning agent's campaign directory. Contains pointers (relative to the campaign workspace) to persona, methodology-for-mode, public table, scene framing, campaign-level context, vocabulary, recent-turn snapshot, actual-play creative influence when applicable, plus an absolute path to where the agent must write its prose (`TURN.md` in the same dir).
   Continuity compression lives in authored summary files (`summary.md` at
   campaign, arc/act, and scene levels); TURN_START points at those surfaces
   but does not generate its own summary prose.
3. **Apply Unix permissions** on the per-turn dir so the spawning user can read TURN_START and write TURN.md. (No-op if provisioning isn't set up.)
4. **Spawn `claude -p --dangerously-skip-permissions`** with `cwd = campaigns/<id>/` (the actual campaign workspace; not a copy). Set env vars: `GLASS_ROLE`, `GLASS_CAMPAIGN_ID`, `GLASS_CONFIG`, `GLASS_TURN_ID`, `AOG_TURN_START`, `AOG_TURN_OUTPUT`, plus `GLASS_API_URL` and `GLASS_API_GRANT_FILE` for player users. The prompt is short — it just says "Read $AOG_TURN_START and write to $AOG_TURN_OUTPUT".
5. **Stream stdout/stderr** to the operator's terminal line-by-line, prefixed with `[<agent-id>]`. Full captures saved beside the agent's TURN files.
6. **Wait** for the subprocess to exit (with timeout from `claude.turn_timeout_seconds`, default 3600s).
7. **Process the agent's prose.** The agent must write public turn prose to
   `TURN.md`/`out.md` at `AOG_TURN_OUTPUT`. If that file is missing or empty,
   the turn fails; stdout/stderr are operational debug captures, not public
   corpus. The orchestrator then calls `glass turn append`, which commits
   `turns.prose` in Postgres, links/inlines pending events, and refreshes
   campaign and scene markdown transcript exports.
8. **Update orchestrator state** (turn number, mode budgets, last speaker). State persists to disk so resume works.
9. **Evaluate scene-end** conditions. Hard turn caps + DM voluntary `glass scene end` for v1.
10. **Loop.**

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
- Per-agent turn scratch (`dm/turns/*`, `players/<id>/turns/*`) → discardable after commit; rebuilt on resume as needed.

`aog session resume <id>` should be idempotent — running it on a clean session is a no-op.

## What the orchestrator does NOT do

- Make narrative decisions.
- Override agent prose.
- Parse agent prose for "intent" or "next speaker hints" (see [`../../docs/principles/codify-only-what-drifts.md`](../../docs/principles/codify-only-what-drifts.md)).
- Write to Postgres or FalkorDB except via the `glass` CLI (same rule that applies to agents).

## Open after the v0 build

- Mode-end coordination (when DM calls `glass mode end`, the orchestrator needs to see that — same path as the future `glass` state store).
- Replacing local `aog-state.json` with the Postgres-backed state boundary
  described above.

See [`tracking-immediate-decisions.md`](../../tracking-immediate-decisions.md) for the broader list.
