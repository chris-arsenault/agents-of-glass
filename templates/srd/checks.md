---
title: Checks
target: player-dm
authority: rules
---

# Checks

When an action is uncertain and consequential, make a check:

```text
total = 1d10 + skill modifier + attribute modifier
margin = total - risk threshold
```

## Risk Levels

| Risk | Threshold |
|------|-----------|
| `controlled` | 5 |
| `standard` | 6 |
| `risky` | 7 |
| `desperate` | 8 |

For player-initiated rolls, the player chooses the risk, skill, and attribute
honestly from the fiction. Hidden state can make the DM's interpretation
authoritative after the fact, but the game should not bounce turns just to
negotiate dice.

The DM chooses risk, skill, and attribute for NPCs, hazards, opposition, and
DM-side PC checks.

## Outcomes

| Margin | Tier | Momentum |
|--------|------|----------|
| `+2` or higher | `breakthrough` | +2 |
| `0` to `+1` | `advance` | +1 |
| `-1` | `stall` | 0 |
| `-2` to `-3` | `regress` | -1 |
| `-4` or lower | `collapse` | -2 |

Breakthrough means the action succeeds and something extra goes right. Collapse
means the action fails badly and the situation worsens. The middle tiers are
interpreted by the table through the fiction.

Momentum is narrative state only. It never changes the roll total. After a roll
updates momentum, use the resulting value as a narrative rider:

- `> 2`: add one extra good visible consequence.
- `1` to `2`: no extra momentum rider.
- `<= 0`: add one extra visible complication.

`stall`, `regress`, and `collapse` do not mean "nothing happens." They require
a visible consequence, worse position, narrowed choice, clock/beat movement, or
other concrete change that keeps the scene moving.

`advance` and `breakthrough` also award skill xp to the rolled skill (+1 and
+2 respectively). Skills auto-promote at fixed thresholds — see
[`skill-advancement.md`](skill-advancement.md).

## Player Roll Authority

Players call their own rolls when acting on their own turns. The DM does not
normally tell a player to spend a separate turn rolling.

When the DM needs a PC check during the DM turn, the DM rolls it for the PC and
uses the outcome immediately. This keeps play from ping-ponging just for dice.
