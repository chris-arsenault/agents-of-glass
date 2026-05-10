# Architecture

The system's structural shape: components, data stores, agents, how they exchange state. For the deeper "why," see [`../principles/`](../principles/). The authoritative store boundaries are in [`persistence.md`](persistence.md).

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
      +----> Markdown files  (prose: lore, notes, derived exports)
      +----> FalkorDB        (graph: entities + typed edges)
      +----> Postgres        (runtime state, public turns, hard stats, search)
```

The orchestrator is dumb. The CLI is the only path to state. The agents have agency *within their turns*.

## Three Data Surfaces

### 1. Markdown — the readable surface

All prose lives in markdown, in three layers:

- **World bible** — `../the-glass-frontier-lore/`. Read-only. The full pre-existing canon. **DM-only** — players never see it directly, and it is *not* bulk-copied into the campaign (that would poison every agent's context with detail that doesn't matter to *this* campaign). The DM consults it as reference, and explicitly imports relevant entries into the campaign via `glass lore import`. See [`/templates/methodologies/campaign-planning.md`](../../templates/methodologies/campaign-planning.md#curate-dont-copy).
- **Campaign lore** — `campaigns/<id>/shared/lore/`. Writable. The curated subset of world-bible entries (imported during campaign planning, 8-15 to start; more on demand during play) plus campaign-emergent entries: NPCs the party has met, locations they've discovered, events they've caused, faction reputations they've earned. **Encyclopedia-shaped, not notes-shaped** — same frontmatter + prose + sections pattern as the world bible, FalkorDB-mirrored. Players see this. Players also draft new entries into their `drafts/`; the DM ratifies (canonize) or rejects via `glass note`. Ratified entries land here.
- **Player-facing context** — three levels: `campaigns/<id>/context.md`, `arcs/<arc>/context.md`, `arcs/<arc>/scenes/<scene>/context.md`. Each authored by the DM, projected into player CWDs as `campaign-context.md`, `arc-context.md`, `scene-context.md`. See [`game-start.md`](game-start.md) and [`context-packages.md`](context-packages.md).
- **Instruction surfaces** — `instructions/`, `methodologies/`, `srd/`,
  and `how-to/`. These are copied from templates into each campaign so runtime
  agents have local binding tool instructions, workflows, public rules, and
  optional examples. See [`instruction-surface.md`](instruction-surface.md).
- **Public table** — `campaigns/<id>/table/`. The immediate visible table
  state for the current scene: `index.md`, `scene.md`, `handouts/`, plus any
  freeform table-root markdown files the DM creates to avoid repeated
  clarification turns. Reset on scene create, archived on scene end. See
  [`table.md`](table.md).
- **Personal notes** — agent-private. Player journals (free-form, may have subdirectories) and the DM workspace (planning drafts, in-progress NPCs). **Journal-shaped, not encyclopedia-shaped.** For thinking; not the canonical record.

Plus derived transcript exports for human review and git history. The public turn corpus itself is structured Postgres rows (see [`../principles/transcripts-as-corpus.md`](../principles/transcripts-as-corpus.md)).

Markdown is human-diffable, version-controllable, and the natural medium for narrative content.

### 2. FalkorDB — the coherence layer

A graph database mirrors the markdown notes. Entities (NPCs, locales, factions, items, arcs, scenes, beats) are nodes; typed edges describe relationships (`LOCATED_IN`, `MET_AT`, `ADVANCES_BEAT`, `OCCURRED_IN`, etc.). The graph answers coherence questions like "what relationships does the duke have?" or "who is at war right now?" General prose recall goes through the Postgres search index.

We reuse the lore repo's pattern: Entity/Section unified node model, typed-edge taxonomy, no free text in the graph itself (prose stays in markdown).

The graph is **not** a separate truth. It's a structural mirror of what's in the markdown, kept in sync via the `glass` CLI's upsert path. The DM gates which player-proposed notes get ratified into the graph.

FalkorDB is on the LAN — same instance the lore repo points at. (Open question — see [`../research/the-glass-frontier-lore.md`](../research/the-glass-frontier-lore.md) — whether we share a database with the lore repo or namespace separately.)

### 3. Postgres — the hard-state and queryable-corpus surface

Anything that needs crisp ground-truth, plus the orchestrator-supplied metadata that makes the corpus queryable:

- Character sheets (attributes, skills, archetype, current momentum)
- Inventory (per character)
- HP and status conditions
- Character consequences (lasting injuries, capture, obligations, other persistent effects)
- Durable clocks (campaign / arc / thread / faction / NPC pressure)
- Dice events (every roll, with context)
- Mode/runtime state (mode stack, speaker queue, turn counter, closing countdown)
- Campaign runtime metadata
- **Per-turn metadata** (turn id, campaign, arc, scene, mode/scene-type, speaker, role, character, turn number, timestamp) — orchestrator-supplied, not agent-supplied. See [`context-packages.md`](context-packages.md).
- **Turn prose** split from metadata in structured `turns` rows. `transcript.md` is a derived markdown export/cache, not the canonical communication surface.
- **Messages** (the `glass msg` bus — sender, recipient, type, body, read state). See [`messaging.md`](messaging.md).
- **Tarot influences** for actual-play creative nudges. See
  [`creative-influences.md`](creative-influences.md).

The Postgres schema is small. Don't push lore/notes into it as "description" columns — durable authored world prose lives in markdown. Turn prose is different: it is the public corpus and viewer feed, so it is stored in Postgres with structured metadata and also exported to markdown for git/human inspection.

Postgres is on the LAN.

## The Orchestrator

A Python process. Its job is small:

1. Hold the campaign + scene state machine (which phase, which arc, which scene, which mode, which budgets, whose turn).
2. Build the next agent's per-turn `in.md` under `dm/turns/` or `players/<id>/turns/`, then project the actor-visible campaign files into `.glass-cwd/`.
3. Spawn `claude -p --dangerously-skip-permissions` in the projection. All tools are available; the role-specific state grant is enforced by the local `glass` API/CLI boundary.
4. Wait for the subprocess to exit.
5. Commit the agent's prose through `glass turn append`, which inserts a structured `turns` row and writes a derived markdown transcript export.
6. Update Postgres-backed runtime state. Decide next speaker. Loop.

The orchestrator does **not**:

- Write to the graph or Postgres directly (only via the `glass` CLI, same as the agents).
- Make narrative decisions.
- Override agent output.

### Resumability

The orchestrator is **resumable**, not one-shot. Runtime state lives in Postgres (campaign row, mode stack, current turn number, next-speaker queue, last-spoken agent), the structured turn corpus lives in Postgres, and the FalkorDB graph mirrors canonical lore. If the process dies or is ctrl-C'd mid-scene, restarting picks up where it left off — the previous turn either committed or didn't via the `glass turn append` boundary, and the orchestrator advances from the last consistent state.

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
glass arc activate <slug>             # DM only — set active arc
glass arc current | list
glass scene create <slug> --type <label>  # DM only — scaffold a scene dir
glass scene current | list | end
glass scene tracker set|tick|list         # DM clocks/progress trackers
glass scene pressure                      # roll-mediated reduction of scene targets
glass clock set|tick|list|show|resolve    # durable cross-scene clocks
glass table current|show|write|append|snapshot
glass mode push <mode> | pop | current    # nested modes within a scene
glass turn initiative                     # DM only — roll/persist action-scene order
glass turn handoff <agent>                # one-off next-speaker override
glass roll <skill> <attribute> --risk <level> [--character <id>]
glass character new|get|set-hp|set-momentum|inventory-add|inventory-rm
glass character consequence-add|consequence-list|consequence-resolve
glass note write <kind> <id> <file.md>
glass note propose <file.md>          # player → DM intake
glass note ratify <id>                # DM accepts proposal
glass entity upsert <file.md>         # markdown → graph
glass entity neighborhood|relations|between|edges|stance|find|similar
glass entity claim <src> <REL> <dst>  # propose relationship, DM ratifies
glass search text|semantic <query>
glass tarot current|list|draw
glass thread current | beat <id>
glass turn append <markdown>          # orchestrator typically calls this
glass msg <type> <recipient> <body>   # see messaging.md
glass turns find [--text ...]
glass summary show|write|append
```

Permissions are per-subcommand, enforced by an environment variable the orchestrator sets when it spawns each agent (e.g. `GLASS_ROLE=player_tev`). The CLI checks the role and rejects calls outside the allowlist.

## The Agents

Five `claude -p` invocations, one per person at the table. Each is given:

- Their **role prompt** (who they are — see [`agents.md`](agents.md))
- Their **context window** (recent transcript, current mode framing, their own notes, relevant lore excerpts)
- Their **tool allowlist** (which `glass` subcommands they can call)

Agents return when they've produced a turn artifact. They can call tools as much as they want during the turn — look up lore, check their notes, roll dice, write a journal entry — but the turn ends when they emit their structured turn output.

See [`agents.md`](agents.md) for the people, [`turn-loop.md`](turn-loop.md) for the turn shape.

Because each invocation starts cold, actor transitions are a major cost. The
system deliberately keeps resolution inside the current actor's turn when that
actor has authority to resolve it. This is why the DM rolls DM-side PC checks
directly instead of handing to a player just to request dice. See
[`../principles/minimize-actor-transitions.md`](../principles/minimize-actor-transitions.md).

## Data Flow Per Turn

1. Orchestrator decides whose turn it is (mode-dependent — see [`modes.md`](modes.md)).
2. Orchestrator writes the agent's per-turn `in.md` into that agent's canonical campaign turn directory, then builds a read-only projected workspace containing only files that actor may see (same relative paths as the campaign root).
3. Orchestrator spawns `claude -p "Read <turn-start path> and take your turn."` with CWD set to the projection and a role-scoped `glass` grant.
4. Agent runs its own tool loop. May call `glass roll`, `glass entity neighborhood`, `glass character set-hp`, `glass msg`, etc. — each call is logged to the audit trail.
5. Agent emits prose (their turn) and exits.
6. Orchestrator wraps the prose with a header (speaker, role, mode, scene, turn number, timestamp) and inlines mechanical event lines drawn from pending events, then calls `glass turn append`. The CLI writes the structured turn row to Postgres and refreshes the markdown transcript export.
7. Orchestrator evaluates mode-end conditions (deferred — see [`scene-ending.md`](scene-ending.md)); per-turn files remain available for debugging.
8. Loop.

Note: agents do not emit structured delta blocks. Whose turn is next, what mode is active, what the player intended — none of that is YAML the agent ships. The orchestrator already knows the speaker and mode from its own state; the DM reads the player's prose to understand intent. See [`turn-loop.md`](turn-loop.md) for the full prose-first principle, and [`../principles/codify-only-what-drifts.md`](../principles/codify-only-what-drifts.md) for the rule.

## Process Isolation

Each agent runs as a separate `claude -p` subprocess inside a fresh per-turn
projection (`cwd = .glass-cwd/<campaign>/<turn>-<agent>/`). The projection is
campaign-shaped: paths such as `table/scene.md`,
`players/tev/public/intro.md`, and `shared/lore/` keep the same relative
location they have in `campaigns/<id>/`, but only files visible to that actor
are copied in.

**The model:**

- The DM runs as the current operator user (`dev`) — full access to the campaign workspace.
- Each player agent has a dedicated Unix user: `aog-tev`, `aog-sumi`, `aog-renno`, `aog-kit`.
- A shared group `aog-agents` contains all agents. Each player has their own primary group (`aog-tev`, etc.) that includes `dev` so the DM can read player private content via group membership.
- Canonical campaign workspace files retain restrictive ownership/mode bits as a backstop. DM-only files: `dev:dev` mode `0700/0600`. Shared content: `dev:aog-agents` mode `2750/0640`. Per-player private: `aog-<player>:aog-<player>` mode `2750/0640` (player rw, dev r via group, others none).
- Per-turn artifacts live under the spawning agent's canonical campaign directory (`dm/turns/<NNNN>/` or `players/<id>/turns/<NNNN>/`) and are also present at the same relative path in the projection for the subprocess.
- Projected files are read-only except `scratch/` and the current projected turn dir. Persistent mutations go through `glass`, whose local API uses the projection as cwd for `--from scratch/...` inputs but writes to the canonical campaign root.
- Player invocations spawn via `sudo -u aog-<player>` (NOPASSWD per a sudoers entry installed at provisioning time).

**Operator setup (run once):**

```
sudo bash scripts/provision-agents.sh
```

This creates the Unix users + groups, adds the operator (`SUDO_USER`) to all relevant groups, installs `/usr/local/bin/aog-permset` (the privileged helper that the orchestrator calls via sudo to chown/chmod new campaign workspaces), and writes a sudoers rule at `/etc/sudoers.d/agents-of-glass`.

**Graceful fallback:** if provisioning hasn't been run, the orchestrator detects this (`permissions.has_provisioned_users()`) and falls through silently — no chowns happen, all agents run as the operator. The projection still limits the ordinary workspace view, but it is not a hard security boundary without Unix users.

## What Lives Where (Quick Reference)

| Concern | Store |
|---------|-------|
| Lore prose | Markdown (read-only from lore repo) |
| Public turn corpus | Postgres `turns` table + campaign/scene markdown exports |
| Search index | Postgres `search_chunks` |
| Event log | Postgres `events` + turn event summaries |
| DM canonical NPCs | Markdown + FalkorDB |
| Player private journal | Markdown (per-agent dir) |
| Character sheet | Postgres + cached markdown summary |
| Current HP, momentum | Postgres |
| Inventory | Postgres |
| Dice events | Postgres (audit) + turn event summaries |
| Tarot influences | Postgres `tarot_influences` |
| Beat advancement | FalkorDB (graph edges) + turn event summaries |
| Mode transitions | Postgres runtime state + event summaries |
| Scene trackers / initiative | Postgres when configured + state export fallback |

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
    dm/, players/, shared/, instructions/, methodologies/, srd/, how-to/
  campaigns/<id>/         # per-campaign live state — see game-start.md and context-packages.md
    state.json
    context.md            # player-facing campaign-level
    table/                # public short-term scene state
    dm/, players/, shared/, instructions/, methodologies/, srd/, how-to/
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
