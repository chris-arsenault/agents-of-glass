---
title: Scene and Act Closeout Methodology
status: authored
audience: dm
applies_to_modes: [scene-play, action, arc-creation, scene-prep, intermission]
---

# Scene and Act Closeout

Run this before `glass scene transition` (the canonical scene boundary command,
for closing the current scene and staging the next one) or `glass arc close`
(when the act is also ending). Every step must produce either a durable update
or an explicit "no change" in `glass done --state`.

## Scene Close Sequence

1. **Read the closing state.**
   - `glass scene current`
   - `glass summary show scene <scene-id> --arc <arc-id>`
   - `glass find --mode turns --scene <scene-id>`
   - `glass clock list --scope scene --anchor <scene-id> --all`
   - `glass scene tracker list --all`
   - `glass character bulk-get --all`
   - Read active `table/`, scene `prep.md`, and scene `context.md`.

2. **Name the scene answer.**
   - Write one sentence naming what the scene proved, cost, changed, or left
     materially unstable.
   - Do not close on "unclear" or "to be decided" for the scene's core tension.
   - Do not make the scene answer primarily "the party proved what happened."
     Remember the action consequence first: who was saved, who was hurt, what
     changed hands, what place became unsafe, what enemy adapted, what
     relationship shifted, or what choice now costs more. Proof can be part of
     the answer; it should not become the spine of every answer.

3. **Apply hard state.** Work through every subsection below, and name the
   answer for each in `glass done --state`. "No change" is a valid answer; an
   unanswered subsection is not.

   3a. **Clocks and trackers.** Run `glass clock list --scope scene --anchor
   <scene-id> --all`, `glass clock list --scope arc --anchor <arc-id> --all`,
   and `glass scene tracker list --all`. For each open clock or tracker, pick
   one: advance it (`glass clock tick`, `glass scene clock tick`, `glass scene
   tracker tick`), close it (`glass clock resolve`), retire obsolete pressure
   (`glass clock archive --note "<why>"`), or explicitly record in `--state`
   why fiction did not move it this scene.

   3b. **Items.** Walk the transcript for items the fiction marked as taken,
   permanently lost, destroyed, gained, or recovered. Use
   `glass character inventory-add` for items newly gained and
   `glass character inventory-rm` for items permanently removed. Do not
   invent status-suffix item ids; the CLI rejects them. Transient state
   (jammed, sealed, lent, expended) stays in scene prose.

   3c. **HP and momentum.** Use `glass character set-hp` and
   `glass character set-momentum` for changes the scene produced beyond what
   `glass roll` already applied. Roll-induced momentum is automatic; do not
   duplicate it.

   3d. **Graph.** Use `glass entity claim`, `link`, `unlink`, or
   `ratify-claim` for graph changes the scene introduced.

4. **Update authored continuity.**
   - `glass summary write scene <scene-id> --arc <arc-id> --body "<scene summary>"`
   - `glass summary append arc <arc-id> --body "<arc-relevant result>"` when
     the scene changed the arc.
   - `glass summary append campaign --body "<campaign-relevant result>"` when
     the scene changed campaign-level continuity.
   - Keep durable memory centered on what the action changed. Records, witnesses,
     tags, and evidence can appear as one consequence, but summaries should not
     repeatedly compress scenes into documentation, custody, public proof, or
     official undeniability.
   - If the scene advances a recurring symbol, antagonist method, faction move,
     NPC consequence, repeated harm pattern, or unresolved campaign question,
     update the long-game thread with
     `glass thread advance <thread-id> --note "<concrete visible beat>"`.
   - Commit notes/lore with `glass sync apply <paths>`.

5. **Update the public table and quest beats.**
   - If the final visible state matters for the next scene, update table files
     with `glass table write` or `glass table append`.
   - Add party-visible beats with `glass quest beat "<beat>"` or by passing
     `--beats` to `glass scene transition`.

6. **Prepare the scene close command.**
   - Create one or two outcome bullets. They must be in-universe facts, not DM
     commentary.
   - XP applies after every scene. Award 3 XP to each participating character
     for a completed scene, or 4 XP when the scene carried major danger,
     sacrifice, discovery, or arc-changing consequence.
   - Add focused bonus XP for characters who resolved a beat in an interesting
     way that increased scene momentum and carried strong narrative weight.
     Usually this is +1 XP to the character most responsible; use +2 only for a
     scene-defining turn. Include these bonuses in the `--xp` totals.
   - Do not use `0` XP for a participating character unless they were absent
     from the scene or did only housekeeping.
   - Prepare any reward/state commands.

7. **Close the scene and stage the next one in one atomic command.**
   `glass scene transition` is the canonical scene boundary command. It
   closes the current scene (writing summary, applying outcomes, awarding
   XP, archiving the table) and creates+enters the next scene's play mode
   in a single call. Every active scene clock on the closing scene must
   have an explicit disposition or the command refuses: either tick
   remaining clocks to resolution during play with
   `glass scene clock tick`, or pass `--carry-clock <id>=<reason>` when
   the pressure continues beyond this scene, or `--retire-clock <id>=<reason>`
   when the clock is obsolete or was resolved by fiction without a tick.
   Each clock may carry only one disposition. Dispositions are written
   into the scene summary so the reasoning carries forward.

```bash
glass scene transition <next-scene-id> --new \
  --type <problem-family> \
  --arc <arc-id> \
  --summary "<compact scene summary for the closing scene>" \
  --outcome "<durable outcome>" \
  --beats "<party-visible beat>" \
  --xp tev=3,sumi=3,renno=3,kit=3 \
  --carry-clock cinder-cascade="Pressure follows the party to the docks" \
  --retire-clock bloom-edge="Cordon Twelve held; threat dissolved in fiction"
```

   `--new` is the right kind for closing-and-opening at the same stack
   level. Use `--nested` for a sub-scene that runs on top of the current
   (action burst, flashback) without closing it; use `--return
   <parent-id>` to close a nested scene and pop back to a parent.

   If the act is also ending, use `glass scene transition --return` or
   `glass scene end` (low-level, recovery) to close the current scene
   without staging a successor, then run the Act Close Sequence.

8. **Stage what follows before ending the DM turn.**
   - Run `glass arc close-check <arc-id>` and choose an arc decision:
     `continue`, `close`, or `reframe`. Record that decision and reason in
     `glass done --state`.
   - If the visible arc pressure is resolved or transformed, continue with the
     Act Close Sequence instead of staging another scene by default.
   - If the act remains open, the `glass scene transition --new` call above
     has already staged + entered the next scene; queue `glass next
     housekeeping-round` to schedule cleanup turns.
   - Before staging the next scene, check the last two scene summaries. If they
     did not include danger, fighting, coercion, pursuit, or another physically
     harmful pressure, the next scene must course-correct with one at the
     opening.
   - Also check the last two scene locations. If they used the same location or
     same location family, the next scene must substantially move the table to a
     different physical environment.
   - The next scene must name an active antagonist or antagonistic force and the
     concrete physical danger to people.
   - The next scene must also name its scene verb, primary problem family,
     variation note versus the last two scenes, three interactable scene toys,
     why the party's default extraction/load-path/proof answer is insufficient
     or costly, objective clock, and threat/timer clock if any.
   - Run `glass thread current`. If the scene or closeout advances a recurring
     symbol, antagonist method, faction move, NPC consequence, repeated harm
     pattern, or unresolved campaign question, use
     `glass thread advance <thread-id> --note "<concrete visible beat>"`.
   - If the act is complete, continue with the Act Close Sequence.

## Act Close Sequence

1. **Read all act material.**
   - `glass arc close-check <arc-id>`
   - `glass summary show arc <arc-id>`
   - `glass find --mode turns --scene <scene-id>` for each major scene if needed.
   - `glass clock list --scope arc --anchor <arc-id> --all`
   - Read `arcs/<arc>/plan.md`, `context.md`, and scene summaries.

2. **Name the act answer.**
   - One sentence: what the act resolved or transformed.
   - Hidden mysteries can remain hidden; the act's visible pressure cannot
     close as unknown.

3. **Apply lasting state.**
   - Resolve or archive act clocks.
   - Apply cross-scene consequences, rewards, obligations, debts, route
     changes, faction relationship shifts, or inventory changes with CLI
     commands where available.
   - Update recurring NPC/location/faction notes with `glass sync apply`.

4. **Update continuity.**
   - `glass summary write arc <arc-id> --body "<act summary>"`
   - `glass summary append campaign --body "<campaign-level fallout>"`
   - Update `shared/quest-log.md` or `shared/party-knowledge.md` if players
     should carry the result forward.
   - Promote one or two long-game beats when the arc created a recurring symbol,
     antagonist method, faction move, NPC consequence, repeated harm pattern, or
     unresolved campaign question. Use
     `glass thread advance <thread-id> --note "<concrete visible beat>"` and
     keep the note table-visible or campaign-actionable, not abstract mystery.

5. **Close the arc.**

```bash
glass arc close <arc-id> \
  --summary "<compact act summary>" \
  --outcome "<durable act outcome>"
```

6. **Start the next lifecycle mode.**
   - If the campaign needs player planning, start or let lifecycle enter
     intermission.
   - If the next scene is already known and player planning is not needed,
     start `scene-prep`.
   - Do not leave a newly active arc with no active mode. If an arc is active
     after this turn, either start `scene-prep`, start the staged scene's
     actual play mode, or close that arc too.

7. **Close the turn.**
   - Write `TURN.md` with the public closure and handoff.
   - Run `glass done --summary "<scene/act closed and next mode staged>" --state "<closeout commands/files updated>" --rolls "<rolls/checks or none>" --scene-status ended --next default`.

## Prohibitions

- Do not close a scene on final narration alone.
- Do not leave hard state only in prose.
- Do not end an open act with no active mode and no staged next scene.
- Do not write player journals for them.

## CLI Encoding Opportunities

These are not commands yet:

- `glass scene close-check` for unresolved trackers, missing summary, missing
  outcomes, stale table, and open act handoff.
