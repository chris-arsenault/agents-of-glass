---
title: Action Scene Reference
target: player-dm
authority: optional-guidance
---

# Action Scene Reference

This preserves action-scene craft guidance that does not belong in the required
turn sequence.

## Toolkit Patterns

Use the tracker shape that matches the fiction:

- combat: HP, morale, cover, exposure, routing
- chase: distance, routes, obstacles, escape windows
- social pressure: concessions, suspicion, leverage, public support
- escape/rescue/disaster: evacuation progress, hazard clocks, trapped people
- heist/infiltration: alert clocks, objective progress, patrol position

Do not force a scene into one of those labels. Name the pressure honestly.

## Scene Clocks

The required scene clock is usually the party objective: what the characters
are trying to accomplish. Use `--polarity objective` for that clock. Add a
separate `--polarity threat` or `--polarity timer` clock when an antagonist,
hazard, or deadline needs its own visible movement.

Use `glass scene clock tick <clock-id> <delta> --outcome "<why>"` when a
meaningful success, failure, DM move, or beat resolution changes one of those
clocks.

## Trackers

Every action scene needs at least one concrete endpoint. Some trackers count up:
morale breaking, alert rising, a gate opening. Some count down: HP, resistance,
distance, structural integrity, nerve.

```bash
glass scene tracker set enemy-rout --label "Enemy rout" --max 6
glass scene tracker tick enemy-rout 2
glass scene tracker set patrol-leader-hp --label "Patrol leader HP" --value 8 --max 8 --resistance 1
```

## Pressure

Use `glass scene pressure` when an action reduces a numeric target:

```bash
glass scene pressure patrol-leader-hp swordsman finesse \
  --risk risky --character tev-pc-1 --impact d8 \
  --bonus 1 --because "dueling saber in close quarters"
```

The same command works for social pressure, chases, and hazards when the fiction
supports a numeric target.

## Outcome Authority

The acting agent narrates the immediate visible outcome of their roll. The DM
owns durable world state, tracker corrections, lasting PC fallout, and any
correction when a narrated consequence overshoots the table state.

If a PC hits 0 HP, they are out of the action, not automatically dead. The DM
chooses and records the consequence if it should persist:

```bash
glass character consequence-add tev-pc-1 "Captured by the patrol" --severity serious --scope arc
```
