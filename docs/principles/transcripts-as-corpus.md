# Transcripts Are the Corpus

The transcript is the product. Everything in this project bends to that.

Companion principle: [`codify-only-what-drifts.md`](codify-only-what-drifts.md) governs which parts of the corpus are structured (orchestrator + CLI emit them) and which are prose (agents emit them). Read together.

## What This Means

- Every turn produces a structured record, not just a chunk of prose.
- Every state mutation is captured in line with the prose that caused it.
- Every speaker is identified. Every dice outcome is recorded. Every mode transition is marked.
- The transcript can be replayed, indexed, and consumed by future analysis without re-parsing prose to recover structure.

## Why

We want to do things to transcripts later that we don't fully know yet. Some examples we already anticipate:

- **Narrative weaving** — turn the raw transcript into prose fiction (similar to ice-remembers).
- **Arc analysis** — measure beat advancement, theme engagement, character development across sessions.
- **Voice analysis** — characterize each agent's distinctive style.
- **Plot extraction** — pull a campaign-shape outline from a corpus of sessions.
- **Failure-mode mining** — find the exact turn where a chase started running away from closure, study the conditions, fix the layer that should have caught it.

All of these are *vastly* cheaper if the transcript is structured at write time. Recovering structure from prose later is research-grade NLP work; emitting it inline is a tagging convention. Pay the cost once, at the source.

## Implications for Every Other Decision

This principle has consequences that touch most of the system:

**The agent emits prose. The orchestrator emits structure.** Agents don't write YAML delta blocks at the end of their turns. They write what they have to say, calling `glass` for any mechanical thing along the way. The orchestrator wraps each turn with a structured header (speaker, role, mode, scene, turn number, timestamp) and inlines mechanical event lines (rolls, HP changes) drawn from the `glass` audit log. Structure comes from the metadata around the prose, not from forcing the agent to author both.

**The durable home is Postgres.** The agent's per-turn `TURN.md` is an
operational handoff file. `glass turn append` commits that prose into
Postgres `turns.prose`, links/inlines pending events, and refreshes campaign
and scene markdown transcript exports. Viewers and narrative-weaving passes
consume the structured turn feed, not per-agent turn folders.

**Two layers per turn: in-character + out-of-character.** Real TTRPG transcripts have both. Tev says "I'm rolling perception" (OOC); Karrith says "what was that sound?" (IC). The transcript preserves both, distinguished by the agent's own prose conventions (e.g. `Tev (OOC):` vs `Karrith:`). We don't enforce the distinction with a schema field — the agents are smart enough to mark their own register, and human readers and narrative-weaving passes can pick it up just fine.

**Speakers are people, not roles.** The transcript records "Tev said X," not "player_2 said X." Same for the DM. This means the people files (`mara.md`, `tev.md`, etc.) are part of the corpus — readers later need to know *who* Tev is to make sense of what Tev said.

**State mutations are events, recorded by the CLI, not by the agent.** When Karrith takes 3 damage, the agent calls `glass character set-hp karrith -3`. The CLI logs the event to Postgres and the orchestrator inlines a one-line mechanical event (`> ❤️ karrith hp -3 (5 → 2)`) into the transcript at the right point. The agent doesn't repeat the mutation in a structured field at the end of their turn. Snapshots can be reconstructed from the event log; events can't be reconstructed from snapshots.

**Mode transitions are first-class records.** "Entering action at chase-through-ringglass-market" is its own transcript entry, written by the orchestrator when the DM calls `glass mode start action`. Scene `--type` carries labels like combat or chase; mode boundaries are how analysis later carves the corpus into scenes.

**Failures are preserved.** A session that ended badly is more valuable than a session that didn't end. Don't delete bad runs. Don't auto-retry. The corpus includes the wreckage.

## What the Transcript Looks Like

Working hypothesis (subject to revision in [`../design/turn-loop.md`](../design/turn-loop.md)):

```markdown
## Turn 17 — Tev (player) — exploration, ringglass-gantry-approach

Tev (OOC): "I'll try to climb the gantry — risky athletics?"

Karrith grabs the rail and starts hauling himself up, wind whipping the kite-cord around his ankle.

> 🎲 athletics (vitality) @ risky → 6 vs 7 → stall

He gets a few rungs up before the wind catches him sideways and he has to lock both arms around the rail, breathing hard.
```

The prose section is what humans (and narrative-weaving) read. The header is the orchestrator's; the `> 🎲` line is inlined from the `glass roll` audit log. There is no trailing YAML block. The canonical structured record (full roll context, the dice, the modifiers, the outcome) lives in Postgres against the `roll_id`, where analysis can find it whenever it needs more than the inline summary.

## What Belongs in the Corpus and What Doesn't

| In the corpus | Not in the corpus |
|---------------|-------------------|
| Every turn (DM and players) | Internal agent reasoning that didn't make it to a turn |
| OOC and IC speech | Prompt scaffolding sent to agents |
| Dice events with full context | Raw LLM API logs |
| Mode transitions | Orchestrator plumbing logs |
| State deltas (HP, inventory, momentum) | State snapshots (those go in the hard-state DB) |
| Notes ratified by the DM into canonical lore | Players' private journals (those are per-agent, separate) |
| Failed sessions, malformed turns, abrupt endings | Anything we tried to "fix" by rewriting after the fact |

## The Single Test

If a future analysis pass needs to ask "what happened in turn 17 of session 4?", the transcript must answer fully without consulting any other file, *including* who was speaking, in what mode, against what resolution conditions, with what dice outcome.

That's the bar.

## Schema Stability

While we're rapidly ideating, schema changes of any shape are fine — add fields, remove fields, rename, restructure. Don't carry crust to preserve old runs. Toss broken transcripts and regenerate as the shape stabilizes.

We will tighten this once the project settles into a regular cadence and old transcripts start being worth keeping. Until then: move fast, break the corpus, regenerate.
