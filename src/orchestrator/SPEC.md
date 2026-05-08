# Orchestrator — Spec

The Python loop that drives the session: picks the next agent, builds their per-turn ephemeral CWD, spawns `claude -p --dangerously-skip-permissions`, and processes their output.

For the full role this plays in the system, see [`../../docs/design/architecture.md`](../../docs/design/architecture.md). For the turn shape it implements, see [`../../docs/design/turn-loop.md`](../../docs/design/turn-loop.md). For the context it builds per turn, see [`../../docs/design/context-packages.md`](../../docs/design/context-packages.md).

This is a **spec, not an implementation**. We fill in details as we build.

## Two binaries

The orchestrator package exposes two scripts:

- **`aog`** — the operator CLI. Start sessions, list sessions, clear scene/session/campaign state, restart from a known point. The human-facing surface.
- **(internal)** — the actual orchestrator loop. Started by `aog session run`. Foreground process for v1; the operator monitors stdout and ctrl-C's to interrupt.

## `aog` surface

```
aog session new --campaign <name>           # create a new session, prepare bootstrap state
aog session run [<id>]                      # run the orchestrator loop for a session (foreground)
aog session resume [<id>]                   # resume from last consistent state
aog session list
aog session show [<id>]
aog clear scene [<scene-id>]                # clear a scene's state (mode stack, scene-framing, etc.)
aog clear session [<id>]                    # clear a session entirely
aog clear campaign <name>                   # nuclear — wipe a campaign
```

Operator concerns only — no agent ever calls `aog`.

## What the orchestrator loop does, per turn

1. **Pick the next agent.** Mode-dependent (round-robin, initiative, DM-prompted, etc.). DM has override authority via the previous DM turn's prose (in v1, no structured next-speaker hint — DM's intent is read from prose).
2. **Build the ephemeral CWD.** A per-turn working directory at `.glass-cwd/<agent-id>-<turn-id>/` containing only the files the agent's role is allowed to see, populated via symlinks/bind-mounts from the canonical state.
3. **Generate `TURN_START.md`** in that CWD — pointers to role, character, scene framing, recent transcript, unread messages, vocabulary index, tool allowlist.
4. **Spawn `claude -p --dangerously-skip-permissions`** with CWD set to the ephemeral dir. Set env vars: `GLASS_ROLE`, `GLASS_SESSION_ID`, `GLASS_CONFIG`.
5. **Wait** for the subprocess to exit. Capture exit code and any output.
6. **Process the agent's prose.** The agent has called `glass turn append` during their turn (or the orchestrator picks up a known well-named output file — TBD during build). The orchestrator wraps with the turn header, inlines mechanical events from the audit log, and commits to `content/sessions/<id>/transcript.md`.
7. **Update orchestrator state** (turn number, mode budgets, last speaker). State persists to Postgres so resume works.
8. **Tear down** the ephemeral CWD.
9. **Evaluate mode-end** conditions. Hard turn caps + DM voluntary `glass mode end` for v1.
10. **Loop.**

## Failure handling

When an agent fails (claude error, timeout, malformed output):

- Stop the loop.
- Log to stderr with the failing turn id.
- The session state in Postgres is at the last consistent boundary (last fully-committed turn).
- The operator inspects, fixes, and runs `aog session resume` — or `aog clear scene` and continues.

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

## Open during build

- How exactly the orchestrator captures the agent's prose (`glass turn append` from inside the subprocess, or known-path convention?). Decide first time the loop runs.
- Mode-end coordination (when DM calls `glass mode end`, the orchestrator needs to see that — same path as above).
- TURN_START.md generation logic (templates? f-strings? small templating lib?). Decide as the file's content settles.

See [`tracking-immediate-decisions.md`](../../tracking-immediate-decisions.md) for the broader list.
