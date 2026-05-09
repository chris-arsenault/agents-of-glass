---
title: Mechanical Terms
---

# Mechanical Terms

Glossary of terms the dice + character system uses. **Reference.** Full definitions and the math live in [`/docs/design/mechanics.md`](../../../docs/design/mechanics.md); this file is just enough to point at the right concept by the right name.

## Dice and checks

- **check** — a 2d6 roll plus modifiers, against a risk threshold. The unit of mechanical resolution.
- **risk level** — the difficulty band the DM picks for a check. One of `controlled` (target 7), `standard` (8), `risky` (9), `desperate` (10).
- **margin** — total minus target. Drives the tier.
- **outcome tier** — the result of a check. One of `breakthrough`, `advance`, `stall`, `regress`, `collapse`. Determines narration and momentum delta.

## Character

- **attribute** — one of seven base stats: `vitality`, `finesse`, `focus`, `resolve`, `attunement`, `ingenuity`, `presence`. Each held at a tier.
- **skill** — a free-form named specialty (no fixed list). Each held at a tier. If a check names a skill the character doesn't have, the modifier defaults to `fool` (-2).
- **tier** — the level ladder. Attributes: `rudimentary`, `standard`, `advanced`, `superior`, `transcendent`. Skills: `fool`, `apprentice`, `artisan`, `virtuoso`, `legend`. Each tier is a fixed numerical modifier.
- **momentum** — per-character integer in `[-2, +3]`. Accumulates from check outcomes; feeds into future check totals. Narrative-energy state.

## World-mechanical (Glass Frontier)

- **resonance** — the ambient energy in the Kaleidos system. The substrate that ringglass shapes.
- **ringglass** — the crystalline material the rings were built from. Now scattered everywhere. Concentrates and channels resonance.
- **band** — what kind of effect a piece of ringglass is tuned for: `structural`, `kinetic`, or `signal`.
- **bandwidth** — how focused the application is: `broad`, `mid`, `narrow`, or theoretical `single-wavelength`. Broader is easier; narrower is more powerful and more dangerous.
- **attunement** — both an *attribute* (sensitivity to resonance) and an *action* (the act of tuning a piece of ringglass). The verb shows up in [combat-moves.md](combat-moves.md).
- **Tuner** — a practitioner who works ringglass at mid-bandwidth deliberately. Different schools (Conclave, Synod, folk Tuners) operate differently.

## When in doubt

If a term isn't here, it's probably not codified. The orchestrator and CLI care about: dice rolls (true randomness), character numbers (HP, momentum, attribute/skill tiers), inventory, names of canonical entities, mode/scene/session/turn labels. Everything else is prose. See [`/docs/principles/codify-only-what-drifts.md`](../../../docs/principles/codify-only-what-drifts.md).
