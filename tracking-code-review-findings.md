# Tracking - Code Review Findings

Findings from the May 9, 2026 implementation/methodology review. Numbered so each can be handled independently.

Status key: `open`, `in-progress`, `done`, `deferred`.

## Findings

### AOG-001 - Player agents cannot reliably run `glass`

Status: `done`

Player users are launched with the operator's PATH, but `/home/dev/.local/bin/glass` imports from the editable repo source tree. That source tree is not traversable/readable by `aog-*` users, so Tev's live character-creation turn produced markdown but failed every required `glass` command with `ModuleNotFoundError: No module named 'cli'`.

Impact: character rows, inventory, and message bus writes can silently be absent while the transcript claims character creation happened.

Likely direction: install the package/venv/wrapper somewhere readable by player users, or invoke a shared project venv explicitly. Do not solve this by per-turn permission workarounds.

Resolution: added a repo-independent `/usr/local/bin/glass` client wrapper and a local API proxy. Player processes no longer need read access to the editable repo source tree to use the CLI surface.

References: `src/orchestrator/runner.py`, `/home/dev/.local/bin/glass`, repo `src/` permissions.

### AOG-002 - Bootstrap advances phases when caps are reached

Status: `done`

`run_loop` returns normally when `max_turns` is reached. `aog campaign bootstrap` then advances to the next phase even if the DM never ended the current mode.

Impact: campaign planning or character creation can be marked complete by a safety cap instead of explicit in-game completion.

Likely direction: treat cap exhaustion during bootstrap phases as paused/failed unless the mode stack has actually ended.

Resolution: bootstrap now reloads runtime state after campaign-planning and character-creation loops and refuses to advance if the expected bootstrap mode is still active. The runtime state is marked paused instead of silently completing a phase on turn-cap exhaustion.

References: `src/orchestrator/runner.py`, `src/orchestrator/main.py`.

### AOG-003 - FalkorDB entity identity is not campaign-scoped

Status: `done`

Graph upserts and links merge entities by `id` alone. A repeated slug across campaigns can overwrite properties, sections, and links across campaign boundaries.

Impact: graph data from one campaign can pollute another campaign; campaign cleanup can also miss shell nodes created without `campaign_id`.

Likely direction: scope graph identity by `(campaign_id, id)` or a composite global id, and apply that consistently to sections, mentions, links, queries, and cleanup.

Resolution: graph entity and section nodes now use campaign-scoped internal `uid` values while retaining public `id` properties. Entity links, unlinks, neighborhoods, mentions, and cleanup now pass campaign scope consistently.

References: `src/cli/graph.py`, `src/cli/commands/entity.py`, `src/cli/commands/lore.py`.

### AOG-004 - Runtime metadata still lives in JSON state instead of Postgres

Status: `done`

The design says Postgres should hold turn, mode, scene, and queryable corpus metadata. The implementation still stores turn metadata, entity fallback cache, mode stack, and phase/runtime state in `state.json` / `aog-state.json`.

Impact: the system remains partly file-backed and hard to query consistently; old JSON state becomes the accidental source of truth.

Likely direction: add migrations and CLI boundaries for turns, modes, scenes, phase history, and graph mirror status; keep markdown as prose, not metadata storage.

Resolution: added Postgres-backed `campaign_runtime_states` and structured `turns` tables. `state.json` is now a derived cache/export when Postgres is configured, while no-DB tests/dev keep the file fallback. Bootstrap phase writes are synced into the same runtime row, and `aog campaign bootstrap/run/resume` applies migrations before orchestration.

References: `src/cli/commands/turn.py`, `src/cli/commands/turns.py`, `src/cli/entities.py`, `src/orchestrator/store.py`.

### AOG-005 - `glass note write` writes to templates/content instead of campaign workspace

Status: `done`

`resolve_note_write_path` returns `paths.content / rel`, so note writes can mutate authored templates/content rather than the active campaign workspace.

Impact: agents may update the wrong tree, and runtime campaign notes can be missing from the live campaign.

Likely direction: resolve note writes against the active campaign root, with template writes reserved for explicit operator/dev flows.

Resolution: `glass note write` now resolves writes under `campaigns/<id>/` and keeps player/DM role write boundaries there. Tests assert player journal writes land in the active campaign, not templates.

References: `src/cli/paths_resolve.py`, `src/cli/commands/note.py`.

### AOG-006 - Several advertised CLI commands are currently broken

Status: `done`

Known examples:

- `glass scene end` calls `load_state(get_paths())` without a campaign id.
- `glass quest beat` calls an undefined `_append_quest_beat`.
- `glass db migrate` calls an undefined `active_session_file`.

Impact: methodology instructions can send agents into commands that fail at runtime.

Likely direction: add focused CLI tests for each documented command path, then repair the command implementations.

Resolution: repaired `scene end`, `quest beat`, and `db migrate` failure paths, and added campaign-layout CLI coverage for arc/scene/quest/scene-end flows.

References: `src/cli/commands/scene.py`, `src/cli/commands/quest.py`, `src/cli/commands/db.py`.

### AOG-007 - Player processes receive raw DB and graph credentials

Status: `done`

The orchestrator preserves Postgres and FalkorDB credential environment variables into player subprocesses. CLI role checks do not prevent a player agent with shell access from bypassing `glass` and connecting directly.

Impact: DM-only or cross-player state boundaries are policy-level only once the agent can use shell/Python.

Likely direction: use role-scoped DB credentials, RLS, a local state proxy, or keep secrets out of player environments and route all mutations through a trusted service.

Resolution: the orchestrator now starts a localhost `glass` API, mints short-lived per-turn grants, and installs each grant into a per-player file read by `/usr/local/bin/glass`. Postgres and FalkorDB credentials stay in the operator/API process.

References: `src/orchestrator/runner.py`, `scripts/provision-agents.sh`.

### AOG-008 - Next-speaker queue is consumed before turn commit

Status: `done`

`prepare_turn` and `run_one_turn` pop `next_speakers` immediately. If the prepared/queued turn fails, or an operator runs `prepare-turn` only for inspection, the queued handoff is lost.

Impact: resume behavior and DM-directed handoffs can drift from the intended speaker order.

Likely direction: peek during preparation and consume only after successful commit, or store an in-flight queue item that can be retried safely.

Resolution: the orchestrator now peeks at `next_speakers` during turn preparation/invocation and consumes the queued entry only after `glass turn append` succeeds. A runner test covers prepare-only queue preservation.

References: `src/orchestrator/runner.py`.

### AOG-009 - Methodology/docs still reference obsolete runtime paths

Status: `done`

Docs and methodologies still mention `shared/methodologies`, `world-lore/`, `dm-world-lore/`, `sessions/shared`, and `.glass-cwd` projections, while the implementation uses campaign-root `methodologies/`, direct campaign cwd, and configured `lore.path`.

Impact: agents follow stale instructions and waste turns probing nonexistent paths.

Likely direction: align methodology language with the actual campaign workspace layout and the current context builder.

Resolution: active methodologies, context-builder text, and design notes now refer to campaign-root `methodologies/`, campaign-root turn files, `shared/lore/`, and the configured lore repo accessed through `glass lore search/import`.

References: `templates/methodologies/README.md`, `templates/methodologies/campaign-planning.md`, `docs/design/context-packages.md`, `docs/design/shared-vocabulary.md`.

### AOG-010 - Character creation can commit markdown without hard-state writes

Status: `done`

The character-creation methodology requires `glass character new` and inventory writes, but the orchestrator only validates that `out.md` has prose. The live Tev turn demonstrates that character creation can "succeed" with only markdown and no Postgres character.

Impact: later rolls fail because no canonical character exists.

Likely direction: add phase-specific done checks before accepting/advancing character creation: each player must have exactly one character row, required public files, and expected inventory rows or equivalent validated state.

Resolution: after the character-creation mode explicitly ends, bootstrap now validates one character row per player, 3-5 inventory entries per character, and required public intro/relationship files before advancing.

References: `templates/methodologies/character-creation.md`, `src/orchestrator/runner.py`, `src/orchestrator/main.py`.

### AOG-011 - Tests target an obsolete `content/sessions` layout

Status: `done`

The current test harness creates `content/sessions` and expects old state fields like `dice_events`. The live CLI now expects campaign workspaces under `campaigns/<id>`.

Impact: the test suite fails before exercising current behavior.

Likely direction: rebuild tests around the campaign workspace layout, Postgres-backed commands, and current `state.json` shape.

Resolution: replaced the obsolete `content/sessions` CLI tests with current campaign-root tests and added a runner test for next-speaker queue behavior.

References: `tests/test_cli.py`.

### AOG-012 - Public transcript should not be a flat-file communication API

Status: `done`

The future viewer UI needs stable ordered events and turn metadata. Parsing an append-only markdown transcript as the primary data surface is brittle and makes filtering, polling, and rendering harder than necessary.

Impact: the UI would have to scrape prose headers and inline event lines from a large flat file, and agents/context builders would keep treating markdown as the canonical corpus boundary.

Resolution: `glass turn append` now writes structured rows to Postgres first and only then refreshes `transcript.md` as a derived compatibility export. `glass turns find` reads the structured store, `glass turns feed --after-turn N` exposes a polling-friendly viewer feed, and the orchestrator context builder reads recent turns from structured storage before falling back to the export.

References: `migrations/006_runtime_state_and_turns.sql`, `src/cli/commands/turn.py`, `src/cli/commands/turns.py`, `src/orchestrator/store.py`, `src/webui/SPEC.md`.
