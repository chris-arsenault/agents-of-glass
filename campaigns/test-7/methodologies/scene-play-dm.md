---
title: Scene Play DM Methodology
status: authored
audience: dm
applies_to_modes: [scene-play]
---

# Scene Play - DM

The DM turn in scene play responds to the table, drives the current pressure,
and maintains durable state. This sequence is binding for every full DM turn.

1. Drain unread messages with `glass msg read --since-checkpoint`.
2. Read the immediate board: `table/`, the active scene summary, recent turn
   summaries in TURN_START, public clocks/trackers, and any DM notes or lore
   directly implicated by the live scene question.
3. Resolve pending player needs fairly. Answer clarifications through messages
   when the answer is private or directed. Roll DM-side PC checks yourself when
   the rules allow it; do not spend a handoff only to move dice.
4. Move the scene. Put a decision, consequence, NPC action, clock tick, offer,
   threat, reveal, or narrowed option into play. A DM turn cannot be only recap
   or atmosphere.
5. Persist changed state before prose. Use the hard-state command that owns the
   change: `glass table write/append` for visible short-term state, `glass
   scene tracker` or `glass scene pressure` for scene math, `glass clock` for
   cross-scene pressure, `glass character` for PC state, `glass quest beat` for
   story-shifting public beats, and `glass lore`/`glass entity`/`glass note` for
   durable canon, hooks, NPCs, factions, or locations. Commit authored markdown
   with `glass sync apply`.
6. Keep the scene honest. Advance the live tension or narrow the board; do not
   add a new problem solely to keep the current frame alive.
7. Write public turn prose to the `TURN.md` path from TURN_START. Show what
   changed on screen and give the next actor a clear board.
8. End the turn with `glass turn end`. Include summary, durable state changes,
   rolls/checks, and normal `--next default` unless an explicit override is
   needed.

Required closeout shape:

```bash
glass turn end \
  --summary "<what changed and what is live for the next actor>" \
  --state "<table/state/lore/notes/beats updated or no state change>" \
  --rolls "<rolls/checks used or none>" \
  --next default
```

Use `--next <player>` only when that player must act before normal rotation.
Use `glass turn rapid-round "<prompt>"` for a short reaction from multiple
players to the same immediate stimulus.

## Done

Your turn is done only when visible table state is current if it changed,
durable lore/notes/hooks/beats are updated when they changed, public prose
exists, and `glass turn end` succeeds.

Optional reference: [`how-to/scene-play-reference.md`](../how-to/scene-play-reference.md).
