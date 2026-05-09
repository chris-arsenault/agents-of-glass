---
title: Message Types
---

# Message Types

The schema for `glass msg <type> <recipient> <body>`. **CLI-validated** — unknown types are rejected with a list of valid options. The body is free-form prose.

For the messaging system itself, see [`/docs/design/messaging.md`](../../../docs/design/messaging.md).

## The types

### `table-talk`
OOC chatter at the table. Rules questions, jokes, snacks, observations about how the session is going. Not in-character.
> `glass msg table-talk all "did Sumi already roll for the trap, or are we still on Renno's perception?"`

### `banter`
In-character dialogue between PCs that's happening *off-camera* — a quiet word between scenes, a shared look the table doesn't need to see staged. Goes in the corpus as IC.
> `glass msg banter sumi "Karrith mutters: 'don't let him talk to me about it tomorrow.'"`

### `instruction`
Coordinated planning — the party agreeing on what to do next, or one PC giving direction to another. IC or OOC; usually IC. Often goes to `party`.
> `glass msg instruction party "we split at the kite-rack: Tev and Sumi take the upper deck, Mork and Renno cover the gantry."`

### `plot-hint`
DM-only sender. A private hint to one player (or the party) that doesn't surface in the public transcript. Used when the DM wants a player to know something their PC would have noticed, without spending a public turn on it.
> `glass msg plot-hint tev "the patrol leader's tuning fork is humming in the wrong band — Karrith would catch this immediately."`

### `secret`
Private knowledge. DM-to-player when the player needs to know something hidden from the rest of the party. Player-to-DM when the player wants to flag intent that other PCs shouldn't see (*"Karrith is going to lie to Mork about the cord"*).
> `glass msg secret dm "Karrith plans to take the shard for himself when the others aren't looking. I'll narrate around it."`

## Visibility

| Type | Who can read |
|------|---------------|
| `table-talk` | recipient + DM |
| `banter` | recipient + DM |
| `instruction` | recipient + DM (or all of party + DM if recipient is `party`) |
| `plot-hint` | recipient + DM (DM is also the sender) |
| `secret` | recipient + DM |

The DM sees everything. Player-to-player messages are file-permission-isolated from other players. See [`/docs/design/context-packages.md`](../../../docs/design/context-packages.md).

## Adding a new type

Don't, casually. The list is short on purpose. A new type is only worth adding when an existing one is being misused for two distinct purposes the corpus would benefit from telling apart. Propose in [`/docs/design/open-questions.md`](../../../docs/design/open-questions.md), not here.
