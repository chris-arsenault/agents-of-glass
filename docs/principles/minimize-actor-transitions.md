# Minimize Actor Transitions

Agent turns are expensive. Each time the orchestrator switches actors, the new
agent rereads `TURN_START.md`, refreshes recent context, drains messages, and
reconstructs the scene before writing a comparatively short completion.

The system should therefore avoid ping-pong between agents unless a real
play decision requires a different person at the table.

## The Principle

**Do the work in the current actor's turn whenever that actor has authority to
do it.**

This is why the design favors:

- DM turns that answer multiple questions at once instead of one handoff per
  clarification.
- Message bus coordination instead of public transcript back-and-forth.
- Rapid-response rounds for brief reactions to the same prompt.
- Action-scene turns that include housekeeping, movement, one action, rolls,
  and outcome narration in one invocation.
- DM-side PC checks when the DM needs a player-character check on the DM's own
  turn.

## DM-Side PC Checks

At a traditional table, the DM often says, "make a check," waits for the
player to roll, then narrates the result. In this system that would cost at
least one extra agent invocation and often two.

Instead, when the DM needs a check for a player character during a DM turn, the
DM rolls it directly:

```bash
glass roll perception attunement --risk standard --character tev-pc-1
```

The `character_id` says whose character the check affects; the command audit
says the DM rolled it. The DM then uses the result in the same turn's narration.

This does not replace player-initiated rolls. When a player is acting on their
own turn and decides their action is uncertain and consequential, they call
their own `glass roll` and narrate around the outcome.

## When To Switch Actors Anyway

Minimizing transitions is not the same as avoiding them entirely. Switch actors
when the next choice genuinely belongs to someone else:

- The player must choose between meaningful alternatives before resolution.
- A private clarification changes what the player wants to do.
- A scene beat is about another character's reaction, not the current actor's
  authority.
- The mode's speaker rule says the next slot has arrived.

Do not switch actors merely to ask for dice, collect a one-word confirmation,
or bounce a minor clarification that can be answered through the bus.

## Design Test

Before adding a handoff, prompt, tool, or workflow step, ask:

> Does this require another agent's judgment right now, or can the current
> actor resolve it honestly and keep the scene moving?

If it can be resolved honestly by the current actor, keep it in the current
turn.
