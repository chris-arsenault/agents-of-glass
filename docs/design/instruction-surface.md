# Instruction Surface

Agents of Glass has several personas in play. Confusing them creates prompt
drift and documents that try to serve incompatible readers.

## Personas

- **Coder** — Codex, Claude Code, or another assistant editing this repository.
  Reads `codex.md`, `CLAUDE.md`, and `docs/design/`.
- **Executing agent** — the process the orchestrator invokes for one turn.
  Receives one injected prompt, reads reference material under `templates/`, and
  interacts with state only through `glass`.
- **Player or DM** — the table role the executing agent is acting as. Reads
  persona, SRD, how-to material, and table state.
- **Character** — the in-fiction person the player controls. Knows only
  character sheet, public table/campaign context, and lore their player can
  reference.

Here, "public table" means facts and hard state exposed in the injected prompt
or returned by authorized `glass` commands. Human web viewers may inspect more
than a character or player agent can see.

## Document Types

| Type | Runtime root | Target | Authority |
|------|--------------|--------|-----------|
| Instructions | `instructions/` | executing agent | Binding CLI and state behavior |
| Methodology | `methodologies/` | executing agent | Binding ordered workflow for a phase or generated turn type |
| SRD | `srd/` | player/DM | Public TTRPG rules and mechanics |
| How-to / examples | `how-to/` | player/DM | Non-binding craft advice and seeds |
| Reference lore | SQLite `lore_entries` | DM/player | Prose source material, not continuity |
| Design docs | `docs/design/` | coder | Implementation rationale and architecture |

## Authority Order

When an executing agent is taking a turn:

1. Injected prompt - current facts, active mode, allowed commands, and output contract.
2. `instructions/` - how to use `glass`, searches, facts, and state safely.
3. The methodology named by the injected prompt - the required sequence for this invocation.
4. `srd/` — game rules.
5. Persona and character sheet — table voice and character behavior.
6. `how-to/` — optional craft guidance and examples.
7. Injected reference lore — source prose, not continuity.

Persona and character shape choices. They do not override instructions,
methodology, table state, dice, or SRD.

## Boundaries

- Instructions say how an executing agent uses the system: `glass` commands,
  message bus, facts, public prose, and search.
- Methodologies say what sequence to follow in this invocation.
- Actual-play methodologies are one contract per role and turn type. A generated
  injected prompt chooses the active document from mode plus metadata such as action
  order, rapid-response prompt, housekeeping queue, or scene-transition state.
  Do not add "if this turn is really another turn type, use another methodology"
  routing inside those documents.
- SRD says what the game rules are, written as public rules rather than
  implementation docs.
- How-to docs offer patterns and examples. They should avoid binding language
  except where they quote a rule from the SRD.
- Reference lore must stay in-fiction. Do not put CLI commands, document
  procedures, prompt advice, or game-design commentary in lore.
- Design docs can reference all of the above, but executing play agents should
  not need to read design docs to take a turn.

Runtime prompt wording follows [`prompt-writing.md`](prompt-writing.md): the
injected prompt should name the active table identity directly before it lists
supporting facts, methodology, and commands.

## Refactor Rule

When adding or moving text, ask who the sentence is commanding:

- If it commands the executing agent's CLI/state behavior, put it in
  `instructions/`.
- If it commands an ordered workflow, put it in `methodologies/`.
- If it explains a game rule a human table could read, put it in `srd/`.
- If it gives taste, examples, or creative options, put it in `how-to/`.
- If a character could know it in-world as durable campaign reality, put it in
  continuity facts. If it is only source prose, put it in embedded reference
  lore.
- If it explains why the code is shaped this way, put it in `docs/design/`.
