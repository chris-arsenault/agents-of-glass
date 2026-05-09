---
title: Scene Play Methodology
status: authored
audience: players, dm
applies_to_modes: [scene-play]
---

# Scene Play

The active mode for free-form scenes — exploration, conversation, investigation, downtime. The DM has framed the scene; you're inside it. This is *the table is rolling*: act, react, ask, decide, narrate.

For action-shaped scenes (combat, chase, social pressure), separate methodologies will apply when those modes exist. This doc is for everything else.

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

- **Drain the bus.** First action of every turn (covered by the always-present TURN_START reminder): `glass msg read --since-checkpoint`. Read what's there. Respond to anything that needs a reply.
- **Look at the world.** Read `shared/lore/`, the scene framing file, recent transcript turns, your character file, other PCs' `players/<id>/public/intro.md`. Open whatever images, maps, or notes are relevant.
- **Decide what your character is doing.** Pick an action, a stance, a line of inquiry, an attempt at something.
- **Take any rolls you decide are needed.** *You* call your rolls; the DM doesn't (see below).
- **Send messages.** Side-channel via the bus: `glass msg banter <pc>` for IC asides, `glass msg secret dm <intent>` to flag hidden-from-party intent, `glass msg instruction party <plan>` for OOC coordination. Multiple is fine — batch them.
- **Ask the DM questions.** Anything you need clarified about the world, the scene, or what your character would know goes through the bus: `glass msg secret dm "<question>"`. Multiple questions in one turn is fine. The DM will respond on their next turn.
- **Write your turn narration.** End by writing IC prose to `<TURN_OUTPUT>` describing what your character did, what was visible to others, and the outcomes of any rolls in narrative form. The dice and message sends already left their own audit trails in the DB; this prose is the *story moment* that the rest of the party will read in the transcript. Tight is good — a paragraph or three.
- **Optional handoff.** Run `glass turn handoff <agent_id>` if the next agent should not be next-in-rotation.

You don't have to do all of these every turn. You don't have to do them in this order. The list is a menu.

## The inversion: you call your own rolls

The traditional "DM tells you to make a check" pattern is reversed here. **Players call their own rolls.**

- If your character is doing something with a real chance of failure, run the roll yourself: `glass roll <skill> <attribute> --risk <level> --character <id>`.
- The risk level is your judgment call:
  - `controlled` — easy / unattended / you've got time
  - `standard` — the default
  - `risky` — active opposition or pressure
  - `desperate` — last-chance / under threat / no margin
- When in doubt, pick lower. The DM will overrule if hidden knowledge demands otherwise.
- Skill choice and attribute choice are also yours. Pick the combination that actually fits what you're doing. If you don't have the skill listed on your sheet, the roll uses `fool` (-2) — that's the system telling you the action is harder for someone untrained.
- The roll's outcome is what it is. Narrate around it. A `regress` doesn't mean nothing happened — it means something specific went wrong. Make the failure interesting.

**The DM only intervenes when hidden knowledge would invalidate the roll** — e.g., the lock you're picking is enchanted in a way that changes the attribute, the door you're listening at is one-way and your roll reveals nothing useful, the patrol you're sneaking past has a tuner with them and `attunement` is the relevant attribute instead of `finesse`. **This should be rare.** Most of your rolls stand as called.

If the DM does push back (they'll do it via `glass msg secret <you>`), take the correction in stride. Re-roll with different parameters or narrate around the outcome. Don't litigate.

## What the DM does on their turn

The DM's job in scene play is roughly threefold: **respond, drive, plan.** Every DM turn does all three.

### Respond

- Drain the bus first (questions, secret intents, anything addressed to you).
- Reply to questions via `glass msg secret <player>` (or `glass msg plot-hint` for world-side nudges). Multiple replies in one turn is fine.
- If a question is urgent enough that a player needs to act before the rotation comes back to them, `glass turn handoff <player>` after responding so they get the next slot.

### Drive

- If the scene has stalled or a player has ended their turn open-endedly ("Tev approaches the door."), nudge them along: `glass msg instruction <player> "what do you do here?"` or `"the door is unlocked — what's your move?"`. The bus is the right channel; a turn of public prose just to ask "what do you do?" wastes the transcript.
- If something in the world should *happen* (an NPC speaks, time passes, a clock ticks, the lights go out), write that as transcript prose to `<TURN_OUTPUT>`. World-side observations are the rare case where the DM's turn is narrative.
- If you need rolls from any/all players, **roll them yourself** (see "DM-side roll inversion" below) — don't interrupt the player rotation just to ask for a check.

### Plan

Every DM turn should also include planning work. The agents only get one turn at a time, so use yours productively:

- Update `dm/scratchpad.md` with where the scene is heading, what the next beat is, what NPC reactions you're tracking.
- Add or refine entries in `dm/notes/` (NPCs, threads, hooks) as the scene reveals new specificity.
- Tick clocks in your tracking files if appropriate.
- Look ahead: what's the natural transition out of this scene? What lore might be relevant to what's coming? Pre-load those reads.
- If a player's secret message reveals hidden intent, file a note in `dm/secret/` about how you'll surface or undermine it later.

Plan even if the bus is empty and the rotation is fine. Idle DM turns are wasted DM turns.

## DM-side roll inversion

The same rule that gives players authority over their rolls applies to you: **don't interrupt a player turn just to ask for a check.** When you need a roll for a player's character — a perception check they didn't take, an opposed roll, a saving throw — run it yourself:

```bash
glass roll perception attunement --risk standard --character tev-pc-1
```

The roll's `actor` field will record that you (the DM) called it; the `character_id` attributes the result to the PC. Use the outcome to inform your own narration. If the player asks afterwards, tell them what they noticed.

Only fall back to "asking the player to roll" (via `glass msg instruction <player> "roll <skill> <attribute> at <risk>"`) when the *moment of the dice* is something the player should experience for the narrative tension — and even then, prefer scheduling them via the rotation rather than interrupting it.

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

The DM ends the mode (`glass mode end`) when the scene's natural arc completes. Closure signals can include:

- The scene's stake is resolved.
- The party has clearly decided to leave.
- A clock has run out and the consequence has landed.
- The scene has yielded everything it's going to.

After `glass mode end`, the orchestrator returns to whatever called scene-play (an arc loop, scene-transition logic, or the operator).

Players don't end the mode — that's the DM's call. If you think the scene is done, fire `glass msg secret dm "I think we're done here"` and let the DM decide.
