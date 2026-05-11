---
title: Action Scene Methodology
status: drafted
audience: players, dm
applies_to_modes: [action]
toolkit_examples: [combat, chase, social-pressure, escape, duel, infiltration, disaster, heist]
---

# Action Scene

Action scenes are quickfire rounds for contested moments: combat, chases,
dangerous escapes, social pressure, disasters, heists, trials, duels, and any
other scene where every turn changes the situation. They use the same basic
table loop as scene play, but the turn order is tighter, fictional time moves in
seconds instead of hours or days, and players should expect to choose rolls more
often because more actions have immediate consequences.

Recent turn narration is not embedded in TURN_START. During action scenes, the
active scene summary is the compact continuity surface: append 2-4 sentences or
bullets at the end of your turn with `glass summary append scene --body "..."`
when the turn changes position, trackers, target state, intention, or the live
question for future actors. The DM may rewrite the scene summary between rounds
when it gets noisy.

Every action turn must move the scene toward its visible end condition. Move,
act, roll if you choose to roll, update the tracker or table when state changes,
then write the visible story beat. Conversation, hesitation, and defense are
valid actions only when they change leverage, position, risk, or the next
actor's choice.

Use shared narrative authority to keep action moving. If a reasonable local
detail would make your action concrete, author it and act: a loose cargo strap,
an open service hatch, a nervous courtier's glance, a cracked paving stone.
Do not spend the action asking the DM to invent every affordance. Do not use
that authority to erase opposition, contradict the table, open a new problem,
or move the scene's goal posts.

For the public rules, read [`srd/action-scenes.md`](../srd/action-scenes.md),
[`srd/checks.md`](../srd/checks.md),
[`srd/shared-narrative.md`](../srd/shared-narrative.md), and
[`srd/pressure.md`](../srd/pressure.md). This methodology is the turn sequence.

`combat`, `chase`, and `social-pressure` are **DM toolkit examples**, not a
formal or exhaustive list. Use them when they fit. Make up another pattern when
the narrative needs one.

## DM Toolkit Shelf

These are patterns that have worked before:

- **combat** — HP, morale, position, cover, exposure, routing.
- **chase** — distance, routes, obstacles, pursuer pressure, escape windows.
- **social-pressure** — concessions, suspicion, leverage, public support, who
  has the room.
- **escape / rescue / disaster** — evacuation progress, hazard clocks, who is
  still trapped, what route remains.
- **heist / infiltration** — alert clocks, objective progress, cover identity,
  patrol position, evidence left behind.

Do not force a scene into one of these names. Pick the tracker and pressure
shape that makes the fiction honest.

## Scene Entry

The DM starts the scene with a public opening layout before initiative:

- where everyone is, what is immediately visible, and what is in motion
- the stakes and exact player-visible exit condition
- the opposition or pressure source
- obvious hazards, cover, routes, leverage, or social fault lines
- the public tracker(s) that define progress, danger, or failure
- known HP/effects when the table needs them to make decisions

Write the kickoff layout to `table/scene.md` and keep the immediate board in
`table/index.md`. Use freeform markdown files at `table/` root for visible
short-term references players will need during the exchange: a named opponent's
visible condition, a route sketch in prose, the duke's current public posture,
or any other table state worth checking before asking for repetition. Use
`table/handouts/` only for in-game handouts.

Do not assume an NPC, monster, hook, graph entity, or DM note is on the player
table just because it exists elsewhere. For action play, if it affects player
decisions and is visible, put the visible state under `table/`.

Every action scene needs at least one honest tracker. Some trackers count up:
morale breaking, an alert clock filling, a gate opening. Some trackers are
pressure targets that count down: HP, the duke's resistance, distance to a
chase target, structural integrity, enemy nerve. Either way, the value must be
concrete enough that the players know what ending the scene means.

Examples:

- `enemy rout: 0/6` — fills when enemies are hurt, isolated, or frightened.
- `duke permission: 0/4` — fills when the party lands credible leverage.
- `escape distance: 0/6` opposed by `patrol alert: 0/4`.
- `gate opens: 0/3 rounds` while `crystal fire: 0/5` threatens the room.

Use `glass scene tracker` to keep the math honest. Command details live in
[`instructions/glass-cli.md`](../instructions/glass-cli.md).

```bash
glass scene tracker set enemy-rout --label "Enemy rout" --max 6
glass scene tracker tick enemy-rout 2
glass scene tracker list
```

For a pressure target, set the current value and any known resistance:

```bash
glass scene tracker set patrol-leader-hp --label "Patrol leader HP" \
  --value 8 --max 8 --resistance 1
```

After writing that layout, the DM rolls action order:

```bash
glass turn initiative
```

The command includes the DM in the order by default. That means the DM's next
turn after the opening layout may land early, late, or between players,
depending on the roll.

Use `glass turn initiative --participants tev,sumi,dm` only for smaller action
scenes where not every PC is actually in the exchange.

## Turn Shape

Each initiative turn has a strict menu:

- **Move.** Reposition, close distance, retreat, get cover, take a better social
  angle, shift lanes in a chase. If you think this is uncertain and
  consequential, call a roll.
- **Take one action.** Do one meaningful thing in the fiction. We are not strict
  about what counts as one action yet; keep it legible and proportional to a few
  seconds of in-world time.
- **Housekeeping.** Drain/respond on the message bus, check inventory, read
  the table, read relevant lore, inspect the character sheet, ask the DM a
  clarification. Housekeeping should support the turn, not become a second
  action. Use `glass search text` / `semantic` or `glass entity relations` /
  `between` when the needed context is already recorded. The verse phrase and
  tarot in TURN_START are only creative texture, not extra actions or mechanics.

Questions to the DM still work like normal scene play. Use the message bus for
clarifications that need a private or directed answer:

```bash
glass msg secret dm "Can I reach the gantry in one move from here?"
glass turn handoff dm
```

The DM answer is an interruption, not a new initiative slot. If the acting
player needs the answer before committing their action, the DM should hand back
to that player; after the handoff queue drains, initiative continues from the
next normal slot.

## Rolls

Follow [`srd/checks.md`](../srd/checks.md). Players call their own rolls on
their own turns. The DM rolls for NPCs, hazards, opposition, and DM-side PC
checks on DM turns. Do not hand off just to ask for dice.

## Pressure

Use pressure when an action should reduce a target's numeric value. The rules
are in [`srd/pressure.md`](../srd/pressure.md); the command shape is in
[`instructions/glass-cli.md`](../instructions/glass-cli.md).

Use `glass scene pressure` for the numeric part:

```bash
glass scene pressure patrol-leader-hp swordsman finesse \
  --risk risky --character tev-pc-1 --impact d8 \
  --bonus 1 --because "dueling saber in close quarters"
```

For social pressure or a chase, use the same command with a different skill,
target, and fiction:

```bash
glass scene pressure duke-resistance court-gossip presence \
  --risk standard --character sumi-pc-1 --impact d6 \
  --note "I imply the petition is already circulating among his rivals."
```

`--note` is not a rules object. It records fictional pressure or side effect so
the table can respond in prose.

## Inventory, Effects, and Signature Moves

Rules for inventory, effects, consequences, and signature moves are in
[`srd/character-state.md`](../srd/character-state.md). This methodology only
cares that action turns stay tight and the table reflects visible changes.
Favored weapons, instruments, apparatus, restraints, protective gear, and trade
tools are all valid ways to justify an action-scene angle when the fiction
supports them.

## Outcome Authority

The acting agent narrates the immediate visible outcome of their roll. The DM
owns durable world state:

- PC HP and inventory mutations go through `glass character ...`.
- NPC HP, enemy morale, chase clocks, social concessions, and persistent
  effects are tracked with `glass scene tracker` or `glass scene pressure` when
  players need the numbers to stay honest. Hidden trackers are fine, but at
  least one action-ending tracker should usually be public.
- Cross-scene pressure belongs in `glass clock`, not scene trackers: faction
  escalation, arc danger, antagonist plans, organization standing.
- Lasting PC fallout belongs in `glass character consequence-add`: injury,
  capture, separation, disgrace, gear strain, obligations, or anything else
  that should survive beyond the current exchange.
- If a player's narrated consequence overshoots the situation, the DM corrects
  it in their next turn and the correction stands.

Keep the prose short. Action scenes fail when every turn becomes a full scene
play turn with extra dice.

## DM Turns

On an initiative DM turn, do one of these:

- act for opposition or the environment
- answer pending clarifications and hand back to the current initiative flow
- update visible pressure: HP, effects, clocks, positions, routes, social
  leverage, who is exposed
- update `table/` when visible short-term state changed, especially if players
  would otherwise ask you to repeat it
- tick or revise `glass scene tracker` values when the math changed
- close or shift the scene if the action has resolved

DM turns are also quickfire. Do not reframe the whole scene every time. State
what changed, make any NPC/hazard rolls you control, mutate hard state, and get
out.

## Ending

End an action scene when its declared endpoint resolves: the enemy is defeated
or flees, the duke grants entry, the escape clock fills, the hazard clock lands,
or the tracker makes clear that the party cannot get what they wanted. Do not
add one more twist after the tracker says the scene is over.

If a PC is reduced to 0 HP, they are out of the action, not automatically dead.
The DM chooses the fictional consequence and records it if it should persist:

```bash
glass character consequence-add tev-pc-1 "Captured by the patrol" \
  --severity serious --scope arc
```

If the scene pauses but the parent scene should continue, `glass mode end`
returns to the parent mode. If the whole scene is over, use `glass scene end`
with summary, beats, and XP as usual.
