# Mechanics

The dice + character system. Cribbed from the-glass-frontier (`packages/skill-check-resolver`, `packages/dto/src/mechanics.ts`) and stripped down for an agentic loop with no UI.

This is intentionally lightweight. The system exists to give the DM a structured way to introduce uncertainty into adjudication; it isn't trying to be a complete RPG.

For how mechanics fit into a turn, see [`turn-loop.md`](turn-loop.md). For state-store layout, see [`architecture.md`](architecture.md).

## The Check

Every uncertain action resolves through a single equation:

```
total = 2d6 + skill_modifier + attribute_modifier + current_momentum
margin = total - target_threshold(risk_level)
tier = ladder(margin)
```

A check produces:

- A **total** (sum of dice + modifiers)
- A **margin** (total minus the risk threshold)
- An **outcome tier** (one of five)
- A **momentum delta** (applied to the character's momentum)

## Risk Levels

| Risk | Threshold |
|------|-----------|
| `controlled` | 7 |
| `standard` | 8 |
| `risky` | 9 |
| `desperate` | 10 |

The DM picks risk based on scene state. "Talking down a guard who isn't paying attention" is `controlled`. "Convincing a faction leader mid-shouting-match" is `desperate`.

## Outcome Tiers

By margin:

| Margin | Tier | Momentum Δ |
|--------|------|-----------|
| ≥ +2 | `breakthrough` | +2 |
| 0 to +1 | `advance` | +1 |
| -1 | `stall` | 0 |
| -2 to -3 | `regress` | -1 |
| ≤ -4 | `collapse` | -2 |

The tier determines how the DM narrates the outcome. Breakthrough = "you do the thing and something extra goes right." Collapse = "the thing fails badly and the situation worsens."

Outcome tiers are also a closure signal — see [`scene-ending.md`](scene-ending.md) for the deferred design that uses them as scene pressure.

## Attributes

Seven, named for resonance and the world:

| Attribute | What it covers |
|-----------|----------------|
| `vitality` | Stamina, raw physicality, soaking damage |
| `finesse` | Precision, agility, sleight |
| `focus` | Attention, recall, sustained mental effort |
| `resolve` | Will, composure, resistance |
| `attunement` | Resonance sensitivity, intuitive read of a place or person |
| `ingenuity` | Improvisation, lateral thinking, problem-solving |
| `presence` | Charisma, command, social weight |

Each character has every attribute at a tier:

| Tier | Modifier |
|------|----------|
| `rudimentary` | -2 |
| `standard` | 0 |
| `advanced` | +1 |
| `superior` | +2 |
| `transcendent` | +4 |

Most starting characters are `standard` across most attributes with one or two `advanced` and at most one `superior`. `Transcendent` is plot-only.

## Skills

Skills are arbitrary strings (no fixed list — characters declare what they're good at) but each has a tier:

| Tier | Modifier |
|------|----------|
| `fool` | -2 |
| `apprentice` | 0 |
| `artisan` | +1 |
| `virtuoso` | +2 |
| `legend` | +4 |

When the DM calls a check, they pick a skill and an attribute. If the character has the skill, the matching tier modifier is used; otherwise it defaults to `fool` (-2) — the character is unskilled and the check is harder. This makes skill choice meaningful without requiring a fixed taxonomy.

## Momentum

A per-character integer that's clamped to `[-2, +3]`. It accumulates from check outcomes and feeds back into future check totals.

- `breakthrough` → +2
- `advance` → +1
- `stall` → 0
- `regress` → -1
- `collapse` → -2

Momentum represents narrative flow: a character on a roll genuinely *is* on a roll. A character whose plans keep collapsing struggles harder.

The DM can also adjust momentum out-of-band (`glass character set-momentum`) for narrative reasons — a major story beat resets it, an inspiring NPC speech bumps it.

## Character Schema

Stored in Postgres (with a markdown summary cached for the agent's context). Working hypothesis:

```yaml
character_id: karrith
player_id: tev
name: "Karrith Veyl"
archetype: "Lapsed Tuner"
pronouns: he/him
attributes:
  vitality: standard
  finesse: advanced
  focus: standard
  resolve: standard
  attunement: superior
  ingenuity: advanced
  presence: standard
skills:
  resonance-tuning: virtuoso
  climbing: artisan
  diplomacy: apprentice
  shooting: fool
momentum:
  current: 0
  floor: -2
  ceiling: 3
hp:
  current: 8
  max: 10
inventory:
  - { id: kite-cord, qty: 1 }
  - { id: tuning-fork-resonator, qty: 1 }
tags: [tuner, ringside-born]
```

Schema isn't final. Will iterate after the first session.

## The Dice CLI

`glass roll` is the only path to a check. Both the DM and player agents call it.

```
$ glass roll diplomacy presence --risk controlled --character karrith
```

Output (yaml on stdout, also written to a per-session dice log):

```yaml
roll_id: 8a3...
session_id: 4
character_id: karrith
skill: diplomacy
attribute: presence
risk: controlled
dice: [3, 5]
skill_modifier: 0
attribute_modifier: 0
momentum_in: +1
total: 9
target: 7
margin: +2
outcome: breakthrough
momentum_delta: +2
momentum_out: +3
```

Every roll is logged in Postgres with full context. This is non-negotiable — dice events are corpus data (see [`../principles/transcripts-as-corpus.md`](../principles/transcripts-as-corpus.md)).

## What's Not in the System

Deliberately omitted (would be added only if a real session demands them):

- **Hit dice / class systems** — characters don't have classes, just an archetype string.
- **Spells / abilities as discrete items** — anything special a character does is just a skill check, possibly with the DM's approval to use a particular angle.
- **Damage types / armor** — HP is a number; damage is whatever the DM narrates after a regress/collapse on a combat check.
- **XP / leveling** — irrelevant for one-session experiments. Revisit if multi-session arcs become a real thing.
- **Currency** — narrate around it. If money matters, the DM tracks it as a tag on the character or a note on the locale.

When in doubt, narrate it instead of mechanizing it. The system exists to *introduce uncertainty*, not to *track everything*.
