---
title: Campaign Planning Methodology
status: authored
audience: dm
applies_to_modes: [campaign-planning]
---

# Campaign Planning

Run this after character creation, not before it. Build the campaign around the
organization and the characters the table actually made. Do not write a plot,
climax, reveal order, or scene script.

## Campaign Genre Contract

This campaign is not legal drama, audit drama, claims drama, or workplace
procedure. Those can appear as texture or clues, but they cannot be the play
loop. The campaign should generally look like an action movie: antagonists act,
people face concrete physical harm, and the party solves dangerous situations
with characterful choices.

Every campaign foundation must name:

- the active antagonist or antagonistic force, including what they are doing
  when the party is not looking
- the concrete bodily danger to people if the party fails or delays
- why paperwork, law, hierarchy, or procedure is not enough to solve it
- the expected course-correction: if two consecutive scenes lack danger,
  fighting, coercion, pursuit, or another physically harmful pressure, the next
  scene opens with one
- the location course-correction: after two scenes in the same location or same
  location family, the next scene substantially changes place

## Sequence

1. **Read the org and the party.**
   - Read `dm/persona.md`, `shared/lore/organization.md`,
     `dm/notes/organization.md`, `summary.md`, and `shared/lore/`.
   - Run `glass character bulk-get --all`.
   - Read every `players/*/public/intro.md` and
     `players/*/public/relationships.md`.
   - Read player secrets or notes only when they are load-bearing for campaign
     framing.
   - Run `glass lore list`, `glass arc list`, and `glass clock list --all`.

2. **Record the anti-generic inputs before authoring major outputs.**
   - Do one world-bible pull with `glass lore search <query>` and import only
     load-bearing entries with `glass lore import <world-bible-path>`.
   - Do one non-adjacent real-world pull outside the repo when the turn has web
     access. Do not use fantasy, RPG, fiction-writing, or campaign advice.
   - Record 2-3 concrete observations from the source, then choose at least one
     campaign surface it changes: campaign question, scarcity, faction
     behavior, named NPC practice, location procedure, hazard, clock segment,
     opening-arc pressure, or first-scene pressure.
   - Before writing major outputs, run:

     ```bash
     glass campaign pull-note \
       --source "<real-world domain/source>" \
       --used-in "<campaign surface changed>" \
       --note "<borrowed concrete detail and exact utilization>"
     ```

   - Mention the lore pull, imported lore ids, and the campaign pull-note path
     in `glass done --state`.

3. **Write the campaign question and scarcity.**
   - Update `dm/foundation.md` with the core question, scarcity, and what the
     campaign is not about.
   - Include the campaign genre contract: active antagonist, off-screen move,
     concrete physical danger, and the note that Mara cannot run this as
     procedural/legal drama.
   - Include the location rule: no more than two consecutive scenes in the same
     place or same kind of procedural room before a substantial location shift.
   - Update `context.md` and `shared/campaign-framing.md` with only the
     player-facing version.
   - Commit with `glass sync apply dm/foundation.md context.md shared/campaign-framing.md`.

4. **Author the DM prep inventory around this party.**
   - Factions: 3-5 files under `dm/notes/factions/`.
   - Named NPCs: 5-8 files under `dm/notes/npcs/`; mark recurring antagonists
     in the file body/frontmatter.
   - At least one antagonist entry must name its current off-screen operation,
     the next harmful move, and who can be physically hurt by it.
   - Recurring creatures or hazards: 2-4 files under `dm/notes/creatures/`.
     At least one must be capable of harming bodies on screen, not only careers,
     claims, access, or reputation.
   - Named things: 3-5 files under `dm/notes/artifacts/`, `dm/notes/ships/`,
     or an appropriate notes directory.
   - Locations: 3-6 files under `dm/notes/locales/`.
   - Long-game threads: 2-4 files under `dm/notes/threads/`, or initialize the
     same ideas with `glass thread advance <thread-id> --note "Opened: ..."`.
     Each thread should have one concrete visible handle the table can recognize
     later: symbol, route, damage pattern, NPC method, faction resource, phrase,
     or recurring consequence.
   - Secrets and hooks: one compact file each under `dm/notes/secrets.md` and
     `dm/notes/hooks.md`.
   - Philosophy or adjudication notes: one compact file under
     `dm/notes/philosophy/` when needed.
   - Commit in batches with `glass sync apply dm/notes`.

5. **Curate public lore only when it is load-bearing now.**
   - Use `glass lore import <world-bible-path>` for public world-bible entries
     the players need during character creation or the opening arc.
   - Aim for 8-15 campaign lore entries by the end of planning.
   - Run `glass lore list` and verify the set is bounded.

6. **Create the opening main arc.**
   - Run `glass arc create <opening-arc-slug> --pull-source "<real-world source/domain>" --pull-utilization "<which threat, node, clock, scarcity, strong start, clue, or hazard uses it>"`.
   - Run `glass arc activate <opening-arc-slug>`.
   - Follow `methodologies/arc-creation.md` to populate the arc plan and
     context.

7. **Update summaries.**
   - Write a compact campaign summary:
     `glass summary write campaign --body "<current campaign foundation summary>"`.
   - Write the opening main arc summary with
     `glass summary write arc <arc-id> --body "<current arc summary>"`.

8. **Run the planning audit.**
   - `glass lore list`
   - `glass arc current`
   - `glass arc list`
   - `glass clock list --all`
   - `glass summary show campaign`

9. **Close the planning turn.**
    - Write `TURN.md` as a short public planning summary.
    - When the phase is complete, run `glass mode end` before closeout.
    - Run `glass done --summary "<what is now ready>" --state "<files and CLI state updated; campaign-planning mode ended>" --rolls none --scene-status ended --next default`.

## Prohibitions

- Do not prewrite scenes, speeches, final answers, or solution paths.
- Do not bulk-copy world-bible material.
- Do not hide durable facts only in turn prose.
- Do not create the campaign before character creation is complete.
- Do not create scenes during this turn (the opening arc's first scene is staged at scene-prep or directly via `scene transition`, not here).
- Do not create the opening main arc without `glass arc create --pull-source ... --pull-utilization ...`.
- Do not claim a non-adjacent pull without recording where the borrowed detail is
  used.
- Do not frame the campaign as a procedural/legal dispute with occasional danger
  attached. Frame it as dangerous adventure where procedure sometimes obstructs,
  reveals, or accelerates the threat.
- Do not let the campaign stay in one site, office, corridor, dock, archive,
  bench, hearing room, checkpoint, or equivalent location family for more than
  two consecutive scenes.

## CLI Encoding Opportunities

These are not commands yet. Prefer adding them later instead of expanding this
methodology again:

- `glass campaign foundation set` for question, scarcity, and public framing.
- `glass campaign planning-check` for required files, lore count, active arc,
  and summary presence.
