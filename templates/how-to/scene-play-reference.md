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
`tev -> sumi -> renno -> kit -> dm`. `glass_done(next_speaker="default")` keeps that
flow. Set `next_speaker="<agent-id>"` only for a real interrupt,
clarification, or direct handoff.

The DM can still use these MCP tools:

```text
glass_turn_rapid_round(prompt="your character's immediate reaction")
glass_turn_restart_order(agent_id="tev")
glass_turn_clear_handoff()
```

Rapid rounds are for moments, not replacing normal scene play.

## Closure

Scenes need explicit closure. Start closing when the stake is resolved, the
party clearly leaves or commits, a clock lands, the scene has yielded what it
can, or recent turns keep revisiting the same choices without changing them.

For longer scenes, use `glass_scene_closing_down(rounds=N)`, then a final
rapid round, then follow `methodologies/closeout.md` and call
`glass_scene_transition(next_scene_id="<next-scene-id>", kind="new", ...)`.
This canonical scene boundary tool closes the current scene and stages the next
in one call. Partial outcomes are fine; the core tension should not end as
unknown.

## Scene Clocks

The primary scene clock is usually the party objective, not only a bad thing
filling up. Use `polarity="objective"` for that clock. Add a separate
`polarity="threat"` or `polarity="timer"` clock when an antagonist, hazard, or
deadline moves independently.

Use `glass_scene_clock_tick(clock_id="<clock-id>", delta=<delta>, outcome="<why>")` when a
meaningful success, failure, DM move, or beat resolution changes one of those
clocks.

Ordinary `glass_roll(...)` calls in active play should use
`target_id="<active-beat-id>"`. Failed outcomes tick that beat's failed-roll
pressure. At two failed rolls the beat closes and the DM takes the next handoff;
the next DM move should offer a fresh route toward the same scene goal, not a
newly named retry of the same obstacle.

## Nested Scenes

Use a nested action scene only when the parent scene is genuinely paused and
will resume (a burst of violence inside a social scene, a flashback, a brief
sub-encounter). `glass_scene_transition(kind="nested", ...)` pushes the
sub-scene on top of the current one without closing it; the parent's scene
clocks and beats stay live underneath. Pop back with
`glass_scene_transition(next_scene_id="<parent-id>", kind="return", ...)` when
the sub-scene resolves:

```text
glass_scene_transition(
  next_scene_id="vestige-square-fight",
  kind="nested",
  scene_type="action",
  arc_id="<arc>",
  new_mode="action",
)
# play the nested action scene
glass_scene_transition(
  next_scene_id="<parent-scene-id>",
  kind="return",
  summary="<closing summary for the nested scene>",
  outcomes=["<outcome>"],
  xp="tev=2,sumi=2,renno=2,kit=2",
  carry_clocks=["<id>=<reason>"],
  retire_clocks=["<id>=<reason>"],
)
```

Most scene shifts are cleaner as `kind="new"` (close-and-replace) rather than
nested. Use nested only when the parent's tension genuinely resumes.

## Quest Beats and XP

Use `glass_quest_beat(text="<public beat>")` for public story-shifting
moments: allegiance changes, clock consequences, faction moves, commitments,
or meaningful assets gained/lost. Two or three beats per scene is healthy.

At scene end, 3-4 XP per participating character is the baseline. Use 3 XP for
a completed scene and 4 XP when the scene carried major danger, sacrifice,
discovery, or arc-changing consequence.

Add focused bonus XP when a character resolves a beat in an interesting way that
increases scene momentum and has strong narrative weight. Usually this is +1 XP
to the character most responsible; use +2 only for a scene-defining turn. The
DM includes those bonuses in the `xp` value for `glass_scene_transition(...)`
(or `glass_scene_end(...)` if the scene is closing without a successor, e.g.
right before `glass_arc_close(...)`).
