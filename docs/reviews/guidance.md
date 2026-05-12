---
title: Transcript Review Guidance
target: operator
authority: reference
status: authored
---

# Transcript Review Guidance

This is the operator's reference for reviewing AoG transcripts and
agent-authored content for prose quality and slop tells. It encodes
findings from the test-7 review and from cross-project work on AI prose
fingerprints (see canonry's `docs/chronicle-review-guide.md` and
`docs/chronicle-corpus-review-guide.md` for related work).

It is *not* binding on agents. The agent-facing equivalents live in
[`templates/how-to/narration-craft-dm.md`](../../templates/how-to/narration-craft-dm.md)
and [`templates/how-to/narration-craft-player.md`](../../templates/how-to/narration-craft-player.md).

Pair with [`docs/principles/resist-generic-drift.md`](../principles/resist-generic-drift.md).

## When to use this

- After a test run, to score the corpus and flag patterns for the next iteration.
- During the run, to spot drift early enough to intervene at the methodology or how-to layer.
- When evaluating a new persona, methodology, or craft doc — does it actually move the needle?

Reviewer rules borrowed from canonry: no superlative corpus claims; rank
within batch; cite evidence not adjectives; "clean" not "flawless";
"has specific issues" not "failed."

---

## Quick scan — lexical and syntactic tells

These are the standard LLM-prose fingerprints. Scan first; if any cluster
hits, the prose has the textbook problem. A clean test run returns ~zero.

| Pattern | Flag if hits |
|---|---|
| `delve / tapestry / intricate / underscore / vibrant / bustling / nestled / stark contrast / rich tapestry / in the heart of / testament to / speaks volumes / delicate balance / ever-shifting / pivotal / commendable / resonate / facilitate / bolster / embark / illuminate / harness (figurative) / beacon` | any single hit is worth checking in context |
| "not X, but Y" / "isn't just A, it's B" / "more than just" | any |
| "It's worth noting" / "stands as a" / "serves as a" | any |
| Sensory clichés: ozone, copper/iron taste, racing heart, blood ran cold, breath caught, stomach dropped, hairs on the back of the neck | any |
| Generic fantasy defaults: ancient evil, whispered secrets, hidden truths, the very fabric, the weight of, the shadow of (figurative) | any |
| Em-dash density | >1 per 4 lines sustained |

Test-7 returned **zero** lexical-tell hits across this checklist. That
is the prose floor we're holding. Future runs should match.

## The dominant test-7 tic — refusal to name

The pattern: characters and narrators constantly gesture at what is *not*
being said, named, finished, or asked. The unsaid carries the weight; the
narrator winks at the reader; everyone has perfect telepathic comprehension.

Counted in test-7 (transcript.md, ~6,150 lines): **130-150 instances** of
distinct refusal-to-name moves, by far the dominant slop signature.

### Sub-flavors (with examples from test-7)

**1. Direct withholding** — "She does not say X." / "She doesn't say Y."
- L2598: *"Drova does not say please. She does not say if you would. She does not say go. The nod is the sentence."*
- L4161: *"She does not say Tek read the binding form or Inka spoke the…"*

**2. "Doesn't need to" — wry omniscience**
- L6024: *"She doesn't finish the conditional. It doesn't need finishing."*
- L5683: *"She doesn't say anything about what Bren didn't find. She doesn't have to."*
- L6270: *"She doesn't say it because everyone in the room can already hear it."*

**3. "The gesture is the speech"** — "X is the sentence/answer/message"
- L2599: *"The nod is the sentence and the nod has been given."*
- L3628-29: *"That is the answer to Fei's question and it is the answer the page already half-named."*

**4. Animate-object omniscience** — "the page knows," "the apron has decided"
- L4126: *"The page knows what the page knows."*
- L2639: *"the thing the apron knows."*

### Why it qualifies as slop

Applied against the canonry **story-vs-document axis** (see scoring
rubric below): refusal-to-name is the "**authorial commentary**" marker
and the "**conceptual where physical should be**" marker. Real
dramatization writes the gesture and the line. Slop writes "the gesture
is the line" and trusts the reader to fill it in.

It is also the model's reach for *gravitas without commitment*. A
committed line can be wrong, banal, or specific in ways that embarrass.
A withheld line costs nothing. At scale, the corpus stops dramatizing.

## Other test-7 tics

These are smaller but cluster with refusal-to-name as one rhythmic-and-semantic complex:

- **"Three breaths."** — 33 hits. Started as a character beat (Drova's
  forensic pause); spread to every character and narrator. Now a campaign
  metronome.
- **"X is the X" tautology** — *"The page is the page."* / *"The form is the form."* Dozens of instances. The model's go-to weight-conferring gesture.
- **Anaphoric negation** — *"She does not look at Tek. She does not look at Bren. She does not look at the office door."* Scene-painting through cascaded denial. Thematically fits witness/record; mechanically over-applied.
- **Hyper-procedural micro-gesture description** — every gesture itemized for hand, direction, height, register, count. Inside one turn: precise. Across the campaign: stage-manager blocking sheet.
- **Procedural metalanguage bleed** — *"graduated certainty," "consistent with," "in the courtesy register"* migrated from Drova's character voice into the DM narrator and other PCs. Quarantine failure.
- **Closing-beat formulaicism** — Mara's *"Mug stays in my hand. Apron still even. tev — your move."* sign-off repeated to tic-level. Authorial closing-beat tell.

## Story vs world-building document axis

Borrowed from canonry. Every turn (and the corpus as a whole) sits
somewhere on this axis. AoG scene-play should sit firmly on the **story** side.

| Story marker | Document marker |
|---|---|
| Active opening; subject acting | Passive opening; atmospheric, diffuse |
| Physical recurring motif (a tic-tracer that beeps gold) | Conceptual recurring trait (*"eyes that held too many timelines"*) |
| Bitter camaraderie / dark humor | Earnest authorial commentary |
| Deaths/decisions mid-action | Decisions in retrospect or in narration |
| Devastating concrete ending (single word, single image) | Thematic summary ending |
| Characters say wrong, banal, embarrassing things | Characters say nothing because everyone already knows |

Test-7 sat closer to the document side than scene-play should. The
refusal-to-name tic is the primary driver.

## House-style sameness diagnostic

The other corpus-level test from canonry: would these turns pass as written by
five different agents? In test-7 the answer was *no* — all five voices share
the same wry-omniscient epistemic posture and the same withholding cadence.

Diagnostic prompts:

- Take a player turn with the speaker label hidden. Can you identify which player wrote it?
- Take the DM closing beat from three different scenes. Are they distinguishable?
- Pick any two characters. Do they have different relationships to silence, to specificity, to confrontation?

If the answer is no, the persona layer alone is not carrying voice
distinctiveness. See the standing proposal at
[`/narration-voice-library-proposal.md`](../../narration-voice-library-proposal.md).

## Scoring rubric

Use this at the end of every review pass. Keep comments specific —
cite a line, not an adjective.

| Dimension | Stars | What it measures |
|---|---|---|
| Standalone quality | ★/5 | Is this good fiction? Momentum, texture, weight, would a reader finish it? |
| Machine-generation tells | ★/5 | Lexical tells, refusal-to-name density, sensory clichés, hedging, balance words |
| Story vs document | story-leaning / mixed / doc-leaning | Where on the axis, and is that appropriate? |
| House-style sameness | ★/5 | Five distinguishable voices? Or one author in five costumes? |
| Lore integration | ★/5 | World facts as lived experience, not exposition |
| Commit / momentum | ★/5 | Do scenes resolve? Does each turn advance, or do turns hold and orbit? |
| Specificity | ★/5 | Concrete nouns, named objects, real distances — vs. fog |
| Naming | ★/5 | Distinct culture-grounded names — vs. generic-fantasy reach |

Star scale:

- ★★★★★ Exceptional, reference-quality
- ★★★★☆ Strong, minor issues
- ★★★☆☆ Solid, notable gaps
- ★★☆☆☆ Weak, significant problems
- ★☆☆☆☆ Failed

## Review workflow

1. **Read a sample cold** without rubric in hand. Note gut reaction to voice, momentum, and whether you want to keep reading.
2. **Run the lexical scan** (grep the flag-word table). Should be near-zero in a healthy run.
3. **Count refusal-to-name density** with the four sub-flavor patterns. Calibration: test-7 hit ~1 instance per 40 lines — that is the *bad* baseline. A clean run should be one order of magnitude lower.
4. **Pick three random turn pairs** from different agents and test the house-style diagnostic.
5. **Score the rubric** with one-line evidence per dimension.
6. **Identify the single biggest pattern** worth attacking before the next run. One problem at a time.

## Recording reviews

Reviews live in `docs/reviews/<campaign-id>.md` with the scoring table
and a short prose report. Cross-reference the transcript line numbers
that informed each score. Don't copy long excerpts — line refs travel
better and stay correct as the corpus evolves.
