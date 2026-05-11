---
title: Action Scene DM Methodology
status: authored
audience: dm
applies_to_modes: [action, combat, chase, social-pressure]
toolkit_examples: [combat, chase, social-pressure, escape, duel, infiltration, disaster, heist]
---

# Action Scene - DM

Action scenes are quickfire contested moments with visible pressure. This
sequence is binding for every DM turn after action order exists.

1. Drain unread messages with `glass msg read --since-checkpoint`.
2. Read `table/`, public trackers, recent turn summaries, and any directly
   implicated DM notes, lore, NPCs, or hazard state.
3. Resolve pending clarifications and checks fairly. Roll for opposition,
   hazards, NPCs, and DM-side PC checks when required. Do not ask a player for a
   roll when the DM can resolve it on this turn.
4. Take one DM action: opposition move, environmental change, clock tick,
   consequence, reveal, route change, social pressure shift, or answer that hands
   the acting player back into the flow.
5. Persist changed state before prose. Use `glass scene tracker`, `glass scene
   pressure`, `glass clock`, `glass character`, and `glass table write/append`
   for the state they own. Update lore, notes, entities, hooks, or quest beats
   when the action scene creates durable facts. Commit authored markdown with
   `glass sync apply`.
6. Keep the endpoint honest. Advance or complete the declared pressure; do not
   add one more twist solely to extend the action scene.
7. Write concise public prose to the `TURN.md` path from TURN_START.
8. End with `glass turn end`. Include position and pressure changes when they
   changed, or none/unchanged when they did not.

Required closeout shape:

```bash
glass turn end \
  --summary "<opposition/environment/action result and live next pressure>" \
  --state "<table/tracker/clock/character/lore updates or no state change>" \
  --rolls "<rolls/pressure used or none>" \
  --position "<position/leverage update or unchanged>" \
  --pressure "<tracker/HP/clock change or none>" \
  --next default
```

Use `--next <player>` only when a clarification or interrupt must return to a
specific player before normal action order continues.

## Done

Your turn is done only when trackers/table/state reflect visible changes, any
durable behind-the-scenes changes are stored, public prose exists, and
`glass turn end` succeeds.

Optional reference: [`how-to/action-scene-reference.md`](../how-to/action-scene-reference.md).
