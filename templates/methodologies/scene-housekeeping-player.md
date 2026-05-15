---
title: Scene Housekeeping Player Methodology
status: authored
audience: players
applies_to_modes: [scene-play, action, combat, chase, social-pressure]
---

# Scene Housekeeping - Player

A housekeeping turn is the one player cleanup pass between two scenes. The DM
has already wrapped the old scene and staged the next one. Your job is local
bookkeeping before play resumes.

1. Read the HOUSEKEEPING TURN block in TURN_START, the scene summary, recent turn
   summaries, and the current `table/` only as needed for cleanup.
2. Update your own local materials: notes, journal, public character notes,
   private requests, inventory reminders, or viewer-facing OOC bookkeeping.
3. Commit authored markdown with `glass sync apply`.
4. Write a short process-only public note to the `TURN.md` path from TURN_START.
5. Run `glass done`. Use `rolls none`,
   `--scene-status ended`, and `--next default`.

This turn does not take in-fiction action, advance the new scene, roll dice, or
design mid- or long-term story; that belongs in intermission.

Required closeout shape:

```bash
glass done \
  --summary "housekeeping only: <what you cleaned up>" \
  --state "<notes/files updated or no state change>" \
  --rolls none \
  --scene-status ended \
  --next default
```

## Done

Your turn is done when your cleanup is committed or explicitly unnecessary,
public prose exists, and `glass done` succeeds.
