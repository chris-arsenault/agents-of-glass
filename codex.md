# Agents of Glass — Agent Instructions

This file is for AI assistants (Claude Code, Codex, etc.) working in this repo. Mirrored at [`codex.md`](codex.md). Read both [`README.md`](README.md) and [`docs/principles/`](docs/principles/) before making non-trivial changes.

## What this repo is

A Python orchestrator + CLI that runs a closed-loop, fully agentic TTRPG simulation: 1 DM agent, 4 player agents, no human at the table. The artifact is a session transcript corpus. Lore comes from `../the-glass-frontier-lore`. Game-design pieces are cribbed from `../the-glass-frontier`. Neither repo's code is being ported.

## Non-negotiable principles

Four principles govern every decision. **Read these first:**

1. **[Codify only what drifts](docs/principles/codify-only-what-drifts.md)** — codification (`glass` CLI, Postgres, FalkorDB) is for numbers, inventory, names, dice. Everything else is prose. If you find yourself adding YAML schema fields to capture agent intent, stop.
2. **[Transcripts are the corpus](docs/principles/transcripts-as-corpus.md)** — the artifact is the product. Structure comes from the orchestrator and CLI; the agent emits prose.
3. **[Resist generic drift](docs/principles/resist-generic-drift.md)** — LLMs default to generic fantasy. Multi-turn loops drift toward "Thorgrim the Bold" / "the tavern" / "ancient evil stirs" unless actively resisted. Specificity is the defense.
4. **[Goals and motivation](docs/principles/goals-and-motivation.md)** — what we're researching and why this exists.

## Code conventions

- Python 3.11+ for orchestrator and CLI.
- Markdown + YAML frontmatter for narrative content (matching the lore repo's pattern).
- All state mutations go through the `glass` CLI — never raw SQL or raw Cypher from the orchestrator or anywhere else.
- Lore is encyclopedia-shaped (frontmatter + prose + sections, FalkorDB-mirrored). Personal notes are journal-shaped (free-form). Don't blur the two.
- Runtime play-facing docs are intentionally split by target persona:
  `instructions/` for executing-agent tool/file behavior, `methodologies/`
  for executing-agent sequences, `srd/` for public player/DM rules,
  `how-to/` for optional player/DM examples, and `shared/lore/` for
  in-fiction character knowledge. Keep new prose in the right surface.
- Actual-play methodologies are one contract per role and generated turn type.
  If a new turn type is needed, update TURN_START selection and add a dedicated
  methodology; don't put turn-type routing branches inside scene/action docs.
- Agents are smart; resist the urge to enforce structure they can handle in prose.

## Working in this repo

- Don't create new top-level directories without asking the operator.
- Don't add new design docs unless explicitly designing — prefer updating existing ones.
- Don't write tests for the orchestrator loop or for agent behavior; CLI-only tests against real data stores. See [`docs/design/architecture.md`](docs/design/architecture.md#testing-strategy).
- Don't add backwards-compat shims; this is pre-v1, change canonical shapes freely. See [`docs/principles/transcripts-as-corpus.md`](docs/principles/transcripts-as-corpus.md#schema-stability).
- Don't author content for `templates/players/*/persona.md` or `templates/dm/persona.md` unless explicitly asked — those are the operator's authoring step.
- Don't write to `templates/` to record runtime mutations — `templates/` is authored input only. Runtime state belongs in `sessions/<id>/` (and the future per-campaign live root).

## Build commands

```
# Once the project is set up:
pip install -e .                              # install the local packages
glass --help                                  # in-play tool surface
aog --help                                    # operator CLI

# One-time security setup (creates Unix users for all agents, sudoers rule):
sudo bash scripts/provision-agents.sh
```

(More commands populate as the build progresses. See [`src/cli/SPEC.md`](src/cli/SPEC.md) and [`src/orchestrator/SPEC.md`](src/orchestrator/SPEC.md) for what's planned.)

## Security model

Spawned agents run as dedicated Unix users: `aog-mara` for the DM and `aog-<player>` for players. The orchestrator/operator remains the operator user. The canonical `campaigns/` tree stays operator-owned; filesystem isolation is enforced by actor-owned per-turn projections under `.glass-cwd/` plus the Glass API boundary. See [`docs/design/architecture.md`](docs/design/architecture.md#process-isolation). Without provisioning, the orchestrator falls through to running agents as the operator for dev/CI only.

## Key reading order for new agents

1. [`README.md`](README.md) — what the project is
2. [`docs/principles/`](docs/principles/) — the rules
3. [`docs/design/architecture.md`](docs/design/architecture.md) — system shape
4. [`docs/design/turn-loop.md`](docs/design/turn-loop.md) — the core loop
5. [`docs/backlog.md`](docs/backlog.md) — what's deferred and why
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
