---
title: Proposal — Narration Voice Library
status: implemented
audience: operator
implementation: templates/styles/
related:
  - docs/reviews/guidance.md
  - templates/styles/README.md
  - templates/players/*/persona.md
  - templates/dm/persona.md
---

# Proposal: Narration Voice Library

> **Status: implemented as `templates/styles/`** (renamed *narrative
> response style library* to track canonry terminology and to
> distinguish it from "voice" as a thing the persona already carries).
> The five inaugural styles are authored. Persona frontmatter carries
> the `narrative_style:` assignment. Phase 1 of the implementation plan
> below is done. Phase 2 (a fresh test campaign run + house-style
> diagnostic against the acceptance criteria) is the next step.
>
> This document remains as the design rationale and acceptance-criteria
> reference; the library README at
> [`templates/styles/README.md`](templates/styles/README.md) is the
> live spec.

## The problem

Test-7 shipped distinct, well-authored personas for Mara (DM) and four
players (Tev, Sumi, Renno, Kit). They have different jobs, different
tics, different sample lines, different things that get under their
skin. On paper the voices are distinct.

In the transcript, they aren't. The
[review](docs/reviews/guidance.md#house-style-sameness-diagnostic)
flagged this: every player narrates their turn-calculus the same way,
every character pauses for "three breaths," every scene closes on a
held moment, the procedural-metalanguage of one PC (Drova's "graduated
certainty") migrated wholesale into the DM narrator and other PCs'
voices. The personas describe *who the player is*. They do not
sufficiently constrain *how that player's narration reads on the page.*

The persona layer carries identity, taste, and table behavior. It does
not carry **prose-level register, sentence rhythm, image discipline,
or narrative reflex**. Those are what produce voice on the page, and
they are exactly what an LLM defaults to a single house-style for unless
explicitly varied.

## The canonry precedent

Canonry hit the same problem at the chronicle level: stories with
different narrative styles still read like one author. The fix that
worked was a *separable* layer on top of persona/perspective:

- **`narrativeStyles.ts`** — per-style prose instructions, craft posture,
  density and restraint constraints, beat-sheet expectations.
- **Suggested motifs** — short echo phrases the style commits to repeating.
- **Narrative voice dimensions** — sentence-level guidance ("sentences
  that compress under weight"), not thematic ("this is a story about
  loss").
- **Entity directives** — per-character writing instructions distinct
  enough from each other that swapping two would visibly change the prose.

The principle was: *narrative voice is operationalized at the
sentence-craft layer, not the character-bio layer.* The bio answers
"who is this?" The voice layer answers "how does this character's
prose move?"

See `the-canonry/docs/chronicle-review-guide.md` § "Cultural Identity
Integration" and § "Perspective Synthesis" for the working pattern.

## Proposed shape — narration voice files

Add a sibling file to each persona that carries the
sentence-craft-layer data. Suggested location:

```
templates/players/<name>/
  persona.md              # who they are at the table (existing)
  narration-voice.md      # how their prose moves (new)
  signature-moves.md      # existing
  scratchpad.md           # existing
```

The DM gets `templates/dm/narration-voice.md` on the same shape.

### What goes in narration-voice.md

A small, *operationalized* spec — not a craft essay. Each field should
be enforceable by a reader scanning prose.

```yaml
---
name: Sumi
role: player
voice: narration-voice
---
```

**Sentence-rhythm posture.** One or two sentences. Not vibe — actual
shape. Example for Sumi:
> *Long observation-sentences with embedded subclauses; periodic ellipsis at thinking-points; refuses to summarize her own actions.*

**Image discipline.** What the character's narration commits to.
Example for Sumi:
> *Always one physical object foregrounded — the loupe, the pen, the
> page-rim. Never abstracts the object into metaphor.*

**Lexical signature** — 3-5 words/phrases this voice reaches for, and
3-5 it refuses. Example for Tev:
> *Reaches for: "okay so", "back-feed", numeric counts, equipment
> brand-shape names. Refuses: "in graduated certainty," "three
> breaths," "the X is the X" tautologies, anything ending in -ness.*

**Narrative reflexes** — what this voice does *instead* of the corpus's
slop attractors. Example for Renno:
> *When a beat would refuse-to-name, names it instead. When a beat
> would tautologize, picks a verb. When a beat would hold for three
> breaths, breaks the rhythm with an OOC interjection.*

**Anti-reflexes** — what the voice will not do even if the rest of the
table is doing it.

**Two-line sample**, written in the voice, used as a benchmark for
self-check at turn-write time.

### Total length

Each file should fit on a screen. ~40-80 lines max. The point is to
give the agent something it can hold in one read and recognize itself
diverging from.

## Distinctness constraint

Voices should be designed *against each other*, not in isolation. A
useful test for the operator authoring the library:

- Take the lexical signatures across all five voices. Are there
  collisions? (Two characters both "reach for graduated certainty" is a
  bug.)
- Take the sentence-rhythm postures. Are they five different shapes?
- Take the anti-reflexes. Do they cover the corpus-level slop attractors
  collectively? (Refusal-to-name should be an anti-reflex for *at least
  one* voice, preferably more.)

## How it reaches the agent

The voice file is read on every turn, the same way the persona is. It
appears in `TURN_START` for the acting agent (and only the acting
agent — voices stay private to their owner; you don't want
cross-contamination).

The methodology pass (the new `narration-craft-*.md` how-to docs)
references the voice file as the agent's first stop when writing prose:

> Before writing public prose, re-read your narration-voice.md.
> The reflexes there override the corpus drift.

## Implementation plan (phased)

**Phase 1 — design and pilot (operator authoring, ~half day).**
- [ ] Author `templates/dm/narration-voice.md` for Mara.
- [ ] Author `templates/players/sumi/narration-voice.md` (highest-risk
      voice because Drova's register became the corpus default).
- [ ] Sanity-check: each file is enforceable on the page.
- [ ] Update `templates/instructions/index.md` and the persona-loading
      surface in the orchestrator's context-package builder to include
      the voice file when present.

**Phase 2 — fill the library.**
- [ ] Author `templates/players/{tev,renno,kit}/narration-voice.md`.
- [ ] Run a 5-turn dry-run scene and inspect for voice distinctness
      against the design constraints above.
- [ ] Iterate on the files that didn't land.

**Phase 3 — wire to the review loop.**
- [ ] Add the house-style diagnostic from `docs/reviews/guidance.md` to
      the post-run review checklist.
- [ ] When a voice persistently fails to differentiate, the fix is at
      the narration-voice.md layer, not the persona layer.

**Phase 4 (optional, deferred) — promote to a methodology-level concept.**
- [ ] If the pattern works, document it in `docs/design/agents.md` as a
      first-class part of the agent shape (persona + voice + signature
      moves + scratchpad).
- [ ] Add a campaign-bootstrap check that warns if any agent is missing
      a voice file.

## Open questions

1. **Voice authorship.** Same constraint as personas: operator-authored,
   not agent-authored. The whole point is that the agent doesn't get
   to drift its own voice.
2. **Drift over a long campaign.** Should narration-voice.md be append-only
   (the operator notes when a voice broke and how) or stable (the
   character's prose register is a campaign constant)? Default to
   stable; revisit if needed.
3. **PC voice vs player voice.** The narration-voice file describes the
   *player*'s prose register, not the PC's diegetic speech. The PC's
   diegetic speech belongs in character intro/relationships. Keep these
   separate; bleeding is what created the test-7 problem in the first
   place.
4. **Interaction with `creative-influences.md`.** That file already
   carries some prose-direction signal at the campaign level. The
   per-agent voice file is more granular and per-character. They
   compose; voice file takes precedence on conflict.

## Acceptance criteria

The proposal is working if, in the next test campaign:

- The house-style diagnostic from
  `docs/reviews/guidance.md` returns a score of ★★★★☆ or better.
- A reviewer can identify which agent wrote a turn from the prose alone,
  in 4/5 attempts, across at least three turn samples.
- Cross-character lexical bleed (Drova's "graduated certainty"
  appearing in Mara's narration) is absent.
- Refusal-to-name density drops by an order of magnitude — and the drop
  is attributable to specific voice files calling it out as an
  anti-reflex, not to luck.

## Non-goals

- Not a craft essay layer. The how-to docs already exist for that.
- Not a constraint that produces stilted prose. Voice files should
  feel like rules the character would write for themselves, not
  external corrections.
- Not infinite. Five voices is enough to test the idea. Don't scale
  to a library of styles before knowing if the core pattern works.
