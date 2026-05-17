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
2. Run `glass check`. Treat the listed scene clock and active beats as the
   live dramatic contract for this turn. If a beat is near or at 10/10, land
   it, close it, convert it, or pass; do not open a fourth beat.
3. Choose movement or position first: where you are, what you close with, what
   cover/leverage/route/social angle you take, or why position is unchanged.
4. Choose one action that changes leverage, target state, progress, risk, or the
   next actor's choice. When a carried asset, scene object, document, tool,
   route, or local affordance gives the action a concrete method, put it to
   work.
5. If your move changes another actor's immediate options, understanding,
   consent, or likely next action, leave the durable bus traffic now before
   prose. Use `banter` for offers/warnings/social pressure, `table-talk` for
   party-visible coordination, `instruction` for explicit asks or handoffs,
   `plot-hint` for clue/suspicion flags, or `secret` for DM-only material.
6. Resolve uncertainty before prose. Use `glass roll` for checks and `glass
   scene pressure` when reducing a tracker/target. In action scenes, uncertain
   consequential actions normally roll, apply pressure, or change a visible
   tracker; `rolls none` fits deterministic action, pure positioning, or setup.
   If your action is not covered by an existing skill, roll it as an improvised
   `fool` skill. Add `--save-skill` only when that skill should become durable
   and a slot is available (cap `3 + level`). See
   [`srd/skill-advancement.md`](../srd/skill-advancement.md). Do not hand off
   just to ask the DM to choose dice for you. If a hidden fact is required
   before you can act, message the DM and end with `--next dm` plus
   `--open-question`. On `stall`, `regress`, or `collapse`, make the result
   move play: record a visible cost, worse position, narrowed choice, beat
   movement, or scene clock tick, or name that consequence in `glass done`.
7. Persist allowed hard state before prose: character state, inventory,
   consequences you are allowed to view, messages, notes, or proposals. Commit
   authored markdown with `glass sync apply`.
8. Write concise public prose to the `TURN.md` path from TURN_START: movement,
   action, roll result or visible consequence, and the new immediate position.
9. Run `glass done`. In action scenes, include `--position`,
   `--pressure`, and the formal `--turn-type`. `pass` is valid only for a
   short visible yield and also requires `--state "no state change"` plus
   `--rolls none`.

Required closeout shape:

```bash
glass done \
  --summary "<action taken and immediate result>" \
  --state "<durable updates or no state change>" \
  --rolls "<rolls/pressure used or none>" \
  --turn-type "<act|answer|support|pass>" \
  --position "<new position or unchanged>" \
  --pressure "<tracker/HP/clock change or none>" \
  --next default
```

## Done

Your turn is done only when the action is resolved as far as your authority
allows, public prose exists, and `glass done` reports `valid: true`.

Optional reference: [`how-to/action-scene-reference.md`](../how-to/action-scene-reference.md).

Narration craft (read before writing public prose):
[`how-to/narration-craft-player.md`](../how-to/narration-craft-player.md).
Action scenes especially: commit to the line, advance the board, resolve
to a new state. Negative-space narration kills action pacing.
