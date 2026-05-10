# Modes (Scene Types)

A **mode** is the turn protocol currently governing a scene. It determines who
speaks, how fast fictional time moves, how often checks fire, and what kind of
state must stay visible.

The `--type` label on a scene is intentionally loose. Some labels are protocol
labels (`scene-play`, `action`, `travel`); some are DM toolkit labels that have
worked before (`combat`, `chase`, `social-pressure`); and the DM can make up a
label that fits the narrative. Do not treat the examples in this doc as an
exhaustive taxonomy.

For the universal turn shape that modes parameterize, see [`turn-loop.md`](turn-loop.md). For closure (deferred), see [`scene-ending.md`](scene-ending.md). For the broader hierarchy of campaign → arc → scene, see [`game-start.md`](game-start.md) and [`context-packages.md`](context-packages.md).

## Why Modes

A free-form loop ("agents talk to each other forever") produces undifferentiated mush. A real table has phases — the tense standoff looks nothing like the quiet investigation looks nothing like the cleanup at the end. Each phase has different rules about who speaks, when checks fire, how time advances.

Modes encode those phase-specific rules so the orchestrator can enforce the
parts that need enforcement. The DM toolkit names give the corpus useful
analysis labels: "what happened in the market chase" is queryable without
claiming that `chase` is the only possible action scene shape.

## How a Scene Gets a Mode

When the DM scaffolds a new scene with `glass scene create <slug> --type <label>`,
the CLI records that label in scene state. Custom slugs are allowed. The DM then
uses the methodology/protocol that fits the scene: usually `scene-play` for
open-ended play, `action` for quickfire rounds, `travel`/`montage` for compressed
movement, or a toolkit label that points to one of those protocols.

A scene's mode can change mid-scene if the situation changes — combat erupts in the middle of a town-mode scene. The DM calls `glass mode push combat` to nest, and `glass mode end` (or `glass mode pop`) to return to the parent. See [Mode Nesting](#mode-nesting) below.

## Mode Spec

Each mode is a markdown file under `modes/` — a description of the protocol, written for the DM to read. Not a schema. The DM applies it through prose.

A mode doc covers three things:

### Entry — what the DM addresses when starting the scene

In prose, the DM frames the scene: where are we, who's here, what's at stake,
what's a reasonable resolution shape. For action scenes that includes action
order, visible stakes, and the numeric tracker(s) that define progress. For
travel it includes the destination and the kind of montage we're after.

The DM's framing prose lands in the scene's `context.md` (player-facing) and is informed by `prep.md` (DM-only working scene prep — see [`/templates/methodologies/scene-prep.md`](../../templates/methodologies/scene-prep.md)).

### Turn protocol — how turns flow in this mode

- **Speaker selection** — round-robin? action order? free-form? DM-prompted? (Codified: the orchestrator implements the rule. See [`open-questions.md`](open-questions.md) for unsettled cases.)
- **Whether checks are typical** — action scenes make player-called checks more common; reflection rarely needs them.
- **What state surfaces matter** — action scenes read HP/trackers/effects every turn; quiet social scenes read notes about NPC disposition.
- **What the DM is licensed to do** — describe environment freely, introduce minor NPCs, advance time, etc.

### Exit — when the scene ends

Three categories:

- **Resolution** — the DM judges the scene's natural endpoint has come, calls `glass scene end`.
- **Budget exhaustion** — hard turn cap hit; orchestrator forces an end. (Closure design deferred — see [`scene-ending.md`](scene-ending.md).)
- **Mode shift** — the situation has changed enough that a different mode applies. DM may push a nested mode (combat erupting inside a town scene) or end the scene and start a new one with `glass scene create`.

For v1, exit is intentionally simple. Layered closure machinery (twist budgets, scene-closer agent, monotonic pressure) is deferred.

## Active Play Protocols

These are protocols, not an exhaustive scene-kind list.

| Protocol | Speaker selection | Fictional time per turn | Checks | Typical turn cap | Ends when |
|----------|-------------------|-------------------------|--------|------------------|-----------|
| **scene-play** | round-robin plus handoffs | minutes, hours, or days as needed | fewer; players roll when they judge uncertainty matters; DM rolls DM-side checks when needed | 12 | DM cuts to next scene, or no player has new action |
| **action** | action order rolled after DM layout | seconds or a few heartbeats | more common; players still choose their own rolls, DM-side checks stay on DM turns | 8 | a visible objective/tracker resolves |
| **travel / montage** | one beat per player, in order | hours, days, or longer | none or one big check | 4 (one per player) | every PC contributed once |

### scene-play

The flexible protocol for open-ended scenes: town business, ordinary social
play, exploration, investigation, downtime, relationship beats, and anything
else where the DM wants broader turns. Players can propose almost anything; the
players decide when their characters roll. Time can advance slowly or in larger
chunks. Notes proliferate.

Toolkit labels that often use `scene-play`: `town`, `social`, `exploration`,
`investigation`, `downtime`, `research`, `planning`, `aftermath`. The DM can add
others freely.

### action

The quickfire protocol for contested moments where every turn changes the
situation. Use it for any scene where the table needs tight order, fast
fictional time, visible pressure, and more frequent player-called rolls.

The action protocol:

1. The DM creates or pushes the scene mode.
2. The DM takes an opening layout turn: location, positions, visible pressure,
   stakes, opposition, and likely exit shape.
3. In that opening turn, after the layout, the DM calls `glass turn initiative`.
   This rolls/shuffles the participants into a persisted action order. The DM is
   included by default, so the DM's next turn after layout lands wherever the
   roll puts it.
4. The orchestrator follows that action order round after round. Handoffs and
   rapid-response queues can interrupt; after the queue drains, play continues
   from the stored action cursor.
5. Each player turn is quickfire: move, one action, housekeeping. Housekeeping
   includes messages, inventory checks, reading relevant lore/state, and asking
   DM clarifications. It should not become a second action.
6. Because the scene is under pressure, actions that change position, HP,
   leverage, escape progress, or scene pressure are usually good candidates for
   player-called rolls. Pure housekeeping and safe movement usually are not.
7. The scene has a **player-visible end condition**, usually numeric, tracked
   through `glass scene tracker` and reduced through `glass scene pressure` when
   the fiction calls for roll-mediated pressure: defeat/rout the opposition,
   fill the escape clock, convince the duke, survive until the gate opens,
   prevent the hazard clock from filling.

The methodology for this protocol is
[`/templates/methodologies/action-scene.md`](../../templates/methodologies/action-scene.md).

Toolkit labels that often use `action`: `combat`, `chase`, `social-pressure`,
`escape`, `duel`, `infiltration`, `trial`, `disaster`, `heist`, `race`,
`exorcism`, `rescue`. These are examples, not the list.

### DM Toolkit Examples

The toolkit is a shelf of patterns that have worked before. The DM can point to
one, combine two, or make up a new one.

| Toolkit label | Usually protocol | Honest tracker examples |
|---------------|------------------|-------------------------|
| `combat` | `action` | enemy HP, enemy morale, party holdout clock |
| `chase` | `action` | escape distance 0/6, pursuit clock 0/4, route hazards |
| `social-pressure` | `action` | concession clock, suspicion clock, public-support clock |
| `investigation` | `scene-play` | clue web, deadlock clock, lead quality |
| `exploration` | `scene-play` | rooms mapped, hazard clock, supplies |
| `travel` | `travel / montage` | days crossed, weather clock, route risk |

### travel / montage

Compressed mode for crossing distance. Each player contributes one beat (an event, a worry, a memory). DM weaves them into a single narrative span. Useful for skipping over uninteresting transit while still preserving character voice.

## Bootstrap-Only Modes

These modes only apply during the bootstrap phases (see [`game-start.md`](game-start.md)). They don't appear in active play.

| Mode | Phase | Speaker selection | Output |
|------|-------|-------------------|--------|
| **campaign-planning** | `campaign_planning` | DM only | campaign foundation per [`/templates/methodologies/campaign-planning.md`](../../templates/methodologies/campaign-planning.md) |
| **character-creation** | `character_creation` | DM + players, sequential | PCs and intro entries per [`/templates/methodologies/character-creation.md`](../../templates/methodologies/character-creation.md) |

## Mode Nesting

Modes can nest. A combat can erupt inside a town/social scene; when the combat ends, the town/social resumes from where it left off. A travel/montage can wrap an investigation that's playing out across multiple stops.

The orchestrator maintains a **mode stack**. `glass mode push <mode>` pushes; `glass mode pop` (or `glass mode end`) pops. The active mode is always the top of the stack. When a mode pops, its parent resumes — the parent's turn budget is *not* reset, but the parent does receive a transcript marker noting what happened in the child.

```yaml
mode_stack:
  - { mode: town, scene_id: keel-quarter, turn_budget_remaining: 7 }
  - { mode: combat, scene_id: ringglass-market-chase, turn_budget_remaining: 5 }
```

Constraints:

- **Children inherit hard rules** from the parent where they don't conflict (e.g. a nested combat still respects any campaign-level turn cap).
- **Children get their own resolution conditions and budgets** declared at entry — they don't borrow from the parent.
- **Pop is always allowed.** A child can always end and return control to the parent.
- **Parent re-entry is a transcript event.** When a child pops, the transcript records "resuming town/social at keel-quarter" so analysis can see the seam.

Some combinations are illegal — the orchestrator validates. For example, you cannot push a bootstrap mode (`campaign-planning`, `character-creation`) onto an active-play stack.

## Authoring New Modes

Most new scene labels do **not** need a new mode. The DM can choose
`scene-play`, `action`, or `travel/montage`, then describe the custom toolkit
shape in prep and scene framing.

Adding a truly new protocol is heavier:

1. Create `modes/<name>.md` with the three required sections.
2. Specify which modes it can nest inside (and which can nest inside it).
3. Add the mode to the orchestrator's mode registry.
4. Run a scene, see how it goes.

Protocols should be cheap to add, but don't create one just to name a narrative
shape. `duel`, `trial`, and `escape` can all use `action` until their turn
rules actually diverge.

## Open Questions

- **Inter-mode budget across a campaign.** Without sessions, there's no natural "we played for four hours, time to stop" boundary. The orchestrator runs as long as the operator runs it. Hard caps still exist per scene; campaign-level caps are tracked but rarely hit.
- **Player-initiated mode change.** Can a player call for a mode shift ("we want to leave the town and travel")? For v1, no — only the DM declares modes. Players propose actions; the DM decides whether those actions warrant a mode shift.
- **Stack depth limits.** Should the orchestrator cap stack depth? Probably yes (3-4 deep) — beyond that, scenes are getting confused, not nested.
