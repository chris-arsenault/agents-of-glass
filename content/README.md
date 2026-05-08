# content/

The actual play content for the simulation. This is what the agents read and write at session time, and what later analysis consumes.

For the design behind this layout, see [`../docs/design/context-packages.md`](../docs/design/context-packages.md).

## Layout

```
content/
  shared/                  cross-session, all agents readable
    campaign-framing.md    DM-owned; what's happening in the campaign right now
    quest-log.md           DM-owned; durable narrative quest log
    party-knowledge.md     party-writable; what the party collectively knows
    lore/                  campaign-specific encyclopedia (DM-canonized)
    vocabulary/            shared dialect — turn verbs, message types, mechanical terms
  dm/                      DM-only
    mara.md                the DM person file (TODO: author)
    secret/                DM-only knowledge
    workspace/             planning, drafts, in-progress NPCs
    intake/                player-drafted lore awaiting ratification
  players/<player>/
    role.md                the person (TODO: author)
    character.md           cached summary of their PC; canonical sheet in Postgres
    journal/               free-form, journal-shaped, private from other players
    drafts/                encyclopedia-shaped lore-in-progress (proposed via glass note)
    inbox/                 readable view of glass msg deliveries
  sessions/<id>/           per-session
    scene-framing.md       current scene's framing
    transcript.md          the corpus
    audit.jsonl            operational audit log
```

## Two shapes of writing

- **Encyclopedia-shaped** (frontmatter + prose + sections, FalkorDB-mirrored) — `shared/lore/`, players' `drafts/`, ratifications.
- **Journal-shaped** (free-form, no schema) — players' `journal/`, DM's `workspace/`, `secret/`, `intake/`.

Don't blur them. The shape signals the intent. See [`../docs/design/agents.md`](../docs/design/agents.md) for the rule.

## What gets committed

Everything in this tree is committed to git — including transcripts, audit logs, ratified lore, drafts. The corpus is the product; preserve it.

Exception: ephemeral per-turn working directories live at `.glass-cwd/` (gitignored).
