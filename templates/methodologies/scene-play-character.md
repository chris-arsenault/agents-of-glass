---
title: Scene Play Character Methodology
status: authored
audience: players
applies_to_modes: [scene-play]
---

# Scene Play - Character Branch

Scene play here is active in-fiction play from the character-facing workspace.
This sequence is binding for every full player turn in the character branch.

1. Drain unread messages with `glass msg read --since-checkpoint`.
2. Read the immediate board: `table/`, the active scene summary, recent turn
   summaries in TURN_START, your character state, and any public clocks or
   trackers named in the scene.
3. Run `glass beat check`. Treat the listed scene clock and active beats as the
   live dramatic contract for this turn. If there is no active scene clock or no
   active beat after completed beats, treat that as a closure gap: make one
   decisive blockbuster-scale contribution if you have one, otherwise pass with
   a table-visible cue, and end with `--next dm`. Do not start a replacement
   beat from a player turn unless the DM explicitly instructed it. If the check
   says a beat is near or at 10/10, resolve it, close it, convert it, or pass;
   do not open a fourth beat.
4. Decide whether another actor needs durable in-character bus traffic from you
   before your prose lands. If your turn changes another actor's options,
   risks, consent, plan, or likely next action, send at least one narrow
   message now: `banter` for offers/warnings/social pressure, `table-talk` for
   party-visible coordination, `instruction` for explicit asks or handoffs,
   `plot-hint` for clue/suspicion flags, or `secret` for DM-only material.
   Prefer character ids from the TURN_START recipient roster; do not guess ids.
   Use `glass character bulk-get --all` if you need to confirm one.
5. Choose one contribution that changes the scene: a decision, action, offer,
   refusal, discovery attempt, concrete question, or visible local detail this
   character can act on.
6. Resolve uncertainty before prose. If a discovery attempt, social push,
   technical read, risky concealment, or contested interpretation has real
   stakes, use `glass roll` or `glass scene pressure` unless the table already
   makes the answer obvious. If hidden information is required before the action
   is valid, send the DM one clear message and end with `--next dm` plus
   `--open-question`.
7. Persist any durable character-side changes before prose: character state,
   inventory, messages, or `players/<id>/secrets/` edits. Commit authored
   markdown with `glass sync apply`.
8. Write public turn prose to the `TURN.md` path from TURN_START. Put the
   visible story beat first. Keep process notes brief and only include what
   another actor or viewer needs.
9. Run `glass turn audit`, then end the turn with `glass turn end`. Follow any
   closure-gap or completed-beat guidance from the audit. Include the compact continuity summary,
   what durable state changed or `no state change`, rolls or checks used or
   `none`, the formal `--turn-type`, and `--next default` unless an override
   is required. `pass` is valid only for a short visible yield and also
   requires `--state "no state change"` plus `--rolls none`.

Required closeout shape:

```bash
glass turn audit
glass turn end \
  --summary "<what changed, what is now live, or what choice was made>" \
  --state "<durable updates or no state change>" \
  --rolls "<rolls/checks used or none>" \
  --turn-type "<act|answer|support|pass>" \
  --next default
```

Use `--open-question "<question>"` for any unresolved question the next actor
must see. Players do not run scene closeout; if the scene seems complete or the
clock/beat contract is empty, hand the turn to the DM with `--next dm`.

## Done

Your turn is done only when the public prose exists, durable updates are
committed or explicitly reported as unchanged, and `glass turn end` reports
`valid: true`.

Optional reference: [`how-to/scene-play-reference.md`](../how-to/scene-play-reference.md).

Narration craft (read before writing public prose):
[`how-to/narration-craft-player.md`](../how-to/narration-craft-player.md).
