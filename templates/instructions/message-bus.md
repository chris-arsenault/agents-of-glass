---
title: Message Bus Instructions
target: executing-agent
authority: binding
---

# Message Bus

Messages are typed coordination outside public turn prose. Use them for private
clarification, proposals, directed table coordination, and DM-readable private
material.

## Start-of-Turn Sequence

1. Full turns: run `glass msg read --since-checkpoint`.
2. Rapid-response turns: read messages only when the prompt depends on them.
3. Respond during the same turn when a message blocks your action.

## Sending Sequence

1. Choose the narrowest recipient: an agent id, `dm`, or `party`.
2. Choose the type.
3. Send one concrete message.

```bash
glass msg <type> <recipient> "<body>"
```

## Types

- `table-talk`: public table coordination or clarification.
- `banter`: player-to-player color, consent, or relationship offers.
- `instruction`: direct coordination, usually from DM to party or a specific PC.
- `plot-hint`: DM-visible or player-visible clue/hook flag.
- `secret`: DM-readable private player material.

## Boundary

Do not use messages as the durable home for facts that belong in character
state, table state, lore, summaries, clocks, or notes. Promote durable material
with the appropriate `glass` command or `glass sync apply`.
