---
title: Mechanical Terms
---

# Mechanical Terms

Glossary of terms the dice + character system uses. **Reference.** This file is
the in-campaign reference for the terms agents need during play.

## Dice and checks

- **check** — a 2d6 roll plus modifiers, against a risk threshold. The unit of mechanical resolution.
- **risk level** — the difficulty band chosen by the actor making the check. One of `controlled` (target 7), `standard` (8), `risky` (9), `desperate` (10).
- **margin** — total minus target. Drives the tier.
- **outcome tier** — the result of a check. One of `breakthrough`, `advance`, `stall`, `regress`, `collapse`. Determines narration and momentum delta.
- **pressure target** — a scene tracker whose numeric value is being reduced:
  HP, resistance, distance, morale, structural integrity, suspicion, or anything
  else the scene treats as a concrete obstacle.
- **durable clock** — a cross-scene clock tracked with `glass clock`: faction
  pressure, arc danger, antagonist plans, organization standing, or any other
  long-running numeric pressure. Postgres is canonical; public clocks project
  to `shared/clocks.md`.
- **resistance** — a known, mostly static modifier that makes a pressure target
  harder to affect. Usually applies to the hit check. Rarely, `impact
  resistance` reduces the final numeric impact.
- **impact die** — `d6`, `d8`, or `d10`, chosen honestly from the fiction when
  a pressure attempt lands. Impact rolls of `1-3` reduce by 1, `4-6` reduce by
  2, and `7-10` reduce by 3. `Stall` pressure is glancing 1 reduction before
  impact resistance, with no impact die.

## Character

- **attribute** — one of seven base stats: `vitality`, `finesse`, `focus`, `resolve`, `attunement`, `ingenuity`, `presence`. Each held at a tier.
- **skill** — a free-form named specialty (no fixed list). Each held at a tier. If a check names a skill the character doesn't have, the modifier defaults to `fool` (-2).
- **tier** — the level ladder. Attributes: `rudimentary`, `standard`, `advanced`, `superior`, `transcendent`. Skills: `fool`, `apprentice`, `artisan`, `virtuoso`, `legend`. Each tier is a fixed numerical modifier.
- **momentum** — per-character integer in `[-2, +3]`. Accumulates from check outcomes; feeds into future check totals. Narrative-energy state.
- **signature move** — a recurring move, spell, maneuver, search style, social
  tactic, or habit a player maintains in `players/<id>/signature-moves.md`.
  Signature moves create narrative consistency; they do not guarantee a
  modifier or outcome.
- **effect tag** — free text on an item or note saying how it can matter in
  play. `glass character inventory-add --effect-tag` can store item tags, but
  the CLI does not interpret them; players and the DM cite them when they make
  fictional sense.
- **consequence** — lasting fictional state on a character, tracked with
  `glass character consequence-*` when it should persist: injury, capture,
  disgrace, obligations, gear strain, separation. Not a condition engine.

## World-mechanical (Glass Frontier)

- **resonance** — the ambient energy in the Kaleidos system. The substrate that ringglass shapes.
- **ringglass** — the crystalline material the rings were built from. Now scattered everywhere. Concentrates and channels resonance.
- **band** — what kind of effect a piece of ringglass is tuned for: `structural`, `kinetic`, or `signal`.
- **bandwidth** — how focused the application is: `broad`, `mid`, `narrow`, or theoretical `single-wavelength`. Broader is easier; narrower is more powerful and more dangerous.
- **attunement** — both an *attribute* (sensitivity to resonance) and a prose action (the act of tuning a piece of ringglass).
- **Tuner** — a practitioner who works ringglass at mid-bandwidth deliberately. Different schools (Conclave, Synod, folk Tuners) operate differently.

## When in doubt

If a term isn't here, it's probably not codified. The orchestrator and CLI care
about: dice rolls (true randomness), character numbers (HP, momentum,
attribute/skill tiers), inventory, names of canonical entities, and
mode/scene/session/turn labels. Everything else is prose.
