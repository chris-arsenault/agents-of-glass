# Architecture

The system's structural shape: components, data stores, agents, how they exchange state. For the deeper "why," see [`../principles/`](../principles/).

## Components At A Glance

```
       Orchestrator (Python)
         |
         | spawns claude -p ... per turn
         |
   +-----+-----+-----+-----+-----+
   |     |     |     |     |     |
  Mara  Tev  Sumi  Renno  Kit
  (DM)
   |     |     |     |     |
   +--+--+--+--+--+--+--+--+
      |
      | calls
      v
   glass CLI  (single tool surface)
      |
      +----> Markdown files  (prose: lore, notes, transcripts)
      +----> FalkorDB        (graph: entities + typed edges + embeddings)
      +----> Postgres        (hard stats: HP, inventory, dice events)
```

The orchestrator is dumb. The CLI is the only path to state. The agents have agency *within their turns*.

## Three Data Surfaces

### 1. Markdown — the readable surface

All prose lives in markdown, in three layers:

- **World bible** — `../the-glass-frontier-lore/player/`. Read-only at play time. The canonical world: cosmology, history, named entities that pre-exist the campaign. The DM additionally has read access to `../the-glass-frontier-lore/dm/` (themes, threads, loops, secret truths). The orchestrator surfaces relevant lore in each agent's CWD via symlinks.
- **Campaign lore** — `campaigns/<id>/shared/lore/`. Writable. The campaign-specific canonical layer that evolves scene by scene: NPCs the party has met, locations they've discovered, events they've caused, faction reputations they've earned. **Encyclopedia-shaped, not notes-shaped** — same frontmatter + prose + sections pattern as the world bible, FalkorDB-mirrored. Players draft entries into a pending area; the DM ratifies (canonize) or rejects via `glass note`. Ratified entries land here.
- **Player-facing context** — three levels: `campaigns/<id>/context.md`, `arcs/<arc>/context.md`, `arcs/<arc>/scenes/<scene>/context.md`. Each authored by the DM, projected into player CWDs as `campaign-context.md`, `arc-context.md`, `scene-context.md`. See [`game-start.md`](game-start.md) and [`context-packages.md`](context-packages.md).
- **Personal notes** — agent-private. Player journals (free-form, may have subdirectories) and the DM workspace (planning drafts, in-progress NPCs). **Journal-shaped, not encyclopedia-shaped.** For thinking; not the canonical record.

Plus per-scene transcripts (`arcs/<arc>/scenes/<scene>/transcript.md`) — the artifact (see [`../principles/transcripts-as-corpus.md`](../principles/transcripts-as-corpus.md)).

Markdown is human-diffable, version-controllable, and the natural medium for narrative content.

### 2. FalkorDB — the coherence layer

A graph database mirrors the markdown notes. Entities (NPCs, locales, factions, items, arcs, scenes, beats) are nodes; typed edges describe relationships (`LOCATED_IN`, `MET_AT`, `ADVANCES_BEAT`, `OCCURRED_IN`, etc.). Embeddings on entity sections support semantic search — "have I seen this kind of NPC before?"

We reuse the lore repo's pattern: Entity/Section unified node model, typed-edge taxonomy, no free text in the graph itself (prose stays in markdown).

The graph is **not** a separate truth. It's a structural mirror of what's in the markdown, kept in sync via the `glass` CLI's upsert path. The DM gates which player-proposed notes get ratified into the graph.

FalkorDB is on the LAN — same instance the lore repo points at. (Open question — see [`../research/the-glass-frontier-lore.md`](../research/the-glass-frontier-lore.md) — whether we share a database with the lore repo or namespace separately.)

### 3. Postgres — the hard-state and queryable-corpus surface

Anything that needs crisp ground-truth, plus the orchestrator-supplied metadata that makes the corpus queryable:

- Character sheets (attributes, skills, archetype, current momentum)
- Inventory (per character)
- HP and status conditions
- Monster stat blocks
- Dice events (every roll, with context)
- Mode transitions (when, why, with what budget)
- Session metadata
- **Per-turn metadata** (turn id, campaign, arc, scene, mode/scene-type, speaker, role, character, turn number, timestamp) — orchestrator-supplied, not agent-supplied. See [`context-packages.md`](context-packages.md).
- **Messages** (the `glass msg` bus — sender, recipient, type, body, read state). See [`messaging.md`](messaging.md).

The Postgres schema is small. Don't push narrative into it as "description" columns — narrative lives in markdown. The Postgres layer is for the things agents drift on (numbers, IDs) plus the structural metadata around the prose that makes "find me what Sumi said in the market scene" answerable without scraping text.

Postgres is on the LAN.

## The Orchestrator

A Python process. Its job is small:

1. Hold the campaign + scene state machine (which phase, which arc, which scene, which mode, which budgets, whose turn).
2. Build the per-turn ephemeral CWD and `TURN_START.md` for the next agent.
3. Spawn `claude -p --dangerously-skip-permissions` in that CWD. All tools available; the role-specific allowlist is enforced at the `glass` CLI level via env vars set by the orchestrator at spawn time.
4. Wait for the subprocess to exit.
5. Append the agent's prose to the transcript with the orchestrator-supplied header and inlined mechanical events from the audit log.
6. Update state. Decide next speaker. Loop.

The orchestrator does **not**:

- Write to the graph or Postgres directly (only via the `glass` CLI, same as the agents).
- Make narrative decisions.
- Override agent output.

### Resumability

The orchestrator is **resumable**, not one-shot. State lives in Postgres (campaign row, scene row, mode stack, current turn number, last-spoken agent), the markdown transcript, and the FalkorDB graph. If the process dies or is ctrl-C'd mid-scene, restarting picks up where it left off — the previous turn either committed or didn't (transactionally, via the `glass turn append` boundary), and the orchestrator advances from the last consistent state.

For v1, when an agent fails (timeout, claude error, malformed output), the orchestrator stops and waits for the operator. No automatic retries, no automatic recovery. The operator inspects, fixes, resumes — or clears state and starts over.

### Operator CLI (separate from `glass`)

`glass` is the in-play tool surface for agents and the orchestrator. The operator (the human running this) needs a different surface: create a campaign, list campaigns, tail a running scene, clear scene/arc/campaign state, restart from a known point. This is the `aog` CLI and is not exposed to agents.

For v1: foreground stdout monitoring is enough. The operator runs the orchestrator in the foreground, watches turns scroll by, ctrl-C's to interrupt. Real logging and a richer ops CLI are post-MVP.

### Audit log

Every `glass` call (including the orchestrator's own internal calls) writes to a per-scene audit log — JSON lines, `arcs/<arc>/scenes/<scene>/audit.jsonl`. This is the operational record (timestamps, command, args, return, errors) and is distinct from the transcript (the corpus). Useful for debugging, replay, and post-hoc analysis. The orchestrator inlines a subset of these (rolls, HP changes) into the transcript at the right turn boundary; the full audit lives in the JSONL.

This separation is deliberate. The orchestrator is straightforward to reason about; the agents are swappable; the CLI is the only state-mutation choke point.

## The `glass` CLI

A single binary (Python, distributed via the project's venv). All state mutations go through it. Both the orchestrator and the agents call it.

Surface (subject to refinement in [`turn-loop.md`](turn-loop.md), [`mechanics.md`](mechanics.md), [`messaging.md`](messaging.md)):

```
glass arc create <slug>               # DM only — scaffold an arc dir
glass arc current | list
glass scene create <slug> --type <mode>   # DM only — scaffold a scene dir
glass scene current | list | end
glass mode push <mode> | pop | current    # nested modes within a scene
glass roll <skill> <attribute> --risk <level> [--character <id>]
glass character new|get|set-hp|set-momentum|inventory-add|inventory-rm
glass note write <kind> <id> <file.md>
glass note propose <file.md>          # player → DM intake
glass note ratify <id>                # DM accepts proposal
glass entity upsert <file.md>         # markdown → graph
glass entity neighborhood <id> | similar <id>
glass thread current | beat <id>
glass turn append <markdown>          # orchestrator typically calls this
glass msg <type> <recipient> <body>   # see messaging.md
glass turns find ...
```

Permissions are per-subcommand, enforced by an environment variable the orchestrator sets when it spawns each agent (e.g. `GLASS_ROLE=player_tev`). The CLI checks the role and rejects calls outside the allowlist.

## The Agents

Five `claude -p` invocations, one per person at the table. Each is given:

- Their **role prompt** (who they are — see [`agents.md`](agents.md))
- Their **context window** (recent transcript, current mode framing, their own notes, relevant lore excerpts)
- Their **tool allowlist** (which `glass` subcommands they can call)

Agents return when they've produced a turn artifact. They can call tools as much as they want during the turn — look up lore, check their notes, roll dice, write a journal entry — but the turn ends when they emit their structured turn output.

See [`agents.md`](agents.md) for the people, [`turn-loop.md`](turn-loop.md) for the turn shape.

## Data Flow Per Turn

1. Orchestrator decides whose turn it is (mode-dependent — see [`modes.md`](modes.md)).
2. Orchestrator builds the agent's per-turn ephemeral working directory and writes `TURN_START.md` into it (see [`context-packages.md`](context-packages.md)). The CWD contains only the files the agent's role is allowed to see — process-level isolation, not policy.
3. Orchestrator spawns `claude -p "Read TURN_START.md and take your turn."` with CWD set to that ephemeral dir and the role-specific tool allowlist.
4. Agent runs its own tool loop. May call `glass roll`, `glass entity neighborhood`, `glass character set-hp`, `glass msg`, etc. — each call is logged to the audit trail.
5. Agent emits prose (their turn) and exits.
6. Orchestrator wraps the prose with a header (speaker, role, mode, scene, turn number, timestamp) and inlines mechanical event lines drawn from the audit trail (rolls, HP changes), then calls `glass turn append`. Orchestrator records the turn metadata in Postgres alongside the markdown.
7. Orchestrator tears down the ephemeral CWD and evaluates mode-end conditions (deferred — see [`scene-ending.md`](scene-ending.md)).
8. Loop.

Note: agents do not emit structured delta blocks. Whose turn is next, what mode is active, what the player intended — none of that is YAML the agent ships. The orchestrator already knows the speaker and mode from its own state; the DM reads the player's prose to understand intent. See [`turn-loop.md`](turn-loop.md) for the full prose-first principle, and [`../principles/codify-only-what-drifts.md`](../principles/codify-only-what-drifts.md) for the rule.

## Process Isolation

Each agent runs as a separate `claude -p` subprocess in a per-turn ephemeral working directory built by the orchestrator. The CWD contains only the files that role is allowed to see. Agents are *too good* at finding things they shouldn't have if those things are accessible from CWD; we enforce at the filesystem level, not by asking nicely.

For v1: ephemeral CWD with selective symlinks/bind-mounts. Easy to inspect, easy to reset between turns.

Possible upgrade: per-player Unix users with file-system group permissions. More durable against half-killed subprocesses leaving scaffolding around. Defer unless we observe leakage. See [`context-packages.md`](context-packages.md) for details.

## What Lives Where (Quick Reference)

| Concern | Store |
|---------|-------|
| Lore prose | Markdown (read-only from lore repo) |
| Scene transcript | Markdown (`campaigns/<id>/arcs/<arc>/scenes/<scene>/transcript.md`) |
| DM canonical NPCs | Markdown + FalkorDB |
| Player private journal | Markdown (per-agent dir) |
| Character sheet | Postgres + cached markdown summary |
| Current HP, momentum | Postgres |
| Inventory | Postgres |
| Dice events | Postgres (audit) + transcript (inline) |
| Beat advancement | FalkorDB (graph edges) + transcript |
| Mode transitions | Postgres + transcript |

## Configuration

A single `agents-of-glass.toml` at the repo root holds non-secret config: Postgres URL, FalkorDB URL, model selection, hard caps, debug flags, paths to lore-repo, templates dir, and campaigns dir.

Secrets (API keys, database passwords) are injected by the operator's secrets-management solution at the environment level — not stored in the TOML, not committed.

## Testing Strategy

For v1: **CLI-only tests.** We test `glass` subcommands against the real data stores (Postgres, FalkorDB) — they're cheap to spin up and the CLI is the contract. We do *not* write tests for the orchestrator loop or for agent behavior; LLM nondeterminism makes those tests fragile, and the corpus itself is our integration signal.

When the build hits a place where a test would protect future iteration, write one — at the CLI level. Don't write end-to-end orchestrator tests with mocked agents; the design isn't stable enough to make them durable, and the burn rate isn't low enough to make them cheap.

## Repo Layout (Anticipated)

```
agents-of-glass/
  README.md
  docs/
    principles/
    design/
    research/
  src/
    glass/                # the CLI
    orchestrator/         # the Python loop
    schema/               # graph + postgres schemas
  templates/              # authored input — copied into campaigns/<id>/ on creation
    dm/, players/, shared/, methodologies/
  campaigns/<id>/         # per-campaign live state — see game-start.md and context-packages.md
    state.json
    context.md            # player-facing campaign-level
    dm/, players/, shared/
    arcs/<arc>/
      context.md          # player-facing arc-level
      plan.md             # DM-only
      scenes/<scene>/
        context.md        # player-facing scene-level
        prep.md           # DM-only
        transcript.md
        audit.jsonl
  modes/                  # one md file per mode (scene type)
  pyproject.toml
```

The detailed campaign layout lives in [`game-start.md`](game-start.md) and [`context-packages.md`](context-packages.md). Final layout settles when the orchestrator and CLI exist.
