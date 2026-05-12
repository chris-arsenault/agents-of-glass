---
title: Lore and Notes Instructions
target: executing-agent
authority: binding
---

# Lore and Notes Instructions

Use the narrowest durable surface. Use `glass` commands when lore or entity
state needs registration.

## DM Sequence

1. Choose the destination.
   - DM-private notes: `dm/notes/`, `dm/workspace/`, `dm/secret/`.
   - Player-visible canon: `shared/lore/`.
   - Current visible board: `table/`.

2. For table-visible material that should become durable public canon, promote
   it instead of leaving it only on the table:

```bash
glass lore promote table/<meaningful-slug>.md --to shared/lore/<path>.md
```

3. For durable lore already created elsewhere that becomes relevant in-scene,
   put the visible portion on the table:

```bash
glass table use shared/lore/<path>.md --as <meaningful-slug>.md
```

4. For world-bible material, import instead of copying:

```bash
glass lore search "<query>"
glass lore import <world-bible-path>
```

5. For new public lore, scaffold and register:

```bash
glass lore new <type> <slug>
glass lore upsert shared/lore/<type>/<slug>.md
```

6. For DM notes, edit the file and commit:

```bash
glass sync apply dm/notes/<category>/<slug>.md
glass sync apply dm/workspace/<name>.md
glass sync apply dm/secret/<name>.md
```

7. For graph relationships, use entity commands:

```bash
glass entity claim <a> <REL> <b> --summary "<what is claimed>"
glass entity link <a> <REL> <b> --prop summary="<durable relation>"
```

## Player Sequence

1. Choose the destination.
   - Private reference: `players/<id>/notes/`.
   - Dated reflection: `players/<id>/journal/`.
   - DM-readable private request: `players/<id>/secrets/`.
   - Party-readable material: `players/<id>/public/`.

2. Edit the file and commit:

```bash
glass sync apply players/<id>/notes/<slug>.md
glass sync apply players/<id>/journal/<date>.md
glass sync apply players/<id>/secrets/<slug>.md
glass sync apply players/<id>/public/<slug>.md
```

3. Propose player-authored canon with:

```bash
glass note propose players/<id>/drafts/<slug>.md
```

## Boundary

Do not put player-visible canon only in DM notes or only in the running table
after it becomes durable. Do not put DM-only material in `shared/lore/`,
`table/`, or player-public files.
