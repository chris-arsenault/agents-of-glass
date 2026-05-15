---
title: Scene Play DM Methodology
status: authored
audience: dm
applies_to_modes: [scene-play]
---

# Scene Play - DM

The DM turn in scene play responds to the table, drives the current pressure,
and maintains durable state. This sequence is binding for every full DM turn.

1. Run `glass check`. It drains unread messages and prints the live scene
   clock/beat contract for this turn.
2. Read the immediate board: `table/`, the active scene summary, recent turn
   summaries in TURN_START, public clocks/trackers, and any DM notes or lore
   directly implicated by the live scene question. Know the active antagonist
   and the concrete physical danger before writing.
3. If the scene has no scene clock or no active beat, first decide whether this
   is a closure gap. If the current scene question has truly landed after
   substantial resolved material, close or transition the scene. If you are
   continuing active play, restore the board with a scene clock and 2-3 active
   beats across distinct problem lanes. Do not take a full DM turn after every
   closed beat just to open one replacement beat.
4. Resolve pending player needs fairly. Answer clarifications through messages
   when the answer is private or directed. When the DM is resolving uncertain
   consequential opposition, hazard, NPC, or DM-side PC action, use `glass roll`
   or `glass scene pressure` when the rules fit; do not spend a handoff only to
   move dice. On `stall`, `regress`, or `collapse`, make the result move play:
   record a visible cost, worse position, narrowed choice, beat movement, or
   scene clock tick, or name that consequence in `glass done`.
5. Move the scene. Put a decision, consequence, NPC action, clock tick, offer,
   threat, reveal, or narrowed option into play. If the live frame is becoming
   only paperwork, logistics, or procedure, put something adventure-facing on
   screen: a vivid object, impossible behavior, strange creature, funny human
   tell, environmental turn, or practical affordance the players can use. A DM
   turn cannot be only recap or atmosphere. It also cannot be only legal,
   audit, claims, or chain-of-custody drama: make the antagonist act or show the
   physical harm their action is causing.
6. Persist changed state before prose. Use the hard-state command that owns the
   change: `glass table write/append scene.md` for the visible situation;
   `glass table write/append <meaningful-slug>.md` for any reusable visible
   lore artifact; `glass table use` when existing durable lore is now on screen;
   `glass lore promote` or `glass lore upsert` when table artifacts become
   durable canon; `glass scene tracker` or `glass scene pressure` for scene
   math; `glass clock` for cross-scene pressure; `glass character` for PC
   state; `glass quest beat` for story-shifting public beats; and
   `glass entity`/`glass note` for graph or note state. When a portable asset
   could matter later, offer it concretely and persist it if taken. Commit
   authored markdown with `glass sync apply`.
7. Keep the scene honest. Advance the live tension or narrow the board; do not
   add a new problem solely to keep the current frame alive. One closed beat is
   not a scene-closure signal; a mature scene usually has multiple active beats
   live and gives several players room to affect the same pressure before the
   DM closes or transitions it. An empty clock/beat contract after substantial
   resolved material is a closure signal. Do not make every turn a spectacle
   beat; calibrate to the fiction, but do not let restraint become the default
   answer. If two scenes have passed without danger, fighting, coercion,
   pursuit, or physical harm pressure, use the next DM opening or transition to
   course-correct. If two scenes have stayed in the same location or location
   family, the next transition must move somewhere substantially different.
8. Write public turn prose to the `TURN.md` path from TURN_START. Show what
   changed on screen and give the next actor a clear board.
9. Run `glass done`. Include summary, durable state changes,
   rolls/checks, and normal `--next default` unless an explicit override is
   needed.

Required closeout shape:

```bash
glass done \
  --summary "<what changed and what is live for the next actor>" \
  --state "<table/state/lore/notes/beats updated or no state change>" \
  --rolls "<rolls/checks used or none>" \
  --next default
```

Use `--next <player>` only when that player must act before normal rotation.
Use `glass next rapid-round "<prompt>"` for a short reaction from multiple
players to the same immediate stimulus.

## Done

Your turn is done only when visible table artifacts are current if they
changed, durable lore/notes/hooks/beats are updated when they changed, public
prose exists, and `glass done` succeeds.

Optional reference: [`how-to/scene-play-reference.md`](../how-to/scene-play-reference.md).

Narration craft (read before writing public prose):
[`how-to/narration-craft-dm.md`](../how-to/narration-craft-dm.md). The
methodology drives the scene; the craft doc covers the slop attractors
the methodology does not. Commit, advance, resolve.
