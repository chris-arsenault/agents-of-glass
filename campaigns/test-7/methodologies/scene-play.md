---
title: Scene Play Methodology
status: authored
audience: players, dm
applies_to_modes: [scene-play]
---

# Scene Play

The active mode for free-form scenes — exploration, conversation, investigation, downtime. The DM has framed the scene; you're inside it. This is *the table is rolling*: act, react, ask, decide, narrate.

For quickfire action scenes, use [`action-scene.md`](action-scene.md). Combat,
chases, and social pressure are common examples, not the exhaustive list.

## Speaker order and handoffs

Default order is round-the-table players, then the DM (`tev → sumi → renno → kit → dm → tev → ...`). The next-speaker queue handles overrides — each `glass turn handoff` call appends one entry; the orchestrator pops one per turn.

**Players** can use `glass turn handoff <agent>` (one entry) at the end of their turn to redirect — most often `glass turn handoff dm` to call the DM with a question. Use sparingly; the rotation handles most flow.

**The DM** has a few additional levers (also rare — the rotation should still be the default):

- `glass turn handoff <agent>` — append one redirect. Multiple calls in a single DM turn queue a sequence: `handoff sumi` then `handoff dm` will run sumi next, then back to the DM, then resume rotation from the DM.
- `glass turn restart-order <agent>` — DM-only. Wipes any pending queue and sets the next speaker to `<agent>`. Use when the rotation has clearly drifted and needs a hard reset ("Sorry kit, we're restarting from tev").
- `glass turn rapid-round <prompt>` — DM-only. Queues a single-shot rapid response from each player to a single prompt (see "Rapid-response rounds" below).
- `glass turn clear-handoff` — DM-only. Wipe the pending queue without setting a new next.

If no handoff is queued, the orchestrator falls through to the round-robin from `last_speaker`.

## What a turn looks like

There is no script. Within your turn, you do whatever the scene calls for. A typical turn includes some of:

- **Drain the bus.** Follow [`instructions/message-bus.md`](../instructions/message-bus.md).
- **Notice creative influence.** In actual play, TURN_START may include a
  verse phrase and current tarot. Use them as minor creative texture; they are
  not mechanics and do not outrank the table or your character.
- **Look at the table.** Follow [`instructions/table.md`](../instructions/table.md).
- **Look at the world.** Read `shared/lore/`, recent transcript turns, your character file, other PCs' `players/<id>/public/intro.md`. Open whatever images, maps, or notes are relevant.
- **Look at summaries and clocks.** Use `summary.md`, arc/scene `summary.md`
  files, and `shared/clocks.md` before asking the DM to repeat campaign
  continuity or public long-running pressure.
- **Maintain the scene summary.** Recent turn narration is not embedded in
  TURN_START. At the end of a normal scene-play turn, append 2-4 sentences or bullets
  to the active scene summary with `glass summary append scene --body "..."`.
  The purpose is compact continuity for the next actor: what changed, what is
  now true, what someone is aiming at, or what question is live. Players append;
  the DM may rewrite/reformat the summary when it gets noisy.
- **Search before asking for old context.** Follow [`instructions/recall-and-search.md`](../instructions/recall-and-search.md).
- **Decide what your character is doing.** Pick an action, a stance, a line of inquiry, an attempt at something.
- **Take any rolls you decide are needed.** Use the roll authority in [`srd/checks.md`](../srd/checks.md).
- **Send messages or ask questions.** Use the message bus; batch minor things.
- **Write your turn narration.** Follow [`instructions/output-contract.md`](../instructions/output-contract.md).
- **Optional handoff.** Run `glass turn handoff <agent_id>` if the next agent should not be next-in-rotation.

You don't have to do all of these every turn. You don't have to do them in this order. The list is a menu.

## Forward momentum

Every full turn should travel toward some kind of resolution. A quiet turn, a
conversation, or a reflective character beat is still active play when it
changes what is true, what someone knows, what someone can decide, or what
pressure is now visible.

Before you write the public prose, know what this turn moved. Examples:

- answer or ask a live question in a way another actor can use
- make, refuse, condition, or defer a decision
- move to a new position or put a tool, document, clue, NPC, or risk into play
- update the table, scene summary, tracker, character state, or message bus so
  the next actor has a clearer board
- surface a cost, promise, threat, offer, or contradiction that narrows the
  scene's choices

Do not spend a full turn only deepening the meaning of the previous beat. If
the main value is coordination, use messages. If the main value is state,
update table/summary/state. The public prose should carry the visible story
beat and then get out of the next actor's way.

## Rules References

- Checks, risk, outcomes, momentum, and DM-side PC checks:
  [`srd/checks.md`](../srd/checks.md).
- Character hard-state commands:
  [`instructions/character-state.md`](../instructions/character-state.md).
- Creative influences:
  [`instructions/creative-influences.md`](../instructions/creative-influences.md).

## What the DM does on their turn

The DM's job in scene play is roughly threefold: **respond, drive, plan.** Every DM turn does all three.

### Table upkeep

Follow [`instructions/table.md`](../instructions/table.md). Update visible
short-term state before ending your turn.

### Respond

- Drain the bus first (questions, secret intents, anything addressed to you).
- Reply to questions via `glass msg secret <player>` (or `glass msg plot-hint` for world-side nudges). Multiple replies in one turn is fine.
- If a question is urgent enough that a player needs to act before the rotation comes back to them, `glass turn handoff <player>` after responding so they get the next slot.

### Drive

- If the scene has stalled or a player has ended their turn open-endedly ("Tev approaches the door."), nudge them along: `glass msg instruction <player> "what do you do here?"` or `"the door is unlocked — what's your move?"`. The bus is the right channel; a turn of public prose just to ask "what do you do?" wastes the transcript.
- If something in the world should *happen* (an NPC speaks, time passes, a clock ticks, the lights go out), write that as transcript prose to `<TURN_OUTPUT>`. World-side observations are the rare case where the DM's turn is narrative.
- If you need checks for any/all player characters, **roll them yourself** (see
  "DM-side roll inversion" below) — don't interrupt the player rotation just to
  ask for dice.

### Plan

Every DM turn should also include planning work. The agents only get one turn at a time, so use yours productively:

- Update `dm/scratchpad.md` with where the scene is heading, what the next beat is, what NPC reactions you're tracking.
- Add or refine entries in `dm/notes/` (NPCs, threads, hooks) as the scene reveals new specificity.
- Tick clocks in your tracking files if appropriate.
- Update durable clocks with `glass clock` when cross-scene pressure changes.
- Update `summary.md` files when continuity has changed enough that future
  agents should not reconstruct it from raw turns.
- Reformat the active scene summary with `glass summary write scene --body "..."`
  when player appends have become noisy or duplicated.
- Look ahead: what's the natural transition out of this scene? What lore might be relevant to what's coming? Pre-load those reads.
- If a player's secret message reveals hidden intent, file a note in `dm/secret/` about how you'll surface or undermine it later.

Plan even if the bus is empty and the rotation is fine. Idle DM turns are wasted DM turns.

## DM-side roll inversion

Follow [`srd/checks.md`](../srd/checks.md): when the DM needs a PC check during
the DM turn, the DM rolls it directly and narrates from the result. Hand off
only when the player has a real decision to make before resolution.

## Rapid-response rounds

Sometimes the DM needs each player to react to the same stimulus quickly — the lights going out, an NPC's pointed question to the room, a sudden shift in the air pressure. Rather than spending four full per-player turns on it, queue a rapid round:

```bash
glass turn rapid-round "the room goes black. roll briefly: what does your character do in the next two seconds?"
```

This queues all four players in order. Each rapid-response turn:

- Sees the prompt at the top of their TURN_START with explicit "single-shot" framing.
- Skips the full per-turn menu — no rolls, no side-channel coordination, no further handoffs.
- Writes a short in-character reaction (a paragraph at most) to `<TURN_OUTPUT>` and exits.

After the four rapid turns drain, the rotation continues from kit (so the next agent is the DM via round-robin).

`glass turn rapid-round --players tev,renno "..."` if you only want a subset to react.

Use rapid-rounds sparingly — they're for *moments*, not for replacing scene-play.

## Closing the scene

Scenes don't end themselves. Without explicit closure, the DM will keep finding "one more thing" to add and the scene runs forever — this is a real failure mode of agentic play. The closure mechanism has multiple layers; the DM is responsible for using all of them.

### Closure signals — concrete

Every DM turn, look for at least one of these. When you see one, start closing:

- The scene's stake is resolved (the question that opened the scene has an answer).
- The party has clearly decided to leave (or to commit to an action that ends this scene's frame).
- A clock has run out and the consequence has landed.
- The scene has yielded everything it's going to.

### When does it *feel* like the scene has gone on too long?

There's no turn-count rule. Many scenes run 10-20 rounds or more — long scenes are good when they keep generating, bad when they stop. Trust your gut and watch for the soft tells:

- **Diminishing returns.** Recent turns are getting smaller and more procedural — players are checking inventory, asking minor clarifications, having brief social niceties. The big beats stopped landing several turns back.
- **Spinning on the same threads.** The party keeps revisiting the same questions or interactions without resolving them. New angles aren't appearing.
- **You can't articulate what's still on the table.** If asked "what is this scene trying to surface that hasn't yet?", you'd struggle to answer specifically.
- **The next interesting beat is a new scene.** What you actually want to do next requires a different setting, a time-skip, or a fresh frame. The current scene is the wrong vehicle.
- **Players are repeating themselves.** Same character moves, same arguments, same vibes. They've shown what they have to show here.

Once two or more of these tells fire, start closing. If a closure signal hasn't fired naturally yet, you can manufacture one — push a clock, have an NPC act, narrate a time-skip. Don't wait for the perfect moment that may never come.

### The two-phase close

Once you've decided to close, run it in two phases:

**Phase 1: closing-down.** Call `glass scene closing-down [--rounds N]` (default 4 rounds, i.e. ~20 agent turns). Every subsequent TURN_START will show the players a "Scene closing — N rounds left" countdown so they know to converge their loose threads. They'll stop opening new arcs of action and start moving toward closure on what's already on the table.

The DM continues normal turns during closing-down: respond, drive, plan. Use this window to surface any final beats that need to land — an NPC's last word, a clock tick, a piece of information the party needs before the scene closes.

For short scenes that are already wound down, you can skip Phase 1 entirely and jump to Phase 2 + scene end. The countdown is pressure for longer scenes where the players need warning to converge; a 4-round scene doesn't need it.

**Phase 2: final round.** When the countdown reaches 0 (or earlier if you're ready), fire a rapid-round prompting each PC for a closing beat:

```bash
glass turn rapid-round "your character's last action, line, or image as this scene closes"
```

This gives every PC a single-shot closing turn. After the four rapid-response turns drain, you call `glass scene end` and the scene is over.

### Hard backstop: the overrun

If the countdown goes past 0 and you still haven't ended, every TURN_START shows a "SCENE OVERRUN" warning. **Call `glass scene end` now even if it feels unfinished.** Imperfect closure beats a scene that runs forever. Whatever wasn't said can carry into the next scene as a hook.

### Bundling wrap-up into `glass scene end`

`glass scene end` takes flags so wrap-up is a single atomic call:

```bash
glass scene end \
    --summary "Tev got the schematic. Senna is dead. The Council knows the party was at the substation." \
    --beats "Senna died protecting the cache.
Tev now carries the Reconnection schematic.
The Displacement Council issued an arrest order for Karet's Echo." \
    --xp tev=2,sumi=1,renno=1,kit=2
```

- `--summary` writes `arcs/<arc>/scenes/<scene>/summary.md` (corpus material; one or two paragraphs).
- `--beats` appends each line to `shared/quest-log.md` tagged with the scene + arc (party-visible canon).
- `--xp` calls `glass character award-xp` for each entry (logged to xp_awards with reason="scene end: <scene_id>").

You can also write any of those manually before ending — `glass quest beat <text>` for ad-hoc beats during the scene, `glass character award-xp` for spot awards mid-scene. Bundling at scene end is the convention; the manual paths are escape hatches.

After ending, update the relevant arc/act and campaign summaries if the scene
changed durable continuity:

```bash
glass summary append arc <arc-id> --body "..."
glass summary append campaign --body "..."
```

Players don't end the scene — that's the DM's call. If you think the scene is done, fire `glass msg secret dm "I think we're done here"` and let the DM decide.

## Nested scenes (push/pop)

Sometimes a scene needs to interrupt itself — a fight breaks out during town exploration, a tense conversation suddenly pivots to a chase. The mode stack handles this: push a new mode + scene on top of the current one, play it through, then pop back to the parent.

```bash
# in town exploration (scene-play, scene id "vestige-square"); a fight starts:
glass scene create vestige-square-fight --type action --arc <arc>
glass mode start action vestige-square-fight     # pushes onto the mode stack

# action plays out under methodologies/action-scene.md...

glass mode end       # pops; active mode is back to scene-play, scene "vestige-square"
```

The orchestrator's active mode is always the top of the stack. Speaker order, methodology pointer, and TURN_START framing all follow the active mode. Closing-down state is per-stack-frame conceptually but currently lives at session level — if you push a nested scene, clear the parent's closing countdown first (`glass turn clear-handoff` does NOT clear it; just `glass scene closing-down --turns 0` won't work either since it requires positive turns; manually edit the JSON if needed). Practically: don't push a nested scene during a closing parent. Close the parent first.

Don't reach for nesting casually — most scene shifts are better as plain transitions (end the old scene, start the new). Nest only when the parent scene is genuinely paused and will resume after the inner scene completes.

## Quest beats — what's worth logging

`glass quest beat <text>` appends a tagged bullet to `shared/quest-log.md`. The log is party-visible canon; the corpus consumes it.

A beat is a real story-shifting moment:

- An NPC's allegiance flips, dies, or reveals something material.
- A clock lands.
- A faction makes a public move.
- A character commits — pledges, betrays, declares.
- The party gains or loses a meaningful asset (information, item, ally, location).

Not a beat:

- "Tev rolled poorly on perception."
- "The party walked across the square."
- "Sumi made a joke."

Two or three beats per scene is healthy. If a scene generates zero beats, either nothing happened or the DM didn't recognize what mattered — use the scene-end summary to capture it instead. If a scene generates eight beats, you're logging too much; keep the most important and let the rest live in the transcript.

The DM is the writer; players don't fire beats directly (use `glass msg instruction dm "I think this should be a beat: ..."` if you want to nominate one).

## Awarding XP

XP is the level-up currency: 10 XP per level, no max. The DM awards via `glass character award-xp` (with `--reason`) or, more commonly, bundled into `glass scene end --xp`.

### Per-scene baseline

Award **1-3 XP per character** at scene end, calibrated to:

- **1 XP** — a quiet scene with little for the character to do, or a scene where the character was largely a bystander.
- **2 XP** — a normal scene with meaningful participation.
- **3 XP** — a scene where the character drove a major beat, took serious risk, or had a strong character moment.

Different characters in the same scene can get different amounts. Don't flatten — XP is a signal of what the table noticed.

### Spot awards

Outside scene-end, give **+1 XP** for:

- A breakthrough on a high-stakes roll.
- A clever solution that bypassed the obvious approach.
- Persistent good RP of an inconvenient trait (the character's flaw genuinely cost them, and the player leaned in anyway).
- A character moment that the table will remember.

Spot awards are rare — once or twice per session per player at most. Use `glass character award-xp <id> 1 --reason "<one-line>"`.

### Calibration

10 XP/level + 1-3 XP/scene means a level takes roughly 5-10 scenes. That's the right pace for a feature unlock or HP bump to feel earned. If players are leveling every 2 scenes you're awarding too much; if they're not leveling for 15 scenes you're awarding too little.
