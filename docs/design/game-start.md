# Game Start

The bootstrap flow that takes a fresh repo from "no campaign exists" to "real
scenes are running." The same agent contract applies from organization
definition through character creation and scene play: agents interact only
through `glass`.

For the workflow docs the agents read inside each phase, see
[`/templates/methodologies/`](../../templates/methodologies/). For the runtime
instruction surface, see [`instruction-surface.md`](instruction-surface.md).

## The Phases

```text
0. INIT (operator)
   aog campaign new <id>
   - create campaign runtime state
   - copy reference templates for operator/debug use
   - phase -> campaign_planning

1. CAMPAIGN PLANNING (DM solo)
   - define organization, premise, operating constraints, and starting pulls
   - record durable facts with `glass fact set` / `glass done --fact`
   - submit public campaign brief with `glass turn append --body`
   - phase -> character_creation

2. CHARACTER CREATION (DM + players)
   - players create character records through `glass character ...`
   - relationships, roles, drives, and public commitments become neutral facts
   - public introductions and relationship prose use `glass turn append --body`
   - phase -> prelude when all required character records and relationship facts exist

3. PRELUDE (DM + players)
   - run a short first incident: one scene-play scene and one action scene
   - use normal scene, fact, roll, tracker, clock, and prose commands
   - phase -> active

4. ACTIVE
   - run scenes indefinitely under the normal turn loop
```

There are no sessions. A scene is the unit of play; its type label helps the DM
frame the protocol without creating a separate state surface.

## Phase State

Each campaign has one runtime state row in embedded SQLite. Conceptually, it carries:

```json
{
  "campaign": "kaleidos-1",
  "phase": "campaign_planning",
  "active_arc": null,
  "active_scene": null,
  "turn_number": 0
}
```

Phase values: `init`, `campaign_planning`, `character_creation`, `prelude`,
`active`.

The orchestrator updates runtime state after committed turns. Phase transitions
are explicit, not inferred from prose.

## Agent Output Requirement

Every agent turn produces two CLI outputs:

```bash
glass done --summary "<compact continuity>" --state "<state delta or none>" --rolls "<rolls or none>" --fact "<neutral fact>"
glass turn append --body "<public prose>"
```

If a phase creates durable continuity, that continuity must be recorded through
facts or purpose-built state commands. Public prose alone is not enough.

## Operator Files

`aog campaign new` may create `campaigns/<id>/` from templates so operators and
viewers have durable reference and exports. Active agents do not write those
files. During agent turns:

- facts go to SQLite through `glass fact ...`
- hard state goes to SQLite through purpose-built `glass` commands
- public prose goes to SQLite through `glass turn append --body`
- markdown exports, if any, are generated after commit

## Operator CLI Surface

```bash
aog campaign run <id>
aog campaign show [<id>]
aog campaign list
aog campaign checkpoint <id> [--label <text>]
aog campaign checkpoints <id>
aog campaign restore <id> <checkpoint-id>
aog campaign clear <id> --back-to <phase|arc|scene>
```

The operator CLI is not exposed to agents.

## Resumability

Every phase and every scene is resumable from the last committed CLI boundary.
If an agent invocation fails, times out, omits `glass done`, or omits
`glass turn append --body`, the orchestrator stops at the last committed turn.

Checkpoint/restore is an operator action and must include embedded campaign
rows and relevant campaign files/exports.
