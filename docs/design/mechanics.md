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

The actor making the roll picks risk based on scene state. For player-initiated
rolls, the player picks. For NPC, hazard, opposition, or DM-side PC checks, the
DM picks. Hidden state can make the DM's interpretation authoritative after the
fact, but the system should not bounce turns just to negotiate dice.

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

## Pressure

Action scenes use one generic pressure model for roll-mediated reduction of a
numeric value. Combat is HP pressure. The same command can reduce the duke's
resistance, the distance to a chase target, enemy morale, structural integrity,
alert, or any other scene-local value.

A pressure attempt has:

- **Numeric value** — a scene tracker, usually public, such as `8/8 HP` or
  `6/6 duke resistance`.
- **Hit check** — arbitrary skill + attribute, with the target's known
  `resistance` applied to the threshold.
- **Impact roll** — `d6`, `d8`, or `d10`, chosen honestly from the fiction.

Impact maps to reduction:

| Impact roll | Reduction |
|-------------|-----------|
| `1-3` | 1 |
| `4-6` | 2 |
| `7-10` | 3 |

The v1 CLI applies impact on `breakthrough` and `advance`; `stall` is glancing
pressure for 1 reduction before impact resistance; `regress` and `collapse`
apply no numeric reduction. Nonnumeric effects remain prose.

## Scene Trackers

Action scenes need a clearly defined endpoint, often numeric and player-visible.
The DM should use scene-local trackers for any progress math that could drift
between agents:

```bash
glass scene tracker set enemy-rout --label "Enemy rout" --max 6
glass scene tracker tick enemy-rout 2
glass scene tracker list
```

Trackers are generic on purpose. A tracker can be HP, morale, suspicion,
distance, leverage, hazard pressure, survival rounds, or anything else that
fits the scene. A pressure target can also carry `resistance` and
`impact_resistance`:

```bash
glass scene tracker set patrol-leader-hp --label "Patrol leader HP" \
  --value 8 --max 8 --resistance 1

glass scene pressure patrol-leader-hp swordsman finesse \
  --risk risky --character tev-pc-1 --impact d8 \
  --bonus 1 --because "dueling saber in close quarters"
```

At least one tracker in an action scene should usually be public so players
know what they are trying to accomplish and when the scene is over. Hidden
trackers are valid for danger clocks or secret opposition.

## Durable Clocks

Scene trackers are short-term. Use them for the current fight, chase, hazard,
or social-pressure exchange.

Durable clocks are cross-scene pressure: a faction crackdown, an antagonist's
plan, an arc danger clock, the party organization's standing, a thread that is
advancing off-screen. These live in Postgres through `glass clock`; public
clocks are projected to markdown so players can reference them without asking
the DM.

```bash
glass clock set accord-crackdown --scope arc --anchor first-arc \
  --label "Accord crackdown" --max 6 --public
glass clock tick accord-crackdown 1 --note "The warrant was issued."
glass clock list
```

Keep the same principle: codify only the number and visibility. What the clock
means, why it ticked, and what happens when it resolves are DM-authored prose.

## HP

HP is staying power in dangerous scenes, not a death simulator. It covers
injury, exhaustion, shock, structural strain on gear, and the loss of ability
to keep acting at full pace.

Default PC baseline remains `hp.current: 8-10`, with the exact max set during
character creation. HP is canonical hard state in Postgres and changes through
`glass character set-hp`.

For v1:

- **0 HP means out of the action**, captured, unconscious, pinned, routed, or
  otherwise unable to keep acting normally. It does not automatically mean dead.
- **Death saves / death policy stay deferred** until a real campaign creates
  the need. See [`../backlog.md`](../backlog.md).
- **Damage is pressure.** Most HP damage comes from `glass scene pressure`:
  impact reduction is usually 1-3 HP. Bigger consequences are DM-authored
  scene events, not a separate damage engine.
- **Healing is also coarse.** In-scene first aid can stabilize or remove an
  effect; larger HP recovery usually waits for scene end, rest, treatment, or a
  DM-authored beat.

## Consequences

A consequence is lasting fictional state that should not drift: cracked ribs,
captured by the patrol, separated from the party, disgraced in court, gear
strained, oath-bound, or any other effect that matters beyond one narration
beat.

Consequences are deliberately not a condition engine. The fields are small:
label, description, severity (`minor`, `serious`, `critical`), scope (`scene`,
`arc`, `campaign`), visibility, status, and resolution note.

```bash
glass character consequence-add tev-pc-1 "Cracked ribs" \
  --severity serious --scope arc \
  --description "Hard breathing and heavy lifting should matter until treated."
glass character consequence-list tev-pc-1
glass character consequence-resolve tev-pc-1 <consequence-id> \
  --note "Treated during downtime."
```

0 HP usually creates a consequence or removes the character from the action:
unconscious, captured, pinned, routed, isolated, or otherwise unable to act at
full pace. It still does not automatically mean dead. Death policy remains a
campaign-tone decision, not a default subsystem.

NPCs and hazards do not need full character rows until they drift. For early
sessions, the DM may track enemy HP in scene prep or public trackers and only
codify what must survive across turns.

## Effects

An effect is a named condition that changes what future actions can reasonably
do. Effects are deliberately lighter than a status-condition subsystem.

Examples:

- Physical: `pinned`, `bleeding`, `winded`, `off-balance`, `separated`
- Tactical: `in-cover`, `flanked`, `route-open`, `line-of-sight-blocked`
- Social: `exposed`, `cornered`, `has-the-room`, `promise-on-record`
- Resonance: `signal-jammed`, `kinetic-overload`, `attunement-noise`

Effects have three fields when the DM needs precision:

```yaml
effect: exposed
target: patrol-leader
duration: until addressed / end of scene / 1 round
```

For now, scene effects are tracked in prose, scene framing, and DM notes.
Codify only what drifts. If the effect is lasting PC fallout, use a character
consequence. If sessions show repeated scene-scoped drift around stacking or
duration, add a small scene-scoped condition surface then, not a large rules
engine.

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

When a check is made, the rolling actor names a skill and an attribute. Players
choose those for player-initiated rolls. The DM chooses them for NPCs, hazards,
opposition, and DM-side PC checks. If the character has the skill, the matching
tier modifier is used; otherwise it defaults to `fool` (-2) — the character is
unskilled and the check is harder. This makes skill choice meaningful without
requiring a fixed taxonomy.

Starting PCs have exactly three trained skills: one `artisan` and two
`apprentice`. Higher tiers are earned through play, not assigned at creation.

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
organization_role: "outside specialist on retainer"
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
  resonance-tuning: artisan
  climbing: apprentice
  diplomacy: apprentice
momentum:
  current: 0
  floor: -2
  ceiling: 3
hp:
  current: 8
  max: 10
inventory:
  - id: ringglass-baton
    qty: 1
    effect_tags:
      - "Favored weapon; may justify pressure against close threats."
  - id: tuning-fork-resonator
    qty: 1
    effect_tags:
      - "May justify pressure against exposed resonance devices."
tags: [tuner, ringside-born]
```

Schema isn't final. Will iterate after the first session.

## The Dice CLI

`glass roll` is the base path for standalone checks. `glass scene pressure`
uses the same check math when a roll is also reducing a scene target. Both the
DM and player agents call these commands. Players call them for their own
chosen rolls. The DM calls them for NPCs, hazards, opposition, and DM-side PC
checks when resolving the check inside the DM turn avoids an unnecessary actor
transition.

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

- **Fixed class lists / class packages** — characters do have a class-like archetype string, but there is no closed list of classes and no package of class mechanics.
- **Fixed spell lists** — spell-like resonance techniques belong in signature
  moves, not a closed spell catalog. They still resolve through fiction, rolls,
  pressure, and table judgment.
- **Damage types / armor** — HP is a number; damage is coarse pressure impact plus narration.
- **XP / leveling** — irrelevant for one-session experiments. Revisit if multi-session arcs become a real thing.
- **Currency** — narrate around it. If money matters, the DM tracks it as a tag on the character or a note on the locale.

When in doubt, narrate it instead of mechanizing it. The system exists to *introduce uncertainty*, not to *track everything*.
