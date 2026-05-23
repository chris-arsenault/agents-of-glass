# Architecture

The system's structural shape: components, data stores, agents, and how they
exchange state. The short version is strict: agents interact with the campaign
only through the `glass` CLI.

## Components At A Glance

```text
      Orchestrator (Python)
        |
        | builds one injected prompt and spawns a provider turn
        v
  Mara / Tev / Sumi / Renno / Kit
        |
        | calls only
        v
     glass CLI
        |
        +--> FalkorDB fact graph  (neutral continuity facts)
        +--> Postgres             (turns, events, characters, rolls, messages)
        +--> operator files       (templates, exports, durable reference)
```

The orchestrator owns turn order and process control. The CLI is the only live
state interface. The agents have agency inside their turns, but they do not get
an alternate file, API, database, or stdout state path.

## Agent Runtime Contract

There is one agent runtime path:

1. The orchestrator builds an injected prompt containing identity, mode, scene,
   selected methodology, allowed commands, current facts, hard-state cues,
   messages, and the output contract.
2. The orchestrator stages the turn with `glass turn begin`.
3. The provider process starts with `cwd = templates/`, which is read-only
   durable reference for methodology, rules, examples, and style.
4. The agent reads current state through `glass check`, `glass fact pack`, and
   other commands explicitly named in the prompt or methodology.
5. The agent mutates durable state only through `glass` commands.
6. The agent records neutral continuity with `glass fact set` or
   `glass done --fact`.
7. The agent closes with `glass done`.
8. The agent submits public prose with `glass turn append --body`.
9. The orchestrator verifies the committed turn row and advances from that
   durable boundary.

The local Glass API grant exists only so the `glass` process can proxy commands
from an isolated provider process. Agents are not instructed to call that API,
do not receive a grant file, and do not treat HTTP as an interaction mode.

## What Agents Cannot Do

During an orchestrated turn, agents do not:

- create, edit, or delete campaign files
- create scratch files
- maintain player or DM working directories
- write public prose to files
- commit markdown syncs
- write SQL or query databases directly
- call local API endpoints directly
- use provider stdout as public prose or state

The only exception is ordinary CLI command output: `glass` returns YAML or text
on stdout so the agent can read the command result. That stdout is not a state
channel by itself.

## Data Stores

### FalkorDB Fact Graph

The fact graph is the agent-readable continuity layer. It stores neutral facts
such as organization definition, scene objectives, visible world state,
character relationships, current commitments, and other durable statements that
future agents must rely on without inheriting narrative phrasing.

Agents read it with:

```bash
glass fact pack --format markdown
glass fact pack --format yaml
```

Agents write it with:

```bash
glass fact set [--scope <scope>] "subject.predicate = value"
glass done --fact "subject.predicate = value"
```

### Postgres

Postgres owns hard and queryable state:

- turn rows and public prose
- events and audit records
- character sheets, HP, momentum, inventory, skills, and consequences
- rolls, scene pressure tracker movement, and scene clock movement
- messages and read checkpoints
- runtime state such as mode, active arc, active scene, queues, and turn number
- search chunks and embeddings

Agents never connect to Postgres directly. They use purpose-built `glass`
commands.

### Operator Files

Markdown and other files remain useful for operator inspection, durable
reference, exports, and authored material outside live agent turns:

- `templates/` contains read-only instructions, methodologies, SRD, how-to
  guidance, style references, and baseline personas.
- `campaigns/<id>/` may contain operator/debug files, exports, and curated
  prose reference.
- transcript markdown exports are generated readability artifacts; the durable
  public corpus is Postgres `turns`.

Files are not the live agent state transport.

## The Orchestrator

The orchestrator:

1. selects the next agent
2. builds the injected prompt
3. stages the turn
4. starts the provider with the `glass` command environment
5. waits for provider exit
6. verifies `glass done` and `glass turn append --body`
7. advances runtime state from the last committed boundary

The orchestrator does not make narrative decisions, parse prose for hidden
schemas, or accept file artifacts as turn output.

## The `glass` CLI

`glass` is the contract. It provides:

- fact graph reads and writes: `glass fact pack`, `glass fact set`
- turn boundaries: `glass turn begin`, `glass done`, `glass turn append --body`
- combined status: `glass check`
- character state: `glass character ...`
- mechanics: `glass roll`, `glass scene pressure`, scene trackers, scene clocks, durable clocks, HP, and consequences
- messages: `glass msg ...`
- past-turn recall: `glass turns find`, `glass turns feed`, `glass find`
- operator/debug commands outside the agent allowlist

Role permissions are enforced per command by environment and grant checks. The
injected prompt also lists the expected command subset for the current turn, but
the CLI is the implementation boundary.

## Viewer Boundary

The web UI is an observer surface. It may display campaign files, facts, turns,
messages, clocks, and debug records. That does not make those surfaces agent
context. Agent visibility is only:

- what the injected prompt includes
- what an authorized `glass` command returns

## Testing Strategy

For v1, tests concentrate at the CLI boundary because the CLI is the contract.
LLM behavior is evaluated through corpus review and real campaign runs, not by
mocked end-to-end agent tests.
