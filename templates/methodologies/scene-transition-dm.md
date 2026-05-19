---
title: Scene Transition DM Methodology
status: authored
audience: dm
applies_to_modes: [scene-play, action]
---

# Scene Transition - DM

This is the DM scene-boundary turn while the current act continues. Close the
old scene, stage the next one, queue player cleanup, and leave actual play
ready to resume. The canonical command for the boundary itself is
`glass scene transition` — it closes the current scene and creates+enters the
next one in a single atomic call. Do not chain `glass scene end` +
`glass scene create` + `glass mode start` for this; that path is recovery-only.

1. Run `glass check` to drain unread messages and inspect current scene state.
2. Read the immediate boundary state: `table/`, active scene summary, recent turn
   summaries in TURN_START, public trackers/clocks, scene prep/context, and any
   directly implicated DM notes or lore.
3. Run [`closeout.md`](closeout.md) through its scene close steps. That gives
   you the summary, outcome, beats, XP totals, and scene-clock dispositions
   you will pass to `glass scene transition` below.
4. Run `glass arc close-check <arc-id>` and record the arc decision in
   closeout: `continue`, `close`, or `reframe`. If the arc is ready to close,
   do not stage another scene by default; follow the Act Close Sequence.
5. Plan the next scene before running the transition command. Write the next
   scene's context/prep, write the current visible situation into
   `table/scene.md`, and create named table artifacts for reusable visible
   lore. The next scene prep must name the scene verb, active antagonist
   move, concrete physical danger to people, primary problem family,
   variation note versus the last two scenes, three interactable scene toys,
   why the party's default extraction/load-path/proof answer is insufficient
   or costly, the objective clock, 2-3 starting beats across distinct
   problem lanes, and the threat/timer clock if any. Use
   [`how-to/problem-families.md`](../how-to/problem-families.md) when choosing
   the family. If the last two scenes lacked danger, fighting, coercion,
   pursuit, or another harm-facing pressure, the next scene must open with
   one. If the last two scenes used the same location or same location
   family, the next scene must substantially move somewhere physically
   different.
6. Commit authored markdown with `glass sync apply`, covering the next scene
   directory, `table/`, and any changed DM notes, lore, or shared files.
7. Run the atomic transition. `glass scene transition <next-scene-id> --new`
   closes the current scene with the summary/outcome/beats/xp/clock
   dispositions, creates the new scene record, and pushes its `scene-play` or
   `action` mode frame. Use labels like combat, chase, travel, or
   social-pressure as the scene `--type`, not as modes:

   ```bash
   glass scene transition <next-scene-id> --new \
     --type <problem-family> \
     --arc <arc-id> \
     --new-mode scene-play \
     --summary "<closing scene summary>" \
     --outcome "<durable outcome>" \
     --beats "<party-visible beat>" \
     --xp tev=3,sumi=3,renno=3,kit=3 \
     --carry-clock <id>=<reason> \
     --retire-clock <id>=<reason>
   ```

   - `--new` is the kind to use for closing-and-opening at the same stack
     level. Use `--nested` only when a sub-scene runs on top of the current
     one without closing it (action burst, flashback). Use `--return
     <parent-id>` to close a nested scene and pop back to a parent.
   - Every active scene clock on the closing scene must have an explicit
     `--carry-clock <id>=<reason>` or `--retire-clock <id>=<reason>` (or be
     resolved during play). The command refuses to close otherwise.
8. Declare the new scene's scene clock(s) and start the opening beats:

   ```bash
   glass scene clock declare <objective-clock-id> \
     --label "..." --goal "..." --value 0 --max <n> \
     --direction progress --polarity objective --visibility public
   glass beat start <beat-id> \
     --clock <objective-clock-id> --label "..." --question "..."
   glass beat start <second-beat-id> \
     --clock <objective-clock-id> --label "..." --question "..."
   ```

   Normal objective clocks usually use max 6-8. Use max 4 only for a brief,
   tightly bounded scene. Closing a normal beat should usually move a clock
   by 1; use 2 only for a major scene-shifting breakthrough after setup or
   coordination. Optionally add a threat/timer clock if the antagonist
   pressure or a deadline needs its own clock.
9. Run `glass thread current`. If a long-game callback fits, make it one
   concrete visible mark, object, NPC behavior, damage pattern, phrase,
   route, faction resource, or repeated method. If that callback advances
   the campaign spine, run `glass thread advance <thread-id> --note
   "<concrete visible beat>"`.
10. Queue one cleanup turn for each player with `glass next housekeeping-round`.
11. Write public transition prose to the `TURN.md` path from TURN_START:
    closure of the old scene first, then the visible board for the next
    scene.
12. Run `glass done` with `--scene-status ended --next default`.

## Done

Your turn is done only when `glass scene transition` succeeded (closing the
old scene and opening the new mode atomically), the new scene's scene clock
and 2-3 active beats are live, `table/` shows the next visible situation
and artifacts, player housekeeping turns are queued, public prose exists,
and `glass done` succeeds.

Do not complete a scene transition into a purely procedural/legal scene.
Claims, records, receipts, audits, and chain-of-custody problems can be
present only if they are attached to an antagonist move and a physical
danger the players can act against.

Do not complete a scene transition into a third consecutive scene in the
same location or location family. A new desk, counter, office, corridor
segment, checkpoint, bench, or document station in the same site is not
enough.
