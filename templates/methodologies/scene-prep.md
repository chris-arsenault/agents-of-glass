---
title: Scene Prep Methodology
status: authored
audience: dm
applies_to_modes: [scene-prep]
---

# Scene Prep

Run this as a DM-only bridge into actual play. A scene-prep turn is complete
only after the next scene exists, the active table is written, the actual play
mode is started, any required active-play scene clock and 2-3 starting beats are
live, and `glass done` succeeds.

## Sequence

1. **Read state.**
   - `glass arc current`
   - `glass scene current`
   - `glass summary show campaign`
   - `glass summary show arc <arc-id>`
   - `glass thread current`
   - `glass find --mode turns --scene <previous-scene-id>` or `glass turns feed --after-turn <n>` when the previous scene matters.
   - Read `arcs/<arc>/plan.md`, `arcs/<arc>/context.md`, relevant `dm/notes/`,
     current `table/`, and [`how-to/problem-families.md`](../how-to/problem-families.md).

2. **Create the scene.**
   - Run `glass scene create <scene-slug> --type <problem-family> [--arc <arc>]`.
     Use a broad problem family from
     [`how-to/problem-families.md`](../how-to/problem-families.md), not the mode
     name and not the expected solution.
   - Run `glass scene current` and verify it points at the new scene.

3. **Import or register load-bearing lore.**
   - Use `glass lore search <query>` and `glass lore import <world-bible-path>`
     only when this scene surfaces new public canon.
   - Use `glass lore upsert <path>` after editing public lore files.

4. **Write `arcs/<arc>/scenes/<scene>/prep.md` in this order.**
   - Recap: why this scene exists now.
   - Scene verb: the table-facing action this scene asks for, such as cross,
     hold, bargain, escape, rescue, breach, contain, lure, expose, survive, or
     choose.
   - Problem family: one broad family from
     [`how-to/problem-families.md`](../how-to/problem-families.md), or a similarly
     broad label. This is the pressure shape, not the solution path. Include a
     variation note explaining how this differs from the last two scenes and
     what part of the party toolkit it pressures differently. Do not use
     "knowledge" as a family; knowledge is an output.
   - Strong start: what is immediately on screen.
   - Active antagonist move: who or what is opposing the party in this scene and
     what they are doing now. If not physically present, name the off-screen
     action already changing the scene.
   - Concrete danger: what physically harmful thing can happen to people in or
     because of this scene. Name the people, crowd, crew, district, or body at
     risk when possible.
   - Three interactable scene toys: objects, terrain, machines, creatures, routes,
     hazards, crowd features, vehicles, tools, unstable magic, or visible lore
     artifacts that players can touch, break, move, weaponize, bargain over, hide
     in, ride, reroute, or otherwise use.
   - Default-answer pressure: why the party's usual extraction/load-path/proof
     answer is insufficient, expensive, risky, or only partly useful here.
     Preserve their toolkit; change what it has to solve.
   - Paper-trail check: if records, witnesses, tags, legal authority, or proof
     matter, name the dangerous choice they create. The scene should not be about
     documenting that an adventure happened; it should be about what people risk
     because the fact is now leverage.
   - Adventure draw: what makes this scene worth playing as fantasy adventure
     rather than only a plausible incident, errand, claim, or logistics problem.
     This does not have to be spectacle, but it should give the table something
     vivid, strange, funny, dangerous, beautiful, gross, mythic, or physically
     playable to engage with.
   - Action-movie check: how this scene includes or points directly into danger,
     fighting, coercion, pursuit, disaster, intrusion, monster pressure, or
     another harm-facing situation. If the previous two scenes lacked that, this
     scene must open with it.
   - Location check: if the previous two scenes used the same location or same
     location family, this scene must substantially move the table somewhere
     physically different. A new counter, office, checkpoint, lane, bench, or
     document station in the same site does not count.
   - Possible directions: 3-5 plausible player routes.
   - NPCs in play.
   - Threats, creatures, antagonists, or pressure sources.
   - Named things in play.
   - Objective clock: the progress clock the players are trying to move. Normal
     scenes usually use max 6-8. Use max 4 only for a brief, tightly bounded
     scene.
   - Threat/timer clock, if any: what worsens independently when the antagonist,
     hazard, pursuit, or countdown advances. Use `none` if the objective clock is
     enough.
   - Long-game callback or hint: run `glass thread current`, then use at most one
     visible callback to an existing campaign thread, or `none`. A good callback
     is concrete and table-visible: mark, object, NPC behavior, damage pattern,
     phrase, route, faction resource, or repeated method. If the callback advances
     the thread, run `glass thread advance <thread-id> --note "<concrete visible beat>"`.
     Do not write abstract mystery language.
   - Secrets that might surface.
   - Open questions the DM will play to answer.

5. **Write player-facing scene context.**
   - Update `arcs/<arc>/scenes/<scene>/context.md` with only visible framing.
   - Run `glass summary write scene <scene> --arc <arc> --body "<compact scene premise>"`.

6. **Write the active table with table commands.**
   - `glass table write scene.md --body "<visible kickoff description>"`
   - Make the three interactable scene toys visible in `table/scene.md` or named
     table artifacts.
   - Add a named artifact for each reusable visible lore item players should
     reason from: `glass table write <meaningful-slug>.md --body "<markdown>"`.
   - Bring existing durable lore onto the table with
     `glass table use shared/lore/<path>.md --as <meaningful-slug>.md`.

7. **Create trackers and clocks before play starts.**
   - Use `glass scene tracker set <id> --max <n>` for scene-local visible
     counters.
   - Use `glass clock set <id> --scope scene --anchor <scene-id> --max <n> [--public]`
     for clocks that must survive beyond the scene.
   - For active play modes, always declare the objective clock:
     `glass scene clock declare <objective-clock-id> --label ... --goal ... --value 0 --max <n> --direction progress --polarity objective --visibility public`.
   - Declare a separate threat/timer scene clock only when pressure should worsen
     independently:
     `glass scene clock declare <threat-clock-id> --label ... --goal ... --value 0 --max <n> --direction progress --polarity threat --visibility public`
     or `glass scene clock declare <timer-clock-id> --label ... --goal ... --value <n> --max <n> --direction countdown --polarity timer --visibility public`.

8. **Commit authored prep.**
   - Run `glass sync apply arcs/<arc>/scenes/<scene>`.
   - Run `glass table snapshot --label before-<scene-slug>` when replacing a
     prior active table matters.

9. **Hand into actual play.**
   - If `scene-prep` is the active mode, run `glass mode end`.
   - Run `glass mode start <scene-play|action> <scene-slug>`. Use `action`
     for quickfire combat, chase, disaster, escape, or social-pressure scenes;
     keep that label in the scene `--type`, not the mode.
   - Confirm the objective scene clock is live.
   - Start 2-3 active beats before handing to players:
     `glass beat start <beat-id> --clock <objective-clock-id> --label ... --question ...`.
     The beats should be distinct problem lanes, not three versions of the same
     task. They can share the objective clock or attach one lane to a
     threat/timer clock. Closing a normal beat should usually move a clock by 1;
     use 2 only for a major scene-shifting breakthrough after setup or
     coordination.
   - Run `glass check` before handing off.
   - If the first actor is not the normal default, run `glass next handoff <agent-id>`.

10. **Close the prep turn.**
    - Write `TURN.md` with the visible scene opening.
    - Run `glass done --summary "<scene staged and mode started>" --state "<scene/context/table artifacts/tracker updates>" --rolls none --next default`.

## Prohibitions

- Do not prep a solution path or required dialogue.
- Do not leave player-visible scene facts only in `prep.md`.
- Do not default to documents, manifests, claims, counts, labels, or other
  procedural artifacts as the whole scene. Those can be the fuse; make sure
  something alive, strange, volatile, personal, or adventure-facing is pushing
  through them.
- Do not stage a scene that is only legal drama, audit drama, chain-of-custody
  preservation, or institutional negotiation. If paperwork matters, attach it to
  an antagonist move and a physical danger on screen or arriving now.
- Do not let the recurring scene endpoint be that the party made events
  witnessed, tagged, recorded, or undeniable. Let that matter when it is useful,
  but make it produce a new danger, choice, cost, confrontation, or movement.
- Do not stage a third consecutive scene in the same location or location family.
- Do not stage a scene that repeats the last two scenes' problem family without
  naming what is different and why this repeat is worth playing.
- Do not make "get more information" the problem family. Knowledge is an output;
  give the scene a pressure shape.
- Do not leave the objective clock implicit.
- Do not end the turn still in bare `scene-prep`.
- Do not start an action scene without action-order setup in the opening DM
  turn or a clear handoff to do it.

## CLI Encoding Opportunities

These are not commands yet:

- `glass scene prep-check <scene>` for prep/context/table/summary/tracker/mode
  readiness.
- `glass scene start <slug> --type <type>` to combine create, table reset,
  mode transition, and initial summary checks.
