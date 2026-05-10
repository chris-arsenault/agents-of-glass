---
title: Lore and Notes Instructions
target: executing-agent
authority: binding
---

# Lore and Notes Instructions

Use the right writing surface.

## DM Notes

DM-only working notes live under `dm/notes/`, `dm/workspace/`, `dm/secret/`,
and `dm/scratchpad.md`.

Optional graph registration:

```bash
glass entity upsert dm/notes/<category>/<slug>.md
```

## Player Notes

Player private reference lives under `players/<id>/notes/`, `journal/`,
`drafts/`, `scratchpad.md`, and `secrets/`.

Players propose canon with:

```bash
glass note propose <path>
```

## Player-Visible Lore

Canonical player-visible lore lives in `shared/lore/` and is DM-ratified.

```bash
glass lore new <type> <slug>
glass lore upsert <path>
glass lore import <world-bible-path>
```

Curate from the world bible. Do not bulk-copy it. The world bible is DM
reference; campaign lore is the subset that matters to this campaign.
