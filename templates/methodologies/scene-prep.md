---
title: Scene Prep Methodology
status: authored
audience: dm
applies_to_modes: [scene-prep]
---

# Scene Prep

Run this as a DM-only bridge into actual play. A scene-prep turn is complete
only after the next scene exists, the active table is written, the actual play
mode is started, and `glass turn end` succeeds.

## Sequence

1. **Read state.**
   - `glass arc current`
   - `glass scene current`
   - `glass summary show campaign`
   - `glass summary show arc <arc-id>`
   - `glass turns find --scene <previous-scene-id>` or `glass turns feed --after-turn <n>` when the previous scene matters.
   - Read `arcs/<arc>/plan.md`, `arcs/<arc>/context.md`, relevant `dm/notes/`,
     and current `table/`.

2. **Create the scene.**
   - Run `glass scene create <scene-slug> --type <scene-play|action|travel|combat|chase|social-pressure|custom> [--arc <arc>]`.
   - Run `glass scene current` and verify it points at the new scene.

3. **Import or register load-bearing lore.**
   - Use `glass lore search <query>` and `glass lore import <world-bible-path>`
     only when this scene surfaces new public canon.
   - Use `glass lore upsert <path>` after editing public lore files.

4. **Write `arcs/<arc>/scenes/<scene>/prep.md` in this order.**
   - Recap: why this scene exists now.
   - Strong start: what is immediately on screen.
   - Possible directions: 3-5 plausible player routes.
   - NPCs in play.
   - Threats, creatures, antagonists, or pressure sources.
   - Named things in play.
   - Secrets that might surface.
   - Open questions the DM will play to answer.

5. **Write player-facing scene context.**
   - Update `arcs/<arc>/scenes/<scene>/context.md` with only visible framing.
   - Run `glass summary write scene <scene> --arc <arc> --body "<compact scene premise>"`.

6. **Write the active table with table commands.**
   - `glass table write scene.md --body "<visible kickoff description>"`
   - Add a named artifact for each reusable visible lore item players should
     reason from: `glass table write <meaningful-slug>.md --body "<markdown>"`.
   - Bring existing durable lore onto the table with
     `glass table use shared/lore/<path>.md --as <meaningful-slug>.md`.

7. **Create trackers and clocks before play starts.**
   - Use `glass scene tracker set <id> --max <n>` for scene-local visible
     counters.
   - Use `glass clock set <id> --scope scene --anchor <scene-id> --max <n> [--public]`
     for clocks that must survive beyond the scene.

8. **Commit authored prep.**
   - Run `glass sync apply arcs/<arc>/scenes/<scene>`.
   - Run `glass table snapshot --label before-<scene-slug>` when replacing a
     prior active table matters.

9. **Hand into actual play.**
   - If `scene-prep` is the active mode, run `glass mode end`.
   - Run `glass mode start <scene-type> <scene-slug>`.
   - If the first actor is not the normal default, run `glass turn handoff <agent-id>`.

10. **Close the prep turn.**
    - Write `TURN.md` with the visible scene opening.
    - Run `glass turn end --summary "<scene staged and mode started>" --state "<scene/context/table artifacts/tracker updates>" --rolls none --next default`.

## Prohibitions

- Do not prep a solution path or required dialogue.
- Do not leave player-visible scene facts only in `prep.md`.
- Do not end the turn still in bare `scene-prep`.
- Do not start an action scene without action-order setup in the opening DM
  turn or a clear handoff to do it.

## CLI Encoding Opportunities

These are not commands yet:

- `glass scene prep-check <scene>` for prep/context/table/summary/tracker/mode
  readiness.
- `glass scene start <slug> --type <type>` to combine create, table reset,
  mode transition, and initial summary checks.
