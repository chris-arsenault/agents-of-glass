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

- **Reading order.** Persona, the public campaign-intro, the world bible (player-facing), the DM's hook list, and **the party's organization** at `shared/lore/organization.md` — including the capabilities the org typically needs.
- **Build the character first, fit them to the org second.** You do *not* have to pick from a predefined role roster. The org's "capabilities the org typically needs" are guidance, not slots — they tell you *what kinds of leverage the org operates by*, not what archetype you have to play. A normal-path soldier in an agency hit squad is fine; an ex-biker who was delivering pizza and ended up on the same hit squad as the info dealer because of his connections is *better*. Come up with a backstory that makes a coherent person, then figure out how that person ended up here.
- **The only required hook into the org:** your intro must explain *why this character is in this organization* in a way that holds up. Recruited, drafted, owed a debt, ran out of options, was already inside before the campaign starts — any narrative reason works as long as it makes sense for who the character is.
- **Character creation outputs:**
  - **`character.md`** — the canonical sheet. Attributes (one of seven), skills (free-form named, with tier), archetype (a string grounded in this world), name (per a culture's actual naming convention), pronouns, starting inventory, momentum/HP defaults. Plus an `org_tie` field — a one-line free-form description of what this PC brings to the org and how they got there. Per [`/docs/design/mechanics.md`](../../../docs/design/mechanics.md).
  - **A public intro entry** — encyclopedia-shaped lore for `drafts/intro.md`. Three or four paragraphs on who this PC is, where they came from, what they want, and how they came to the org. References at least one of the DM's planning-phase hooks, NPCs, or the org by name.
- **Constraints.** Specificity always. No "half-elf rogue with a tragic past" — pick a culture, commit to a naming convention, build the backstory from this world's actual species/culture/profession space. The persona's tastes shape what kind of PC this player would build (Sumi gravitates to morally complicated; Tev gravitates to mechanically interesting; etc.).
- **Submission.** The player calls `glass note propose drafts/intro.md` to push to DM intake. The character.md is just written into place.
- **Re-submission flow.** If the DM rejects, the player reads the secret message, revises, re-proposes.

### Done criteria

All four players have a ratified character + intro. Every PC has an `org_tie` that explains how they ended up in the organization. Every PC has at least one tie to a DM-authored hook, NPC, or org member. The DM signals phase-complete with a final invocation.

## Status

Empty placeholder. Needs author pass.
