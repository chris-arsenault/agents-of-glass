# templates/

**Authored content. Stable input.** This is the operator-curated baseline that the orchestrator copies into a campaign at start. Nothing in this tree is mutated by active play.

For runtime mutable content, see `campaigns/<id>/` (per-campaign live state, created by `aog campaign new`).

For the design behind this layout, see [`../docs/design/context-packages.md`](../docs/design/context-packages.md).

## Layout

```
templates/
  shared/                  cross-arc, all agents readable (template form)
    campaign-framing.md    DM-owned starter framing
    quest-log.md           starter quest log
    party-knowledge.md     party-writable starter
    lore/                  starter campaign encyclopedia (usually empty until canonization happens)
    vocabulary/            shared dialect — turn verbs, message types, mechanical terms
  dm/                      DM workspace template
    persona.md             who Mara is at the table
    scratchpad.md          starter current-notes file
    notes/index.md         encyclopedia how-to-use
    journal/               starter dir
    workspace/             starter dir
    secret/                starter dir
    intake/                starter dir
  players/<player>/
    persona.md             who they are at the table
    character.md           starter character sheet (filled during character creation; canonical numbers in Postgres)
    scratchpad.md          starter current-notes file
    notes/index.md         encyclopedia how-to-use
    journal/               starter dir
    drafts/                starter dir
    inbox/                 starter dir
  methodologies/           the real instructions the agents read during each phase
    README.md              what's here and when each is invoked
    campaign-planning.md   world level — DM solo foundation (Question, Scarcity, factions, NPCs+antagonists, creatures, named things, locales, secrets, hooks, philosophy, opening arcs)
    arc-creation.md        multi-scene pressure — invoked from campaign-planning AND during active play
    scene-prep.md          single-scene level — run before each scene in active play
    character-creation.md  DM + players authoring PCs and intros
```

For the bootstrap flow these methodologies drive, see [`../docs/design/game-start.md`](../docs/design/game-start.md).

## Authored vs runtime

Two distinct concerns:

- **Authored** (this directory). The operator writes and curates. Stable across runs. Updates here apply to *future* campaigns, not running ones.
- **Runtime live content** (`campaigns/<id>/`). What the agents mutate during play — three levels of player-facing context, DM workspace, per-arc and per-scene state. Each campaign starts with a snapshot of this directory and evolves from there. Past campaigns stay reproducible from their own contents.

The orchestrator copies `templates/` into a per-campaign root at campaign creation. Once copied, the campaign is independent — editing templates does not retroactively change the campaign.

## Two shapes of writing

- **Encyclopedia-shaped** (frontmatter + prose + sections, FalkorDB-mirrored when canonized) — `shared/lore/`, players' `drafts/`, players' `notes/`, DM's `notes/`.
- **Journal-shaped** (free-form, no schema) — players' `journal/` and `scratchpad.md`, DM's `journal/` and `scratchpad.md` and `workspace/` and `secret/` and `intake/`.

Don't blur them. The shape signals the intent. See [`../docs/design/agents.md`](../docs/design/agents.md) for the rule.

## What gets committed

Everything in this tree is committed to git — it's the authored baseline. Personas, vocabulary, the how-to-use indexes, the starter framing files. All durable.
