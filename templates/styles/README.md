---
title: Narrative Response Style Library
target: operator
authority: reference
status: authored
---

# Narrative Response Style Library

This directory is the static, durable craft-and-voice layer that
accompanies agent personas. Each agent (1 DM + 4 players) is assigned
exactly one **narrative response style**. The style governs *how the
agent's turn-prose moves on the page* — independent of what PC that
agent happens to be playing this campaign. Persona is who the agent
is at the table; style is the prose register they write in,
character-agnostic.

Design draws on canonry's `packages/world-schema/src/narrativeStyles.ts`
shape (prose instructions, craft posture, lexical signature) and on a
research pass over actual-play criticism, play-by-post writing guides,
Forge/Big Model stance theory, OSR vs PbtA design, and improv import.

Rationale and acceptance criteria live at
[`/narration-voice-library-proposal.md`](../../narration-voice-library-proposal.md).

## What this layer is for

Test-7 demonstrated that persona-level differentiation does not survive
the LLM's house-style attractor. Five distinct personas converged on a
single voice (Drova's forensic register, "three breaths" cadence,
refusal-to-name as default move, universal "X is the X" tautology,
anaphoric negation as scene-painting default).

The persona file describes who the agent *is at the table*. The style
file constrains **how their prose moves on the page** along axes that
vary between real players — and assigns each voice explicit
responsibility for refusing a subset of the corpus-level slop
attractors.

See [`docs/reviews/guidance.md`](../../docs/reviews/guidance.md) for
the full slop attractor inventory and the test-7 review evidence.

## Library contents

The library is a set of reusable archetypes. Each agent's persona
points at one via the `narrative_style:` frontmatter field; the
archetype itself describes a *type of player*, not the specific person
currently assigned to it.

| Style ID | Name | "Plays the…" | Current assignee |
|---|---|---|---|
| `restrained-director` | Restrained Director | plays the room, not the people | Mara (DM) |
| `rules-first-actor` | Rules-First Actor | plays the profession, not the class | Tev |
| `method-author` | Method Author | plays the character, slowly | Sumi |
| `interrogative-scout` | Interrogative Scout | plays the questions | Renno |
| `voiced-improv-lead` | Voiced Improv Lead | plays the bit, voices the NPCs | Kit |

Style files do not record their current assignee in their own frontmatter
— the assignment lives in the persona's `narrative_style:` field, which
is the single source of truth. This keeps archetypes reusable: a player
who changes seats or a new agent joining the table picks whichever
archetype fits, and the style file does not have to be edited.

## The eight prose axes

Styles are specified on eight axes that have empirical variation across
real players. Each style file places its assigned agent at a named
position on each axis. The axes are designed to be roughly orthogonal
and to surface differentiation that survives the LLM's house-style
attractor.

1. **Person/Tense** — `first-immediate` / `third-named-past` / `third-pronoun-present` / `mixed-with-quoted-IC`. The strongest house-style attractor; convergence here collapses all voices into one narrator.
2. **Stance** (Edwards/Forge) — `actor` (only what the PC senses) / `author` (move chosen, motive shown) / `director` (declares world facts) / `pawn` (mechanics only). Most consequential axis for the kind of fiction produced. If everyone defaults to actor, the world goes inert; if everyone is director, DM authority dissolves.
3. **Density** — `terse-imperative` / `medium-novelistic` / `lush-purple`. Information budget per beat.
4. **Subject focus** — `action-mechanical` / `interior` / `environment-pickup` / `other-character-reactive`. Where the camera points.
5. **Rule-fiction interface** — `fiction-only` / `fiction-then-mechanics` / `interleaved` / `mechanics-only`. How rules surface in prose.
6. **Commitment latency** — `decisive` / `interrogative-hedged` / `late-but-firm` / `retractable`. When the player lands.
7. **Authorship invitation** — `declarative-closed` / `declarative-open` / `invitational-question`. What the turn's close hands to the next actor.
8. **Humor mode** — `dramatic-straight` / `wry-dry` / `loud-bit` / `character-deprecating` / `dice-deprecating`.

### House-style sameness risks (ranked)

1. **Person/Tense convergence** — every player ends up writing in one register; the table reads as one narrator.
2. **Stance convergence** — fiction loses friction (everyone actor) or DM authority dissolves (everyone director).
3. **Humor convergence** — uniform wry-dry produces detachment; uniform loud-bit exhausts.
4. **Authorship invitation convergence on declarative-closed** — no hooks for other players to grab; prose stops feeding itself.

### Sources informing the axis taxonomy

- Wikipedia: Play-by-post role-playing game
- Forum Roleplay & Doomed Hero's Paizo PBP guide (third-person past as PBP default; bold-for-dialogue conventions)
- The Angry GM, *Declare-Determine-Describe* (commitment language)
- bankuei, *Stances 101* (actor/author/director examples)
- darkshire RPG Theory Glossary (pawn stance)
- Discover Pods on *Friends At The Table* ("draw maps, leave blanks")
- OSR vs PbtA design literature (distributed vs centralized narrative authority)
- Buried Without Ceremony, *Belonging Outside Belonging / Wanderhome* (invitational play)
- Springhole, *Tips for Better Roleplay Posts* (show-don't-tell via body language)
- ZedneWeb on Griffin McElroy's "we see / the camera pans" cinematic register
- Cambridge, *Critical Role on voice quality in D&D* (phonatory variation)
- By Arcadia, *Second-Person Narration in Streamed RPGs*

## How styles reach the agent

The persona frontmatter declares the style assignment:

```yaml
---
name: Sumi
role: player
narrative_style: sumi-calibrated-witness
---
```

The orchestrator's `projection.assigned_style_id()` reads this at
projection time. Each agent's per-turn projection contains exactly one
style file: their own. Cross-contamination of style files is exactly
what produced the test-7 house-style problem; the projection layer
enforces strict per-owner visibility.

TURN_START carries a one-sentence pointer to the assigned style file.
The agent reads the style file from their workspace once, like any
other persona-shape doc; TURN_START stays a thin shell.

## File shape (five sections)

Each style file is short — target 60-80 lines — and contains exactly
these sections:

1. **One-sentence identity** — what register, what posture.
2. **Prose axes** — the player's position on each of the eight axes, with a one-line concretion per position. This is the binding spec.
3. **Prose instructions** — Tone / Density / Subject focus / Authorship / **Avoid**. The Avoid block carries this voice's assigned anti-slop reflexes.
4. **Craft posture** — three or four bullets on density, restraint, and withholding mode.
5. **Lexical signature** — register-class reaches/refuses. *Reaches for* names a class of vocabulary (e.g., "interrogative openings," "domain vocabulary specific to whatever the PC's craft provides") rather than specific words. *Refuses* names the anti-patterns this voice owns.

We removed two earlier sections:

- *Designed against* — operator meta-commentary that leaked the names of other styles into private projections and bloated the file.
- *Benchmark sample* — quoted sample sentences bias the agent toward exact reproduction when framed as instructions. The axis positions and the lexical signature carry the spec without the bias.

## Anti-slop reflex coverage

Each style takes responsibility for refusing a specific subset of slop
attractors, written into its **Avoid** block. Collectively the five
styles cover the corpus-level inventory. This is a *design property* —
when revising or adding styles, verify the coverage table still holds.

| Slop attractor | Refused by |
|---|---|
| Refusal-to-name (direct, "doesn't need to") | `method-author` |
| "X is the X" tautology | `rules-first-actor` |
| "X is the sentence" gesture | `restrained-director`, `method-author` |
| Animate-object omniscience | `restrained-director` |
| Anaphoric negation cascade | `interrogative-scout` |
| Rhythmic count tic ("three breaths" etc.) | `interrogative-scout` |
| Procedural-metalanguage bleed between PCs / from PC to narrator | `method-author` |
| Conditional-cascade closing | `interrogative-scout` |
| OOC procedural opener block | `voiced-improv-lead` |
| Closing-beat formulaicism | `restrained-director` |
| Authorial commentary on scene meaning | `restrained-director` |
| Hyper-procedural micro-gesture description | `voiced-improv-lead` |
| Held moments without resolution | `voiced-improv-lead`, `rules-first-actor` |
| Metaphor-reach where literal description would serve | `rules-first-actor` |

## Derivation note

The five styles are **archetypes of player prose**, not portraits of
specific players. Earlier drafts keyed styles to current PCs
(forensic-clerk vocabulary, kite-craft vocabulary, listener-cuff
vocabulary) which would have locked each player into one type of
character forever. A second pass key them to the existing personas by
name ("Witness-Lit Narration" for Mara, "Calibrated Witness" for Sumi)
which had the same problem at the player level — the names locked
each player into one archetype forever.

The current draft names archetypes by *type* — "Restrained Director,"
"Rules-First Actor," "Method Author," "Interrogative Scout," "Voiced
Improv Lead" — with axis positions that travel. The current assignment
of each archetype to a specific agent lives in the persona's
`narrative_style:` field, not in the style file. A player who changes
preferred mode, or a new agent joining the table, can be reassigned
to whichever archetype fits without editing the style library.

The initial archetypes were chosen to match the existing personas
(Tev's "okay so" and rule-first habit; Sumi's "refers to PC by name,
almost never says I"; Renno's PbtA-style "what do I notice?"; Kit's
loud-fast voiced-NPC delivery; Mara's sparse one-image-per-beat, no
NPC voices) and cross-checked for spread across all eight axes.

For a future library expansion, new archetypes should be added with
explicit attention to which axis combinations are not yet represented
— the goal is coverage of the axis space, not duplication of existing
voices.

## Distinctness constraints

When authoring or revising styles:

- **Lexical signatures must not collide** at the class level. Two
  styles "reaching for" the same vocabulary class is a bug.
- **Axis positions should produce visible spread** across all eight
  axes. If three styles land at the same position on any single axis,
  consider whether that axis is doing work for the library.
- **Anti-slop reflex assignments should be near-orthogonal.** If two
  styles both refuse the same attractor as primary, one of them should
  pick a different primary.
- **No style should reference another style by name** or describe
  another agent's voice. The projection layer enforces per-owner
  privacy; the file content should not leak around it.

## Maintenance

Style files are intended to be durable — closer to the persona than to
the campaign. Edit them when:

- A review identifies a new slop attractor not in the coverage table.
- An axis position proves under-constrained in practice and needs a
  tighter reflex.
- The agent's persona evolves significantly.

Do *not* edit them per-campaign. Per-campaign craft notes live in
`campaigns/<id>/how-to/` and the campaign-specific surfaces.

## See also

- [`docs/reviews/guidance.md`](../../docs/reviews/guidance.md) — review framework and slop attractor inventory
- [`templates/how-to/narration-craft-dm.md`](../how-to/narration-craft-dm.md) — DM craft guide (shared anti-slop, all roles)
- [`templates/how-to/narration-craft-player.md`](../how-to/narration-craft-player.md) — player craft guide
- [`/narration-voice-library-proposal.md`](../../narration-voice-library-proposal.md) — original design rationale and acceptance criteria
