---
title: Intermission Methodology
status: authored
audience: dm-and-players
applies_to_modes: [intermission]
---

# Intermission

Intermission is the table-facing planning room after a closed act.
It is not used between ordinary scenes inside an open act.

## DM Opening Turn

1. **Read the closed material.**
   - `glass summary show campaign`
   - `glass summary show arc <closed-arc>`
   - `glass turns feed --after-turn <n>` if recent player intent matters.
   - Read `shared/quest-log.md`, `shared/party-knowledge.md`, and active
     `dm/notes/hooks.md`.

2. **Put the intermission prompt on the table.**
   - `glass table write scene.md --body "<what the table should choose now>"`
   - `glass table write <meaningful-slug>.md --body "<visible planning artifact>"`
     when an option, faction, place, or lead should remain available as lore.

3. **Ask for concrete player input.**
   - Use `glass next handoff <agent-id>` or normal rotation.
   - End with `glass done --summary "intermission opened" --state "table prompt updated" --rolls none --next default`.

## Player Turn

1. **Read the prompt and recent continuity.**
   - Read `table/scene.md`, named table artifacts, `shared/quest-log.md`,
     `shared/party-knowledge.md`, your public character display, and unread messages.
   - Use `glass find --mode turns` or `glass find` only when specific recall is needed.

2. **Answer with concrete requests.**
   - Name threads you want followed.
   - Name relationships you want tested or protected.
   - Name character goals, training, gear, allies, debts, fears, or scenes you
     want the next act to make relevant.
   - If you want to add a new declared skill from intermission training and a
     free slot is available (cap `3 + level`), run
     `glass character skill-declare <id> <skill-name>`. The skill starts at
     `fool` and grows by use in the next act.

3. **Persist only useful player material.**
   - Update `players/<id>/journal/`, `players/<id>/notes/`, `players/<id>/public/`,
     or `players/<id>/secrets/` when the material should persist.
   - Commit with `glass sync apply <paths>`.

4. **Close the turn.**
   - Write `TURN.md` with the concrete requests.
   - Run `glass done --summary "<player intermission requests>" --state "<files updated or no state change>" --rolls none --next default`.

## DM Closing Turn

1. **Synthesize player requests.**
   - Read all intermission turns with `glass find --mode turns --scene <intermission-id>`.
   - Update `shared/quest-log.md` or `shared/party-knowledge.md` with
     player-visible commitments.
   - Update `dm/workspace/<next-act>.md` or arc prep with private planning.

2. **Create or activate the next arc.**
   - If a new act is needed, follow `methodologies/arc-creation.md` and run
     `glass arc create <arc-slug> --pull-source "<real-world source/domain>" --pull-utilization "<which next-arc pressure uses it>"`.
   - Run `glass arc activate <arc-slug>`.

3. **Close intermission.**
   - Commit authored files with `glass sync apply`.
   - Run `glass summary append campaign --body "<intermission synthesis>"`.
   - Write `TURN.md` with the synthesis and next-act handoff.
   - Run `glass done --summary "intermission closed and next arc selected" --state "<quest/party/arc/summaries updated>" --rolls none --scene-status ended --next default`.
   - Run `glass mode end`.

## CLI Encoding Opportunities

These are not commands yet:

- `glass intermission open` for table prompt plus handoff setup.
- `glass intermission synthesize` for collecting player requests into
  quest/party surfaces and campaign summary.
