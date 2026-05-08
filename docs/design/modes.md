# Modes (Scene Types)

A **mode** is the turn protocol for a particular kind of scene. Combat is a mode. Town/social is a mode. Each scene has exactly one mode at any moment — the mode determines who speaks, whether checks fire, how time advances.

"Mode" and "scene type" are synonyms in this project. The technical field is `mode`; the user-facing word is "scene type."

For the universal turn shape that modes parameterize, see [`turn-loop.md`](turn-loop.md). For closure (deferred), see [`scene-ending.md`](scene-ending.md). For the broader hierarchy of campaign → arc → scene, see [`game-start.md`](game-start.md) and [`context-packages.md`](context-packages.md).

## Why Modes

A free-form loop ("agents talk to each other forever") produces undifferentiated mush. A real table has phases — the dungeon crawl looks nothing like the negotiation looks nothing like the cleanup at the end. Each phase has different rules about who speaks, when checks fire, how time advances.

Modes encode those phase-specific rules so the orchestrator can enforce them. They also give the corpus cut-points for analysis: "what happened in the combat at the market" is a queryable scene, not a fuzzy region.

## How a Scene Gets a Mode

When the DM scaffolds a new scene with `glass scene create <slug> --type <mode>`, the CLI records the mode in scene state. From that point, the orchestrator runs the scene under that mode's turn protocol.

A scene's mode can change mid-scene if the situation changes — combat erupts in the middle of a town-mode scene. The DM calls `glass mode push combat` to nest, and `glass mode end` (or `glass mode pop`) to return to the parent. See [Mode Nesting](#mode-nesting) below.

## Mode Spec

Each mode is a markdown file under `modes/` — a description of the protocol, written for the DM to read. Not a schema. The DM applies it through prose.

A mode doc covers three things:

### Entry — what the DM addresses when starting the scene

In prose, the DM frames the scene: where are we, who's here, what's at stake, what's a reasonable resolution shape. For combat that includes initiative ordering and the lineup of monsters; for travel it includes the destination and the kind of montage we're after.

The DM's framing prose lands in the scene's `context.md` (player-facing) and is informed by `prep.md` (DM-only working scene prep — see [`/templates/methodologies/scene-prep.md`](../../templates/methodologies/scene-prep.md)).

### Turn protocol — how turns flow in this mode

- **Speaker selection** — round-robin? initiative? free-form? DM-prompted? (Codified: the orchestrator implements the rule. See [`open-questions.md`](open-questions.md) for unsettled cases.)
- **Whether checks are typical** — combat fires checks constantly; reflection rarely.
- **What state surfaces matter** — combat reads HP every turn; town/social reads notes about NPC disposition.
- **What the DM is licensed to do** — describe environment freely, introduce minor NPCs, advance time, etc.

### Exit — when the scene ends

Three categories:

- **Resolution** — the DM judges the scene's natural endpoint has come, calls `glass scene end`.
- **Budget exhaustion** — hard turn cap hit; orchestrator forces an end. (Closure design deferred — see [`scene-ending.md`](scene-ending.md).)
- **Mode shift** — the situation has changed enough that a different mode applies. DM may push a nested mode (combat erupting inside a town scene) or end the scene and start a new one with `glass scene create`.

For v1, exit is intentionally simple. Layered closure machinery (twist budgets, scene-closer agent, monotonic pressure) is deferred.

## Starter Mode Set (Active Play)

| Mode | Speaker selection | Checks | Typical turn cap | Ends when |
|------|-------------------|--------|------------------|-----------|
| **town / social** | DM addresses one player or asks "anyone?" | mid-stakes inquiry, social pressure | 12 | DM cuts to next scene, or no player has new action |
| **exploration** | round-robin | environmental, perception, navigation | 8 | locale fully described or party moves on |
| **investigation** | free-form, DM-gated reveals | inquiry + planning checks | 10 | key clue surfaces or party deadlocks |
| **combat** | initiative order (rolled, persisted) | every action | 8 | one side resolved (defeated/fled/yielded) |
| **travel / montage** | one beat per player, in order | none or one big check | 4 (one per player) | every PC contributed once |

### town / social

The most flexible mode. Players can propose almost anything; the DM decides which proposals warrant checks. Time advances slowly. Notes proliferate (NPCs met, rumors heard, deals brokered). The default mode when no other mode is active.

### exploration

The party moves through a locale, learning it. Round-robin gives every player a chance to interact with the environment. DM emits descriptions; players probe, climb, search. Distinct from investigation: there's no specific clue to find, just terrain to know.

### investigation

The party is hunting something specific (a clue, a person, a truth). DM-gated reveals — the DM controls what surfaces and when, players' actions tilt the odds. Free-form speaker selection allows the most engaged player to push. The DM's twist budget matters here.

### combat

The hardest mode. Initiative ordered, HP ticking, every action a check. Atomic combat — declaration + roll + outcome narration in one turn (see [`turn-loop.md`](turn-loop.md#combat-specifically)). No reactions; no after-the-fact mitigation. Players cannot write notes mid-combat (no time at the table). Reads heavily from Postgres. Combats that drag are the canonical failure mode — the hard turn cap matters.

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

Adding a mode is:

1. Create `modes/<name>.md` with the three required sections.
2. Specify which modes it can nest inside (and which can nest inside it).
3. Add the mode to the orchestrator's mode registry.
4. Run a scene, see how it goes.

Modes should be cheap to add. Don't over-engineer mode inheritance or shared machinery — three similar modes is better than a premature abstraction layer.

## Open Questions

- **Inter-mode budget across a campaign.** Without sessions, there's no natural "we played for four hours, time to stop" boundary. The orchestrator runs as long as the operator runs it. Hard caps still exist per scene; campaign-level caps are tracked but rarely hit.
- **Player-initiated mode change.** Can a player call for a mode shift ("we want to leave the town and travel")? For v1, no — only the DM declares modes. Players propose actions; the DM decides whether those actions warrant a mode shift.
- **Stack depth limits.** Should the orchestrator cap stack depth? Probably yes (3-4 deep) — beyond that, scenes are getting confused, not nested.
