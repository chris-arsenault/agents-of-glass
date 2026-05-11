---
title: Lore and Notes Instructions
target: executing-agent
authority: binding
---

# Lore and Notes Instructions

Use the right writing surface. Read workspace files directly, edit writable
note/lore files in place, and persist authored markdown with `glass sync apply`
or a more specific `glass` command.

## DM Notes

DM-only working notes live under `dm/notes/`, `dm/workspace/`, `dm/secret/`,
and `dm/scratchpad.md`.

```bash
glass sync apply dm/workspace/<name>.md
glass sync apply dm/notes/<category>/<slug>.md
glass sync apply dm/secret/<name>.md
```

Entity-shaped note writes are registered through the same persistence facade.
If you need to refresh graph/search state for an existing authored lore file,
use:

```bash
glass lore upsert shared/lore/<category>/<slug>.md
```

## Player Notes

Player private reference lives under `players/<id>/notes/`, `journal/`,
`drafts/`, `scratchpad.md`, and `secrets/`.

```bash
glass sync apply players/<id>/notes/<slug>.md
glass sync apply players/<id>/journal/<date>.md
glass sync apply players/<id>/drafts/<slug>.md
glass sync apply players/<id>/secrets/<slug>.md
```

For multiple note writes in one turn, pass directories to one `glass sync
apply` call.

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
