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

When a player tries something not covered by an existing skill, they may
declare a new one and roll it on the same turn, as long as they have a free
slot. The simplest path is to just roll it:

```bash
glass roll <new-skill-name> <attribute> --risk <level> --character <id>
```

If `<new-skill-name>` is not already on the sheet and a slot is free, `glass
roll` auto-declares the skill at `fool` and proceeds with the roll. The roll
output reports `skill_auto_declared: true` and the player turn log records the
new slot used.

If no slot is free, the roll errors. The character must wait until the next
level (which adds a slot) before declaring another skill. A player can also
declare without rolling — typically during intermission training — with:

```bash
glass character skill-declare <id> <new-skill-name>
```

## Starting Tier

Every declared skill starts at `fool` (skill modifier −2). This is the same
modifier an undeclared skill would have, so the immediate roll is not
mechanically better than improvising. The reason to declare is that a declared
skill **accumulates skill xp** and ranks up over time.

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
