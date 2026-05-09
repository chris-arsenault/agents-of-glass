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

Default order is round-the-table players, then the DM (`tev → sumi → renno → kit → dm → tev → ...`). At the **end of your turn** you can override who goes next with:

```bash
glass turn handoff <agent_id>
```

One-shot — applies to the next turn only, then the round-robin resumes from the redirected agent. Use this to:

- Call the DM with an urgent question (`glass turn handoff dm`).
- Pass focus to a PC who's clearly in the spotlight.
- Hand back to whoever was mid-action when the DM was interrupted.

Don't reach for it casually — most scenes flow fine through the default rotation. If you don't call `handoff`, the orchestrator picks next-in-line.

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

## What the DM does in scene play

When the DM is up, they typically:

- Drain the bus (questions, secret intents, anything addressed to them).
- Respond to questions on the bus — usually via `glass msg secret <player>`, sometimes by writing a transcript turn that delivers world-side observations (an NPC speaks, the building shakes, time passes, a clock ticks).
- Update the scene framing if the situation has shifted.
- Hand off to whichever PC is in focus, or back to the round-robin.

The DM rarely takes a *narrative* turn unless the world is doing something the players need to see. Most DM turns are short — service the bus, hand off.

## Closing the scene

The DM ends the mode (`glass mode end`) when the scene's natural arc completes. Closure signals can include:

- The scene's stake is resolved.
- The party has clearly decided to leave.
- A clock has run out and the consequence has landed.
- The scene has yielded everything it's going to.

After `glass mode end`, the orchestrator returns to whatever called scene-play (an arc loop, scene-transition logic, or the operator).

Players don't end the mode — that's the DM's call. If you think the scene is done, fire `glass msg secret dm "I think we're done here"` and let the DM decide.
