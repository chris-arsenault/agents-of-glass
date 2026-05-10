# Codify Only What Drifts

The rule for what goes in a schema vs what stays in prose.

## The Principle

**Codify the things agents drift on. Everything else is prose.**

Codification — the `glass` CLI, Postgres tables, FalkorDB nodes and edges — exists as a *coherence mechanism*. Its job is to make sure five separate Claude invocations agree on the things they cannot reliably re-derive. It is not a turn-structure enforcer, not an intent classifier, not a play-style policy.

Outside the narrow list below, default to prose. The agents are smart enough.

## What's Codified

Drift-prone things that must stay consistent across agents:

- **Dice outcomes** — agents cannot generate fair randomness. `glass roll` produces verifiable rolls.
- **Numerical character state** — HP, momentum, attribute tiers, skill tiers. Agents lose track of numbers.
- **Inventory lists** — what items a character has, in what quantity. Agents will quietly add or drop things.
- **Canonical names** — places, NPCs, factions. The DM ratifies new entities into the graph; everyone references them by id.
- **Speaker / mode / scene / turn / session labels** — the orchestrator's own state. These are not in question by anyone.
- **Mechanical event timing** — when a roll happened, when HP changed, in what order. The audit log records these per turn.

That's the list. It's short on purpose.

## What's NOT Codified

These were tempting but stay in prose:

- **Intent classification.** No `action` / `inquiry` / `clarification` / `possibility` / `planning` / `reflection` enum. The DM reads the player's prose and adjudicates from it. The Glass Frontier intent taxonomy was a single-prompt-engine necessity; we have a real DM agent that can read.
- **Proposed checks / proposed actions.** Players narrate what they want to do
  and either roll directly on their turn or leave the situation for the DM to
  resolve in prose. When the DM needs a PC check on the DM turn, the DM rolls it
  directly; see [`minimize-actor-transitions.md`](minimize-actor-transitions.md).
  No `proposed_check: { skill: ..., risk: ... }` field.
- **Prepared abilities.** "I prepare my shield instead of attacking" is a thing the player wrote. The DM tracks it from prose. No `prepared_actions: [{ trigger: ..., effect: ... }]` array.
- **Visibility flags.** A hidden preparation is hidden because the prose says it's hidden ("Mork subtly attunes a barrier nobody can see"), and the DM honors that in their narration. No `visibility: dm_only` flag on actions.
- **Questions.** When a player asks the DM things, they ask in prose. The DM answers in prose. No `questions: []` array.
- **Interjection requests.** Players signal in their prose ("I want to back Renno up before Kit shoots this down") and the DM honors or doesn't. No `interjection_request:` field.
- **Next-speaker hints.** The mode's speaker rule plus the DM's judgment determines order. The agent doesn't emit a `next_speaker:` field.
- **Turn structure.** No "first declare, then roll, then narrate" enforced sequence. The agent writes their turn however the moment calls for it.

## Why

Two reasons. They reinforce each other.

**Schema enforcement is brittle.** A YAML delta block is a contract that fails silently when the agent emits it slightly wrong. Five `claude -p` invocations with five slightly-different schemas accumulating across hundreds of turns becomes unmaintainable. Prose is forgiving — there's no way for an agent to write prose "wrong."

**Schema enforcement gets in the way of the experiment.** This project is asking whether multi-agent autonomy produces richer fiction than single-prompt generation (see [`goals-and-motivation.md`](goals-and-motivation.md)). Forcing every turn through a structured delta block is exactly the kind of constraint that flattens fiction. We want texture; texture lives in prose.

## What Structure the Corpus Has

Despite all of the above, the transcript is a richly structured artifact. The structure comes from *metadata around the prose*, not from forcing the agent to author both:

- **Per-turn header** (orchestrator-supplied) — speaker, role, mode, scene, turn number, timestamp.
- **Inline mechanical event lines** (orchestrator-inserted from the `glass` audit log) — e.g. `> pressure Patrol leader HP: advance, impact d8=5 -> 2, -2 (8/8 -> 6/8)`.
- **Mode transition records** (orchestrator-supplied at `glass mode start` / `glass mode end`).
- **Dice events fully recorded in Postgres** — the inline summary is for readability; the canonical record (every modifier, the seed, the outcome math) is queryable by `roll_id`.

The agent writes prose. The orchestrator and the CLI wrap that prose in structure. Both ship in the same transcript file. See [`transcripts-as-corpus.md`](transcripts-as-corpus.md) for what that produces.

## The Single Test

Before adding a new structured field anywhere, ask:

> If the agents produce conflicting answers about this, will I lose the session?

If yes — codify it. HP drift would corrupt a combat. Inventory drift would corrupt a heist. Dice drift would corrupt every check.

If no — prose. Whether a turn was "an inquiry" or "an action" doesn't matter once the DM has responded. Whether a player "addressed" another player is read from the prose by everyone who needs to know.

When in doubt, prose. We can always codify later if drift shows up. We cannot easily de-codify once schema accretes — every consumer downstream gets shaped by the schema and unwinding it costs more than holding the line.
