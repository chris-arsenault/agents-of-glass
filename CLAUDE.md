# Agents of Glass — Agent Instructions

This file is for AI assistants (Claude Code, Codex, etc.) working in this repo. Mirrored at [`codex.md`](codex.md). Read both [`README.md`](README.md) and [`docs/principles/`](docs/principles/) before making non-trivial changes.

## What this repo is

A Python orchestrator + CLI that runs a closed-loop, fully agentic TTRPG simulation: 1 DM agent, 4 player agents, no human at the table. The artifact is a session transcript corpus. Lore comes from `../the-glass-frontier-lore`. Game-design pieces are cribbed from `../the-glass-frontier`. Neither repo's code is being ported.

## Non-negotiable principles

Three principles govern every decision. **Read these first:**

1. **[Codify only what drifts](docs/principles/codify-only-what-drifts.md)** — codification (`glass` CLI, Postgres, FalkorDB) is for numbers, inventory, names, dice. Everything else is prose. If you find yourself adding YAML schema fields to capture agent intent, stop.
2. **[Transcripts are the corpus](docs/principles/transcripts-as-corpus.md)** — the artifact is the product. Structure comes from the orchestrator and CLI; the agent emits prose.
3. **[Goals and motivation](docs/principles/goals-and-motivation.md)** — what we're researching and why this exists.

## Code conventions

- Python 3.11+ for orchestrator and CLI.
- Markdown + YAML frontmatter for narrative content (matching the lore repo's pattern).
- All state mutations go through the `glass` CLI — never raw SQL or raw Cypher from the orchestrator or anywhere else.
- Lore is encyclopedia-shaped (frontmatter + prose + sections, FalkorDB-mirrored). Personal notes are journal-shaped (free-form). Don't blur the two.
- Agents are smart; resist the urge to enforce structure they can handle in prose.

## Working in this repo

- Don't create new top-level directories without asking the operator.
- Don't add new design docs unless explicitly designing — prefer updating existing ones.
- Don't write tests for the orchestrator loop or for agent behavior; CLI-only tests against real data stores. See [`docs/design/architecture.md`](docs/design/architecture.md#testing-strategy).
- Don't add backwards-compat shims; this is pre-v1, change canonical shapes freely. See [`docs/principles/transcripts-as-corpus.md`](docs/principles/transcripts-as-corpus.md#schema-stability).
- Don't author content for `content/players/*/role.md` or `content/dm/mara.md` unless explicitly asked — those are the operator's authoring step.

## Build commands

```
# Once the project is set up:
pip install -e .                    # install the local packages
glass --help                        # in-session CLI
aog --help                          # operator CLI (sessions, clear, list)
```

(More commands populate as the build progresses. See [`src/cli/SPEC.md`](src/cli/SPEC.md) and [`src/orchestrator/SPEC.md`](src/orchestrator/SPEC.md) for what's planned.)

## Key reading order for new agents

1. [`README.md`](README.md) — what the project is
2. [`docs/principles/`](docs/principles/) — the rules
3. [`docs/design/architecture.md`](docs/design/architecture.md) — system shape
4. [`docs/design/turn-loop.md`](docs/design/turn-loop.md) — the core loop
5. [`tracking-immediate-decisions.md`](tracking-immediate-decisions.md) — what's deferred and why
6. The specific design doc relevant to the task at hand

## Environment

- **Postgres** is on the LAN; connection via `agents-of-glass.toml`.
- **FalkorDB** is on the LAN, same instance the lore repo uses; connection via `agents-of-glass.toml`.
- **Secrets** are injected by the operator's external secrets manager (`with-cred -- <command>` in this PTY). Never write API keys to `.env` files or commit them.
- **Lore repo** at `../the-glass-frontier-lore` is read-only at session time.

## When in doubt

- **Prose over schema.**
- **Update existing docs over creating new ones.**
- **Ask the operator if scope is unclear.** Don't speculate-build features that weren't asked for.
