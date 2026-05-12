---
title: Character Creation DM Relationship Setup
status: authored
audience: dm
applies_to_modes: [character-creation]
---

# Character Creation DM Relationship Setup

This is the DM turn after every player has a public character mirror and intro,
but before the relationship files exist. Its job is to start the relationship
round, not to ratify or end character creation.

1. Run `glass character bulk-get --all`.
2. Read every `players/*/public/intro.md`.
3. Read [`how-to/narration-craft-dm.md`](../how-to/narration-craft-dm.md).
4. Read DM intake that should shape relationship prompts.
5. Update `table/scene.md` with the visible party situation if it changed.
6. If useful, send focused prompts with
   `glass msg table-talk <player> "<specific relationship prompt>"` or
   `glass msg banter <player> "<specific relationship question>"`.
7. Write `TURN.md` as a short public bridge into relationship writing.
8. Run `glass turn end --summary "relationship round opened" --state "<visible table or prompt updates, or no state change>" --rolls none --next default`.

Do not run `glass mode end`. `glass mode end` is only valid after every player
has a non-empty `players/<id>/public/relationships.md`.
