---
title: Scene Play Reference
target: player-dm
authority: optional-guidance
---

# Scene Play Reference

This preserves craft and control guidance that does not belong in the required
scene-play turn sequence.

## Speaker Controls

Default scene-play order is round-the-table players, then the DM:
`tev -> sumi -> renno -> kit -> dm`. `glass done --next default` keeps that
flow. Use `--next <agent-id>` only for a real interrupt, clarification, or
direct handoff.

The DM can still use:

```bash
glass next rapid-round "your character's immediate reaction"
glass next restart-order tev
glass next clear
```

Rapid rounds are for moments, not replacing normal scene play.

## Closure

Scenes need explicit closure. Start closing when the stake is resolved, the
party clearly leaves or commits, a clock lands, the scene has yielded what it
can, or recent turns keep revisiting the same choices without changing them.

For longer scenes, use `glass scene closing-down --rounds N`, then a final
rapid round, then follow `methodologies/closeout.md` and call `glass scene end`.
Partial outcomes are fine; the core tension should not end as unknown.

## Scene Clocks

The primary scene clock is usually the party objective, not only a bad thing
filling up. Use `--polarity objective` for that clock. Add a separate
`--polarity threat` or `--polarity timer` clock when an antagonist, hazard, or
deadline moves independently.

Use `glass scene clock tick <clock-id> <delta> --outcome "<why>"` when a
meaningful success, failure, DM move, or beat resolution changes one of those
clocks.

## Nested Scenes

Use a nested action scene only when the parent scene is genuinely paused and
will resume:

```bash
glass scene create vestige-square-fight --type action --arc <arc>
glass mode start action vestige-square-fight
# play the action scene
glass mode end
```

Most scene shifts are cleaner as ending the current scene and starting another.

## Quest Beats and XP

Use `glass quest beat <text>` for public story-shifting moments: allegiance
changes, clock consequences, faction moves, commitments, or meaningful assets
gained/lost. Two or three beats per scene is healthy.

At scene end, 3-4 XP per participating character is the baseline. Use 3 XP for
a completed scene and 4 XP when the scene carried major danger, sacrifice,
discovery, or arc-changing consequence.

Add focused bonus XP when a character resolves a beat in an interesting way that
increases scene momentum and has strong narrative weight. Usually this is +1 XP
to the character most responsible; use +2 only for a scene-defining turn. The
DM includes those bonuses in the `glass scene end --xp` totals.
