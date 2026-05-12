---
title: Action Scene Player Methodology
status: authored
audience: players
applies_to_modes: [action, combat, chase, social-pressure]
---

# Action Scene - Player

Action scenes are quickfire contested moments. Fictional time is seconds or a
few heartbeats. This sequence is binding for every player initiative turn.

1. Read the action-order block in TURN_START, `table/`, public scene trackers,
   recent turn summaries, your character state, and any directly relevant public
   rules named by TURN_START.
2. Choose movement or position first: where you are, what you close with, what
   cover/leverage/route/social angle you take, or why position is unchanged.
3. Choose one action that changes leverage, target state, progress, risk, or the
   next actor's choice. When a carried asset, scene object, document, tool,
   route, or local affordance gives the action a concrete method, put it to
   work.
4. Resolve uncertainty before prose. Use `glass roll` for checks and `glass
   scene pressure` when reducing a tracker/target. In action scenes, uncertain
   consequential actions normally roll, apply pressure, or change a visible
   tracker; `rolls none` fits deterministic action, pure positioning, or setup.
   If your action is not covered by an existing skill and you have a free
   skill slot (cap `3 + level`), pass a new specific skill name to the roll
   command and it will auto-declare at `fool`. See
   [`srd/skill-advancement.md`](../srd/skill-advancement.md). Do not hand off
   just to ask the DM to choose dice for you. If a hidden fact is required
   before you can act, message the DM and end with `--next dm` plus
   `--open-question`.
5. Persist allowed hard state before prose: character state, inventory,
   consequences you are allowed to view, messages, notes, or proposals. Commit
   authored markdown with `glass sync apply`.
6. Write concise public prose to the `TURN.md` path from TURN_START: movement,
   action, roll result or visible consequence, and the new immediate position.
7. End with `glass turn end`. In action scenes, include `--position` and
   `--pressure` when they changed or explicitly say unchanged/none.

Required closeout shape:

```bash
glass turn end \
  --summary "<action taken and immediate result>" \
  --state "<durable updates or no state change>" \
  --rolls "<rolls/pressure used or none>" \
  --position "<new position or unchanged>" \
  --pressure "<tracker/HP/clock change or none>" \
  --next default
```

## Done

Your turn is done only when the action is resolved as far as your authority
allows, public prose exists, and `glass turn end` succeeds.

Optional reference: [`how-to/action-scene-reference.md`](../how-to/action-scene-reference.md).

Narration craft (read before writing public prose):
[`how-to/narration-craft-player.md`](../how-to/narration-craft-player.md).
Action scenes especially: commit to the line, advance the board, resolve
to a new state. Negative-space narration kills action pacing.
