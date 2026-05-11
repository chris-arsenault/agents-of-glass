---
title: Message Bus
target: executing-agent
authority: binding
---

# Message Bus

First action of every full turn: read unread messages.

```bash
glass msg read --since-checkpoint
```

This drains anything new since your last turn: side-channel coordination,
secret messages, table talk, DM hints, and party plans. Respond to messages
that require a response before writing your public turn prose.

Rapid-response turns may skip the full menu when `TURN_START.md` explicitly
says they are single-shot responses.

## Sending

```bash
glass msg <type> <recipient> <body>
```

Recipients are `dm`, `party`, or a player id.

## Types

### `table-talk`

OOC table chatter, rules questions, and coordination that is not in character.

### `banter`

In-character off-camera dialogue between PCs.

### `instruction`

Coordinated planning or direction, usually sent to `party` or a specific PC.

### `plot-hint`

DM-only sender. A private hint about something a character would know or notice.

### `secret`

Private knowledge or hidden intent between sender and recipient. Player-to-DM
secret messages are the right place to flag plans other PCs should not see.

## Visibility

The DM can read every message. Players can read messages they sent, messages
addressed to them, and party messages.

Use the bus instead of public transcript turns for minor clarification,
coordination, hidden intent, and private answers.
