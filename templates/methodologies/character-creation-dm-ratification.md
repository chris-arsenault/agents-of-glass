---
title: Character Creation DM Ratification
status: authored
audience: dm
applies_to_modes: [character-creation]
---

# Character Creation DM Ratification

Use this only after every player has a character row, public mirror, public
intro, and non-empty public relationships file.

1. Run `glass character bulk-get --all`. Verify every character row includes a
   non-empty `primary_drive`, `positive_trait`, `table_presence`,
   `non_work_want`, `opening_social_action`, 2-3 `life_prompt_answers`, and
   `pull_utilization_note`.
2. Read every `players/*/public/intro.md` and
   `players/*/public/relationships.md`.
3. Read [`how-to/narration-craft-dm.md`](../how-to/narration-craft-dm.md).
4. Fix hard-state drift with `glass character bulk-update --json '<payload>'`
   and `glass character mirror <id>` when needed.
5. Commit any authored markdown corrections with `glass sync apply`.
6. Update `shared/party-knowledge.md` if needed.
7. Write `TURN.md` with the public party lock-in.
8. Run `glass turn end --summary "character creation complete" --state "<party state locked in and mirrors/relationships updated>" --rolls none --next default`.
9. Run `glass mode end`.

If `glass mode end` reports missing relationship files, stop. The relationship
round is not complete.
