---
title: Scene Play Player Methodology
status: authored
audience: players
applies_to_modes: [scene-play]
---

# Scene Play - Player

Scene play is free-form exploration, conversation, investigation, and downtime.
This sequence is binding for every full player turn.

1. Drain unread messages with `glass msg read --since-checkpoint`.
2. Read the immediate board: `table/`, the active scene summary, recent turn
   summaries in TURN_START, your character state, and any public clocks or
   trackers named in the scene.
3. Choose one contribution that changes the scene: a decision, action, offer,
   refusal, discovery attempt, cost accepted, concrete question, or visible
   local detail your character can act on.
4. Resolve uncertainty before prose. If the action is uncertain and
   consequential, use `glass roll` or `glass scene pressure` as allowed by the
   SRD. If hidden information is required before the action is valid, send the
   DM one clear message and end with `--next dm`.
5. Persist any durable player-side changes before prose: character state,
   inventory, messages, public/secrets/notes/journal edits, or note proposals.
   Commit authored markdown with `glass sync apply`.
6. Write public turn prose to the `TURN.md` path from TURN_START. Put the visible
   story beat first. Keep OOC process notes brief and only include what another
   actor or viewer needs.
7. End the turn with `glass turn end`. Include the compact continuity summary,
   what durable state changed or `no state change`, rolls/checks used or `none`,
   and `--next default` unless an override is required.

Required closeout shape:

```bash
glass turn end \
  --summary "<what changed, what is now live, or what choice was made>" \
  --state "<durable updates or no state change>" \
  --rolls "<rolls/checks used or none>" \
  --next default
```

Use `--open-question "<question>"` for any unresolved question the next actor
must see. Players do not end scenes; message the DM if the scene seems complete.

## Done

Your turn is done only when the public prose exists, durable updates are
committed or explicitly reported as unchanged, and `glass turn end` succeeds.

Optional reference: [`how-to/scene-play-reference.md`](../how-to/scene-play-reference.md).
