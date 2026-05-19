# Scene Ending — Closure Design

**Status:** Deferred. We are not building this yet. The goal of v1 is "something that even plays" — a session that runs end to end, even if it ends badly. This document captures the closure design so we can return to it once a working loop exists and we can see the failure modes for ourselves.

**Do not implement layers from this doc until v1 produces transcripts.** When we come back, read the transcripts first and let real failures choose which layers to build.

**Note for revisitors:** the layers below assume a "DM emits structured turn-delta block" pattern that has since been ruled out — see [`turn-loop.md`](turn-loop.md). When this design is picked back up, the budget-tracking and twist-counting layers need to be redesigned to work from prose + `glass` audit log instead of from agent-emitted YAML. The closure questions (what to track, how to apply pressure, when to force wrap) are unchanged; only the *plumbing* needs revisiting.

---

## The Problem

Observed in the-glass-frontier prototype: a great chase scene almost reaches its conclusion, then the DM throws in another twist. The scene never reaches the finish point. Same shape repeats at session level — sessions don't end because there's always another beat to add.

LLM default helpfulness is to continue the conversation. "Add interesting detail" / "raise the stakes" / "say yes" all cut against closure. Each turn looks locally fine — only a global view sees the runaway. Player agents are also helpful and propose continuations, not endings.

**Implication for our design:** prompting alone will not solve this. Closure must be guarded in multiple layers, with at least one layer that the agents cannot override.

---

## Three Scales of Closure

Closure isn't one problem. It operates at three nested scales, each with its own machinery:

| Scale | What's closing | Failure mode | Budget unit |
|-------|----------------|--------------|-------------|
| **Beat** | A single dramatic moment within a scene (a check resolves, an NPC reacts, a clue surfaces) | "Yes, and…" forever — the moment never lands | Turns |
| **Scene** | A full play-mode block (the chase, the negotiation, the combat) | The chase that gets one more twist | Beats per scene + wall-clock turns |
| **Session** | The whole sitting, with a clear stopping point | New mode keeps starting, party never goes home | Scenes per session + arc-completion |

Don't conflate them. The same shape of guard applies at each scale, but the budgets and signals are different.

---

## The Layers

Ordered cheapest → most elaborate. Build all of them eventually; pick the starter combination based on what failures we actually observe.

### Layer A — Pre-declaration

When entering a mode, the DM writes a structured `mode-entry` block before any turns fire:

```yaml
mode: action
scene_id: chase-through-ringglass-market
resolution_conditions:
  - party escapes the market patrol
  - party is captured
  - party kills/disables the patrol leader
turn_budget: 120
twist_budget: 2
stakes_ceiling: high
```

Orchestrator validates the block exists. Every subsequent DM turn gets the resolution conditions injected with "are any of them met yet? answer yes/no per condition."

**Why it works:** forces the DM to commit to "what done looks like" *before* it starts narrating, and to re-evaluate against that commitment every turn. Removes the wiggle room.

### Layer B — Hard budgets (orchestrator-enforced)

`turn_budget` and `twist_budget` are counted by the orchestrator, not the agents.

- At 75% of `turn_budget`: orchestrator injects `WRAP PRESSURE: 90 of 120` into the DM prompt.
- At 100%: orchestrator forces `mode end`. DM must narrate closure with whatever state exists.

The DM doesn't get to vote on this. **Single most important guard.** Soft pressure never works alone.

### Layer C — Twist budget

DM gets N "twists" per scene. A twist = introducing a new complication, NPC, threat, or stakes raise. Once the budget is spent, the DM is structurally prevented from adding new threats — only resolution paths remain.

Mode-scoped:
- combat: 1
- chase / pursuit: 1
- investigation: 2
- town / social: 3

Tracked by the orchestrator from the DM's structured turn-delta block (see open question below). This layer is what actually kills "one more twist."

### Layer D — Scene-closer agent (independent vote)

A separate `claude -p` invocation, different role prompt, run every K turns. Sees only the recent transcript and the resolution conditions. Returns a structured verdict:

```yaml
should_close: true|false
reason: "the chase has reached the rooftop; resolution_conditions[0] is satisfiable now"
confidence: 0.7
```

If `should_close=true` above a confidence threshold, orchestrator forces wrap.

The closer is **biased toward closure** — its prompt explicitly says "you exist because DMs add too many twists; lean toward ending." Counterweight to the DM's continuation gradient. Mirrors `chronicle-closer` from the-glass-frontier.

### Layer E — Outcome-tier as closure signal

The skill check ladder already produces `breakthrough` / `advance` / `stall` / `regress` / `collapse`. Reinterpret these as closure pressure:

- `breakthrough` → resolution condition is now satisfiable; DM should close on this beat unless there's strong reason not to
- `collapse` → failure resolution available; close on this if appropriate
- `advance` / `regress` → progress, scene continues
- `stall` → no progress; if budget is tight, stall counts as wasted turns

Orchestrator surfaces this as a count to the DM: "3 stalls in last 4 turns; consider whether the scene has stopped progressing."

### Layer F — Prompt design

DM system prompt explicitly: *"Your job is to RESOLVE scenes, not extend them. The most boring DM extends every scene. The best DM closes scenes at their natural peak. Default to closing earlier than you think."* Plus per-scale variants for sessions and beats.

Necessary but never sufficient. The floor, not the ceiling.

---

## Session-Level Closure

Same shape, different scale. Sessions need an **arc declaration** at start:

> "This session will advance thread `reconnection` from beat 3 to beat 4 OR finish at beat 3 with a memorable scene."

Once that beat is advanced (or definitively unreachable), the session enters wrap pressure. Session has a max-scenes cap. **Wrap is itself a mode** — DM produces a session summary, persists graph deltas, the loop ends.

---

## Recommended Starter Combination (for whenever we revisit)

Build **A + B + F**, with skeleton hooks for C and D so they can be wired in without refactoring:

- A + B together (pre-declaration + hard budgets) gives ~80% of the benefit for ~20% of the work.
- F is just prompt copy.
- C (twist budget) is the next layer to add once we see what fails. Probably needed before any combat scene works.
- D (closer agent) is the cleanest backstop but the most expensive in invocations. Add once we have transcripts to tune the prompt against.
- E falls out of the mechanics layer for free once outcome tiers are wired through.

---

## Open Question

How structured do we want the DM's per-turn output? Imagined shape:

```markdown
## DM Turn 4
[in-character narration that goes into the transcript]

---
delta:
  resolution_check: condition[0] not yet met
  twists_used_this_turn: 0
  next_speaker: tev
  scene_status: in_progress
```

That gives the orchestrator everything it needs to enforce budgets without re-parsing prose. But it makes the DM more structured and less "fun" to read.

Tradeoff to settle when we revisit: strict structured output vs. orchestrator that parses freer DM output.
