# Goals and Motivation

This project asks specific questions about agentic systems by setting up a controlled experiment in tabletop RPG form. This document is the deep "why."

## The Core Questions

### Q1. Does multi-agent autonomy produce richer fiction than single-prompt generation?

Single-prompt narrative generation has a known flat affect — competent, polished, predictable. Multi-agent systems with constrained autonomy might produce something with more texture: characters who *push back* on each other, mistakes that don't get retconned, in-jokes that emerge across turns, friction that a single-prompt narrator would smooth out.

We don't know this is true. We set up the experiment to find out.

### Q2. What's the right shape of constraint?

A fully unconstrained multi-agent loop will drift, contradict itself, and (as observed in the-glass-frontier prototype) never reach closure. A fully constrained loop will produce something indistinguishable from single-prompt output. The interesting territory is between.

This project's structure — typed turn shape, mode-specific protocols, hard budgets, gatekeeper-mediated graph writes — is one specific point in that space. We expect to revise it.

### Q3. What does the corpus look like as a first-class artifact?

The transcript is the product. The graph is the product. The character notes are the product. Each turn produces a structured record that future passes can mine. We don't know what those passes will be — narrative weaving (similar to ice-remembers), arc summarization, character voice analysis, plot-structure extraction — but they all need the corpus to be richly structured at write time. See [transcripts-as-corpus.md](transcripts-as-corpus.md) for the deeper commitment.

## What Success Looks Like

A working v1 produces:

1. **A transcript** of a played session that reads like a real game — banter, OOC commentary, friction, dice talk, in-character speech.
2. **A persistent graph** that captured what happened: NPCs encountered, locations visited, beats advanced, threads progressed.
3. **Hard-state records** that survived the session — character HP changes, inventory deltas, momentum trajectories.
4. **A loop that ended on its own.** Even if badly. Even if abruptly. The session must terminate without intervention.

A v1 that produces all four is a success regardless of whether the transcript is "good." The interesting work — improving fiction quality, tuning closure, deepening the agents — happens *after* the loop runs end to end.

## Non-Goals

This project is **not**:

- A product anyone is meant to use as a TTRPG aid
- A multiplayer game with AI players
- A general-purpose agentic framework
- A port of the-glass-frontier
- A re-implementation of the-glass-frontier-lore tooling

We resist scope creep toward any of these. Each one is a different project that would smother the actual experiment.

## The Research Frame

Treat this as a long-running experiment, not a feature roadmap. Consequences:

- **Capture, don't curate.** Every transcript is preserved, even (especially) the broken ones. The failures are the data.
- **Instrument before optimizing.** Add structured emission first; tune behavior second.
- **Prefer reversible over robust.** Easy to change the agent personalities, the mode set, the mechanics. Hard to change the transcript schema or the graph topology — design those for evolution.
- **One question at a time.** Don't try to answer Q1, Q2, and Q3 simultaneously. Pick the question the next iteration is investigating, and tune for it.

## Why TTRPG?

Because it's a domain where the failure modes are visible and meaningful. A tabletop session has a clear shape — scenes, beats, resolutions, sessions — and the breakdowns of that shape (the chase that doesn't end, the NPC who behaves inconsistently, the player who never gets the spotlight) are immediately legible to anyone who has played a game. We don't need to invent metrics; the form provides them.

It's also a domain where structure and improvisation coexist, which is exactly the question we want to study.

## What This Document Is Not

This document doesn't describe *how* the system works. For that, see [docs/design/](../design/). It also doesn't enumerate specific milestones — those are conversation-scope, not document-scope. The goals here are durable; the milestones change weekly.
