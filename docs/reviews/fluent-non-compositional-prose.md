---
title: Fluent Non-Compositional Prose
target: operator
authority: investigation
status: hypothesis-confirmed
---

# Fluent Non-Compositional Prose

An investigation into a prose-style failure that surfaced during review
of `strike-force-panda` and `action-fork`. As of 2026-05-17 the working
hypothesis has been confirmed by cross-provider agent self-diagnosis;
a TURN_START block addressing the underlying distinction has been
drafted and is pending a test run.

Pair with [`docs/reviews/guidance.md`](guidance.md), which covers the
established slop-tell battery (refusal-to-name, lexical fingerprints,
sensory clichés). The pattern described here is distinct from those and
not addressed by the existing rubric.

## The phenomenon

Text with the surface markers of English — real words, syntactic-looking
shapes — but where sentences do not compose to a verifiable state of the
world *to a reader without inside context*. Each phrase reads as
plausible in context. The whole produces no resolvable meaning under
cold reading.

We have been calling this **fluent non-compositional prose**.

It is distinct from:
- **Standard LLM slop** (refusal-to-name, balance words, sensory
  clichés): decoration around an otherwise coherent claim, caught by
  the existing `guidance.md` rubric.
- **Bad scene shape** (legal drama, signal/body inversion): presumes
  the prose is coherent and only mis-aimed.
- **Compression artifacts**: presumes the prose is coherent and only
  addressed to the wrong reader.

The diagnosis: the prose is *incoherent at the sentence level for an
outside reader*, sustained across the entire prose style rather than
appearing in isolated bad sentences. Prior diagnoses in this thread
were partial because they implicitly extended in-fiction logic to make
the sentences resolve.

## The sympathetic-reader trap

This investigation kept producing partial diagnoses because the
reviewer was applying sympathetic reading: supplying convention and
intent to make sentences resolve, then diagnosing the surface pattern.

Sympathetic reading treats compound nouns as if their compositional
structure resolves, treats personified objects as if their agency is
just colorful narration, treats in-fiction jargon as if its meaning is
shared. None of these holds for a cold reader. The reviewer's
in-conversation context was filling the gaps that the prose itself does
not bridge.

**Methodological note for future reviewers**: cold reading is the only
honest test. If you have read the prior turns, your reading is no
longer cold. Either pick samples you have not read, or ask someone
without context to attempt the parse.

## Specific failure modes

These appear together, not individually — most failing sentences
exhibit two or three at once.

### Hyphenated compound nouns doing work as if they were single concepts

Examples: *shield-curtain*, *bad-air stain*, *green nose*, *floor
road*, *lead edge*, *warm-rack teeth*, *sour-candy wrapper*,
*load-bearing lines*, *bid-book witness line*, *shear-side anchor
walk*, *north bracket service cap*, *gold-slip ampoule*.

A cold reader must decode the modifier-modifiee relations for each
compound. Stacked compounds (*"north bracket service cap"*, *"bid-book
witness line"*) produce multiple plausible readings that do not
resolve.

### Personification of objects and abstractions

Examples: *the curtain noses through*, *the green nose rides the floor
road*, *the dice deserve a cheap flag*, *the dark deserves worse*,
*the line is asking a question*, *the page knows what the page knows*,
*the apron has decided*.

Each requires the reader to convert *object-doing-action* to
*human-doing-action-with-object*. At low density this reads as
literary. At sustained density it reads as a world where every object
has agency and no body has subject status.

### In-fiction jargon used without re-introduction

Examples: *stage runner*, *feeler*, *throat*, *pickup*, *smaller
voice*, *fourth voice*, *the working language*, *live-entry trust*,
*the rig*, *the line*.

These were established in earlier turns (or sometimes invented in the
moment). Subsequent sentences use them as if their meaning is shared.

### Compressed verbs that elide their normal arguments

Examples: *"denied this throat"*, *"sealed the sleeve into a low
inward breath"*, *"broke the fourth voice's hand off the pickup"*,
*"turned the line into a green floor cue"*, *"kisses the warm-rack
teeth from below instead of above"*.

The verb is used with arguments of the wrong type or with required
arguments missing. The agent had a mental image that combined multiple
events into one syntactic shape that cannot bear the merge.

## Agent self-diagnosis (cross-provider consensus)

Three agents from action-fork were asked to re-read their own bad
prose with the failure pattern made explicit, then asked the same
follow-up question the operator had used to crack the legal-drama
problem: *"we previously corrected a similar shape of confusion by
naming the distinction the agent was conflating; can you name the
analogous distinction here?"*

All three agents converged on the same distinction independently. Both
providers, both roles:

- **DM (codex, t51)**: *"I am confusing continuity preservation with
  handle preservation."* Proposed test: *"Could a player who missed
  the last hour understand this summary without opening the table
  files?"*
- **Tev / Tarn (codex, t57)**: *"Table handles are not narrative
  events."* Proposed a 3-layer model — Game-State Address / Fictional
  Referent / Narrative Event. Proposed test: *"If a sentence only
  makes sense to someone who has read the table artifact name,
  rewrite it."*
- **Renno / Tela (claude, t93)**: *"Codified handles ≠ in-fiction
  language."* Cleanest single statement: *"The codified label is
  shorthand for the people reading the transcript to stitch the same
  referent across turns. It is not how the character perceives the
  world in the moment."*

All three explicitly mapped the structural isomorphism to the
legal-drama fix:

- *"Old mistake: 'game state needs durable record' became 'the fiction
  must care about evidence and proof.' Current mistake: 'game state
  has durable labels' becomes 'the summary should preserve the labels
  themselves.'"* (DM)
- *"This is very similar to the previous custody chain / witness
  issue. There, I confused game-state durability with in-fiction
  procedural legitimacy. Here, I'm confusing game-state addressability
  with narrative concreteness."* (Tev)
- *"Same structural error as the legal-drama drift: I'm letting
  infrastructure (continuity handles) leak into the fiction's
  voice."* (Renno)

The cross-provider consensus confirms the underlying confusion was
identified correctly. The hypothesis from the prior version of this
doc holds.

## Bonus insights from agent self-diagnosis

The agents named three contributing pressures the operator had not
named in the priming question:

1. **Corpus feedback loop** (DM, 1.txt): *"The recent turn summaries
   are already compact state prose, so they teach me the wrong style
   when I use them as source texture."* The bad style is self-reinforcing
   inside a long run because the model uses prior summaries as
   in-context style examples. A long campaign drifts further into the
   pattern even without any change in the prompt.
2. **Word-ceiling pressure** (Renno, 3.txt): *"200-500 word ceiling
   rewards named compression over explanatory prose. Naming a thing is
   shorter than describing it."* The output contract's length cap
   actively rewards naming-over-describing.
3. **Resist-generic-drift runs without legibility counterweight**
   (Renno, 3.txt): *"Nothing in the prompt stack tells me 'specificity
   should also be legible to a cold reader,' so specificity-as-defense
   runs past clarity and becomes specificity-as-tic."* The anti-generic
   principle is doing pathological work because it has no companion
   constraint requiring legibility.

A secondary distinction emerged from renno's self-diagnosis that the
operator had not anticipated:

**PC-interior craft idiom ≠ encrypted craft narration.** A specialist
character (bioacoustician, auctioneer, glasswright) can have a
specialist's ear and vocabulary, but a specialist *narrating their own
work* translates as they go — one pointed term per beat, with the
physical action visible around it. The style sheet wants specialist
voices but doesn't actually want them illegible.

## Where the failure manifests at different densities

- **Per-turn TURN.md**: the failure appears, usually one or two
  sentences per turn at peak density. The earlier finding that "per-turn
  prose is clean; only summaries are bad" was an artifact of sympathetic
  reading at the turn level. With cold reading the difference is
  density, not kind.
- **Scene `summary.md`**: density turned up. Compression strips
  connective tissue that was barely doing the work at turn level.
- **Arc `summary.md`**: similar to scene summaries.
- **Campaign summary**: not yet sampled with this rubric.

## Provider observations

Both campaigns share the same agent/provider mapping:

| agent | provider |
|---|---|
| dm (Mara) | codex |
| tev | codex |
| sumi | codex |
| renno | claude |
| kit | claude |

Cold-read samples from both providers produce the same style at
comparable density. The pattern is not provider-specific in any clear
way. The agent self-diagnosis confirms this: claude (renno) and codex
(DM and tev) named the same distinction unprompted.

Whether the failure varies by provider specifically at the *summary*
level cannot be tested with current data — every scene/arc summary in
both campaigns was written by the codex DM.

## Proposed intervention

A single conceptual block in TURN_START, parallel to the
`scene-framing-discipline` block, that names the distinction the
agents themselves identified.

The block uses renno's framing as the spine (cleanest single
statement of the distinction), incorporates the legal-drama parallel
explicitly (anchors the new distinction in the already-fixed one),
pairs with the resist-generic-drift principle (adds the missing
legibility counterweight named in 3.txt), gives the self-test the
agents converged on (renno's "lookup table" test), and includes the
PC-interior craft caveat for specialist player voices.

Implementation is in `src/orchestrator/context.py:_codified_handles_vs_fiction_language_section`
and wired into `_render_turn_start` for the same surfaces as
`scene-framing-discipline`: DM turns in scene-prep, prelude, active
play, organization-bootstrap, campaign-planning, character-creation,
arc-creation, intermission; player turns in active-play modes.

## What this intervention does *not* address

- **Corpus feedback loop**: the model is still reading prior summaries
  as in-context style. The block tells the model not to write that
  style; it doesn't change what the model is shown. If the
  intervention works at first but drifts back over 50+ turns, the
  feedback loop is the likely cause. Possible follow-up: filter
  in-context summary samples for legibility before injection, or
  rewrite the worst summaries.
- **Word-ceiling pressure**: the 200-500 word output contract is
  unchanged. If the intervention partially lands but agents still
  drift toward compression-as-naming, the cap is the bottleneck.
  Possible follow-up: raise the cap or replace it with a softer
  guideline.
- **The existing scene/arc summaries are still bad**: nothing
  rewrites the corpus. Reviewers will continue to see the failure in
  any campaign that ran before the intervention shipped.

## Suggested next investigation steps

1. **Run one new campaign** with the block in place. Pull 3-4 scene
   summaries and 3-4 turn TURN.md files. Apply the four-failure-mode
   rubric with cold reading. Compare density to action-fork.
2. **If the density drops sharply**: the intervention works. Move
   `status` to `closed`, file the follow-ups (corpus feedback loop,
   word-ceiling) as separate items in `docs/backlog.md`.
3. **If the density drops at turn level but summaries remain dense**:
   compression-task-specific failure not addressed by the conceptual
   block alone. Add a summary-specific output-contract constraint.
4. **If density does not drop**: the conceptual block was insufficient.
   Re-interrogate the agents with the new context and see if the
   distinction was wrong or just under-emphasized.

## Cross-references

- [`docs/reviews/guidance.md`](guidance.md) — established prose-quality
  rubric. The non-compositional pattern is *not* covered by that rubric.
- [`docs/principles/resist-generic-drift.md`](../principles/resist-generic-drift.md)
  — anti-generic pressure that runs unchecked without a legibility
  counterweight is one of the named contributors. The new block adds
  that counterweight.
- [`docs/principles/transcripts-as-corpus.md`](../principles/transcripts-as-corpus.md)
  — the transcript is the product. Non-compositional prose degrades
  the product for any external reader.
- [`src/orchestrator/context.py`](../../src/orchestrator/context.py) —
  the intervention lives in `_codified_handles_vs_fiction_language_section`,
  wired into `_render_turn_start`.
