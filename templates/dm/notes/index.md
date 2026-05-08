---
title: DM Notes
status: stub
---

# DM Notes — Mara's Encyclopedia

The DM's reference encyclopedia. Where the world lives between scenes.

This is expected to be **much bigger** than any player's notes directory. The DM tracks: every NPC introduced, every location visited, every monster prepared, the world's behavior, encounters in flight, encounters in reserve, the philosophical premises of the campaign. Most of what makes a session feel coherent comes from the DM's notes being deep and well-organized.

## How to use this directory

Encyclopedia-shaped entries. **One file per topic.** Subdirectories by category. The structure below is a starter — extend as the campaign demands.

### Recommended subdirectories

```
notes/
  encounters/      planned and in-progress encounters (combat, social, environmental)
  npcs/            every NPC the party has met or will meet
  monsters/        creature stat blocks + behavior notes
  locales/         places (settlements, regions, landmarks) — campaign-specific elaborations
  factions/        organized groups, with current stances and entanglements
  philosophy/      world-level themes; how things actually work; what conflicts the campaign is investigating
  threads/         active narrative threads (which beats are open; what's next; what's been advanced)
  loops/           recurring narrative patterns relevant to this campaign
  hooks/           open hooks the players haven't picked up yet
```

Add categories as needed. A campaign-specific category (e.g. `corruption-progression/` if the campaign is about the Bloom) is welcome.

### Format

Lightweight encyclopedia entries:

```markdown
---
title: Patrol Leader (Ringglass Market scene)
type: npc
status: introduced     # or planned, retired, etc.
prominence: marginal   # mythic, renowned, recognized, marginal, forgotten
---

# Patrol Leader

[A few paragraphs: what they want, what they're afraid of, how they sound, what mistake they're poised to make. Concrete details. Specific names. No generic-fantasy fallbacks — see /docs/principles/resist-generic-drift.md.]

## Mechanics
[If they have a stat block, summarize. The hard data is in Postgres.]

## Open hooks
[If they're connected to an active thread or other entities, list those connections.]
```

### Conventions

- **One file per topic.** Mega-files are illegible.
- **Encyclopedia-shaped, not journal-shaped.** Journal entries (chronological reflection — "today the players surprised me by going to X") go in `../journal/`. Working drafts go in `../workspace/`. This directory is for *finished, ready-to-reference material*.
- **Link freely.** Markdown relative links across files are encouraged.
- **Update, don't append.** Notes are current-state; if an NPC's situation changes, edit the entry.
- **Specificity always.** Per [`/docs/principles/resist-generic-drift.md`](../../../docs/principles/resist-generic-drift.md), every entry should be defensible against the lore repo's quality bar. No "ancient evil stirs," no "the wizard casts fire." Read [`/home/dev/repos/the-glass-frontier-lore/player/cosmology/resonance.md`](../../../../the-glass-frontier-lore/player/cosmology/resonance.md) when in doubt.

### Distinct from neighboring directories

- `notes/` — published reference. The DM's encyclopedia. Read frequently during play.
- `../workspace/` — in-progress drafts. NPCs not ready for the table yet. Sketches.
- `../secret/` — knowledge the players should never see. The DM-only truth behind public-facing entries (mirrors the lore repo's `dm/` vs `player/` split).
- `../journal/` — chronological DM reflection.
- `../scratchpad.md` — current working notes; overwriteable.
- `../intake/` — player-drafted lore awaiting ratification.

When something is ready for the table, it lives here. Until then it's in `workspace/`.

### Lore vs notes

Notes are the DM's working reference. They are not automatically canonical for the players. When a note represents something canonical to the campaign that other agents should also know about, the DM uses `glass entity upsert` to push it into the FalkorDB graph and (typically) into `sessions/shared/lore/` as a published encyclopedia entry. **Player-facing canon goes to shared lore; DM-only canon stays here in notes/**.
