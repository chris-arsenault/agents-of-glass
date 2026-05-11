---
title: Prelude Arc Methodology
status: authored
audience: dm
applies_to_modes: [prelude]
---

# Prelude Arc

The prelude is the first thing the finished player characters do together. It
is the campaign's first on-screen incident: a short first mission, job, crisis,
summons, accident, or encounter that shows who these people are together.

Your job is not to start the main campaign at full speed. Your job is to run a
short, decisive prelude: one normal scene, one action scene, then a clear time
jump into the main campaign.

## Purpose

The prelude should:

- give the PCs a concrete reason to act together now
- bring each player's voice, secret pressure, relationship, or signature move
  on screen at least once
- establish how the party's organization feels in actual play
- create one consequence, obligation, ally, scar, or question that can survive
  the time jump
- show action-scene pressure with a visible endpoint and honest tracker

The prelude is allowed to have consequences. It should not decide the campaign's
central question, burn the main antagonist, or lock the party into a path before
real play starts.

## Command Discipline

When this methodology shows a `glass` command, execute it during the turn. Do
not paste command lines into your public prose. The public prose should describe
what the table sees; the command audit trail records the state change.

The prelude coordinator is DM-only. You must hand control into actual table
play before ending any prelude setup turn: start `scene-play`, start `action`,
queue player turns, or end the prelude. If the campaign remains in bare
`prelude` with no queued player turns, the run is invalid.

## Read First

1. Your persona.
2. `context.md`, `summary.md`, and `dm/foundation.md`.
3. `players/*/public/intro.md`, `players/*/public/relationships.md`, and
   `players/*/signature-moves.md`.
4. The party organization at `shared/lore/organization.md`.
5. The planned opening arc, if one exists, at `arcs/<arc>/plan.md`.
6. [`scene-prep.md`](scene-prep.md), [`scene-play.md`](scene-play.md), and
   [`action-scene.md`](action-scene.md).
7. [`instructions/table.md`](../instructions/table.md),
   [`instructions/output-contract.md`](../instructions/output-contract.md),
   [`srd/action-scenes.md`](../srd/action-scenes.md), and
   [`srd/pressure.md`](../srd/pressure.md).

## Required Shape

Exactly two scenes:

1. **Normal scene** using `scene-play`.
2. **Action scene** using `action`.

Do not add a third scene. If the second scene reveals something interesting,
write it as a hook or summary beat and carry it into the post-prelude time jump.

The normal scene should be a low-friction situation where all PCs can speak,
show one habit, and make one meaningful choice. One full table round plus a DM
turn is often enough. Start closing as soon as the party has made a shared
decision or revealed a useful conflict.

The action scene should pressure that choice immediately. It can be combat,
chase, social pressure, escape, disaster, heist, or any other action shape. It
must have a player-visible endpoint and at least one honest tracker. Two or
three action rounds is the target. Use a small tracker: usually 3-6 segments or
an HP/resistance value that can resolve fast.

Hard invariant: the prelude can leave hooks and hidden mysteries, but the
visible crisis must not close on an unknown. If the party partially succeeds or
fails, assign the consequence and impact before ending the scene or arc.

## Build the Arc

Before creating the prelude, check and remember the current main opening arc:

```bash
glass arc current
```

Scaffold a dedicated prelude arc:

```bash
glass arc create prelude
```

Populate `arcs/prelude/plan.md` with only these sections:

- **Prelude promise** — what this first incident should reveal about the party
  in play.
- **Normal scene** — locale, starting pressure, who is present, what choice the
  party can make now.
- **Action scene** — pressure source, public endpoint, tracker shape,
  resistance if any, and what failure looks like.
- **Character spotlights** — one short line per PC naming what this prelude
  gives them room to show.
- **Time jump** — what can be skipped after the prelude if the campaign
  continues, and which main arc should become active after the jump.
- **Exit criteria** — what must be true before you end the prelude mode.

Populate `arcs/prelude/context.md` with what the characters know at the start.
Keep it short. This is not an onboarding essay.

## Scene 1: Normal Scene

Scaffold and frame the first scene:

```bash
glass scene create prelude-opening --type scene-play --arc prelude
```

Write the player-facing scene framing in `arcs/prelude/scenes/prelude-opening/context.md`.
Write the visible board in `table/scene.md` and `table/index.md`.
The visible board is exactly the player-agent table directory, not the DM's
notes or graph state.

Then start play:

```bash
glass mode start scene-play prelude-opening
```

Run the scene tightly. Use the table to prevent repeat clarification. When the
scene has produced a shared decision, a conflict, or a clear next pressure,
follow [`closeout.md`](closeout.md), then close it:

```bash
glass scene end --summary "..." --outcome "..." --beats "..."
glass mode end
```

## Scene 2: Action Scene

Scaffold the second scene from the first scene's consequence:

```bash
glass scene create prelude-action --type action --arc prelude
```

Write the action layout to `table/scene.md` and the current board to
`table/index.md`. Include:

- where everyone is
- what is happening right now
- the public endpoint
- public tracker(s)
- known resistance, HP, distance, suspicion, morale, or other numeric pressure

Start action mode and roll initiative:

```bash
glass mode start action prelude-action
glass turn initiative
```

Use [`action-scene.md`](action-scene.md). Keep turns short. Do not add a twist
after the tracker resolves. Follow [`closeout.md`](closeout.md), then close the
scene when the endpoint resolves:

```bash
glass scene end --summary "..." --outcome "..." --beats "..."
glass mode end
```

## Time Jump and Handoff

After the action scene, write a short prelude wrap in your final `prelude` mode
turn:

- update the arc summary with `glass summary write arc prelude --body "..."`
- append any campaign-level continuity with
  `glass summary append campaign --body "..."`
- update `shared/quest-log.md` if a beat should remain player-visible
- write a durable DM workspace note with your read on party chemistry, friction,
  standout hooks, and what should carry forward
- name the time jump if the campaign continues: hours, days, weeks, or "after
  training / repair / fallout"
- reactivate the main opening arc if one exists:

```bash
glass arc activate <main-opening-arc>
```

The time jump should move the party to the actual opening campaign situation.
It may leave scars, obligations, allies, or reputation from the prelude. It
should not require a third prelude scene.

## Hard Limits

- Exactly two scenes.
- One normal scene, then one action scene.
- No main-campaign climax.
- No extensive lore lecture.
- No new long arc spawned inside the prelude.
- No hidden "real plot" that invalidates the players' prelude choices.
- No third scene. Summarize and jump.
- No unresolved close on the prelude's core tension. Hidden mysteries can
  survive; the visible crisis must receive consequence and impact.

## Done Criteria

End the `prelude` mode only when:

- both scenes have ended with `glass scene end`
- both scene modes have ended with `glass mode end`
- the prelude arc summary says what happened and what remains true
- the prelude arc has 1-2 in-universe outcome bullets via `glass arc close`
- `summary.md` or `shared/quest-log.md` carries any campaign-visible fallout
- a durable DM workspace note records party chemistry, friction, standout hooks, and
  carry-forward concerns
- the final turn names the time jump into the main campaign

Follow [`closeout.md`](closeout.md) for the act closeout first. Then call:

```bash
glass arc close prelude --summary "..." --outcome "..."
glass mode end
```

If play exposes serious campaign or character friction, write it plainly in the
prelude wrap and still end the mode. Treat that friction as table knowledge for
the campaign's next step, not as a reason to add a third prelude scene.
