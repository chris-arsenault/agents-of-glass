# The Turn Loop

What a turn is, end to end.

For deeper "why," see [`../principles/`](../principles/), especially
[`minimize-actor-transitions.md`](../principles/minimize-actor-transitions.md).
For modes, see [`modes.md`](modes.md). For closure (deferred), see
[`scene-ending.md`](scene-ending.md). For unsettled design questions about
speaker selection and inter-player dialog, see [`open-questions.md`](open-questions.md).

## In One Paragraph

The orchestrator picks the next agent based on the current mode's speaker rule. It spawns the agent with their role prompt, the recent transcript, their notes, and a tool allowlist. The agent writes prose — their turn — and along the way calls `glass` for any mechanical thing that needs coherence (dice, HP changes, notes, mode transitions). When the agent exits, the orchestrator commits their prose to the transcript with the right header and moves on.

## Codified vs Prose

Three principles run the whole show:

1. **Codify the things agents drift on.** Numbers (dice, HP, momentum, attributes). Inventory lists. Names of places and NPCs. Mutations to canonical state. Speaker / mode / scene / turn labels. These go through the `glass` CLI (or the orchestrator's own state) so they stay consistent across turns and across agents.

2. **Everything else is prose.** Intent, scene structure, what kind of action this is, whether the player is asking a question, what the DM thinks of the player's idea, who's preparing what defensive ability, what's visible to whom — the agents handle this in narrative. We do not enumerate intent types, build proposed-action arrays, require structured delta blocks, or attach visibility flags to actions. The agents are reading each other's prose; they're smart enough to handle it.

3. **Minimize actor transitions.** A new agent invocation is expensive because
it must reread context before writing a short turn. If the current actor can
resolve something honestly within their authority, they should do it now
instead of creating a handoff. This is why the DM rolls DM-side PC checks
directly instead of asking a player to take an extra turn just to roll dice.

**The codification is a coherence mechanism, not a turn-structure enforcer.** It exists because numbers drift and names drift; everything else, agents do fine in prose.

## How a Turn Begins

The orchestrator builds a `TURN_START.md` file in the agent's per-turn working directory. The agent's prompt is essentially "Read `TURN_START.md` and take your turn." TURN_START is a thin pointer file — links to the role, public table, scene framing, recent transcript, unread messages, vocabulary index, and the tool allowlist. Full layout in [`context-packages.md`](context-packages.md).

The orchestrator builds a fresh CWD per turn with only the files the agent's role is allowed to see. Process-level isolation, not policy. See [`architecture.md`](architecture.md) for how.

## What an Agent's Turn Is

Plain markdown. Whatever they want to say, written as the person they are.

While they write it, they may call `glass` tools:

- `glass roll <skill> <attribute> --risk <level> --character <id>` — when they want a check
- `glass character set-hp` / `set-momentum` / `inventory-add` / `inventory-rm` — to record state changes
- `glass character consequence-add` / `consequence-list` / `consequence-resolve` — lasting fictional state that should not drift
- `glass clock set` / `tick` / `list` / `show` / `resolve` — durable cross-scene pressure
- `glass summary show` / `write` / `append` — authored continuity summaries at campaign, arc/act, and scene level
- `glass note write` (DM canonical or workspace) or write to their journal directory (player private)
- `glass entity upsert` (DM only)
- `glass mode start` / `mode end` (DM only)
- `glass entity neighborhood` / `relations` / `between` / `edges` /
  `stance` / `glass thread beat` — read-only coherence lookups
- `glass search text` / `semantic` — bounded recall over indexed turns and
  markdown
- `glass msg <type> <recipient> <body>` — send a typed message ([`messaging.md`](messaging.md))
- `glass msg read [--since-checkpoint]` — read messages addressed to them
- `glass turns find ...` — exact past-turn lookup by metadata or `--text` when
  more context is needed

They make these calls in the order they would normally do them at a real table. When they're done writing, they exit.

There is **no structured delta block** at the end of a turn. There is no `next_speaker` field. There is no `intent: action` tag. There is no `proposed_check` block. There is no `prepared_actions: [...]` array. The orchestrator already knows who's speaking, in what mode, at what turn number; the DM reads the player's prose and responds like a person who can read.

## What the Orchestrator Adds

The transcript is a markdown file. The orchestrator owns its structure:

- A **per-turn header** that records who's speaking, the role (DM or player), the active mode, the scene id, the turn number, the timestamp.
- The **agent's prose** as written.
- Inline **mechanical event lines**, automatically inserted by `glass turn append` based on the side-effects the agent triggered during their turn (rolls, pressure reductions, HP changes, inventory deltas).

Example:

```markdown
## Turn 24 — Tev (player) — combat, ringglass-market-chase

Tev (OOC): "Okay Karrith's gonna swing on the patrol leader."

Karrith hauls back the hammer and brings it down toward the leader's shoulder.

> pressure Patrol leader HP: advance, impact d8=5 -> 2, -2 (8/8 -> 6/8)

The hammer connects with a brutal crunch — the leader staggers but doesn't go down.
```

The `> 🎲` line is auto-inserted from the `glass roll` audit log at the right place in the prose. It's there for human readability and corpus indexing; the canonical record lives in Postgres.

## What the DM Does

Reads the prose. Responds in prose.

The DM does not parse YAML or read schema fields off the player's turn. They read what the player wrote and react like a person — same as a real GM at a real table.

If a player says "I prep my shield instead of attacking, Karrith's exposed," the DM understands this in plain language. The next time something attacks Karrith, the DM narrates the shield in play. There is no `prepared_actions` array; the prose is the source of truth, and the DM is smart enough to track preparations across the recent transcript window.

If the preparation is meant to be hidden in-fiction ("Mork subtly attunes a barrier nobody can see"), that's also prose — and the DM honors the visibility in their narration. The monster doesn't know about it; the DM may attack anyway, and the shield trips at resolution time. **Visibility is a narrative choice, not a flag.**

The same applies to questions the player has, intents the player has, requests for clarification — all prose, all read by the DM, all answered in the DM's next turn.

## Action Scenes

Action scenes are the quickfire version of the turn loop. `combat`, `chase`,
and `social-pressure` are toolkit examples, not an exhaustive list. The actual
distinction is protocol: tight turn order, fictional time measured in seconds
or a few heartbeats, player-chosen rolls happening more often, and a visible
objective tracked honestly.

Action scenes use a persisted action order rolled by the DM after the opening
layout:

```bash
glass turn initiative
```

The DM is included in that order by default. Handoffs and rapid-response queues
can interrupt for clarifications or bursts of reaction; when they drain, play
continues from the stored action-order cursor.

An action-scene turn is **atomic**. One agent invocation handles the turn's
housekeeping, movement, one action, any roll, and immediate outcome narration;
no other-agent input is required unless the acting agent explicitly hands off
for a DM clarification.

> Karrith hauls back the hammer and brings it down toward the leader's shoulder.
> [`glass scene pressure patrol-leader-hp hammer-work vitality --risk risky --character karrith --impact d8`]
> The hammer connects with a brutal crunch — the leader staggers but doesn't go down.

The pressure command resolved the mechanics; the player narrated both intent
and outcome. The DM's turns for monsters, environmental hazards, or other
opposition follow the same quickfire shape for the things the DM controls. If
the DM needs a player-character check during the DM turn, the DM rolls it
directly and uses the result in that same turn. Player-initiated rolls on
player turns remain player-called.

**Required:** an action-scene turn with a roll must include outcome narration
that reflects the roll result. A player who rolls and doesn't narrate has
produced a malformed turn. (This is a soft rule we enforce in the prompt, not a
schema. The orchestrator can flag it but won't reject.)

**One turn menu:** move, one action, housekeeping. Housekeeping includes message
bus work, inventory checks, reading relevant lore/state, and asking DM
questions. It does not grant a second action.

**Rolls are more common, not handoff-heavy.** In ordinary scene play, many
actions resolve through prose. In action scenes, more player actions are
obviously uncertain and consequential, so players should expect to call rolls
more often on their own turns. DM-side checks happen on the DM's turn without
handing off just for dice. Safe movement, short speech, and pure housekeeping
usually do not need rolls.

**The end condition is visible.** The DM declares what would end the action
scene and tracks it numerically when numbers matter: enemy HP/morale, escape
distance, suspicion, concession progress, hazard pressure, survival rounds.
Use `glass scene tracker set/tick/list` for clocks and `glass scene pressure`
for roll-mediated reduction so the math does not drift across agents.

**No reactions by default.** Once an attack lands on you, it lands. Your *next*
turn can include the consequences in narration ("blood from the gash she opened
earlier is making my grip slick"), but you can't interrupt an attacker's turn to
mitigate it.

**Preparations are prose.** "I prepare my shield" is a thing the player wrote. The DM (or the next NPC turn) reads it and responds appropriately.

## Non-Combat

The player describes what they're doing — narrative, possibly with embedded `glass roll` calls if they think a check is warranted. The DM responds — narrative, possibly with embedded `glass roll` calls or NPC actions. There is **no enforced sequence** of "ask, adjudicate, roll, narrate." The agents handle pacing the way real players do: by writing.

The DM can decide a player's roll was at the wrong risk or the wrong skill
because of hidden state. Usually the DM corrects the interpretation in prose or,
if a new check is actually needed, rolls the corrected DM-side PC check during
the DM turn. Do not add a handoff solely to request a re-roll.

## The Agent Tool Loop

Inside their invocation, the agent runs Claude's normal tool loop. They can:

- Look up lore (`glass entity neighborhood`, file reads against the lore repo's player-facing content)
- Check their own notes (read their journal directory)
- Roll dice (`glass roll`)
- Update state (`glass character set-hp`, `glass note write`, etc.)
- Reference the current mode framing the orchestrator gave them

They exit when they've finished writing their turn. The orchestrator picks up the prose artifact and the audit log of any tool calls they made, assembles them into the transcript, and moves on.

## What the Loop Does Not Do

- **Retry on failure.** A weird turn is a transcript event, not a do-over.
- **Edit prior turns.** The public turn corpus is append-only; `transcript.md` is only a derived export.
- **Hide internal reasoning.** Agent reasoning that didn't make it to a turn is not in the transcript by design.
- **Make narrative decisions.** The orchestrator decides whose turn is next; nothing else.
- **Parse the agent's prose for "intent" or "next-speaker hints."** Whose turn is next is decided by the mode's speaker rule (with the open-question caveats about interjections — see [`open-questions.md`](open-questions.md)).

## Open Questions

Speaker selection beyond the mode default, and inter-player dialog (table talk), are catalogued in [`open-questions.md`](open-questions.md).
