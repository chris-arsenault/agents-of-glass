# Game Start

The bootstrap flow that takes a fresh repo from "no campaign exists" to "real scenes are running." Two agent-driven phases plus an operator init step. Each phase produces transcripts, messages, public lore, and private notes. Every phase is clearable and resumable.

For the methodology docs the agents read inside each phase, see [`/templates/methodologies/`](../../templates/methodologies/) — those are the *real instructions*. The core set is campaign-planning, arc-creation, scene-prep, scene-play, action-scene, and character-creation.

For the campaign-level state machine, see [Phase state](#phase-state). For the operator CLI, see [`/src/orchestrator/SPEC.md`](../../src/orchestrator/SPEC.md).

## The Phases

```
0. INIT (operator)
   aog campaign new <id>
   - Copy templates/ → campaigns/<id>/
   - Write campaigns/<id>/state.json
   - Phase: → campaign_planning

1. CAMPAIGN PLANNING (DM solo, 1-few invocations)
   - DM reads: campaign-planning methodology, persona, world bible
  - DM authors:
     - campaigns/<id>/context.md (player-facing campaign-level)
     - campaigns/<id>/summary.md (running campaign continuity summary)
     - dm/foundation.md (DM-only working framing)
     - dm/notes/factions/, dm/notes/npcs/ (with antagonist flag), dm/notes/creatures/,
       dm/notes/artifacts/, dm/notes/ships/, dm/notes/locales/, dm/notes/secrets.md,
       dm/notes/hooks/, dm/notes/philosophy/
     - One opening arc, scaffolded via `glass arc create <slug>`:
       - arcs/<slug>/plan.md (DM-only)
       - arcs/<slug>/context.md (player-facing)
   - Done: DM declares planning complete
   - Phase: → character_creation

2. CHARACTER CREATION (DM + players, multi-invocation)
   - DM first: writes a public campaign-intro the players read
   - Each player: authors character.md + a public intro entry
   - DM: ratifies or pushes back via messages
   - Done: all players ratified
   - Phase: → active

3. ACTIVE
   - Scenes can now be started via `glass scene create <slug> --type <type>`
   - The first scene is just the first scene — the DM has prepped for it during planning, runs it like any other
   - Phase stays `active` indefinitely
```

There are no "sessions." A scene is the unit of play; its `--type` is a
protocol/toolkit label, not an exhaustive taxonomy. Common protocols are
`scene-play`, `action`, and `travel/montage`; toolkit labels like `combat`,
`chase`, `social-pressure`, `investigation`, or a custom slug help the DM frame
the scene. The agents play as long as the operator runs the orchestrator. When a
scene ends, the next scene starts when the DM is ready.

## Phase State

Each campaign has `campaigns/<id>/state.json`:

```json
{
  "campaign": "kaleidos-1",
  "phase": "campaign_planning",
  "phase_history": [
    { "phase": "init", "started_at": "...", "completed_at": "..." },
    { "phase": "campaign_planning", "started_at": "..." }
  ],
  "active_arc": null,
  "active_scene": null,
  "arcs": [],
  "created_at": "..."
}
```

Phase values: `init`, `campaign_planning`, `character_creation`, `active`.

The orchestrator tracks `active_arc` and `active_scene` as the campaign progresses through `active`. State updates after every agent invocation.

## Three Levels of Player-Facing Context

The DM produces three player-facing context documents — one per level — that get projected into every player's working directory throughout play. The DM also produces DM-only working documents that the players never see.

| Level | Player-facing | DM-only |
|-------|---------------|---------|
| **Campaign** | `campaigns/<id>/context.md` | `dm/foundation.md`, `dm/notes/**` |
| **Arc / act** | `arcs/<arc>/context.md`, `summary.md`, `clocks.md` | `arcs/<arc>/plan.md` |
| **Scene** | `arcs/<arc>/scenes/<scene>/context.md`, `summary.md` | `arcs/<arc>/scenes/<scene>/prep.md` |

In a player's per-turn CWD, these get projected as:
- `campaign-context.md`
- `arc-context.md` (if an arc is active)
- `scene-context.md` (if a scene is active)

Three levels of zoom. The DM updates each as the campaign / arc / scene evolves; the players read them on every turn.

## Hierarchy Managed by `glass`

The arc and scene directories are scaffolded by the CLI, not by the DM hand-creating folders:

- `aog campaign new <id>` (operator) — copies templates, creates `campaigns/<id>/` with the standard layout.
- `glass arc create <slug>` (DM) — creates `arcs/<slug>/` with `plan.md`, `context.md`, and an empty `scenes/`.
- `glass scene create <slug> --type <type>` (DM) — creates `arcs/<active>/scenes/<slug>/` with `prep.md`, `context.md`, `transcript.md`, `audit.jsonl`. Sets the new scene as active.

The DM populates the contents using the relevant methodology. The CLI ensures the folders, stub files, and state-machine entries are consistent.

## Per-Phase Inputs and Outputs

| Phase | Methodology | Agents | Mode | Reads | Writes |
|-------|-------------|--------|------|-------|--------|
| **campaign_planning** | `campaign-planning.md` | DM only | `campaign-planning` | methodology, persona, world bible (player + dm) | `campaigns/<id>/context.md`, `dm/foundation.md`, `dm/notes/**`, **8-15 curated entries in `shared/lore/`** (imported from world bible via `glass lore import`), opening arc dir via `glass arc create` |
| **character_creation** | `character-creation.md` | DM + players | `character-creation` | methodology, persona, campaign context, world bible | DM: `campaign-intro.md` (where TBD — likely campaign root or shared/), ratifications. Players: `players/<id>/character.md`, public intro entries. After ratification: `lore/characters/<id>.md`. Messages: DM↔player negotiation. |

Once `character_creation` completes, the campaign is `active`. The DM uses [`scene-prep.md`](../../templates/methodologies/scene-prep.md) before each scene; new arcs get authored via [`arc-creation.md`](../../templates/methodologies/arc-creation.md) when they emerge from play.

Each phase produces a transcript scoped to a scene (every phase runs as a typed scene under a meta-arc, e.g. `arcs/_bootstrap/scenes/planning/`). Plus the agent-authored content lands in the campaign tree directly.

**The output requirement:** every phase produces *both* transcript-and-messages *and* public/private lore-or-notes. The transcript records the process; the lore/notes records the durable result. Don't conflate them.

## Repo Structure

```
templates/                          # authored, stable; copied at campaign creation
  dm/                               # existing
  players/<id>/                     # existing
  shared/                           # existing — lore, vocabulary, party-knowledge etc.
  methodologies/                    # campaign-planning, arc-creation, scene-prep, character-creation
    README.md

campaigns/<id>/                     # per-campaign runtime root
  state.json                        # campaign phase state
  context.md                        # PLAYER-FACING campaign-level context
  summary.md                        # running campaign continuity summary
  table/                            # public short-term state, reset per scene
    index.md                        # at-a-glance board
    scene.md                        # scene kickoff description
    handouts/                       # in-game handouts
  dm/                               # copy of templates/dm/, mutates during play
    persona.md, scratchpad.md, journal/, notes/, secret/, intake/, workspace/
    foundation.md                   # DM-only working framing for the campaign
  players/<id>/                     # copy of templates/players/<id>/, mutates
  methodologies/                    # frozen snapshot of templates/methodologies/
  shared/                           # copy of templates/shared/, mutates
    lore/                           # campaign-canon (DM-canonized)
    vocabulary/
    quest-log.md
    party-knowledge.md
    clocks.md                       # public durable-clock projection
  arcs/<arc-slug>/                  # one dir per arc — created by `glass arc create`
    context.md                      # PLAYER-FACING arc-level context
    summary.md                      # running arc/act continuity summary
    clocks.md                       # public durable clocks for this arc/act
    plan.md                         # DM-only arc plan
    scenes/<scene-slug>/            # created by `glass scene create`
      context.md                    # PLAYER-FACING scene-level context
      summary.md                    # finalized via `glass scene end --summary`
      prep.md                       # DM-only scene prep
      transcript.md                 # scene-level transcript export; Postgres turns are canonical
      audit.jsonl                   # operational audit log
```

Each campaign is **self-contained**: clone or move `campaigns/<id>/` and you have the whole thing — methodologies snapshot, all arc and scene state, all lore, all transcripts. Editing `templates/` does not retroactively change a campaign that's already been created.

## Operator CLI Surface

```
aog campaign new <id>                # init: copy templates, write state.json, advance to campaign_planning
aog campaign show [<id>]             # show phase, active arc, active scene
aog campaign list
aog campaign plan [<id>]             # run the campaign_planning phase
aog campaign character-create [<id>] # run the character_creation phase
aog campaign run [<id>]              # advance from current phase, doing whatever's next
aog campaign resume [<id>]           # alias for `run`, framed for failure recovery
aog campaign clear <id> --back-to <phase|arc|scene>   # roll back state

aog scene run [<scene-slug>]         # run the active or named scene (foreground orchestrator loop)
aog scene resume [<scene-slug>]      # resume an interrupted scene
aog scene list [--arc <arc>]
aog scene show [<scene-slug>]
aog scene prepare-turn [<scene-slug>]
aog clear scene <scene-slug>
```

There is no `aog session ...` — sessions don't exist. Scenes are the unit.

## Resumability

Every phase and every scene is resumable mid-flight. State persists after every agent invocation. Failure semantics:

- If an agent invocation fails (claude error, timeout, malformed output): the orchestrator stops. Scene-level state in `arcs/<arc>/scenes/<scene>/` reflects the last fully-committed turn. Campaign-level state is unchanged.
- Operator inspects, fixes, runs `aog scene resume` (or `aog campaign resume` if no scene is active).
- For structural failure: `aog campaign clear <id> --back-to <phase|arc|scene>` wipes state forward, preserves earlier work.

Phase transitions are **explicit, not automatic**. The DM declares planning complete. The DM ratifies the last character. Scenes end when the DM calls `glass scene end`. This is so a half-finished phase or scene doesn't accidentally advance because of a stray turn.

## Why This Hierarchy

Each level has its own player-facing context document because the *zoom level* matters. A player in a scene needs scene framing (immediate), arc context (mid-term stakes), and campaign framing (long-term world state) — three levels of focus, all on every turn. The live `table/` sits beside those documents as the short-term public board: current visible state, scene kickoff, handouts, and freeform immediate references. The DM authors each separately because they update at different cadences:

- Campaign context updates rarely — when a major faction shift, a region change, a thread advances dramatically.
- Arc context updates per scene or two — what the players have learned, who's pushing on them, what clocks have ticked.
- Scene context updates within a scene — when the situation shifts substantially.
- Table updates whenever visible immediate state changes and players would
  otherwise ask for repetition.

The DM-only working documents (`foundation.md`, `plan.md`, `prep.md`) hold the full picture — secrets, possible end-states, what NPCs are *really* doing. The player-facing `context.md` holds only what the players have seen.

## What's Not Decided

- **Exact `state.json` shape** — sketched above; the orchestrator pins it during build.
- **Methodology content for character-creation** — still a stub; needs co-authoring.
- **How `aog campaign new` handles re-creation if the campaign-id already exists.** Probably an error unless `--force`.
- **Whether `glass scene end` is the only way to end a scene** or whether the orchestrator can force-end at a hard turn cap. (The latter is the deferred closure design — see [`scene-ending.md`](scene-ending.md).)
- **Hard caps per phase.** Pin during build.

See [`/tracking-immediate-decisions.md`](../../tracking-immediate-decisions.md) for the working list.
