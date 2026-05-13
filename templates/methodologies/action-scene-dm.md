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
3. Run `glass beat check`. If the scene has no scene clock or no active beat,
   fix that before continuing active play. When opening or reframing a scene,
   declare at least one scene clock and start the first beat.
4. Resolve pending clarifications and checks fairly. Use `glass roll`,
   `glass scene pressure`, tracker/clock movement, or a clearly deterministic
   move for opposition, hazards, NPCs, and DM-side PC checks. Do not ask a
   player for a roll when the DM can resolve it on this turn.
5. Take one DM action: opposition move, environmental change, clock tick,
   consequence, reveal, route change, social pressure shift, or answer that hands
   the acting player back into the flow.
6. Persist changed state before prose. Use `glass scene tracker`, `glass scene
   pressure`, `glass clock`, `glass character`, and `glass table write/append`
   for the state they own. Use named table artifacts for reusable visible lore,
   and use `glass lore promote`/`glass lore upsert` when action-scene facts
   become durable. If the scene creates a portable asset that can matter later,
   make it concrete and persist it with the owning command when someone takes
   it. Update notes, entities, hooks, or quest beats when needed. Commit authored
   markdown with `glass sync apply`.
7. Keep the endpoint honest. Advance or complete the declared pressure; do not
   add one more twist solely to extend the action scene. Do not reroll
   initiative after action order exists unless intentionally restarting the
   order.
8. Write concise public prose to the `TURN.md` path from TURN_START.
9. Run `glass turn audit`, then end with `glass turn end`. Include position and pressure changes when they
   changed, or none/unchanged when they did not.

Required closeout shape:

```bash
glass turn audit
glass turn end \
  --summary "<opposition/environment/action result and live next pressure>" \
  --state "<table/tracker/clock/character/lore updates or no state change>" \
  --rolls "<rolls/pressure used, or none with brief reason>" \
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

Narration craft (read before writing public prose):
[`how-to/narration-craft-dm.md`](../how-to/narration-craft-dm.md). Action
scenes especially: commit to the line, advance the board, resolve to a
new state. Negative-space narration kills action pacing.
