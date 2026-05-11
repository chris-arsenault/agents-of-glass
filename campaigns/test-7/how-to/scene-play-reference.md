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
`tev -> sumi -> renno -> kit -> dm`. `glass turn end --next default` keeps that
flow. Use `--next <agent-id>` only for a real interrupt, clarification, or
direct handoff.

The DM can still use:

```bash
glass turn rapid-round "your character's immediate reaction"
glass turn restart-order tev
glass turn clear-handoff
```

Rapid rounds are for moments, not replacing normal scene play.

## Closure

Scenes need explicit closure. Start closing when the stake is resolved, the
party clearly leaves or commits, a clock lands, the scene has yielded what it
can, or recent turns keep revisiting the same choices without changing them.

For longer scenes, use `glass scene closing-down --rounds N`, then a final
rapid round, then follow `methodologies/closeout.md` and call `glass scene end`.
Partial outcomes are fine; the core tension should not end as unknown.

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

At scene end, 1-3 XP per character is the baseline: 1 for quiet participation,
2 for meaningful participation, 3 for major risk or a memorable character beat.
Spot awards are rare and should have a clear reason.
