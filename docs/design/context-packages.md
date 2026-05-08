# Context Packages

What each agent has in its prompt vs what it can query, per role. The shape of the per-turn handoff.

For the codification rules behind this, see [`../principles/codify-only-what-drifts.md`](../principles/codify-only-what-drifts.md). For the message bus that supplements always-on context, see [`messaging.md`](messaging.md). For the vocabulary the agents share, see [`shared-vocabulary.md`](shared-vocabulary.md).

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

## Scene framing
See [scene-framing.md](./scene-framing.md). Current state: the patrol leader is up and angry; Karrith is exposed.

## Recent turns
[Last 6 turns](./transcript-recent.md) — full prose. [Earlier turns](./transcript-summary.md) — summarized;
pull detail with `glass turns find ...`.

## Messages waiting for you
2 unread. Read with `glass msg read --since-checkpoint`.

## Vocabulary
TOC at [vocabulary/index.md](./vocabulary/index.md).

## Your tools (allowlist)
- glass roll
- glass character set-hp / set-momentum / inventory-add (your character only)
- glass msg <type> <recipient> <body>
- glass note write (your journal)
- glass entity neighborhood / similar (read-only graph queries)
- glass turns find ... (query past turns)

When done, exit.
```

The DM's TURN_START has additional pointers: thread/beat states, intake of unratified player notes, the DM workspace, and a reminder of the **dual-purpose turn** (respond + plan ahead — see [`agents.md`](agents.md)).

## What's Always-On vs Queryable

### Always-on for every agent (in TURN_START as content or near-pointer)
- Their `persona.md` (who they are)
- Their `scratchpad.md` (current working notes — overwriteable)
- Current mode + scene framing
- Campaign framing
- Recent turns (last K, K depends on mode)
- Pointer to unread messages
- Pointer to vocabulary index
- Pointer to their `notes/index.md` (their personal encyclopedia)

### Always-on for players additionally
- Their `character.md` (cached markdown summary; canonical in Postgres)
- Their character-specific scene framing (positioning, prepared abilities they declared in prose)

### Always-on for the DM additionally
- Active thread states (what beats are open, what's been advanced)
- Intake (unratified player proposals)
- Pointer to DM workspace (for the planning half of the dual-purpose turn)

### Queryable by everyone
- **World bible** (read-only) — `../the-glass-frontier-lore/player/`. The pre-existing canonical world.
- **Campaign lore** (read-only for players, write-via-ratification) — `campaigns/<id>/shared/lore/`. The encyclopedia that's grown across this campaign. Players draft entries that become campaign lore once the DM ratifies.
- Quest log (`campaigns/<id>/shared/quest-log.md` — DM-writable, all-readable)
- Party knowledge (`campaigns/<id>/shared/party-knowledge.md` — party-writable, all-readable)
- Vocabulary detail files (`campaigns/<id>/shared/vocabulary/*.md`)
- Past turns from prior scenes (via `glass turns find ...`)
- Their own journal directory
- Entity graph (read-only via `glass entity ...`)

### Queryable by DM only
- DM canonical notes (NPCs, locales, etc.)
- DM secret notes
- **All player journals** (the DM can see what every player has been writing)
- Monster stat blocks
- Thread/loop authorial scaffolding from the lore repo's `dm/` directory
- DM workspace (planning, in-progress NPC drafts, future-scene seeds)

### Per-player private
- Their journal directory (free-form, journal-shaped, no schema, no size limit, can have subdirectories)
- Messages addressed specifically to them (other players cannot read)
- Their own lore drafts pending DM ratification (encyclopedia-shaped — once ratified, they move into campaign lore)

Note: a player's journal is *private from other players* but *visible to the DM*. Players who want to share something publicly use `glass msg party "..."` for short-form, or write a campaign-lore entry and propose it via `glass note` for canonical-record long-form.

### Three levels of player-facing context

Each prep level produces a player-facing `context.md` at its own directory. All three are **DM-owned** and read by every player on every turn:

- `campaigns/<id>/context.md` — campaign-level. Updates rarely. Projected as `campaign-context.md` in the player's CWD.
- `arcs/<arc>/context.md` — arc-level. Updates per scene or two as the arc evolves. Projected as `arc-context.md` (when an arc is active).
- `arcs/<arc>/scenes/<scene>/context.md` — scene-level. The "where are we right now" framing. Projected as `scene-context.md` (when a scene is active).

The DM authors each level using the relevant methodology — campaign-level during planning, arc-level during arc creation, scene-level during scene prep. Each has a corresponding DM-only working document (`dm/foundation.md`, `arcs/<arc>/plan.md`, `arcs/<arc>/scenes/<scene>/prep.md`) that holds the full picture; the player-facing `context.md` holds only what's been shown.

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
    vocabulary/                        # see shared-vocabulary.md
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
  dm/                                  # DM workspace mutates over campaign
    foundation.md                      # DM-only working framing
    notes/                             # NPCs, factions, creatures, artifacts, ships, locales, secrets, hooks, philosophy
  players/<player>/                    # journals, drafts, notes accumulate
  shared/                              # methodologies snapshot, lore, vocabulary, quest-log, party-knowledge
  arcs/<arc>/                          # one dir per arc, scaffolded via `glass arc create`
    context.md                         # PLAYER-FACING arc-level context
    plan.md                            # DM-only arc plan
    scenes/<scene>/                    # one dir per scene, scaffolded via `glass scene create`
      context.md                       # PLAYER-FACING scene-level context
      prep.md                          # DM-only scene prep
      transcript.md                    # the corpus
      audit.jsonl                      # operational audit log
```

**Note on the lore vs notes split:**

- The campaign's `shared/lore/` is **encyclopedia-shaped** — same frontmatter + prose + sections pattern as the world bible (`../the-glass-frontier-lore/`), FalkorDB-mirrored. Canonical, DM-ratified.
- Player `journal/` and DM `notes/`, `workspace/` are **journal-shaped** — free-form, private, for thinking. Not canonical, not graph-mirrored.

Players draft lore entries in their `drafts/` directory (encyclopedia-shaped), then call `glass note propose` to push to the DM's `intake/`. The DM ratifies (entry moves to the campaign's `shared/lore/` and gets graph-upserted) or rejects. Personal-thought scribbles stay in `journal/`.

The `inbox/` and `transcript-recent.md` etc. are orchestrator-maintained projections of canonical state (Postgres + graph + the canonical transcript). Agents read these flat files; they don't query the database directly (except via `glass`).

## Process Isolation

Each agent runs as a separate `claude -p` subprocess in a per-turn ephemeral working directory. The directory is built by the orchestrator with bind-mounts (or a per-turn copy/symlink fan-out, depending on what works) so the agent can only see the files in their permitted view.

For v1: ephemeral CWD with selective symlinks/bind-mounts. Light-weight, easy to inspect, easy to reset between turns.

Possible upgrade path: per-player Unix users with file-system group permissions. More durable against half-killed subprocesses leaving scaffolding around. Defer unless we observe leakage in v1 — but it's a real upgrade we may want.

The principle: **do not trust agents to honor "don't read X."** Agents are too good at finding things they shouldn't have. Enforce at the OS level, not via instructions in the prompt.

## Recent-Turns Window Policy

For v1: include the entire current scene plus the last 2 scenes' turns, with older scenes available via summary index plus on-demand `glass turns find` queries. Token budget is not the v1 concern; **context quality** is — too much old text drowns out the current scene; too little loses continuity.

The transcript-recent / transcript-summary split is orchestrator-maintained:

- **Recent turns** are full prose, included directly.
- **Older turns** are summarized in a way that preserves who-did-what-where but compresses dialog. Agents can always pull full older turns via `glass turns find --turn-id ...` if they need detail.

Summaries are auto-generated by the orchestrator (probably a small "summarizer" agent, scheduled when a scene closes). Not agent-emitted at turn time.

## Postgres Turn Metadata

Beyond raw markdown, the orchestrator records per-turn metadata in Postgres for queryability:

| Column | Purpose |
|--------|---------|
| `turn_id` | unique |
| `campaign_id` | scope |
| `arc_id` | which arc |
| `scene_id` | which scene |
| `scene_type` | town / combat / exploration / social / etc. |
| `speaker` | agent id |
| `role` | dm / player |
| `character_id` | the PC, if applicable |
| `turn_number` | ordering within scene |
| `ts` | wall clock |

This is **not** agent-provided metadata. The orchestrator knows all of these from its own state; it just records them so `glass turns find ...` can ask "what happened in scene X by player Y?" without scraping prose.

Mechanical events (rolls, HP changes, mode transitions) are joined to turns via roll_id / event_id. The text of the turn lives in the markdown transcript; the metadata lives in Postgres.

This is the queryability layer that lets the always-on context stay small. An agent who needs more can ask for it.

## Worked Example: Sumi's Turn

The orchestrator decides Sumi is up next during scene `keel-quarter-aftermath` in arc `reconnect-to-vantara`. It:

1. Builds `.glass-cwd/<scene-id>/sumi-tNNNN/` (ephemeral) with: `persona.md`, `character.md`, `scratchpad.md` (her own), `campaign-context.md` (from `campaigns/<id>/context.md`), `arc-context.md` (from `arcs/reconnect-to-vantara/context.md`), `scene-context.md` (from `arcs/reconnect-to-vantara/scenes/keel-quarter-aftermath/context.md`), `transcript-recent.md` (built fresh from last 6 turns of this scene plus tail of prior scene), `inbox/` (her unread messages), `vocabulary/index.md` (symlinked), `notes/` (her own).
2. Generates `TURN_START.md` in that CWD with pointers to all of the above.
3. Spawns `claude -p --dangerously-skip-permissions "Read TURN_START.md and take your turn."` with CWD set to the ephemeral dir and the Sumi-role tool allowlist (via env var).
4. Waits for the subprocess to exit.
5. Reads the prose Sumi wrote to `TURN.md`; the audit log of any `glass` calls she made; appends to `arcs/reconnect-to-vantara/scenes/keel-quarter-aftermath/transcript.md` with header.
6. Tears down the ephemeral CWD.
7. Picks the next agent.

## What This Doc Does Not Cover

- The actual vocabulary entries (those are in `campaigns/<id>/shared/vocabulary/`).
- How modes parameterize the always-on set (covered in [`modes.md`](modes.md)).
- The DM's dual-purpose turn — what they do besides responding (covered in [`agents.md`](agents.md)).
- The message bus details (covered in [`messaging.md`](messaging.md)).
