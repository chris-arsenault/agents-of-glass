---
title: Action Scene Opening DM Methodology
status: authored
audience: dm
applies_to_modes: [action, combat, chase, social-pressure]
toolkit_examples: [combat, chase, social-pressure, escape, duel, infiltration, disaster, heist]
---

# Action Scene Opening - DM

This is the DM layout turn before action order exists. Establish the actionable
board, create visible pressure, roll action order, and exit.

1. Drain unread messages with `glass msg read --since-checkpoint`.
2. Read `table/`, the active scene summary, recent turn summaries in TURN_START,
   and any DM notes, lore, NPCs, opposition, or hazard files needed for the
   immediate board.
3. Establish the visible board: positions, stakes, exit condition, opposition,
   hazards/routes/leverage, public tracker shape, and any visible HP/effects
   players need for decisions.
4. Persist the board before prose. Write visible state into `table/scene.md` and
   `table/index.md`; create public trackers with `glass scene tracker`; update
   character, clock, lore, note, entity, hook, or quest-beat state that already
   changed. Commit authored markdown with `glass sync apply`.
5. Roll and persist action order with `glass turn initiative`.
6. Write concise public prose to the `TURN.md` path from TURN_START: the threat,
   positions, visible objective, and what the action order means on screen.
7. End with `glass turn end`. Include position and pressure changes when they
   changed, or none/unchanged when they did not.

Required closeout shape:

```bash
glass turn end \
  --summary "<action board established and live first pressure>" \
  --state "<table/tracker/clock/character/lore updates or no state change>" \
  --rolls "<initiative plus any checks used or none>" \
  --position "<starting positions or unchanged>" \
  --pressure "<tracker/HP/clock setup or none>" \
  --next default
```

## Done

Your turn is done only when the table and public trackers show the actionable
board, action order exists, public prose exists, and `glass turn end` succeeds.

Optional reference: [`how-to/action-scene-reference.md`](../how-to/action-scene-reference.md).
