---
title: Character-Branch Message Bus Instructions
target: executing-agent
authority: binding
---

# Message Bus

Messages in this branch are durable in-character dialogue and coordination
outside public turn prose. Address other characters, the whole party, or the
DM during normal scene play and action play. Do not reserve the bus only for
hidden-info blockers.

## Start-of-Turn Sequence

1. Full turns: run `glass msg read --since-checkpoint`.
2. Rapid-response turns: read messages only when the prompt depends on them.
3. Respond during the same turn when a message blocks your action.
4. If another actor needs a durable line from your character before your prose
   lands, send it during this turn.

## Sending Sequence

1. Choose the narrowest recipient from the TURN_START roster: a character id,
   `dm`, or `party`.
2. Choose the type that matches the job.
3. Send one concrete message that changes what the recipient now knows,
   expects, or can do.

```bash
glass msg <type> <recipient> "<body>"
```

## Types

### `table-talk`

Party-visible coordination, clarification, or durable table answer.

### `banter`

Character-to-character offer, warning, reassurance, tension, or social contact.

### `instruction`

Explicit ask, handoff, or tactical direction between characters or from the DM.

### `plot-hint`

Clue, suspicion, lead, or hook you want the party or DM to keep in play.

### `secret`

DM-only private character material, concealed intent, or off-screen action.

## DM Recipient

`dm` remains valid in this branch. Use it for off-screen rulings, hidden facts,
private clarification, concealed intent, or DM-only close/advance signals.

## Boundary

Do not use messages as the durable home for facts that belong in character
state, table state, lore, summaries, clocks, or notes. Promote durable material
with the appropriate `glass` command or `glass sync apply`.
