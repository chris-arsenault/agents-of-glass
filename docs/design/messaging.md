# Messaging

Inter-agent durable communication. Solves the inter-player dialog problem and gives the DM and players a way to share content out-of-band of the turn loop.

## The Mechanism

A simple typed message bus, exposed as a single CLI command:

```
glass msg <type> <recipient> <body>
```

- **`type`** — a string from a controlled vocabulary (`table-talk`, `banter`, `instruction`, `plot-hint`, `secret`, ...). The CLI validates against `sessions/shared/vocabulary/message-types.md`. Unknown types produce a helpful error so the agent can retry inline (the error includes the valid set and the closest match to what they tried).
- **`recipient`** — a player name (`tev`, `sumi`, `renno`, `kit`), `party` (all players), or `dm`. The CLI validates against the active session's roster.
- **`body`** — a multi-line string. Free-form prose. No other fields.

There is no "subject," no "priority," no "thread," no "reply-to." Agents are smart; they handle threading in prose.

## Reading

```
glass msg read [--since-checkpoint] [--from <sender>] [--type <type>]
```

Each agent has a per-recipient read checkpoint, advanced when they read. Reading without `--since-checkpoint` returns recent messages; with it, only unread. Agents typically read unread messages at turn start as part of `TURN_START.md` (see [`context-packages.md`](context-packages.md)).

## Storage

Messages live in Postgres. Small schema:

| Column | Purpose |
|--------|---------|
| `id` | message id |
| `ts` | sent timestamp |
| `session_id` | session scope |
| `sender` | agent id |
| `recipient` | `tev` / `party` / `dm` / etc. |
| `type` | from message-types vocabulary |
| `body` | text |

Read state:

| Column | Purpose |
|--------|---------|
| `agent_id` | who read it |
| `message_id` | which one |
| `read_ts` | when |

Postgres because messages are queryable corpus data. Analysis later wants to ask "who messaged whom most" or "did secret messages correlate with later betrayals." Markdown-only would lose this.

The orchestrator also projects each agent's unread messages into a flat `inbox/` directory inside their per-turn working directory, so agents who'd rather read files than run a CLI command have a path. Both paths land at the same place.

## What This Gets Us

- **Inter-player dialog** that survives across turns. A player can mutter something to another player via `glass msg banter sumi "..."`; Sumi sees it next turn.
- **DM-private hints** (`glass msg plot-hint tev "..."`) that don't show up in the public transcript.
- **Coordinated planning** (`glass msg instruction party "..."`) without spinning up a planning-mode scene.
- **Structured corpus** of what was said off-camera, queryable by type.

## What's Codified vs Prose

Per [`../principles/codify-only-what-drifts.md`](../principles/codify-only-what-drifts.md):

- **Codified:** the type, the sender/recipient, the timestamp, the read-checkpoint state. These need to agree across agents.
- **Prose:** the body. Free-form text. The agent writes it like they'd write any other prose.

The type vocabulary is the one place we validate, because untyped messages would defeat the purpose — the type is the indexable signal we want for analysis later. Type changes are vocabulary additions (see [`shared-vocabulary.md`](shared-vocabulary.md)), not schema migrations.

## Visibility

- A message to `dm` is readable only by the DM.
- A message to a specific player is readable by that player **and by the DM** (the DM is the table arbiter and sees everything; players' journals are also DM-visible — see [`context-packages.md`](context-packages.md)).
- A message to `party` is readable by all players (and the DM).
- A player cannot read messages sent to other specific players. File-permission-level isolation (per-turn ephemeral CWD) makes this enforceable, not just policy.

## Failure Cases

- Unknown type → CLI returns the valid set + closest match. Agent retries inline.
- Unknown recipient → CLI returns the active roster. Agent retries inline.
- Agent doesn't read messages at turn start → no automatic enforcement. `TURN_START.md` surfaces unread message counts prominently; agents that ignore them are producing a worse turn, but the orchestrator does not fire an error.

## Relationship to the Transcript

Messages are **not** in the transcript by default. They are corpus data, but a separate kind of corpus. They get woven into transcript reading on demand:

- The transcript is the public IC/OOC record of what happened at the table.
- The message bus is the off-camera communication that *informed* what happened at the table.

Analysis passes that want both can join `messages` to `turns` by `(session_id, ts)` to reconstruct "what did Sumi know when she made that decision."

A message can also be referenced *into* the transcript: when an agent wants their message-driven decision visible at the table, they can quote or paraphrase the relevant message in their turn prose. They choose; the orchestrator doesn't auto-splice.
