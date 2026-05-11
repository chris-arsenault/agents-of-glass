---
title: Scene Transition DM Methodology
status: authored
audience: dm
applies_to_modes: [scene-play, action, combat, chase, social-pressure]
---

# Scene Transition - DM

This is the DM scene-boundary turn while the current act continues. Close the
old scene, stage the next one, queue player cleanup, and leave actual play ready
to resume.

1. Drain unread messages with `glass msg read --since-checkpoint`.
2. Read the immediate boundary state: `table/`, active scene summary, recent turn
   summaries in TURN_START, public trackers/clocks, scene prep/context, and any
   directly implicated DM notes or lore.
3. Run [`closeout.md`](closeout.md) through its scene close steps and execute
   `glass scene end` with summary, outcome, beats, and XP/reward values.
4. End the old mode with `glass mode end`.
5. Create and stage the next scene. Use `glass scene create <next-scene> --type
   <protocol-or-toolkit-label>`, write the next scene's context/prep, and write
   the visible starting board into `table/scene.md` and `table/index.md`.
6. Commit authored markdown with `glass sync apply`, covering the next scene
   directory, `table/`, and any changed DM notes, lore, or shared files.
7. Start the next scene mode with `glass mode start <protocol-or-toolkit-label>
   <next-scene>`.
8. Queue one cleanup turn for each player with `glass turn housekeeping-round`.
9. Write public transition prose to the `TURN.md` path from TURN_START: closure of
   the old scene first, then the visible board for the next scene.
10. End with `glass turn end --scene-status ended --next default`.

Required command sequence:

```bash
glass scene end \
  --summary "..." \
  --outcome "..." \
  --beats "..." \
  --xp tev=0,sumi=0,renno=0,kit=0
glass mode end
glass scene create <next-scene> --type <protocol-or-toolkit-label>
glass sync apply arcs/<arc>/scenes/<next-scene> table
glass mode start <protocol-or-toolkit-label> <next-scene>
glass turn housekeeping-round \
  --previous-scene <closed-scene> \
  --next-scene <next-scene> \
  --next default
glass turn end \
  --summary "<old scene closed; next scene staged>" \
  --state "<scene/table/notes/lore updates>" \
  --rolls "<rolls/checks used or none>" \
  --scene-status ended \
  --next default
```

## Done

Your turn is done only when the old scene is closed, the next scene mode is
active, `table/` shows the next visible board, player housekeeping turns are
queued, public prose exists, and `glass turn end` succeeds.
