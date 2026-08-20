# The Turn Loop

What a turn is, end to end. For the system boundary, see
[`architecture.md`](architecture.md). For modes, see [`modes.md`](modes.md).

## In One Paragraph

The orchestrator picks the next agent, injects the current prompt, stages the
turn with `glass turn begin`, and starts the provider. The agent reads facts and
hard state through `glass`, writes any durable changes through `glass`, closes
with `glass done`, then commits the viewer-facing prose with
`glass turn append --body`. The orchestrator accepts the turn only after the
CLI has a closeout and a committed turn row.

## Codified vs Prose

Three principles run the loop:

1. **Codify what drifts.** Numbers, rolls, HP, inventory, names that must remain
   stable, relationships, scene objectives, messages, mode, scene, speaker, and
   turn metadata go through `glass`.
2. **Keep prose as prose.** Intent, tone, table talk, narration, and subjective
   interpretation belong in the public prose submitted through
   `glass turn append --body`.
3. **Do not let prose become state by accident.** If the next agent must rely on
   a fact, record it neutrally with `glass fact set` or `glass done --fact`.

There is no structured delta block in the prose. The mandatory structure is in
CLI commands.

## How A Turn Begins

The orchestrator builds one injected prompt. It includes:

- the active table person and character, if any
- mode, arc, scene, and generated turn type
- the selected methodology
- the allowed command surface
- current continuity facts
- hard-state cues from `glass` commands
- relevant messages and recall pointers
- the output contract

The prompt is instruction and context, not a writable state surface. Agents may
refresh context with `glass check`, `glass fact pack`, and the commands named by
the prompt or methodology.

## What An Agent Does

Inside the provider invocation, the agent may call `glass` commands in the order
the table turn requires:

- `glass check`
- `glass fact pack --format markdown`
- `glass roll ...`
- `glass scene pressure ...`
- `glass scene clock tick ...`
- `glass character ...`
- `glass clock ...`
- `glass msg ...`
- `glass turns find ...`
- `glass find ...`
- `glass fact set ...`
- `glass done ... --fact ...`
- `glass turn append --body "..."`

The agent does not create files, edit campaign markdown, write notes, maintain
table files, or call a direct API. If a needed durable change lacks a CLI
command, the turn should close with a blocker or message the DM/operator rather
than inventing another state path.

## What The Orchestrator Adds

The orchestrator supplies metadata that agents should not have to author:

- campaign id, arc id, scene id, mode, role, speaker, turn number, timestamp
- staged turn id
- event linkage for rolls, HP changes, messages, scene clocks, and durable clocks

`glass turn append --body` commits the public prose into the structured turn
feed. Markdown transcript exports may be refreshed for human review, but they
are derived artifacts.

## Public Prose

Public prose is submitted only through:

```bash
glass turn append --body "<public prose>"
```

Provider stdout is not public prose. A final chat response is not public prose.
A markdown file is not public prose. Literal `glass ...` command lines inside
the prose do not execute commands.

## Action Scenes

Action scenes use the same turn loop with tighter expectations:

- keep one actor invocation atomic: upkeep, movement, one action, any roll, and
  immediate outcome narration
- use scene clocks, HP, inventory, consequences, messages, and neutral facts
  when the result must not drift
- record visible objectives and durable action-scene facts in the graph
- submit the final narration with `glass turn append --body`

DM-side player-character checks are allowed when resolving them in the current
DM turn avoids an unnecessary actor transition. Player-initiated rolls remain
player-called on player turns.

## What The Loop Does Not Do

- It does not retry a weird turn automatically.
- It does not edit prior turns.
- It does not parse prose for "intent" fields or hidden schemas.
- It does not accept file artifacts as a completed turn.
- It does not make narrative decisions for the agents.
