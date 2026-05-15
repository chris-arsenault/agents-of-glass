---
title: Scene Transition DM Methodology
status: authored
audience: dm
applies_to_modes: [scene-play, action, combat, chase, social-pressure]
---

# Scene Transition - DM

This is the DM scene-boundary turn while the current act continues. Close the
old scene, stage the next one, queue player cleanup, and leave actual play ready
to resume.

1. Run `glass check` to drain unread messages and inspect current scene state.
2. Read the immediate boundary state: `table/`, active scene summary, recent turn
   summaries in TURN_START, public trackers/clocks, scene prep/context, and any
   directly implicated DM notes or lore.
3. Run [`closeout.md`](closeout.md) through its scene close steps and execute
   `glass scene end` with summary, outcome, beats, and XP/reward values.
4. End the old mode with `glass mode end`.
5. Run `glass arc close-check <arc-id>` and record the arc decision in closeout:
   `continue`, `close`, or `reframe`. If the arc is ready to close, do not stage
   another scene by default; follow the Act Close Sequence.
6. Create and stage the next scene when the arc continues. Use
   `glass scene create <next-scene> --type <problem-family>`, write the next
   scene's context/prep, write the current visible situation into
   `table/scene.md`, and create named table artifacts for reusable visible lore.
   The next scene prep must name the scene verb, active antagonist move, concrete
   physical danger to people, primary problem family, variation note versus the
   last two scenes, three interactable scene toys, why the party's default
   extraction/load-path/proof answer is insufficient or costly, the objective
   clock, 2-3 starting beats across distinct problem lanes, and the
   threat/timer clock if any. Use
   [`how-to/problem-families.md`](../how-to/problem-families.md) when choosing the
   family. If the last two scenes lacked danger, fighting, coercion, pursuit, or
   another harm-facing pressure, the next scene must open with one. If the last
   two scenes used the same location or same location family, the next scene must
   substantially move somewhere physically different.
7. Run `glass thread current`. If a long-game callback fits, make it one concrete
   visible mark, object, NPC behavior, damage pattern, phrase, route, faction
   resource, or repeated method. If that callback advances the campaign spine,
   run `glass thread advance <thread-id> --note "<concrete visible beat>"`.
8. Commit authored markdown with `glass sync apply`, covering the next scene
   directory, `table/`, and any changed DM notes, lore, or shared files.
9. Start the next scene mode with `glass mode start
   <scene-play|action|combat|chase|social-pressure> <next-scene>`.
10. Declare the next scene objective clock, declare a separate threat/timer clock
    only if needed, and start 2-3 active beats across distinct problem lanes.
    Normal objective clocks usually use max 6-8. Use max 4 only for a brief,
    tightly bounded scene. Closing a normal beat should usually move a clock by
    1; use 2 only for a major scene-shifting breakthrough after setup or
    coordination.
11. Queue one cleanup turn for each player with `glass next housekeeping-round`.
12. Write public transition prose to the `TURN.md` path from TURN_START: closure
    of the old scene first, then the visible board for the next scene.
13. Run `glass done` with `--scene-status ended --next default`.

Required command sequence:

```bash
glass scene end \
  --summary "..." \
  --outcome "..." \
  --beats "..." \
  --xp tev=3,sumi=3,renno=3,kit=3
glass mode end
glass arc close-check <arc-id>
glass scene create <next-scene> --type <problem-family>
glass thread current
glass scene clock declare <objective-clock-id> \
  --label "..." \
  --goal "..." \
  --value 0 \
  --max <n> \
  --direction progress \
  --polarity objective \
  --visibility public
glass beat start <beat-id> \
  --clock <objective-clock-id> \
  --label "..." \
  --question "..."
glass beat start <second-beat-id> \
  --clock <objective-clock-id> \
  --label "..." \
  --question "..."
glass sync apply arcs/<arc>/scenes/<next-scene> table
glass mode start <scene-play|action|combat|chase|social-pressure> <next-scene>
glass next housekeeping-round \
  --previous-scene <closed-scene> \
  --next-scene <next-scene> \
  --next default
glass done \
  --summary "<old scene closed; next scene staged>" \
  --state "<scene/table artifacts/notes/lore updates>" \
  --rolls "<rolls/checks used or none>" \
  --scene-status ended \
  --next default
```

## Done

Your turn is done only when the old scene is closed, the next scene mode is
active, `table/` shows the next visible situation and artifacts, player housekeeping turns are
queued, public prose exists, and `glass done` succeeds.

Do not complete a scene transition into a purely procedural/legal scene. Claims,
records, receipts, audits, and chain-of-custody problems can be present only if
they are attached to an antagonist move and a physical danger the players can
act against.

Do not complete a scene transition into a third consecutive scene in the same
location or location family. A new desk, counter, office, corridor segment,
checkpoint, bench, or document station in the same site is not enough.
