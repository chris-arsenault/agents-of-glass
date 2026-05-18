---
title: Output Contract
target: executing-agent
authority: binding
---

# Output Contract

Every turn has two outputs:

1. Public prose in `TURN.md`.
2. Compact closeout from `glass done`.

## Sequence

1. Run `glass check` on full turns, then finish required `glass` mutations and `glass sync apply` commits.
2. Write public prose to the `TURN.md` path named in TURN_START.
3. Run `glass done`.
4. Exit.

## Public Prose

`TURN.md` is the visible story beat or process note. It is not the state
transport layer.

- Normal full turn: target 300-800 words. Prefer cutting a beat over compressing an event into a codified label when over budget.
- Rapid response: answer only the prompt.
- Housekeeping: short process-only note.
- Scene transition or close: include the visible closure and next visible board.

Do not put JSON, YAML, private planning, raw command logs, or long tool
transcripts in `TURN.md`. Literal `glass ...` command lines are debug material;
the command audit stores actual mutations.

## Closeout

```bash
glass done \
  --summary "<1-3 sentence continuity for the next actor>" \
  --state "<durable updates or no state change>" \
  --rolls "<rolls/checks used or none>" \
  --next default
```

For normal active-play player turns, add:

```bash
--turn-type "<act|answer|support|pass>"
```

`pass` is a real visible turn, not empty filler. It also requires
`--state "no state change"` and `--rolls none`.

Add fields when relevant:

```bash
--open-question "<question the next actor must see>"
--position "<position/leverage changed or unchanged>"
--pressure "<tracker/clock/HP/pressure changed or none>"
--scene-status active|closing|ending|ended|blocked
```

Use `--next <agent-id>` only when overriding normal rotation or action order.
On active-play turns, run `glass check` before the prose pass; `glass done`
will tell you if that requirement is still missing.
