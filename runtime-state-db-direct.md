---
title: Runtime State Direct-to-DB Migration
status: proposed
owner: unassigned
---

# Runtime State Direct-to-DB Migration

A design for eliminating the in-memory `state` dict pattern from CLI
commands and the desync class of bugs it produces.

## Why this exists

The current pattern is structurally unsound. Every CLI command loads a
full snapshot of the campaign runtime state into a Python dict, mutates
it, and saves the whole dict at the end via `commit()`. Subcommands
(`_workspace.create_scene`, `_workspace.end_scene`, etc.) internally do
their *own* `load_state → mutate → save_state` against fresh snapshots.
When the outer command finishes and `commit()` writes its stale snapshot
back, it clobbers subcommand writes.

This has produced real bugs in shipped campaigns. From the
`spirit-fingers` review:

- 23 turns (39–61) ran with `arc_id=NULL` in the turn table. The DM's
  `scene transition --new --close-parent` ran `_apply_scene_close` which
  cleared `active_scene/active_scene_arc` to None both in-memory and in
  DB. Then `_workspace.create_scene` set them to the new scene in DB
  but not in the caller's in-memory copy. The outer `commit()` wrote
  the stale in-memory copy (Nones) back, overwriting the workspace
  write. Every subsequent turn read NULL.
- `arcs/None/` directory exists on disk. Same root cause: when the
  caller's in-memory state had `current_arc_id = None`, code stringified
  it (`str(None) = "None"`) and used it as a path component.
- Turns 25 and 38 (DM scene-close turns) had `arc_id=NULL` even though
  the scene they closed belonged to a real arc. `_turn_export_info`
  reads `workspace.current_scene` which had been cleared earlier in the
  same turn body.
- `action-fork` mode stack accumulation, 132-turn run wrecked at turn
  114 because `scene end` saved active_scene=None to DB without popping
  the mode_stack, then the next DM turn's stale in-memory state didn't
  reflect the workspace's write.

The fix in this document is structural. Targeted "refresh in-memory
state after subcommand" patches (which I shipped at
`src/cli/commands/scene.py:_scene_transition_nested` and
`_scene_transition_new` lines noted below) are divergent
implementations that paper over the bug at one site without fixing the
pattern. **Those patches should be reverted as step 0 of this work.**

## Current architecture

### The state dict

Defined in `src/cli/state.py:default_state()`. Field inventory as of
schema_version 5:

| field | type | semantics |
|---|---|---|
| `schema_version` | int | migration cursor |
| `campaign` | str | primary key |
| `status` | str | active / wrapped / failed |
| `created_at`, `updated_at`, `wrapped_at` | iso str | timestamps |
| `summary` | str | rolling campaign summary blurb |
| `turn_counter` | int | monotonic turn count |
| `mode_stack` | list[dict] | stack frames: `{mode, scene_id, started_at, started_by}` |
| `pending_events` | list[dict] | queued event records awaiting flush |
| `note_intake` | list[dict] | unratified player drafts |
| `entities`, `threads` | dict | graph caches |
| `turns` | list[dict] | turn records (duplicates DB rows) |
| `next_speakers` | list[dict] | handoff queue |
| `action_order` | dict\|None | initiative cursor |
| `scene_trackers` | dict | per-scene tracker state cache |
| `scene_closing_turns` | int\|None | wind-down countdown |
| `active_turn_*` (12 fields) | various | currently-active turn metadata |
| `closeout_*` (10 fields) | various | staged closeout payload |
| `active_arc`, `active_scene`, `active_scene_arc`, `active_scene_type` | str\|None | workspace state pointers (also written by `_workspace.create_scene` / `end_scene`) |
| `closed_arcs`, `arcs` | list | arc registry |
| `run_metadata` | dict | scheduler bookkeeping |

These fields fall into rough categories:

1. **Per-campaign identity** (`campaign`, `status`, timestamps,
   `summary`, `turn_counter`)
2. **Mode/scene/arc pointers** (the workspace-state fields:
   `active_arc`, `active_scene`, `active_scene_arc`, `active_scene_type`,
   `closed_arcs`, `arcs`, `mode_stack`)
3. **Per-turn ephemeral** (`active_turn_*`, `closeout_*`)
4. **Queues and caches** (`pending_events`, `note_intake`, `next_speakers`,
   `action_order`, `scene_trackers`, `scene_closing_turns`)
5. **Stale duplicates of DB data** (`turns` — already in the `turns`
   table; `entities`, `threads` — already in FalkorDB)

### The load/save/commit lifecycle

In `src/cli/state.py`:

- `load_state(paths, campaign_id)` — reads the runtime state row from
  Postgres, applies `normalize_state` to backfill defaults
- `save_state(paths, state)` — writes the whole dict back via
  `runtime_state_upsert`
- `commit(paths, state, ctx, event, params, result)` — calls
  `save_state` plus appends an audit row

In every CLI command (sampled from `src/cli/commands/scene.py`,
`character.py`, `turn.py`, `beat.py`, `mode.py`, `arc.py`, ...):

```python
def some_command(ctx, ...):
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)   # snapshot
    # ... mutate state in place ...
    state["foo"] = bar
    commit(paths, state, ctx, "event.name", params, result)  # whole-dict save
```

### Where the desync originates

The workspace primitives in `src/cli/workspace.py` *also* do
`load_state / save_state`:

- `create_scene` calls `load_campaign_state(workspace)` → mutates
  `active_scene`, `active_scene_arc`, `active_scene_type` → calls
  `save_campaign_state(workspace, state)` (which is just
  `save_state(get_paths(), state)`).
- `end_scene` does the same to clear those fields.
- `archive_table` reads but doesn't mutate.

When a CLI command loads state, then calls one of these workspace
primitives, then calls `commit()`:

1. Caller has snapshot S₀.
2. Caller mutates S₀ → S₁.
3. Subcommand loads its own snapshot S₂ (= S₁ if nothing else wrote).
4. Subcommand mutates S₂ → S₃, saves S₃ to DB. DB = S₃.
5. Caller does more work on S₁ (which doesn't reflect S₃).
6. Caller's `commit()` saves S₁. DB = S₁. **The subcommand's writes
   are gone.**

The bug class lives in step 6. Every multi-step command that calls a
workspace primitive (or any other intermediate saver) is exposed.

## Target architecture

### Pattern

No in-memory `state` dict in CLI commands. Each field has a typed
accessor on a session/state object that reads from and writes to the
DB transactionally. Multi-step commands open one DB transaction at the
start and either commit or roll back at the end.

```python
def some_command(ctx, ...):
    paths = get_paths()
    campaign_id = active_campaign_id()
    with runtime_session(paths, campaign_id) as session:
        # session is a thin wrapper over a Postgres connection +
        # campaign_id. All reads and writes go through it.
        session.set_active_arc("new-arc")
        session.push_mode_frame(mode="scene-play", scene_id="opening",
                                started_by=role.actor)
        # commit happens automatically when the with-block exits cleanly,
        # rollback happens on exception
```

### Accessor surface

One accessor module (`src/cli/db_state.py` or extend `db.py`) exposes
typed reads and writes. Sketch:

```python
# Per-campaign identity
def get_campaign_id(session) -> str: ...
def get_status(session) -> str: ...
def set_status(session, status: str) -> None: ...
def get_turn_counter(session) -> int: ...
def increment_turn_counter(session) -> int: ...
def get_summary(session) -> str: ...
def set_summary(session, summary: str) -> None: ...

# Mode/scene/arc pointers
def get_active_arc(session) -> str | None: ...
def set_active_arc(session, arc_id: str | None) -> None: ...
def get_active_scene(session) -> SceneRef | None: ...
def set_active_scene(session, scene_id: str | None, arc_id: str | None,
                     scene_type: str | None) -> None: ...
def get_closed_arcs(session) -> list[str]: ...
def add_closed_arc(session, arc_id: str) -> None: ...
def list_arcs(session) -> list[str]: ...
def add_arc(session, arc_id: str) -> None: ...

# Mode stack — operate on individual frames, not the whole list
def push_mode_frame(session, mode: str, scene_id: str,
                    started_by: str) -> None: ...
def pop_mode_frame(session) -> ModeFrame | None: ...
def peek_mode_frame(session) -> ModeFrame | None: ...
def list_mode_stack(session) -> list[ModeFrame]: ...
def has_mode_on_stack(session, mode: str, scene_id: str) -> bool: ...

# Per-turn ephemeral
def get_active_turn_context(session) -> TurnContext | None: ...
def set_active_turn_context(session, ctx: TurnContext) -> None: ...
def clear_active_turn_context(session) -> None: ...

# Closeout staging
def stage_closeout(session, payload: ClosePayload, valid: bool,
                   problems: list[str]) -> None: ...
def get_staged_closeout(session) -> StagedCloseout | None: ...
def clear_staged_closeout(session) -> None: ...

# Queues
def queue_event(session, actor: str, summary: str, payload: dict) -> None: ...
def flush_events_for_actor(session, actor: str) -> list[Event]: ...
def push_next_speaker(session, entry: dict) -> None: ...
def peek_next_speaker(session) -> dict | None: ...
def pop_next_speaker(session) -> dict | None: ...
def get_action_order(session) -> ActionOrder | None: ...
def set_action_order(session, order: ActionOrder) -> None: ...
def get_scene_closing_turns(session) -> int | None: ...
def set_scene_closing_turns(session, value: int | None) -> None: ...
def decrement_scene_closing_turns(session) -> int | None: ...

# Scene trackers
def get_scene_tracker(session, scene_id: str, tracker_id: str) -> Tracker | None: ...
def upsert_scene_tracker(session, scene_id: str, tracker_id: str,
                         tracker: Tracker) -> None: ...
def drop_scene_trackers(session, scene_id: str) -> None: ...
```

Each accessor maps to a single SQL statement or a small handful, all
running on the session's open transaction. No accessor takes or
returns a "whole state dict."

### Session object

```python
class RuntimeSession:
    """Thin wrapper over a Postgres connection + campaign id.

    Provides typed accessors and ensures every write goes through a
    single transaction. Commit on clean __exit__, rollback on
    exception.
    """
    def __init__(self, conn, campaign_id: str):
        self._conn = conn
        self.campaign_id = campaign_id

    # Accessors live as standalone functions taking `session`, not
    # methods. This lets us split the surface across modules
    # (db_state_modes.py, db_state_turns.py, etc.) without expanding
    # this class.

@contextmanager
def runtime_session(paths: Paths, campaign_id: str):
    pg_config = load_pg_config(load_config(paths))
    with connect(pg_config) as conn:
        session = RuntimeSession(conn, campaign_id)
        try:
            yield session
            conn.commit()
        except Exception:
            conn.rollback()
            raise
```

### Workspace primitive refactor

`_workspace.create_scene` etc. currently do their own load/save. They
should be refactored to take a session and write through it:

```python
def create_scene(session: RuntimeSession, workspace: CampaignWorkspace,
                 scene_id: str, scene_type: str,
                 arc_id: str | None = None) -> Path:
    # arc resolution, directory creation, file writes — same as today
    # state writes go through session, not via workspace.save_campaign_state
    db_state.set_active_scene(session, scene_id, arc_id, scene_type)
    return scene_dir
```

This eliminates the parallel-save vector. The workspace primitive
runs inside the caller's transaction.

### Atomicity contract

Single-step commands wrap their body in `runtime_session(...)` and
get atomic semantics for free. Multi-step commands like
`scene_transition` already need atomicity for correctness; with this
pattern they get it automatically — the whole transition is one
transaction; any exception rolls everything back.

### Audit log

The audit log (`audit.jsonl`) is a separate concern. Currently
`commit()` does both `save_state` and append-audit. In the new model:

- State writes go through session accessors during the command body.
- Audit appending stays as its own call at the end of the command,
  outside the transaction (or as part of it if we want strict
  audit-state coherence — design decision below).

## Migration plan

Sequence and dependencies. Steps are independent enough to ship in
separate PRs.

### Step 0 — revert the divergent partial fix

I shipped two patches that explicitly refresh in-memory state after
`_create_scene_record` writes to DB:

- `src/cli/commands/scene.py`: in `_scene_transition_nested`, after
  `_create_scene_record`, lines that set `state["active_scene"]`,
  `state["active_scene_arc"]`, `state["active_scene_type"]`.
- `src/cli/commands/scene.py`: in `_scene_transition_new`, same
  pattern after the `_create_scene_record` call.

These work locally but create a divergent implementation — only
`scene_transition` uses the refresh pattern, no other CLI command
does. Future bugs in other commands won't have the refresh. Revert
both blocks (search for the comment that starts with
`# _create_scene_record (via _workspace.create_scene) saves new`)
before doing this work. The DB-direct refactor fixes the underlying
bug at the pattern level, so the local fix becomes dead code.

The other recent partial fix that should be unified through this work:

- `src/cli/commands/scene.py`: arc derivation in
  `_scene_transition_new` and `_scene_transition_return` that calls
  `_workspace.arc_for_scene` first, then falls back to runtime state.
  Keep `_workspace.arc_for_scene` as a primitive — it's the right
  lookup. But the fallback chain should disappear once state goes
  through the session: the session knows arc context without runtime-
  state-pointer ambiguity.

### Step 1 — accessor module scaffolding

Create `src/cli/db_state.py` (or `src/cli/runtime/`). Implement the
session context manager and accessors for the simplest fields first:

- `get/set_status`, `get/increment_turn_counter`, `get/set_summary`
- `get/set_active_arc`, `get/list/add_arcs`, `get/add_closed_arcs`
- `get/set_active_scene` (the SceneRef bundle)

Add unit tests against a real Postgres test DB. These accessors should
exist alongside the existing `load_state/save_state` until enough
commands are migrated.

### Step 2 — mode stack and turn context accessors

The mode stack and active-turn context are the highest-leverage. Most
of the bugs surface around mode-stack manipulation and turn-record
attribution.

- `push/pop/peek/list_mode_stack`, `has_mode_on_stack`
- `get/set/clear_active_turn_context`
- `stage_closeout`, `get_staged_closeout`, `clear_staged_closeout`

Mode stack should ideally move from a JSONB column to its own table
(`campaign_mode_stack`) so push/pop are real INSERT/DELETE not
"read JSONB, mutate, write JSONB." This makes concurrent reasoning
easier and lets us add per-frame columns (e.g., `arc_id` on the frame)
without schema-thrashing the parent row. Decide if this restructuring
happens here or stays JSONB.

### Step 3 — migrate `scene_transition` to the new pattern

Highest-bug-density command. Migrating it validates the pattern under
real complexity:

- Replace `load_state` + `commit` with `runtime_session(...)`.
- Replace every `state["…"]` access with the corresponding accessor
  call.
- Pass the session to workspace primitives (which also get refactored
  to take the session).
- Remove the partial-fix refresh blocks from step 0 (already done if
  step 0 ran).

After this command works, the pattern is proven. The audit-log
appending stays via the existing `append_audit` for now.

### Step 4 — migrate the other lifecycle commands

In order of bug-density observed in campaigns:

1. `scene_end_cmd` and the `_apply_scene_close` helper
2. `mode_start`, `mode_end`
3. `arc_close` (which already has the disposition gate refactor in
   recent shipped code; verify it stays correct)
4. `arc_create`, `arc_activate`
5. `scene_create` (the standalone command; the workspace primitive
   is what scene_transition consumes)
6. `character.*` commands that mutate runtime state (skill XP, HP,
   momentum, inventory) — most of these touch character rows
   directly, not runtime_state, so they may need less migration
7. Turn lifecycle: `turn_begin`, `turn_end`, `turn_append`, `done`

### Step 5 — remove `load_state` and the `state` dict

Once every CLI command uses `runtime_session`, the `state` dict is
unused. Remove:

- `cli/state.py::default_state` (or convert to internal-only used by
  initial campaign provisioning)
- `cli/state.py::normalize_state` (no longer needed; schema is
  enforced at the table level)
- `cli/state.py::load_state` / `save_state`
- `cli/state.py::commit` (or repurpose to be transaction commit +
  audit append)
- `_workspace.load_campaign_state` / `_workspace.save_campaign_state`

The Postgres `campaign_runtime_states` table can shrink to just the
small per-campaign metadata (status, timestamps, summary, turn
counter). Everything else moves to its own tables or stays as JSONB
columns that are only ever read and written through session
accessors.

### Step 6 — extend to web_api_server and orchestrator state reads

`src/cli/web_api_server.py` reads runtime state for the timeline UI.
After migration, it should read through the same accessors or via
read-only queries against the same tables.

`src/orchestrator/store.py` syncs orchestrator session state from
glass state. With DB-direct accessors, the orchestrator can read
directly from the campaign_runtime_states table (or wherever the
fields live post-migration) without going through `load_state`.

## Resumability implication

This is a feature the user explicitly named. After migration:

- Any agent or CLI process can crash at any point.
- The next invocation reads canonical state from DB. There's no
  partially-written in-memory dict that vanished with the process.
- A multi-step command that crashed mid-flight either committed (its
  transaction succeeded, all writes are durable) or rolled back (no
  writes happened). No partial writes.

The current architecture cannot guarantee this. A command that
crashes between `_workspace.create_scene` (which saves) and the
outer `commit()` leaves the DB in a state where the scene exists in
the workspace but the runtime state doesn't reflect it.

## Tests

The integration test surface should grow:

- Unit tests for each accessor against a real Postgres test DB.
- Integration tests that run multi-step commands and assert the DB
  state matches expectations *after a simulated crash mid-command*
  (verifies rollback works).
- Regression tests for the four bugs in the spirit-fingers/action-fork
  reviews:
  - Cross-arc scene transition retains arc_id on every subsequent
    turn row
  - Scene-close turn's own row has arc_id of the closed scene, not
    NULL
  - No `arcs/None/` directory ever created
  - Mode stack doesn't accumulate duplicate frames
  - `--close-parent` against a non-scene-play parent doesn't create
    spurious files

Existing tests (`tests/test_cli.py`, `tests/test_runner.py`) should
continue to pass throughout the migration. Tests that assert on
in-memory `state` dict shape can stay as long as the underlying
fields exist; once `load_state` is removed (step 5), those assertions
need to convert to accessor calls.

## Open design questions

1. **Mode stack as table or JSONB?** Table gives per-frame columns
   and easier concurrent reasoning. JSONB preserves the existing
   schema. Recommend table; defer until step 2 design.

2. **Audit log atomicity.** Should `append_audit` run inside the
   session transaction (so audit + state are atomic together) or
   outside (so a state commit happens even if audit append fails)?
   Recommend inside, with audit-write failures retried separately if
   the audit pipeline becomes a bottleneck.

3. **`runtime_state_upsert` removal.** This function exists to write
   the whole-state JSONB row. After migration there's no whole-state
   write. Recommend removing it in step 5; the per-field accessors
   are the only writers.

4. **Workspace state cache.** `_workspace.current_scene` reads state
   via `load_campaign_state`. With DB-direct, it should take a session
   or do a small read query. Workspace primitives that are read-only
   (e.g., `arc_for_scene` which walks the filesystem) don't need
   migration.

5. **Concurrent access.** Today there's effectively no concurrency
   (one CLI command at a time per campaign). With DB-direct + proper
   transactions, concurrent CLI processes against the same campaign
   become possible — desirable for the orchestrator coordinating
   multiple agents. Should the session take a row-level lock on the
   campaign? Recommend yes; cheap insurance.

6. **JSONB vs columns for new tables.** The mode stack split-out is
   the model for future restructurings. Each accessor surface should
   evaluate: is this field genuinely a value (column) or a structured
   queryable thing (its own table)? Don't blindly turn every JSONB
   field into a table; only do it where queryability or atomicity
   benefits.

## What is explicitly out of scope for this doc

- Changing the audit log format
- Migrating FalkorDB graph access patterns
- Changing the workspace filesystem layout
- Changing the orchestrator's per-agent process model

These can move on their own schedules. The state-direct-to-DB
migration is necessary regardless of whether those move too.

## References

- Bug catalog: `docs/reviews/fluent-non-compositional-prose.md` (not
  directly related but documents the review discipline that surfaced
  the state-sync bugs)
- Current state shape: `src/cli/state.py:default_state` and
  `normalize_state`
- Current state I/O: `src/cli/state.py::load_state`, `save_state`,
  `commit`
- Workspace primitives that do parallel saves:
  `src/cli/workspace.py::create_scene`, `end_scene`,
  `load_campaign_state`, `save_campaign_state`
- The desync vector in scene_transition:
  `src/cli/commands/scene.py::_scene_transition_new`,
  `_scene_transition_nested`, including the partial-fix refresh
  blocks that should be reverted as step 0
- Specific bug evidence: `spirit-fingers` campaign at turns 25, 38,
  39-61; `action-fork` campaign mode-stack accumulation at turns
  113-132
