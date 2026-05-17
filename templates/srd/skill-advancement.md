---
title: Skill Advancement
target: player-dm
authority: rules
---

# Skill Advancement

Skills grow by use. Characters can also pick up new skills as they play, up to
a per-character cap.

## Skill Slots

A character's **declared skills** are the named skills on their sheet at any
tier from `fool` upward. The slot cap is:

```text
slots = 3 + character_level
```

| Level | Slots |
|-------|-------|
| 1 | 4 |
| 2 | 5 |
| 3 | 6 |
| 4 | 7 |
| ...   | ...   |

Three slots are filled at character creation (two `apprentice`, one `artisan`).
That leaves one free slot at level 1. Each level adds one more.

## Declaring a New Skill

When a player tries something not covered by an existing skill, they may roll
it as an improvised `fool` skill. Improvised skills do not use a declared skill
slot, do not become durable, and do not gain skill xp.

If the action should become part of the character's durable toolkit, save the
skill while rolling:

```bash
glass roll <new-skill-name> <attribute> --risk <level> --character <id> --save-skill
```

`--save-skill` declares the skill at `fool` before the roll if a slot is
available, then lets that roll earn skill xp normally. If no slot is free, the
command errors; roll without `--save-skill` to keep the check improvised.

Players can also declare without rolling — usually during intermission
training or a quiet between-scene decision — with:

```bash
glass character skill-declare <id> <new-skill-name>
```

Use existing declared skills when they fit. Use improvised rolls for one-off
actions. Use `--save-skill` only when the skill should persist on the sheet.

## Starting Tier

Every newly declared skill starts at `fool` (skill modifier −2). Declared
skills **accumulate skill xp** and rank up over time.

## Per-Skill XP and Auto-Promotion

Successful rolls grant skill xp to the rolled skill:

| Outcome | Skill XP |
|---------|---------:|
| `breakthrough` | +2 |
| `advance` | +1 |
| `stall`, `regress`, `collapse` | 0 |

When a skill's xp crosses a threshold, the skill auto-promotes to the next
tier on the roll itself. No separate command is needed.

| Skill XP | Tier |
|---------:|------|
| 0 | `fool` |
| 5 | `apprentice` |
| 15 | `artisan` |
| 30 | `virtuoso` |

`legend` is not earned through skill-by-use. Treat it as plot-only.

## Naming Skills

Use the guidance in [`how-to/skills-and-signature-moves.md`](../how-to/skills-and-signature-moves.md).
A declared skill name should be specific enough to create choices and broad
enough to come up more than once. Do not declare a skill so narrow it can only
be rolled once.
