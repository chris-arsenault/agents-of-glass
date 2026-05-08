---
title: Character Creation Methodology
status: stub
---

# Character Creation

**Stub. To be co-authored.**

## What this is

The methodology document the DM and players read during the `character_creation` phase (see [`/docs/design/game-start.md`](../../../docs/design/game-start.md)). DM goes first, then each player, then DM ratifies. The output is a full party of PCs, each with a public intro entry, ready for the first session.

## What this doc will cover (when authored)

### DM-side

- **Goal of the public intro.** What `shared/campaign-intro.md` should contain — a few paragraphs of player-facing scene-setting that names the situation, the party's reason to be together, and 2-3 of the planning-phase hooks. Specific, not "you all meet in a tavern."
- **What to include and what to withhold.** DM-only knowledge stays in `dm/notes/`; the public intro reveals only what the players' characters would already know.
- **How to ratify.** Reading each player's draft character + intro and either canonizing it (move to `shared/lore/characters/<id>.md`, graph-upsert) or pushing back via `glass msg secret <player>` with concrete revisions requested. Rejection is a real option for generic-fantasy drift.

### Player-side

- **Reading order.** Persona, the public campaign-intro, the world bible (player-facing), the DM's hook list (also player-facing).
- **Character creation outputs:**
  - **`character.md`** — the canonical sheet. Attributes (one of seven), skills (free-form named, with tier), archetype (a string grounded in this world), name (per a culture's actual naming convention), pronouns, starting inventory, momentum/HP defaults. Per [`/docs/design/mechanics.md`](../../../docs/design/mechanics.md).
  - **A public intro entry** — encyclopedia-shaped lore for `drafts/intro.md`. Three or four paragraphs on who this PC is, where they came from, what they want. References at least one of the DM's planning-phase hooks or NPCs by name.
- **Constraints.** Specificity always. No "half-elf rogue with a tragic past" — pick a culture, commit to a naming convention, build the backstory from this world's actual species/culture/profession space. The persona's tastes shape what kind of PC this player would build (Sumi gravitates to morally complicated; Tev gravitates to mechanically interesting; etc.).
- **Submission.** The player calls `glass note propose drafts/intro.md` to push to DM intake. The character.md is just written into place.
- **Re-submission flow.** If the DM rejects, the player reads the secret message, revises, re-proposes.

### Done criteria

All four players have a ratified character + intro. Every PC has at least one tie to a DM-authored hook or NPC. The DM signals phase-complete with a final invocation.

## Status

Empty placeholder. Needs author pass.
