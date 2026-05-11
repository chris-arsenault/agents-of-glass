---
title: Rapid Response Player Methodology
status: authored
audience: players
applies_to_modes: [scene-play, action, combat, chase, social-pressure]
---

# Rapid Response - Player

A rapid-response turn is a short answer to one DM prompt. It is not a full
player turn.

1. Read the prompt in TURN_START.
2. Read only the current table, scene summary, or unread messages needed to
   answer that prompt.
3. Write a brief direct response to the `TURN.md` path from TURN_START: usually
   one paragraph, one line, or one image.
4. End with `glass turn end` using `no state change`, `rolls none`, and
   `--next default`.

Required closeout shape:

```bash
glass turn end \
  --summary "<what changed or no state change>" \
  --state "no state change" \
  --rolls none \
  --next default
```

## Done

Your turn is done only when the response exists and `glass turn end` succeeds.
