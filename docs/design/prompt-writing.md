# Prompt Writing Guidance

Runtime prompting is a two-layer stack. The **system prompt** carries who the
agent is and how they write; the **injected turn message** carries the current
situation and this turn's job. Do not mix the layers: identity and craft do not
belong in the turn message, and turn state does not belong in the system prompt.

## The system prompt layer

Claude-provider actors run with a fully custom system prompt that replaces the
default coding-agent prompt (`claude -p --system-prompt-file`). It is assembled
per actor by `src/orchestrator/system_prompt.py` from three authored inputs:

- `templates/prompts/{dm,player}-base.md` — role identity frame, creative
  direction, craft principles, fairness rules, boundaries, and the durable
  guards relocated from the old turn prompt (see `prompt-guard-ledger.md`).
- The actor's persona (`templates/dm/persona.md`,
  `templates/players/<id>/persona.md`) — inlined wholesale under "Who you are
  at the table". Personas are embodied, never referenced as files.
- The persona's assigned narrative style (`templates/styles/<style>.md`, via
  `narrative_style:` frontmatter) — inlined under "How your prose moves".

Codex-provider actors do not yet get a system prompt override; the turn prompt
renders its legacy identity and guard sections for them (see
`docs/backlog.md` "Codex System-Prompt Support").

## The turn message layer

`ContextBuilder._render_turn_start` builds one injected message per turn. When
the actor has an active system prompt it contains only: a one-line identity
pointer, mode/scene/turn-type header, turn-kind sections (rapid, action order,
closing countdown, housekeeping), output contract, message-bus check, creative
influence, fact pack, reference lore, workspace pointers, and the per-turn-type
tool card. The tool card keeps exact call shapes on purpose — it is what
prevents malformed tool calls.

## Persona stack

Four layers stay distinct:

- **Executing agent:** the subprocess invoked for one turn. Follows the system
  prompt, the injected turn message, and the active methodology.
- **Table person:** Mara, Tev, Sumi, Renno, or Kit — carried by the system
  prompt (persona + style inlined).
- **Character:** the in-fiction PC, known through continuity facts and
  hard-state MCP tool output.
- **World state:** facts, rolls, clocks, messages, scene state behind `glass_*`
  tools.

## Wording rules

- The system prompt says "You are..." and speaks in the second person about the
  agent's own tastes and craft; it never describes the persona as a document.
- The turn message names the active table identity in one line and defers to
  the system prompt for everything durable.
- No file-path references to persona or style files anywhere an agent reads:
  contents are inlined, paths are build inputs.
- Put operator, inspection, shakedown, evaluation, and implementation language
  only in operator/coder-facing docs. Runtime prompts express the in-table job.
- Guard text is governed by `prompt-guard-ledger.md`: guards are regression
  fixes; move or remove them only with a ledger disposition.
