# Persistence Contract

Agents of Glass has one embedded runtime store plus authored and generated
files. Agents do not choose between them directly. They use `glass`, and
`glass` writes the correct surface.

## Embedded SQLite

The `facts` table owns neutral continuity: relationship facts, organization facts,
visible scene state, commitments, stable descriptors, and any arbitrary factual
statement that future agents need without inheriting narrative embellishment.

Agents read it through:

```bash
glass fact pack --format markdown
glass fact pack --format yaml
```

Agents write it through:

```bash
glass fact set [--scope <scope>] "subject.predicate = value"
glass done --fact "subject.predicate = value"
```

SQLite also owns hard/queryable runtime state:

- public turn rows and `turns.prose`
- event log and command audit
- character records, HP, momentum, skills, inventory, and consequences
- rolls, scene pressure events, scene trackers, scene clocks, durable clocks, HP, and consequences
- messages and read checkpoints
- mode, scene, arc, queues, and other runtime metadata
- search chunks and embeddings

It also stores reference lore and search embeddings. SQLite is sufficient here
because one orchestrator owns mutations, the viewer is read-only, and campaign
data is local and modest. WAL mode permits concurrent viewer reads while a turn
commits. A server database and graph traversal engine add deployment and
credential failure modes without providing a capability the runtime uses.

Agents never open the database directly. They use purpose-built `glass`
commands. The file defaults to `campaigns/.agents-of-glass.sqlite3`; `[storage]`
may override the path.

## Markdown And Files

Markdown is durable reference and human-readable export, not an agent mutation
path during orchestrated turns.

Files may contain:

- templates, instructions, methodologies, SRD, how-to, and style references
- operator-curated lore or notes outside active agent turns
- generated transcript exports and debug artifacts
- campaign workspace files for operator inspection

Agent turns do not write markdown, scratch files, turn files, summaries, or
notes. Public prose is committed through:

```bash
glass turn append --body "<public prose>"
```

## Search

Agents use bounded recall through the CLI:

- `glass turns find ...`
- `glass turns feed ...`
- `glass find ...`

Search results are recall aids. If a recovered detail becomes load-bearing, the
agent should record the neutral fact with `glass fact set` or `glass done
--fact` before relying on it across future turns.

## Checkpoints And Restore

Operator checkpoints are campaign-wide. A checkpoint must capture every store
that can affect what future agents see or remember:

- embedded rows for the campaign, including facts and lore
- campaign files and generated exports needed for operator/debug continuity

Checkpoint and restore are `aog` operator actions, not agent actions.

## Rule Of Thumb

If a future agent must know it as concrete state, put it in continuity facts or a
purpose-built hard-state command.

If it is public narration, submit it with `glass turn append --body`.

If it is durable prose reference for humans or operators, it may live in
markdown, but active agents still do not mutate it directly.
