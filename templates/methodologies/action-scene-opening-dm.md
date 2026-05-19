---
title: Action Scene Opening DM Methodology
status: authored
audience: dm
applies_to_modes: [action]
toolkit_examples: [combat, chase, social-pressure, escape, duel, infiltration, disaster, heist]
---

# Action Scene Opening - DM

This is the DM layout turn before action order exists. Establish the actionable
board, create visible pressure, roll action order, and exit.

1. Run `glass check` to drain unread messages and inspect current scene state.
2. Read `table/`, the active scene summary, recent turn summaries in TURN_START,
   and any DM notes, lore, NPCs, opposition, or hazard files needed for the
   immediate board.
3. Declare the scene objective clock and start 2-3 active beats across
   distinct problem lanes if they are not already live for this scene. Use
   `glass scene clock declare ...` with `--polarity objective` for the party
   objective, and `glass beat start ...` before continuing active play.
4. Run `glass check`. If the scene still has no active clock or beat, fix
   that before writing the board.
5. Establish the visible board: positions, stakes, exit condition, opposition,
   hazards/routes/leverage, public tracker shape, and any visible HP/effects
   players need for decisions.
6. Persist the board before prose. Write visible position and stakes into
   `table/scene.md`; create/update named table artifacts for visible reusable
   lore; create public trackers with `glass scene tracker`; update character,
   clock, lore, note, entity, hook, or quest-beat state that already changed.
   Commit authored markdown with `glass sync apply`.
7. Roll and persist action order with `glass turn initiative`.
8. Write concise public prose to the `TURN.md` path from TURN_START: the threat,
   positions, visible objective, and what the action order means on screen.
9. Run `glass done`. Include position and
   pressure changes when they changed, or none/unchanged when they did not.

Required closeout shape:

```bash
glass done \
  --summary "<action board established and live first pressure>" \
  --state "<table/tracker/clock/character/lore updates or no state change>" \
  --rolls "<initiative plus any checks used or none>" \
  --position "<starting positions or unchanged>" \
  --pressure "<tracker/HP/clock setup or none>" \
  --next default
```

## Done

Your turn is done only when the table and public trackers show the actionable
board, action order exists, public prose exists, and `glass done` succeeds.

Optional reference: [`how-to/action-scene-reference.md`](../how-to/action-scene-reference.md).
