---
title: Scene Play Player Methodology
status: authored
audience: players
applies_to_modes: [scene-play]
---

# Scene Play - Player

Scene play is free-form exploration, conversation, investigation, and downtime.
This sequence is binding for every full player turn.

1. Run `glass check`. It drains unread messages and prints the live scene
   clock/beat contract for this turn.
2. Read the immediate board: `table/`, the active scene summary, recent turn
   summaries in TURN_START, your character state, and any public clocks or
   trackers named in the scene.
3. Treat the listed scene clock and active beats as the live dramatic contract
   for this turn. If there is no active scene clock or no
   active beat after completed beats, treat that as a closure gap: make one
   decisive blockbuster-scale contribution if you have one, otherwise pass with
   a table-visible cue, and end with `--next dm`. Do not start a replacement
   beat from a player turn unless the DM explicitly instructed it. If the check
   says a beat is near or at 10/10, resolve it, close it, convert it, or pass;
   do not open a fourth beat.
4. Decide whether another actor needs durable bus traffic from you before your
   prose lands. If your turn changes another actor's options, risks, consent,
   plan, or likely next action, send at least one narrow message now:
   `banter` for offers/warnings/relationship pressure, `table-talk` for
   party-visible coordination, `instruction` for explicit asks or handoffs,
   `plot-hint` for clue/suspicion flags, or `secret` for DM-only material.
5. Choose one contribution that changes the scene: a decision, action, offer,
   refusal, discovery attempt, cost accepted, concrete question, or visible
   local detail your character can act on.
6. Resolve uncertainty before prose. If a discovery attempt, social push,
   technical read, risky concealment, or contested interpretation has real
   stakes, use `glass roll` or `glass scene pressure` unless the table already
   makes the answer obvious. If your action is not covered by an existing
   skill on your sheet and you have a free skill slot (cap `3 + level`), pass
   a new specific skill name to the roll command and it will auto-declare at
   `fool`. See [`srd/skill-advancement.md`](../srd/skill-advancement.md). If
   hidden information is required before the action is valid, send the DM one
   clear message and end with `--next dm` plus `--open-question`. On `stall`,
   `regress`, or `collapse`, make the result move play: record a visible cost,
   worse position, narrowed choice, beat movement, or scene clock tick, or name
   that consequence in `glass done`.
7. Persist any durable player-side changes before prose: character state,
   inventory, messages, public/secrets/notes/journal edits, or note proposals.
   When your character takes, spends, receives, breaks, or keeps a meaningful
   portable asset, use the inventory command that owns it. Commit authored
   markdown with `glass sync apply`.
8. Write public turn prose to the `TURN.md` path from TURN_START. Put the visible
   story beat first. Keep OOC process notes brief and only include what another
   actor or viewer needs.
9. Run `glass done`. Follow any
   closure-gap or completed-beat guidance from the audit. Include the compact continuity summary,
   what durable state changed or `no state change`, rolls/checks used or `none`,
   the formal `--turn-type`, and `--next default` unless an override is
   required. `pass` is valid only for a short visible yield and also requires
   `--state "no state change"` plus `--rolls none`.

Required closeout shape:

```bash
glass done \
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
committed or explicitly reported as unchanged, and `glass done` reports
`valid: true`.

Optional reference: [`how-to/scene-play-reference.md`](../how-to/scene-play-reference.md).

Narration craft (read before writing public prose):
[`how-to/narration-craft-player.md`](../how-to/narration-craft-player.md).
The methodology drives the turn; the craft doc covers the slop attractors
the methodology does not. Commit, advance, resolve.
