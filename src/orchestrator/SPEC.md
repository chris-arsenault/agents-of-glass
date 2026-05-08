# Orchestrator — Spec

The Python loop that drives a scene: picks the next agent, builds their per-turn ephemeral CWD, spawns `claude -p --dangerously-skip-permissions`, and processes their output. Plus the campaign/arc/scene lifecycle that runs around scenes.

For the full role this plays in the system, see [`../../docs/design/architecture.md`](../../docs/design/architecture.md). For the turn shape it implements, see [`../../docs/design/turn-loop.md`](../../docs/design/turn-loop.md). For the context it builds per turn, see [`../../docs/design/context-packages.md`](../../docs/design/context-packages.md). For the campaign/arc/scene hierarchy this drives, see [`../../docs/design/game-start.md`](../../docs/design/game-start.md).

This started as a spec. The current implementation is a v0 bootstrap predating the full hierarchy — paths get migrated as the build catches up:

- target shape: scene state at `campaigns/<id>/arcs/<arc>/scenes/<scene>/state.json`;
- transcript, scene context, and audit files at `campaigns/<id>/arcs/<arc>/scenes/<scene>/`;
- per-turn context packages under `.glass-cwd/<scene-id>/`;
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
aog campaign new <name>                     # init: copy templates, write state.json, advance to campaign_planning
aog campaign show [<name>]                  # show phase, sessions, progress
aog campaign list                           # list all campaigns
aog campaign plan [<name>]                  # run the campaign_planning phase
aog campaign character-create [<name>]      # run the character_creation phase
aog campaign run [<name>]                   # advance from current phase, doing whatever's next
aog campaign resume [<name>]                # alias for `run`, framed for failure recovery
aog campaign clear <name> --back-to <phase> # roll back state to before <phase>
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

1. **Pick the next agent.** Mode-dependent (round-robin, initiative, DM-prompted, etc.). DM has override authority via the previous DM turn's prose (in v1, no structured next-speaker hint — DM's intent is read from prose).
2. **Build the ephemeral CWD.** A per-turn working directory at `.glass-cwd/<scene-id>/<agent-id>-<turn-number>/` containing only the files the agent's role is allowed to see, populated via symlinks/bind-mounts from the canonical state. Includes the three projected context files: `campaign-context.md`, `arc-context.md`, `scene-context.md`.
3. **Generate `TURN_START.md`** in that CWD — pointers to persona, character, the three context levels, recent transcript, unread messages, vocabulary index, tool allowlist.
4. **Spawn `claude -p --dangerously-skip-permissions`** with CWD set to the ephemeral dir. Set env vars: `GLASS_ROLE`, `GLASS_CAMPAIGN_ID`, `GLASS_ARC_ID`, `GLASS_SCENE_ID`, `GLASS_CONFIG`.
5. **Wait** for the subprocess to exit. Capture exit code and any output.
6. **Process the agent's prose.** v0 contract: the agent writes public turn prose
   to `TURN.md`. If that file is missing, the orchestrator uses stdout as a
   fallback. The orchestrator then calls `glass turn append`, which owns the
   transcript header, mechanical event inlining, and the glass state update.
7. **Update orchestrator state** (turn number, mode budgets, last speaker). State persists to Postgres so resume works.
8. **Tear down** the ephemeral CWD.
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
- Ephemeral state (current `.glass-cwd/*`) → discardable; rebuilt on resume.

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
