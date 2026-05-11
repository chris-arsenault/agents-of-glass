# Context Packages

What each agent has in its prompt vs what it can query, per role. The shape of the per-turn handoff.

For the codification rules behind this, see [`../principles/codify-only-what-drifts.md`](../principles/codify-only-what-drifts.md). For the message bus that supplements always-on context, see [`messaging.md`](messaging.md). For the runtime instruction surfaces, see [`instruction-surface.md`](instruction-surface.md).
For actual-play anti-staleness nudges, see [`creative-influences.md`](creative-influences.md).

## TURN_START.md — the single entry point

The orchestrator builds a per-turn `TURN_START.md` file in the agent's
canonical turn directory and copies it into the projected workspace before each
invocation. The agent's prompt is essentially:

> Read `TURN_START.md` and take your turn.

…spawned as `claude -p --dangerously-skip-permissions` with all tools
available, inside a per-turn projection of the campaign workspace.
Role-specific mutation authority is enforced at the `glass` CLI/API boundary,
not by Claude Code's permission system.

The TURN_START is dynamic — regenerated every turn — and contains pointers
(links and headlines), not the full content of every relevant file. It also
selects exactly one active methodology for the actor's role and turn type.
Agents do not choose between scene-play, action, transition, rapid-response, or
housekeeping methodologies themselves.

A typical player TURN_START:

```markdown
# Turn 24 — Tev

You are Tev, a player in a Glass Frontier TTRPG session. Act as this player at
the table, using the personality, voice, tastes, and habits in
`players/tev/persona.md`. You are playing the character summarized in
`players/tev/public/character.md`. Make choices as the player, and when you
speak or act in fiction, embody only what the character knows and can do.

It's your turn. Mode: **combat** | Scene: **ringglass-market-chase**.

## Table
See [table/index.md](./table/index.md) for the at-a-glance state and
[table/scene.md](./table/scene.md) for the scene kickoff. Current state: the
patrol leader is up and angry; Karrith is exposed.

## Scene Summary
Compact scene continuity is embedded from `arcs/<arc>/scenes/<scene>/summary.md`.
Per-turn continuity comes from `glass turn end --summary`; the DM rewrites the
scene summary when scene-level truth has changed enough to deserve durable
compression.

## History Lookup
Full turn narration is not embedded. Pull exact detail with
`transcript.md`, `glass turns find ...`, `glass search text ...`, or
`glass search semantic ...`.

## Messages waiting for you
2 unread. Read with `glass msg read --since-checkpoint`.

## Instruction Surface
Use `instructions/` for tool/file behavior, `methodologies/` for required
turn sequence, `srd/` for public rules, and `how-to/` for optional examples.

## Your tools (allowlist)
- glass roll
- glass character bulk-get / bulk-update (bulk-update your character only)
- glass character set-hp / set-momentum / inventory-add (single-change convenience)
- glass msg <type> <recipient> <body>
- glass sync apply [path-or-directory ...] (commit projected markdown edits)
- glass entity neighborhood / similar (read-only graph queries)
- glass turns find / feed ... (query past turns)

When done, exit.
```

The DM's TURN_START has additional pointers: thread/beat states, intake of unratified player notes, the DM workspace, and a reminder of the **dual-purpose turn** (respond + plan ahead — see [`agents.md`](agents.md)).

## What's Always-On vs Queryable

### Always-on for every agent (in TURN_START as content or near-pointer)
- An embodied identity paragraph drawn from their `persona.md`
- Current mode + scene framing
- A generated turn type plus one methodology pointer selected by role, mode, and
  turn metadata
- Current public table: `table/index.md`, `table/scene.md`, `table/handouts/`,
  and any other files under `table/`
- Campaign framing
- Compact active scene summary, embedded and capped
- Campaign / arc summaries as pointers
- Full recent turns are queryable, not embedded
- Actual-play creative influence: one verse phrase plus current persisted tarot
  draw. This is omitted during non-play bootstrap/prep modes. Prelude
  coordinator turns omit it; the actual scene-play/action child turns can use
  it because characters are now in play.
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
- Indexed prose search (`glass search text ...` and vector-backed
  `glass search semantic ...`)
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
- `arcs/<arc>/scenes/<scene>/context.md` / `summary.md` — scene-level. The scene summary is finalized by `glass scene end --summary --outcome`.

The DM authors each level using the relevant methodology — campaign-level during planning, arc-level during arc creation, scene-level during scene prep. Each has a corresponding DM-only working document (`dm/foundation.md`, `arcs/<arc>/plan.md`, `arcs/<arc>/scenes/<scene>/prep.md`) that holds the full picture; the player-facing `context.md` holds only what's been shown.

The live `table/` is separate from those context documents. It is the
short-term public board for the current scene: `index.md` for at-a-glance
state, `scene.md` for the kickoff description, `handouts/` for in-game
handouts, and freeform table-root markdown files for whatever visible immediate
reference would prevent repeated clarification turns.

This is the same boundary the web UI's Active Table uses. The viewer may expose
DM notes, graph entities, hooks, messages, lore, and other campaign files in
other panes, but those are inspection surfaces. A player agent has table
visibility only when the relevant information is present under `table/` in its
projected CWD.

Format and update cadence are intentionally not pre-specified beyond the methodology guidance — see [`/docs/backlog.md`](../backlog.md). We codify further after first sessions show what's useful.

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
    notes/index.md                     # encyclopedia how-to-use
    journal/  workspace/  secret/  intake/   # starter dirs
  players/<player>/
    persona.md                         # who they are at the table
    character.md                       # starter sheet (filled during character creation)
    notes/index.md
    journal/  drafts/  inbox/

campaigns/<id>/                        # per-campaign live root, copied from templates/
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

Each agent runs as a separate `claude -p` subprocess inside a fresh per-turn
projection at `.glass-cwd/<campaign>/<turn>-<agent>/`. The projection mirrors
the canonical campaign tree's relative paths, but contains only the files that
actor may read. For example, `table/scene.md` stays `table/scene.md`; Tev's
private notes stay `players/tev/notes/`; another player's private notes simply
are not present.

The canonical campaign root remains `campaigns/<id>/`. TURN_START and turn
artifacts are written canonically under `dm/turns/<NNNN>/` or
`players/<id>/turns/<NNNN>/`, and copied into the projection at the same
relative path before the subprocess starts. The agent writes `TURN.md` in the
projected turn dir and runs `glass turn end` to create `turn-closeout.json`;
the orchestrator copies them back to canonical storage before committing the
turn.

The projection is owned by the spawned actor. Projected files are writable only
on role-authorized document surfaces and in the current turn dir; before Claude
starts, the orchestrator proves the actor can create, edit, and delete arbitrary
files in that current turn dir. Persistent mutations must go through `glass`:
`glass sync apply` commits projected markdown edits, while `glass character`,
`glass scene`, `glass clock`, `glass entity`, and related commands own hard
state. The local `glass` API runs commands against the canonical campaign while
using the projection as cwd, so agents can author at normal relative paths
without seeing extra canonical files.

Unix users still matter: spawned agents run as dedicated users (`aog-mara`,
`aog-tev`, `aog-sumi`, `aog-renno`, `aog-kit`) via `sudo -u`, while the
orchestrator remains the operator process. Projection trees are actor-owned and
grouped to the operator's primary group; this lets the operator/API read and
refresh projected files without relying on the operator shell having refreshed
supplementary groups. The canonical campaign tree remains operator-owned;
agents never use it as their filesystem surface. The projection removes the
dependency on canonical campaign permissions for normal reads, and the `glass`
boundary removes direct canonical writes from agent turns.

The principle: **do not trust agents to honor "don't read X" or "only mutate
through Y" instructions.** Agents are too good at finding things they shouldn't
have. Give each actor a workspace containing only the correct readable files,
and make the durable mutation path explicit.

## Streaming Output

The orchestrator runs in the foreground. When it spawns each agent invocation, it streams the agent's stdout (and stderr) line-by-line to the operator's terminal, prefixed with the agent id (e.g. `[mara]`, `[tev]`). Full captures land beside the agent's TURN files for post-hoc inspection.

This is the operator's primary debugging tool during play — you can see the agent reading files, calling `glass` commands, doing web searches, and writing files in real time. The default per-turn timeout is 60 minutes (`claude.turn_timeout_seconds = 3600`), bumped from 5 minutes after the first inspection runs showed real DM work needs more breathing room.

## Turn History Policy

For v1: do not embed full turn narration in TURN_START. The active scene
summary is the always-on compression surface; raw turns stay available via
`transcript.md`, `glass turns find`, `glass search text`, and
`glass search semantic`. Token budget is a real concern because every actor has
to cold-start context on each turn.

The recent/context split is orchestrator-maintained:

- **Scene summary** is compact authored continuity, included directly.
- **Raw turns** are available through `transcript.md`, `glass turns find`,
  `glass search text`, and `glass search semantic`.
- **Campaign/arc summaries** remain authored continuity compression and are
  read as files or through `glass summary show`.

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

1. Generates canonical `players/sumi/turns/<NNNN>/TURN_START.md` with an embodied identity paragraph plus pointers to her readable campaign files: `persona.md`, `character.md`, campaign context, arc context, scene context, recent turn summaries, messages, instruction surfaces, notes, and the one methodology selected for this turn.
2. Builds `.glass-cwd/<campaign>/<NNNN>-sumi/` with the same relative paths for Sumi's visible files.
3. Spawns `claude -p --dangerously-skip-permissions "Read players/sumi/turns/<NNNN>/TURN_START.md and take your turn."` with CWD set to the projection and the Sumi role grant installed for `glass`.
4. Waits for the subprocess to exit.
5. Copies projected turn artifacts back to the canonical turn dir, reads `TURN.md`, and appends the turn plus closeout metadata to Postgres and markdown transcript exports.
6. Picks the next agent.

## What This Doc Does Not Cover

- The actual SRD, instruction, how-to, and lore prose entries.
- How modes parameterize the always-on set (covered in [`modes.md`](modes.md)).
- The DM's dual-purpose turn — what they do besides responding (covered in [`agents.md`](agents.md)).
- The message bus details (covered in [`messaging.md`](messaging.md)).
