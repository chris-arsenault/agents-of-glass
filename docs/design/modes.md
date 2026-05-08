# Modes

A mode is a named protocol for what a turn looks like during a particular kind of scene. Combat is a mode. Town exploration is a mode. Worldbuilding is a mode.

Modes are first-class objects: each has a name, an entry contract, a turn protocol, and an exit condition. The DM declares a mode at the start of each scene and can call the next one when this one ends.

For the universal turn shape that modes parameterize, see [`turn-loop.md`](turn-loop.md). For mode-end logic (deferred), see [`scene-ending.md`](scene-ending.md).

## Why Modes

A free-form loop ("agents talk to each other forever") produces undifferentiated mush. A real TTRPG session has phases — the dungeon crawl looks nothing like the negotiation looks nothing like the cleanup at the end. Each phase has different rules about who speaks, when checks fire, how time advances.

Modes encode those phase-specific rules so the orchestrator can enforce them. They also give the corpus cut-points for analysis: "what happened in the combat at the market" is a queryable scene, not a fuzzy region.

## Mode Spec

Every mode is a markdown file (`modes/<mode-name>.md`) — a description of how a scene goes, written for the DM to read. Not a schema for the orchestrator to validate. The DM is smart enough to enter a mode by reading the mode's doc and addressing what it says in prose.

A mode doc covers three things:

### Entry — what the DM addresses when starting the scene

In prose, the DM frames the scene at mode start: where are we, who's here, what's at stake, what's a reasonable resolution shape. For combat that includes initiative ordering and the lineup of monsters; for worldbuilding it includes the seed situation; for travel it includes the destination and the kind of montage we're after.

The DM calls `glass mode start <mode> <scene-id>` to mark the transition (mode label + scene id are the only codified fields — everything else is the DM's framing prose, which lands in the transcript). The orchestrator records the transition; it doesn't validate a schema.

### Turn protocol — how turns flow in this mode

Things the mode doc spells out so the DM can play it consistently:

- **Speaker selection** — round-robin? initiative? free-form? DM-prompted? (Codified: the orchestrator implements the rule. See [`open-questions.md`](open-questions.md) for unsettled cases.)
- **Whether checks are typical** — combat fires checks constantly; reflection rarely.
- **What state surfaces matter** — combat reads HP every turn; town/social reads notes about NPC disposition.
- **What the DM is licensed to do** — describe environment freely, introduce minor NPCs, advance time, etc.

### Exit — when the scene ends

Three rough categories the mode doc names:

- **Resolution** — the DM judges the scene's natural endpoint has come.
- **Budget exhaustion** — turn cap hit; orchestrator forces wrap. (Hard turn caps are codified per mode; see [`scene-ending.md`](scene-ending.md), deferred.)
- **DM call** — DM judges the scene is done, calls `glass mode end`.

For v1, exit is intentionally simple. Layered closure machinery (twist budgets, scene-closer agent, monotonic pressure) is in [`scene-ending.md`](scene-ending.md), deferred.

## Starter Mode Set

| Mode | Speaker selection | Checks | Typical turn budget | Exits when |
|------|-------------------|--------|---------------------|------------|
| **worldbuilding** | DM-prompted, free-form | never | none (DM judgment) | DM declares "we have enough to begin" |
| **town / social** | DM addresses one player or asks "anyone?" | mid-stakes inquiry, social pressure | 12 | DM cuts to next scene, or no player has new action |
| **exploration** | round-robin | environmental, perception, navigation | 8 | locale fully described or party moves on |
| **investigation** | free-form, DM-gated reveals | inquiry + planning checks | 10 | key clue surfaces or party deadlocks |
| **combat** | initiative order (rolled, persisted) | every action | 8 | one side resolved (defeated/fled/yielded) |
| **travel / montage** | one beat per player, in order | none or one big check | 4 (one per player) | every PC contributed once |
| **wrap** | DM-only | none | 1-3 | DM produces session summary |

### worldbuilding

The pre-session mode. DM proposes seed (party situation, location, opening hook). Players riff on character ideas, locale details, complications. DM ratifies into the graph as it goes. Output: PCs created, opening hook locked in, locale notes seeded. Without this mode, sessions can't start.

### town / social

The most flexible mode. Players can propose almost anything; DM decides which proposals warrant checks. Time advances slowly. Notes proliferate (NPCs met, rumors heard, deals brokered). The default mode when no other mode is active.

### exploration

The party moves through a locale, learning it. Round-robin gives every player a chance to interact with the environment. DM emits descriptions; players probe, climb, search. Distinct from investigation: there's no specific clue to find, just terrain to know.

### investigation

The party is hunting something specific (a clue, a person, a truth). DM-gated reveals — the DM controls what surfaces and when, players' actions tilt the odds. Free-form speaker selection allows the most engaged player to push. The DM's twist budget matters here.

### combat

Hardest mode. Initiative ordered, HP ticking, every action is a check. Reads heavily from Postgres. Turn budget is firm — combats that drag are the canonical failure mode. Players cannot write notes mid-combat (no time at the table).

### travel / montage

Compressed mode for crossing distance. Each player contributes one beat (an event, a worry, a memory). DM weaves them into a single narrative span. Useful for skipping over uninteresting transit while still preserving character voice.

### wrap

The session-end mode. DM produces a session summary, persists final graph deltas, marks any threads/beats advanced. The DM is the only speaker. Wrap mode is itself a mode so it appears in the corpus the same way every other mode does.

## Mode Transitions

The DM ends a mode by calling `glass mode end`. The DM starts the next mode by calling `glass mode start <new-mode> <new-scene-id>`.

The transition itself appears in the transcript as a header — orchestrator-supplied, no agent-emitted YAML — recording the from/to mode and scene IDs and a timestamp. This gives analysis a clean boundary to slice on.

Some transitions are illegal (e.g. you can't go directly from worldbuilding to wrap without something in between, and you can't push wrap onto a non-empty mode stack). The orchestrator enforces the few legality rules; the DM's framing prose at mode start is otherwise unconstrained.

## What Happens Between Modes

Nothing. There is no "limbo." When one mode ends, another begins (or the session ends). If the DM needs a moment to think between modes, that's a single DM turn during the new mode's entry — not a state outside any mode.

## Mode Nesting

Modes can nest. A combat can erupt inside a town/social scene; when the combat ends, the town/social resumes from where it left off. A travel/montage can wrap an investigation that's playing out across multiple stops.

The orchestrator maintains a **mode stack**. `glass mode start <mode>` pushes; `glass mode end` pops. The active mode is always the top of the stack. When a mode pops, its parent resumes — the parent's turn budget is *not* reset, but the parent does receive a transcript marker noting what happened in the child.

```yaml
mode_stack:
  - { mode: town, scene_id: keel-quarter, turn_budget_remaining: 7 }
  - { mode: combat, scene_id: ringglass-market-chase, turn_budget_remaining: 5 }
```

Constraints:

- **Children inherit hard rules** from the parent where they don't conflict (e.g. a nested combat still respects the session's overall turn cap).
- **Children get their own resolution conditions and budgets** declared at entry — they don't borrow from the parent.
- **Pop is always allowed.** A child can always end and return control to the parent.
- **Parent re-entry is a transcript event.** When a child pops, the transcript records "resuming town/social at keel-quarter" so analysis can see the seam.

Some combinations are illegal — the orchestrator validates. For example, you can't nest worldbuilding inside anything else (worldbuilding is a session-opening-only mode), and you can't push a wrap onto a non-empty stack (wrap implies the session is ending, so all parents must already be popped).

## Authoring New Modes

Adding a mode is:

1. Create `modes/<name>.md` with the three required sections.
2. Specify which modes it can nest inside (and which can nest inside it).
3. Add the mode to the orchestrator's mode registry.
4. Run a session, see how it goes.

Modes should be cheap to add. Don't over-engineer mode inheritance or shared machinery — three similar modes is better than a premature abstraction layer. We'll only know what abstractions are real after we have several working modes.

## Open Questions

- **Inter-mode budget.** Can a session run for unlimited modes if each mode stays under budget? Sessions also have a max-mode count and an arc-completion check that gate the wrap.
- **Player-initiated mode change.** Can a player call for a mode change ("we want to leave the town and travel")? For v1, no — only the DM declares modes. Players propose actions; the DM decides whether those actions warrant a mode shift.
- **Stack depth limits.** Should the orchestrator cap stack depth? Probably yes (3-4 deep) — beyond that, scenes are getting confused, not nested.
