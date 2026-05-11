# Instruction Surface

Agents of Glass has several personas in play. Confusing them creates prompt
drift and documents that try to serve incompatible readers.

## Personas

- **Coder** — Codex, Claude Code, or another assistant editing this repository.
  Reads `codex.md`, `CLAUDE.md`, and `docs/design/`.
- **Executing agent** — the process the orchestrator invokes for one turn.
  Reads `TURN_START.md`, `instructions/`, and the active methodology.
- **Player or DM** — the table role the executing agent is acting as. Reads
  persona, SRD, how-to material, and table state.
- **Character** — the in-fiction person the player controls. Knows only
  character sheet, public table/campaign context, and lore their player can
  reference.

Here, "public table" has a precise runtime meaning: files under `table/` that
are projected into player-agent CWDs. Human web viewers may inspect more than a
character or player agent can see.

## Document Types

| Type | Runtime root | Target | Authority |
|------|--------------|--------|-----------|
| Instructions | `instructions/` | executing agent | Binding mechanical tool/file behavior |
| Methodology | `methodologies/` | executing agent | Binding ordered workflow for a phase or turn mode |
| SRD | `srd/` | player/DM | Public TTRPG rules and mechanics |
| How-to / examples | `how-to/` | player/DM | Non-binding craft advice and seeds |
| Lore | `shared/lore/` | character | In-fiction world knowledge |
| Design docs | `docs/design/` | coder | Implementation rationale and architecture |

## Authority Order

When an executing agent is taking a turn:

1. `TURN_START.md` — current facts, output path, active mode, table pointers.
2. `instructions/` — how to use tools, files, searches, and state safely.
3. `methodologies/<mode>.md` — the required sequence for this invocation.
4. `srd/` — game rules.
5. Persona and character sheet — table voice and character behavior.
6. `how-to/` — optional craft guidance and examples.
7. `shared/lore/` — in-fiction knowledge.

Persona and character shape choices. They do not override instructions,
methodology, table state, dice, or SRD.

## Boundaries

- Instructions say how an executing agent uses the system: `glass` commands,
  message bus, table, output files, search, and note/lore paths.
- Methodologies say what sequence to follow in this invocation.
- SRD says what the game rules are, written as public rules rather than
  implementation docs.
- How-to docs offer patterns and examples. They should avoid binding language
  except where they quote a rule from the SRD.
- Lore must stay in-fiction. Do not put CLI commands, document procedures,
  prompt advice, or game-design commentary in lore.
- Design docs can reference all of the above, but executing play agents should
  not need to read design docs to take a turn.

Runtime prompt wording follows [`prompt-writing.md`](prompt-writing.md):
generated `TURN_START.md` files should name the active table identity directly
before they list supporting files.

## Refactor Rule

When adding or moving text, ask who the sentence is commanding:

- If it commands the executing agent's tool/file behavior, put it in
  `instructions/`.
- If it commands an ordered workflow, put it in `methodologies/`.
- If it explains a game rule a human table could read, put it in `srd/`.
- If it gives taste, examples, or creative options, put it in `how-to/`.
- If a character could know it in-world, put it in `shared/lore/`.
- If it explains why the code is shaped this way, put it in `docs/design/`.
