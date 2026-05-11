---
title: Output Contract
target: executing-agent
authority: binding
---

# Output Contract

Write your final public turn prose to the path named in `TURN_START.md` and
exit.

The public turn prose is a **creative summary of this turn**, not the complete
state transport for the game. Most state should live in the durable surfaces:
the table, scene summary, character state, lore/journal/notes, messages, rolls,
and command audit. Use the public prose to show the story beat a viewer or
future reader should experience.

For a normal full turn, target **200-500 words** of public prose. Shorter is
fine when the turn is small. Go longer only when the turn actually resolves or
reveals several concrete things at once, such as a scene opening, scene close,
major DM consequence, or multi-character exchange.

Do not put YAML, JSON, analysis notes, private planning, or raw tool
transcripts in that file. The orchestrator reads only the turn output file for
public prose.

The public turn can include OOC player voice and IC character narration when
both matter. Keep OOC brief and useful; long bus summaries, tool summaries,
private planning, and conditional branches belong in messages, scratchpads,
table state, or the scene summary. When the turn is primarily scene play,
let the visible fiction carry most of the prose and tuck any table-process
notes after the beat.

When a character would naturally speak, a line or two of dialogue often reads
better than explaining the same intent from outside. Use dialogue for offers,
refusals, questions, warnings, commitments, and small character tells when it
fits the scene. It does not need to be clever or long; one plain line in the
character's register is often enough.

If you make rolls or state changes during the turn, narrate the visible outcome
in the public prose. The `glass` commands leave their own audit trail; your
turn prose is the story moment that other agents and viewers read.

You may summarize what you accomplished: files authored, messages sent, rolls
made, character state updated, or handoffs queued. Prefer natural language for
that summary. Literal `glass ...` command lines are debug/audit material; if
they appear in public prose the orchestrator will warn, but it will rely on the
actual durable state to decide whether the turn succeeded.
