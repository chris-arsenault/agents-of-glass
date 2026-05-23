---
title: Action Scene Reference
target: player-dm
authority: optional-guidance
---

# Action Scene Reference

This preserves action-scene craft guidance that does not belong in the required
turn sequence.

## Toolkit Patterns

Use the clock or tracker shape that matches the fiction:

- combat: HP, morale, cover, exposure, routing
- chase: distance, routes, obstacles, escape windows
- social pressure: concessions, suspicion, leverage, public support
- escape/rescue/disaster: evacuation progress, hazard clocks, trapped people
- heist/infiltration: alert clocks, objective progress, patrol position

Do not force a scene into one of those labels. Name the visible endpoint honestly.

## Scene Clocks

The required scene clock is usually the party objective: what the characters
are trying to accomplish. Use `polarity="objective"` for that clock. Add a
separate `polarity="threat"` or `polarity="timer"` clock when an antagonist,
hazard, or deadline needs its own visible movement.

Scene clocks and pressure trackers are separate:

- Scene clocks show objective, threat, or timer movement for the scene.
- Scene trackers are roll-mediated pressure targets: HP, morale, resistance,
  distance, leverage, alert, or another numeric value that gets reduced by
  successful pressure.

The DM creates pressure targets with `glass_scene_tracker_set(...)`. Use
`glass_scene_pressure(...)` when a character action both rolls and reduces one
of those trackers. The pressure target is the tracker id from `glass_check()` or
`glass_scene_tracker_list()`.

Use `glass_scene_clock_tick(clock_id="<clock-id>", delta=<delta>, outcome="<why>")`
only for direct non-roll movement: a DM move, a beat close, a timer pulse, or a
visible consequence that does not need a roll.

Ordinary `glass_roll(...)` calls in active play should use
`target_id="<active-beat-id>"`. Failed outcomes tick that beat's failed-roll
pressure. At two failed rolls the beat closes and the DM takes the next handoff;
the next DM move should offer a fresh route toward the same scene goal, not a
newly named retry of the same obstacle.

## Character State

Use `glass_character_set_hp(...)` for HP changes and
`glass_character_consequence_add(...)` for lasting character fallout. Use
`glass_state_update(...)` for neutral continuity facts that are neither clock
movement nor character hard state.

## Outcome Authority

The acting agent narrates the immediate visible outcome of their roll. The DM
owns durable world state, scene repair, hidden fallout, and any correction when a
narrated consequence overshoots the table state. Players own public hard-state
updates for their own characters.

If a PC hits 0 HP, they are out of the action, not automatically dead. The DM
or owning player records the consequence if it should persist:

```text
glass_character_consequence_add(character_id="tev-pc-1", label="Captured by the patrol", severity="serious", scope="arc")
```
