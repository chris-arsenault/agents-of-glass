---
title: Character-Branch Message Bus Instructions
target: executing-agent
authority: binding
---

# Message Bus

Messages in this branch are character-facing coordination outside public turn
prose. Address other characters, the whole party, or the DM.

## Start-of-Turn Sequence

1. Full turns: run `glass msg read --since-checkpoint`.
2. Rapid-response turns: read messages only when the prompt depends on them.
3. Respond during the same turn when a message blocks your action.

## Sending Sequence

1. Choose the narrowest recipient: a character id, `dm`, or `party`.
2. Choose the type.
3. Send one concrete message.

```bash
glass msg <type> <recipient> "<body>"
```

## Types

### `table-talk`

Public table coordination or clarification.

### `banter`

Character-to-character color, offers, or social contact.

### `instruction`

Direct coordination, usually from the DM to the party or from one character to
another around an immediate plan.

### `plot-hint`

DM-visible or party-visible clue or hook flag.

### `secret`

DM-readable private character material.

## DM Recipient

`dm` remains valid in this branch. Use it when an off-screen ruling, hidden
fact, or private clarification is required before your action is valid.

## Boundary

Do not use messages as the durable home for facts that belong in character
state, table state, lore, summaries, clocks, or notes. Promote durable material
with the appropriate `glass` command or `glass sync apply`.
