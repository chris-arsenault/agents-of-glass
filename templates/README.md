# templates/

**Authored content. Stable input.** This is the operator-curated baseline that the orchestrator copies into a campaign at start. Nothing in this tree is mutated by active play.

For runtime mutable content, see `campaigns/<id>/` (per-campaign live state,
created by `aog campaign new`).

## Layout

```
templates/
  summary.md               running campaign continuity summary starter
  shared/                  cross-arc, all agents readable (template form)
    campaign-framing.md    DM-owned starter framing
    quest-log.md           starter quest log
    party-knowledge.md     party-writable starter
    clocks.md              generated public durable-clock projection starter
    lore/                  starter campaign encyclopedia (usually empty until canonization happens)
  instructions/            binding executing-agent tool/file instructions
  methodologies/           binding ordered workflows by mode/phase
  srd/                     public game rules for players and DMs
  how-to/                  optional player/DM examples and craft guidance
  table/                   player-agent-visible short-term table state (reset per scene)
    scene.md               current visible situation
    <meaningful-slug>.md   named player-visible table artifacts
    handouts/              in-game handouts
  dm/                      DM workspace template
    persona.md             who Mara is at the table
    notes/index.md         encyclopedia how-to-use
    journal/               starter dir
    workspace/             starter dir
    secret/                starter dir
    intake/                starter dir
  players/<player>/
    persona.md             who they are at the table
    signature-moves.md     recurring prose moves; starts with one slot
    character.md           starter character sheet (filled during character creation; canonical numbers in Postgres)
    notes/index.md         encyclopedia how-to-use
    journal/               starter dir
    drafts/                starter dir
    inbox/                 starter dir
```

## Authored vs runtime

Two distinct concerns:

- **Authored** (this directory). The operator writes and curates. Stable across runs. Updates here apply to *future* campaigns, not running ones.
- **Runtime live content** (`campaigns/<id>/`). What the agents mutate during play — three levels of player-facing context, DM workspace, per-arc and per-scene state. Each campaign starts with a snapshot of this directory and evolves from there. Past campaigns stay reproducible from their own contents.

The orchestrator copies `templates/` into a per-campaign root at campaign creation. Once copied, the campaign is independent — editing templates does not retroactively change the campaign.

## Two shapes of writing

- **Instruction-shaped** (binding tool/file behavior for executing agents) —
  `instructions/`.
- **Methodology-shaped** (binding ordered workflows for executing agents) —
  `methodologies/`.
- **SRD-shaped** (public rules for player/DM roles) — `srd/`.
- **How-to-shaped** (optional examples and craft guidance) — `how-to/`.
- **Encyclopedia-shaped** (frontmatter + prose + sections, FalkorDB-mirrored when canonized) — `shared/lore/`, players' `drafts/`, players' `notes/`, DM's `notes/`.
- **Journal-shaped** (free-form, no schema) — players' `journal/`, DM's `journal/`, `workspace/`, `secret/`, and `intake/`.
- **Table-shaped** (short, current, player-agent-visible) —
  `table/scene.md` plus named markdown artifacts at `table/` root. These
  artifacts are player-visible lore candidates: NPCs, places, documents, ships,
  clues, objects, or anything else the scene needs. There is no authored
  `table/index.md`. This is the material projected to player CWDs and shown in
  the web UI's Active Table. DM notes, hooks, lore, graph entities, and messages
  are separate surfaces even when human viewers can inspect them elsewhere.
- **Summary-shaped** (authored continuity compression) — `summary.md` at
  campaign, arc/act, and scene level. These are summaries of what remains true,
  not immediate scene boards.

Don't blur them. The shape signals the intent.

Runtime authority is split intentionally: markdown is the readable authored
surface, Postgres owns hard/queryable state and the public turn corpus, and
FalkorDB owns entity relationships. See
[`docs/design/persistence.md`](../docs/design/persistence.md).

## What gets committed

Everything in this tree is committed to git — it's the authored baseline.
Personas, instructions, methodologies, SRD, how-to files, starter framing, and
starter lore are all durable.
