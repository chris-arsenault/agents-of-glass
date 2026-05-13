---
title: Character Creation DM Setup
status: authored
audience: dm
applies_to_modes: [character-creation]
---

# Character Creation DM Setup

Use this only when the organization bootstrap did not already put a usable
character-creation brief on the table, or when Mara needs to refresh that brief
before player build turns.

1. Verify `shared/lore/organization.md` and `table/scene.md` exist. Treat
   `context.md` and `shared/campaign-framing.md` as optional at this stage.
2. Read [`how-to/narration-craft-dm.md`](../how-to/narration-craft-dm.md).
3. Put the character creation brief on the table with
   `glass table write scene.md --body "<who the organization is, what roles it needs, and what kinds of people fit>"`.
4. Run `glass lore list`.
5. Write `TURN.md` with the player-facing creation brief.
6. Run `glass turn audit`, then `glass turn end --summary "character creation brief is ready" --state "organization brief refreshed on the table" --rolls none --next default`.

Do not run `glass mode end`.
