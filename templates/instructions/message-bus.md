---
title: Message Bus Instructions
target: executing-agent
authority: binding
---

# Message Bus

Messages are typed durable dialogue and coordination outside public turn prose.
Use them during normal scene play and action play for offers, warnings,
questions, clarifications, handoffs, clue flags, and DM-readable private
material. Do not reserve the bus only for hidden-info blockers.

## Start-of-Turn Sequence

1. Full turns: run `glass check`.
2. Rapid-response turns: read messages only when the prompt depends on them.
3. Respond during the same turn when a message blocks your action.
4. If another actor needs a durable line from you before your prose lands, send
   it during this turn.

## Sending Sequence

1. Choose the narrowest recipient from the TURN_START roster: a player id,
   `dm`, or `party`.
2. Choose the type that matches the job.
3. Send one concrete message that changes what the recipient now knows,
   expects, or can do.

```bash
glass msg <type> <recipient> "<body>"
```

## Types

- `table-talk`: party-visible coordination, clarification, or durable table
  answer.
- `banter`: player-to-player offer, warning, reassurance, tension, consent, or
  relationship pressure.
- `instruction`: explicit ask, handoff, or tactical direction.
- `plot-hint`: clue, suspicion, lead, or hook you want the table or DM to keep.
- `secret`: DM-only private material, concealed intent, or off-screen action.

## Boundary

Do not use messages as the durable home for facts that belong in character
state, table state, lore, summaries, clocks, or notes. Promote durable material
with the appropriate `glass` command or `glass sync apply`.
