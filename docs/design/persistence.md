# Persistence Contract

Agents of Glass has two persistence surfaces. They overlap deliberately, but
each one has a different authority.

## Markdown

Markdown is the readable prose surface. Agents can inspect it cheaply, diff it,
and write authored game documents in it.

Markdown owns:

- campaign, arc, and scene `context.md`
- campaign, arc, and scene `summary.md`
- player-agent-visible table files under `table/`
- shared lore prose under `shared/lore/`
- quest log, party knowledge, instructions, methodologies, SRD, how-to guidance
- DM notes/workspace/secret files
- player notes, journals, drafts, public files, signature moves

Markdown also receives generated projections:

- `transcript.md` at campaign root
- scene transcript exports at `arcs/<arc>/scenes/<scene>/transcript.md`
- public clock projections such as `shared/clocks.md`

Those projections are for agent readability, git history, and operator
inspection. They are not the canonical runtime store.

## Postgres

Postgres is the coherent state and public corpus surface. Anything numeric,
ordered, queryable, or mechanically consequential belongs here.

Postgres owns:

- character hard state: attributes, skills, HP, momentum, inventory, XP
- rolls and mechanical history
- messages and read checkpoints
- public turn corpus in `turns`
- event log in `events`
- runtime metadata such as mode stack, turn counter, handoff queues
- scene trackers and action-scene initiative order when Postgres is configured
- durable clocks and character consequences
- persisted tarot influences for actual-play creative nudges
- search chunks for bounded recall over turns and indexed markdown

Final public turn prose has a durable home in Postgres `turns.prose`. The
orchestrator captures each agent's `TURN.md`, then commits it through
`glass turn append`. The per-agent `TURN.md`, closeout JSON, stdout, stderr, and debug logs are
operational artifacts. The viewer UI and future narrative-weaving passes should
read `glass turns feed` / Postgres, not scrape agent turn folders.

The viewer UI may also inspect markdown files directly for debugging and
audience context. That broad inspection does not change table visibility:
Active Table is still only `campaigns/<id>/table/**`.

## Search

Agents should not solve old-context recall by asking another agent to repeat
known information. They should query bounded stores:

- exact turn recall: `glass turns find --text ...`
- structured viewer feed: `glass turns feed --after-turn N`
- indexed prose recall: `glass search text ...`
- semantic-search surface: `glass search semantic ...`
- actual-play influence recall: `glass tarot current` / `glass tarot list`

`glass search semantic` is vector-backed recall over Postgres `search_chunks`
embeddings. New committed turns are embedded at `glass turn append`; markdown
search chunks are embedded by CLI write facades and refreshed by
`glass search reindex`. The default provider is the local OpenAI-compatible
Nomic embedder at `192.168.66.3:5361`, returning 768-dimensional
`nomic-ai/nomic-embed-text-v1.5` vectors. Postgres requires `pgvector`; vectors
are stored as `vector(768)` and ranked with pgvector cosine distance using an
HNSW index.

## Checkpoints And Restore

Operator checkpoints are campaign-wide. A checkpoint is not just runtime JSON:
it snapshots every state surface that can change what agents see or remember.

`aog campaign checkpoint <campaign-id>` captures:

- the live campaign filesystem under `campaigns/<id>/`
- all Postgres rows for the campaign, including `search_chunks.embedding_vector`

Checkpoints live outside agent discovery at
`campaigns/.checkpoints/<campaign-id>/<checkpoint-id>/`. Restoring a checkpoint
archives the previous live campaign state under that checkpoint root, replaces
the live filesystem, restores Postgres rows, clears stale projected CWDs, and
reapplies filesystem permissions.

Use:

```bash
aog campaign checkpoint <campaign-id> --label before-risky-replay
aog campaign checkpoints <campaign-id>
aog campaign restore <campaign-id> <checkpoint-id>
aog campaign reconcile <campaign-id> --repair
```

Bootstrap creates checkpoints after campaign planning, after character
creation, and after the prelude. Operators should create explicit checkpoints
before manual repair, replay, risky resume, or long-running scenes.

## Rule Of Thumb

If the value is authored prose, put it in markdown.

If the value is a number, event, turn, queue, permissioned message, or ordered
fact, put it in Postgres.

If the value is a relationship between named things, write it into durable
authored markdown and keep the relevant summary current.

If agents need to read it often, provide a markdown projection or a bounded CLI
query. Do not make them ask another actor for information already recorded.
