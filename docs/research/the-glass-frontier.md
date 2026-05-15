# the-glass-frontier

Located: `/home/dev/repos/the-glass-frontier`

## What It Is

A TypeScript monorepo (turbo + pnpm) implementing a single-player AI-driven narrative chronicle engine for the same Kaleidos setting. A player chats with a GM; the GM narrates, calls skill checks, tracks beats, updates inventory, advances the world. Lambda + S3 + DynamoDB on the AWS side; React + Vite on the client.

Production-ish code with serious shape. Most of it is plumbing (Lambda glue, WebSocket progress events, prompt template runtime, chronicle storage). The interesting parts for us are the game design pieces, not the architecture.

## Architecture We're Cribbing

### Game math (`packages/skill-check-resolver/`, `packages/dto/src/mechanics.ts`)

- **Original source math:** 2d6 + skill mod + attribute mod + momentum vs risk threshold.
- **Current Agents of Glass math:** 1d10 + skill mod + attribute mod.
- **Current risk levels:** controlled=5, standard=6, risky=7, desperate=8.
- **Outcome tiers:** breakthrough / advance / stall / regress / collapse with momentum deltas of +2/+1/0/-1/-2.
- **Tier thresholds (by margin):** ≥+2 breakthrough, 0..+1 advance, -1 stall, -2..-3 regress, ≤-4 collapse.
- **Attribute tiers:** rudimentary (-2), standard (0), advanced (+1), superior (+2), transcendent (+4).
- **Skill tiers:** fool (-2), apprentice (0), artisan (+1), virtuoso (+2), legend (+4).
- **Momentum** clamped to `[-2, +3]`, narrative-only.

We keep the tier labels, modifiers, and momentum clamp, but tuned the check die
and risk thresholds for multiplayer agent play. Momentum no longer modifies
check totals; after a check updates momentum, `> 2` means add one extra good
visible consequence, `<= 0` means add one extra visible complication, and `1`
or `2` has no extra rider.

### Intent taxonomy (`packages/dto/src/narrative/IntentType.ts`)

`action`, `inquiry`, `clarification`, `possibility`, `planning`, `reflection`, `wrap`. Used to route player utterances to different DM behaviors. We adopt this directly — see [`../design/turn-loop.md`](../design/turn-loop.md).

### GM pipeline shape (`apps/gm-api/src/gmGraph/orchestrator.ts`, `gmEngine.ts`)

The single-player engine runs each player message through:

```
intent-classifier
  → (beat-detector ∥ check-planner)
  → entity-selector
  → check-runner
  → gm-response (per intent type)
  → (entity-judge ∥ beat-tracker ∥ gm-summary ∥ inventory-delta ∥ location-delta)
```

We're not implementing this pipeline — for us, much of it collapses into the DM agent's own tool loop. But the *shape* is informative: classify → adjudicate → resolve → narrate → post-update is roughly what a turn does.

### Chronicle closure (`apps/chronicle-closer`)

A separate service whose job is to decide when a chronicle is done and emit a closure event. We crib this directly — our scene-closer agent (deferred design, [`../design/scene-ending.md`](../design/scene-ending.md)) has the same shape: separate agent, no narrative authority, just votes on closure.

### Prompt runtime (`apps/gm-api/src/prompts/`)

Template-based prompts with context fragments injected per template. We probably won't need this complexity — markdown role prompts + scene-context strings should suffice — but the *idea* of "swap context fragments per intent type" is a reusable trick.

### Postgres knowledge graph schema (`POSTGRES_MIGRATION.md`)

A generic property graph (`node` + `edge` tables) plus thin typed companion tables (`character`, `location`, `chronicle`, `chronicle_turn`). They're moving toward this from earlier S3-blob storage. We'll likely *not* use this exact schema (we prefer FalkorDB for the graph), but the typed-companion-table pattern is good for our hard-state Postgres.

## What We're Explicitly Not Cribbing

- **The TypeScript stack.** Python is the orchestrator language. No reason for two languages.
- **Lambda / API Gateway / WebSocket plumbing.** We're not building a service.
- **The React client.** No human at the table; no UI.
- **The S3-based world-state stores** (`packages/persistence`). FalkorDB + Postgres replace these.
- **The world schema versioning** (`worldSchema.json`, `apps/world-schema-api`). Useful for a multi-tenant product; not for our experiment.
- **The progress emitter** (Step Functions → SQS → API Gateway). Our orchestrator is in-process.
- **The DTO Zod layer.** We'll have our own type contracts in Python, simpler.

## Key Files to Re-Read When Designing

- `apps/gm-api/src/gmEngine.ts` — top-level turn handling
- `apps/gm-api/src/gmGraph/orchestrator.ts` — pipeline structure
- `apps/gm-api/src/gmGraph/nodes/classifiers/IntentClassifierNode.ts` — intent classification prompt shape
- `apps/gm-api/src/gmGraph/nodes/IntentHandlerNodes.ts` — per-intent response styles, temperatures
- `packages/skill-check-resolver/src/SkillCheckResolver.ts` — the math
- `packages/dto/src/mechanics.ts` — the constants
- `POSTGRES_MIGRATION.md` — graph + thin-table schema reference
- `AGENTS.md` — their guardrails (some transferable: "preserve user-authored tweaks," "no fallback logic")

## Open Questions

- **How much of the GM pipeline collapses into a single DM-agent prompt vs stays as separate orchestrator stages?** Probably most of it collapses (the DM is one Claude call), but adjudication might want to be separate to keep DM context smaller per call.
- **Do we want the same intent taxonomy for player→DM that they use for player→GM, or do we want fewer/more intents for a five-person table?** Their taxonomy was designed for 1:1; we may need different categories when players talk to each other.
