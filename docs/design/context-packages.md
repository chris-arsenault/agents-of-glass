# Context Packages

What each agent has in its prompt vs what it can query, per role. The shape of the per-turn handoff.

For the codification rules behind this, see [`../principles/codify-only-what-drifts.md`](../principles/codify-only-what-drifts.md). For the message bus that supplements always-on context, see [`messaging.md`](messaging.md). For the runtime instruction surfaces, see [`instruction-surface.md`](instruction-surface.md).
For actual-play anti-staleness nudges, see [`creative-influences.md`](creative-influences.md).

## TURN_START.md — the single entry point

The orchestrator builds a `TURN_START.md` file in the agent's working directory before each invocation. The agent's prompt is essentially:

> Read `TURN_START.md` and take your turn.

…spawned as `claude -p --dangerously-skip-permissions` with all tools available. Role-specific tool restriction is enforced at the `glass` CLI level (via env vars set by the orchestrator), not by Claude Code's permission system.

The TURN_START is dynamic — regenerated every turn — and contains pointers (links and headlines), not the full content of every relevant file. It pulls the agent into the right sub-files via curiosity instead of dumping everything in the prompt.

A typical player TURN_START:

```markdown
# Turn 24 — Tev

You are Tev. See [persona.md](./persona.md) (who you are), [character.md](./character.md) (your PC), and [scratchpad.md](./scratchpad.md) (your current working notes).

It's your turn. Mode: **combat** | Scene: **ringglass-market-chase**.

## Table
See [table/index.md](./table/index.md) for the at-a-glance state and
[table/scene.md](./table/scene.md) for the scene kickoff. Current state: the
patrol leader is up and angry; Karrith is exposed.

## Recent turns
Last few turns are embedded. Pull older detail with `glass search text ...`,
`glass search semantic ...`, or `glass turns find ...`.

## Messages waiting for you
2 unread. Read with `glass msg read --since-checkpoint`.

## Instruction Surface
Use `instructions/` for tool/file behavior, `methodologies/` for required
turn sequence, `srd/` for public rules, and `how-to/` for optional examples.

## Your tools (allowlist)
- glass roll
- glass character set-hp / set-momentum / inventory-add (your character only)
- glass msg <type> <recipient> <body>
- glass note write (your journal)
- glass entity neighborhood / similar (read-only graph queries)
- glass turns find / feed ... (query past turns)

When done, exit.
```

The DM's TURN_START has additional pointers: thread/beat states, intake of unratified player notes, the DM workspace, and a reminder of the **dual-purpose turn** (respond + plan ahead — see [`agents.md`](agents.md)).

## What's Always-On vs Queryable

### Always-on for every agent (in TURN_START as content or near-pointer)
- Their `persona.md` (who they are)
- Their `scratchpad.md` (current working notes — overwriteable)
- Current mode + scene framing
- Current public table: `table/index.md`, `table/scene.md`, and `table/handouts/`
- Campaign framing
- Campaign / arc / scene summaries as pointers, not embedded compression
- Recent turns (last K, K depends on mode)
- Actual-play creative influence: one verse phrase plus current persisted tarot
  draw. This is omitted during bootstrap/prep modes.
- Pointer to unread messages
- Pointer to the relevant instruction surface roots
- Pointer to their `notes/index.md` (their personal encyclopedia)

### Always-on for players additionally
- Their `character.md` (cached markdown summary; canonical in Postgres)
- Their character-specific scene framing (positioning, prepared abilities they declared in prose)

### Always-on for the DM additionally
- Active thread states (what beats are open, what's been advanced)
- Intake (unratified player proposals)
- Pointer to DM workspace (for the planning half of the dual-purpose turn)

### Queryable by everyone
- **Campaign lore** — `campaigns/<id>/shared/lore/`. The curated subset of world canon that matters to *this* campaign. Players see this. Read-only for players (write-via-ratification). The DM seeds this during planning (8-15 entries, imported from the world bible via `glass lore import`) and adds more on demand during play.
- Quest log (`campaigns/<id>/shared/quest-log.md` — DM-writable, all-readable)
- Public durable clocks (`campaigns/<id>/shared/clocks.md` and arc-local
  `clocks.md` projections — Postgres is canonical)
- Party knowledge (`campaigns/<id>/shared/party-knowledge.md` — party-writable, all-readable)
- Public rules and examples (`campaigns/<id>/srd/`,
  `campaigns/<id>/how-to/`)
- Past turns from prior scenes (via `glass turns find ...`, including `--text`)
- Current and historical tarot influences (via `glass tarot current` and
  `glass tarot list`)
- Indexed prose search (`glass search text ...` and `glass search semantic ...`;
  semantic currently falls back to the Postgres text index until embeddings are
  populated)
- Their own journal directory
- Entity graph (`glass entity neighborhood`, `relations`, `between`, `edges`,
  `stance`, `find`, `similar`; players can propose edges with
  `glass entity claim`)

### Queryable by DM only
- **World bible** — `../the-glass-frontier-lore/player/` and `../the-glass-frontier-lore/dm/`. The full canon. The DM consults it as reference at any time. **Players never see it directly.** Bulk-copying it would poison every agent's context. See [`/templates/methodologies/campaign-planning.md`](../../templates/methodologies/campaign-planning.md#curate-dont-copy) for the curation principle.

### Queryable by DM only
- DM canonical notes (NPCs, locales, etc.)
- DM secret notes
- **All player journals** (the DM can see what every player has been writing)
- DM creature/opposition notes
- Thread/loop authorial scaffolding from the lore repo's `dm/` directory
- DM workspace (planning, in-progress NPC drafts, future-scene seeds)

### Per-player private
- Their journal directory (free-form, journal-shaped, no schema, no size limit, can have subdirectories)
- Messages addressed specifically to them (other players cannot read)
- Their own lore drafts pending DM ratification (encyclopedia-shaped — once ratified, they move into campaign lore)

Note: a player's journal is *private from other players* but *visible to the DM*. Players who want to share something publicly use `glass msg party "..."` for short-form, or write a campaign-lore entry and propose it via `glass note` for canonical-record long-form.

### Three levels of player-facing context

Each prep level produces a player-facing `context.md` and a running
`summary.md` at its own directory. Context is framing: what the players can see
or know right now. Summary is continuity compression: what remains true after
play has moved on. All summary files are authored markdown; they are not
generated into TURN_START.

- `campaigns/<id>/context.md` / `summary.md` — campaign-level. Updates rarely.
- `arcs/<arc>/context.md` / `summary.md` — arc/act-level. Updates per scene or two as the arc evolves.
- `arcs/<arc>/scenes/<scene>/context.md` / `summary.md` — scene-level. The scene summary is finalized by `glass scene end --summary`.

The DM authors each level using the relevant methodology — campaign-level during planning, arc-level during arc creation, scene-level during scene prep. Each has a corresponding DM-only working document (`dm/foundation.md`, `arcs/<arc>/plan.md`, `arcs/<arc>/scenes/<scene>/prep.md`) that holds the full picture; the player-facing `context.md` holds only what's been shown.

The live `table/` is separate from those context documents. It is the
short-term public board for the current scene: `index.md` for at-a-glance
state, `scene.md` for the kickoff description, `handouts/` for in-game
handouts, and freeform table-root markdown files for whatever visible immediate
reference would prevent repeated clarification turns.

Format and update cadence are intentionally not pre-specified beyond the methodology guidance — see [`/tracking-immediate-decisions.md`](../../tracking-immediate-decisions.md). We codify further after first sessions show what's useful.

## File Layout

A working sketch of the per-campaign root the orchestrator manages:

Two layers — **authored templates** and **runtime live**. The orchestrator copies `templates/` into the campaign's live root at campaign creation; the live root is what mutates during play.

```
templates/                             # authored, stable input
  shared/
    campaign-framing.md                # starter
    quest-log.md
    party-knowledge.md
    lore/                              # usually empty in templates
  instructions/                        # executing-agent tool/file behavior
  methodologies/                       # executing-agent workflows
  srd/                                 # public game rules for players/DMs
  how-to/                              # optional table examples and craft guidance
  dm/
    persona.md                         # who Mara is — voice, tastes, what she cuts
    scratchpad.md                      # starter current-notes file
    notes/index.md                     # encyclopedia how-to-use
    journal/  workspace/  secret/  intake/   # starter dirs
  players/<player>/
    persona.md                         # who they are at the table
    character.md                       # starter sheet (filled during character creation)
    scratchpad.md
    notes/index.md
    journal/  drafts/  inbox/

campaigns/<id>/                        # per-campaign live root, copied from templates/
  state.json                           # campaign phase + active arc/scene
  context.md                           # PLAYER-FACING campaign-level context
  summary.md                           # running campaign continuity summary
  dm/                                  # DM workspace mutates over campaign
    foundation.md                      # DM-only working framing
    notes/                             # NPCs, factions, creatures, artifacts, ships, locales, secrets, hooks, philosophy
  players/<player>/                    # journals, drafts, notes accumulate
  instructions/                        # frozen snapshot of templates/instructions/
  methodologies/                       # frozen snapshot of templates/methodologies/
  srd/                                 # frozen snapshot of templates/srd/
  how-to/                              # frozen snapshot of templates/how-to/
  shared/                              # lore, quest-log, party-knowledge, clock projection
  arcs/<arc>/                          # one dir per arc, scaffolded via `glass arc create`
    context.md                         # PLAYER-FACING arc-level context
    summary.md                         # running arc/act continuity summary
    clocks.md                          # public durable-clock projection for this arc
    plan.md                            # DM-only arc plan
    scenes/<scene>/                    # one dir per scene, scaffolded via `glass scene create`
      context.md                       # PLAYER-FACING scene-level context
      summary.md                       # scene summary, finalized at scene end
      prep.md                          # DM-only scene prep
      transcript.md                    # scene-level derived turn export/cache
      audit.jsonl                      # operational audit log
```

**Note on the lore vs notes split:**

- The campaign's `shared/lore/` is **encyclopedia-shaped** — same frontmatter + prose + sections pattern as the world bible (`../the-glass-frontier-lore/`), FalkorDB-mirrored. Canonical, DM-ratified.
- Player `journal/` and DM `notes/`, `workspace/` are **journal-shaped** — free-form, private, for thinking. Not canonical, not graph-mirrored.

Players draft lore entries in their `drafts/` directory (encyclopedia-shaped), then call `glass note propose` to push to the DM's `intake/`. The DM ratifies (entry moves to the campaign's `shared/lore/` and gets graph-upserted) or rejects. Personal-thought scribbles stay in `journal/`.

The recent-turn excerpt in `TURN_START.md` is an orchestrator-maintained
projection of canonical state (Postgres + graph + structured turns). Agents
read this excerpt and can query deeper history through `glass`; they don't
connect to the database directly. Old-context recall should use `glass search`
or `glass turns find`, not another actor transition just to repeat recorded
information.

## Process Isolation

Each agent runs as a separate `claude -p` subprocess **directly inside the campaign workspace** (`cwd = campaigns/<id>/`). No per-turn ephemeral CWD with file projections. Per-turn artifacts (TURN_START.md, TURN.md) live under that agent's campaign directory: `dm/turns/<NNNN>/` for the DM and `players/<id>/turns/<NNNN>/` for players.

Filesystem isolation between agents is enforced by Unix users + group-based chmod. See [`architecture.md`](architecture.md#process-isolation) for the full setup. Quick summary:

- DM = the operator user (`dev`); full access.
- Players = dedicated users (`aog-tev`, `aog-sumi`, `aog-renno`, `aog-kit`); each runs via `sudo -u`.
- Shared content owned by `dev:aog-agents` mode `2750/0640` — all agents read, only the operator writes.
- Player private (`journal`, `drafts`, `notes`, `inbox`, `scratchpad`, `persona`): owned by the player user + their primary group (which includes `dev` so the DM can read), mode `2750/0640`. Other players cannot see.
- DM-only (`dm/foundation.md`, `dm/secret/`, etc.): `dev:dev` mode `0700/0600`. Players cannot see.

Operator setup is one command: `sudo bash scripts/provision-agents.sh`. Without it, the orchestrator falls through to running all agents as the operator (no isolation; documented as the dev/CI path).

The principle: **do not trust agents to honor "don't read X."** Agents are too good at finding things they shouldn't have. Enforce at the OS level, not via instructions in the prompt.

## Streaming Output

The orchestrator runs in the foreground. When it spawns each agent invocation, it streams the agent's stdout (and stderr) line-by-line to the operator's terminal, prefixed with the agent id (e.g. `[mara]`, `[tev]`). Full captures land beside the agent's TURN files for post-hoc inspection.

This is the operator's primary debugging tool during play — you can see the agent reading files, calling `glass` commands, doing web searches, and writing files in real time. The default per-turn timeout is 60 minutes (`claude.turn_timeout_seconds = 3600`), bumped from 5 minutes after the first inspection runs showed real DM work needs more breathing room.

## Recent-Turns Window Policy

For v1: include the entire current scene plus the last 2 scenes' turns, with older scenes available via summary index plus on-demand `glass turns find` queries. Token budget is not the v1 concern; **context quality** is — too much old text drowns out the current scene; too little loses continuity.

The recent/context split is orchestrator-maintained:

- **Recent turns** are full prose, included directly.
- **Older turns** are available through `glass turns find`, `glass search text`,
  and `glass search semantic`. Campaign/arc/scene `summary.md` files are
  authored continuity compression, not generated into TURN_START.

Embeddings are a search-index concern, not a prompt-dump concern. The goal is
bounded retrieval, not loading the whole campaign into each cold agent start.

## Postgres Turn Metadata

Beyond raw markdown, the orchestrator records per-turn metadata in Postgres for queryability:

| Column | Purpose |
|--------|---------|
| `turn_id` | unique |
| `campaign_id` | scope |
| `arc_id` | which arc |
| `scene_id` | which scene |
| `scene_type` | protocol/toolkit label, e.g. scene-play / action / travel / combat / custom |
| `speaker` | agent id |
| `role` | dm / player |
| `character_id` | the PC, if applicable |
| `turn_number` | ordering within scene |
| `ts` | wall clock |

This is **not** agent-provided metadata. The orchestrator knows all of these from its own state; it just records them so `glass turns find ...` can ask "what happened in scene X by player Y?" without scraping prose.

Mechanical events (rolls, HP changes, mode transitions) are joined to turns via
event/roll ids. The final public prose of the turn lives in Postgres
`turns.prose`; markdown transcripts are generated exports for readability.

This is the queryability layer that lets the always-on context stay small. An agent who needs more can ask for it.

## Worked Example: Sumi's Turn

The orchestrator decides Sumi is up next during scene `keel-quarter-aftermath` in arc `reconnect-to-vantara`. It:

1. Generates `players/sumi/turns/<NNNN>/TURN_START.md` with pointers to her readable campaign files: `persona.md`, `character.md`, `scratchpad.md`, campaign context, arc context, scene context, recent transcript, messages, instruction surfaces, and notes.
2. Spawns `claude -p --dangerously-skip-permissions "Read <absolute TURN_START path> and take your turn."` with CWD set to `campaigns/<id>/` and the Sumi role grant installed for `glass`.
3. Waits for the subprocess to exit.
4. Reads the prose Sumi wrote to `players/sumi/turns/<NNNN>/TURN.md`; the audit log of any `glass` calls she made; appends to the campaign transcript with a header.
5. Picks the next agent.

## What This Doc Does Not Cover

- The actual SRD, instruction, how-to, and lore prose entries.
- How modes parameterize the always-on set (covered in [`modes.md`](modes.md)).
- The DM's dual-purpose turn — what they do besides responding (covered in [`agents.md`](agents.md)).
- The message bus details (covered in [`messaging.md`](messaging.md)).
