---
title: Action Scene Character Methodology
status: authored
audience: players
applies_to_modes: [action, combat, chase, social-pressure]
---

# Action Scene - Character Branch

Action scenes are quickfire contested moments. Fictional time is seconds or a
few heartbeats. This sequence is binding for every player initiative turn in
the character branch.

1. Read the action-order block in TURN_START, `table/`, public scene trackers,
   recent turn summaries, your character state, and any directly relevant rules
   named by TURN_START.
2. Choose movement or position first: where you are, what you close with, what
   cover, leverage, route, or social angle you take, or why position is
   unchanged.
3. Choose one action that changes leverage, target state, progress, risk, or
   the next actor's choice.
4. Resolve uncertainty before prose. Use `glass roll` for checks and `glass
   scene pressure` when reducing a tracker or target. If a hidden fact is
   required before you can act, message the DM and end with `--next dm` plus
   `--open-question`.
5. Persist allowed hard state before prose: character state, inventory,
   messages, or `players/<id>/secrets/` edits. Commit authored markdown with
   `glass sync apply`.
6. Write concise public prose to the `TURN.md` path from TURN_START: movement,
   action, roll result or visible consequence, and the new immediate position.
7. End with `glass turn end`. In action scenes, include `--position` and
   `--pressure` when they changed or explicitly say unchanged or none.

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
