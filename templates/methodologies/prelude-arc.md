---
title: Prelude Arc Methodology
status: authored
audience: dm
applies_to_modes: [prelude]
---

# Prelude Arc

Run the prelude as exactly two scenes: one normal scene, then one action scene.
It is a shakedown and calibration arc, not the main campaign. Campaign
planning should already have created the `prelude` arc shell.

## Sequence

1. **Read the party, campaign foundation, and prelude shell.**
   - `glass character bulk-get --all`
   - `glass summary show campaign`
   - `glass lore list`
   - Read `context.md`, `shared/lore/organization.md`,
     `players/*/public/intro.md`, `players/*/public/relationships.md`, and
     `players/*/signature-moves.md`.
   - Read `arcs/prelude/plan.md` and `arcs/prelude/context.md`.

2. **Ensure the prelude arc is ready.**
   - Normal path: `glass arc activate prelude`.
   - If `prelude` is missing, create it with `glass arc create prelude ...`,
     write its plan/context, and then activate it.
   - Refine `arcs/prelude/plan.md` or `arcs/prelude/context.md` only if the
     character-creation outcome requires it.
   - Commit with `glass sync apply arcs/prelude`.

3. **Stage Scene 1 as normal scene play.**
   - `glass scene create prelude-opening --type scene-play --arc prelude`
   - Write `prep.md`, `context.md`, `summary.md`, and the active table.
   - Scene 1 still needs an active antagonist or antagonistic force and concrete
     physical danger, coercion, pursuit, or harm-facing pressure. It can begin
     as scene play, but it cannot be only orientation, paperwork, or an
     institutional briefing.
   - Use `glass table write scene.md --body "<visible scene start>"`.
   - Use `glass table write <meaningful-slug>.md --body "<visible artifact>"`
     for each reusable public lore item the prelude puts on screen.
   - `glass sync apply arcs/prelude/scenes/prelude-opening`
   - `glass mode start scene-play prelude-opening`
   - Declare at least one scene-specific clock with
     `glass scene clock declare <clock-id> --label ... --goal ... --value 0 --max <n> --direction progress|countdown --visibility public|dm`.
   - Start the first beat with
     `glass beat start <beat-id> --clock <clock-id> --label ... --question ...`.
   - Run `glass beat check` and do not finish the prelude turn until the new
     scene shows a live clock and beat.

4. **Run Scene 1 to a real consequence.**
   - Use normal scene-play methodologies.
   - The DM may call `glass scene closing-down --turns <n>` when the scene has
     entered final exchange.
   - Before ending, follow `methodologies/closeout.md`.
   - End with `glass scene end --summary "<summary>" --outcome "<outcome>"`.

5. **Stage Scene 2 as action.**
   - `glass scene create prelude-action --type action --arc prelude`
   - Write `prep.md`, `context.md`, `summary.md`, and the active table.
   - Scene 2 must put bodies in danger on screen. The action can be combat,
     chase, rescue, disaster response, coercive standoff, escape, or another
     action-movie pressure, but not a procedural dispute.
   - Create public trackers or clocks before the first action turn.
   - `glass sync apply arcs/prelude/scenes/prelude-action`
   - `glass mode start action prelude-action`
   - Declare at least one scene-specific clock with
     `glass scene clock declare <clock-id> --label ... --goal ... --value 0 --max <n> --direction progress|countdown --visibility public|dm`.
   - Start the first beat with
     `glass beat start <beat-id> --clock <clock-id> --label ... --question ...`.
   - Run `glass beat check` and do not finish the prelude turn until the new
     action scene shows a live clock and beat.
   - Establish order with `glass turn initiative`.
     The DM is always included in the roll, even when a custom participant
     list is used.

6. **Run Scene 2 to a resolved impact.**
   - Use action-scene methodologies.
   - Make the final consequence visible with `glass scene end --summary ... --outcome ...`.
   - Apply HP, consequences, inventory, clocks, or tracker changes with CLI
     commands before close.

7. **Close the prelude arc.**
   - Follow `methodologies/closeout.md` Act Close Sequence.
   - `glass summary write arc prelude --body "<what the prelude changed>"`
   - `glass summary append campaign --body "<campaign-facing fallout>"`
   - Update `shared/quest-log.md` or `shared/party-knowledge.md` if players
     should carry a visible result forward.
   - `glass arc close prelude --summary "<prelude summary>" --outcome "<durable outcome>"`

8. **Handoff to active campaign play.**
   - Activate the main opening arc with `glass arc activate <main-arc>`.
   - Start the active-campaign bridge before closeout. If the first main scene
     is not fully staged yet, run `glass mode start scene-prep <main-arc>-setup`
     so Mara has a concrete next turn to stage it. If the first scene is
     already staged, start its actual play mode instead.
   - Do not close the turn with an active main arc and no active mode.
   - Name the time jump in `TURN.md`.
   - Run `glass turn audit`.
   - Run `glass turn end --summary "prelude complete and main arc bridge staged" --state "<summaries/arc/quest/mode state updated>" --rolls "<rolls/checks or none>" --scene-status ended --next default`.
   - Run `glass mode end` for the old prelude/scene modes before starting
     `scene-prep` or the next actual play mode.

## Hard Limits

- Exactly two scenes.
- No main-campaign climax.
- No third scene.
- No hidden reveal that invalidates player prelude choices.
- No unresolved close on the visible prelude pressure.

## CLI Encoding Opportunities

These are not commands yet:

- `glass prelude create` for arc scaffold plus the two required scene shells.
- `glass prelude check` for exactly two scenes, summaries, outcomes, arc close,
  and main-arc activation.
