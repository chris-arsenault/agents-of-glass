---
title: Intermission Methodology
status: authored
audience: dm_and_players
applies_to_modes: [intermission]
---

# Intermission

Intermission is the short player-facing planning room between major campaign
sections: after the prelude, and after an act closes before the next act starts.
It is not an in-fiction scene. It is collaborative mid- to long-term campaign
planning.

## Purpose

Use intermission to let the table say what it wants before Mara frames the next
act:

- unresolved threads players want followed up
- relationships or NPCs they want more time with
- magic items, equipment, training, repairs, or abilities they hope to pursue
- tone requests: harder, stranger, quieter, more dangerous, more political
- boundaries around what should be summarized instead of played out

Mara participates as facilitator, not as an adjudicating scene DM. Players speak
as players; they may reference their characters, but no character takes binding
in-fiction action here.

## Turn Shape

The intermission cap is 15 turns total: three passes through Mara, Tev, Sumi,
Renno, and Kit. Shorter is fine. Do not stretch to fill the cap.

Mara opens first. In the opening turn:

- name the broad pressure or tone of the next act without spoiling secrets
- remind the table which unresolved threads are available
- invite requests about what the players want to see, resolve, find, learn, or
  change

Players answer with concrete preferences. Good intermission turns are specific:
"I want Drova and Tek to have one scene about the tic-tracer" is better than
"more character stuff."

## Outputs

Before the intermission closes, Mara should write a compact synthesis to
`dm/scratchpad.md` and, when useful, a player-visible version to
`shared/quest-log.md` or `shared/party-knowledge.md`.

Players may update their own scratchpads, journals, public notes, or private
requests to Mara. Keep these concise and commit them with `glass sync apply`.

## Ending

Mara may end intermission early once the useful requests are captured:

```bash
glass mode end
```

If nobody ends it manually, the orchestrator stops it at the 15-turn cap. The
next `aog campaign run` starts Mara in `scene-prep` for the next act.
