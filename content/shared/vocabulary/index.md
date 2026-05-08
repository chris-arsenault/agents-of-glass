---
title: Shared Vocabulary
status: stub
---

# Shared Vocabulary

The agents' shared dialect. Read this for terms that recur in turns and the messaging system.

For the theory behind this directory, see [`../../../docs/design/shared-vocabulary.md`](../../../docs/design/shared-vocabulary.md).

## Files

- [`turn-verbs.md`](turn-verbs.md) — kinds of turns players take (action, inquiry, possibility, planning, reflection, prepare, address)
- [`message-types.md`](message-types.md) — the schema for `glass msg <type>`. **CLI-validated.**
- [`combat-moves.md`](combat-moves.md) — attack, prepare, hold, retreat, etc.
- [`social-moves.md`](social-moves.md) — negotiate, intimidate, persuade, etc.
- [`mechanical-terms.md`](mechanical-terms.md) — advantage, push, momentum, attunement, etc.

## Conventions

- Vocabulary is **reference, not validation** — except for `message-types.md`, which the CLI does validate (because typed messages are the indexable signal).
- Build entries as the need shows up in real sessions, not in advance.
- Skills stay free-form (any string). Skills are *not* in this vocabulary.

This index file is read into every agent's TURN_START. The detail files are read on demand.
