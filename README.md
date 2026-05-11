# Agents of Glass

A closed-loop, fully agentic tabletop RPG simulation. One DM agent, four player agents, no human at the table. The agents take turns inside an orchestrated loop and produce scene transcripts as the artifact.

The world is the Kaleidos system from [The Glass Frontier](docs/research/the-glass-frontier-lore.md) — a shattered ring world, a planet dusted in crystal, a solar system relearning how to be one civilization. Serious hopecore. The agents inhabit this world the way fictional players inhabit a game.

This is a research project, not a product. The output is a corpus of scene transcripts and the structured graph that grew alongside them. Later passes turn the corpus into narrative.

## Why

The interesting question isn't "can an LLM run a TTRPG game." That's been done. The interesting questions are:

- **What kind of fiction emerges when nobody at the table is human, but every participant is a *specific person* with preferences and friction?**
- **Can a multi-agent loop produce something with more texture than single-prompt narrative generation — improv, push-back, mistakes, in-jokes — by giving each agent enough autonomy to actually disagree?**
- **What does the structured byproduct (graph state, per-character notes, dice events, beat advancement) look like as a first-class artifact alongside the prose?**

We don't know the answers. The project is set up to find out. See [docs/principles/goals-and-motivation.md](docs/principles/goals-and-motivation.md) for the long version.

## The Shape

- **One DM agent** (Mara) and **four player agents** (Tev, Sumi, Renno, Kit). Each is a fictional person with a name, voice, likes, dislikes, playstyle. They are *not* archetypes.
- Each agent is its own `claude -p` invocation. The orchestrator is a dumb Python loop that owns turn order, mode state, transcript append, and which agent runs next.
- The agents talk to state through a single CLI (`glass`). They do not write SQL or Cypher directly.
- Authored prose lives in markdown, entity relationships live in FalkorDB, and hard/queryable state — turns, events, HP, inventory, dice, momentum — lives in Postgres.
- The lore comes from `the-glass-frontier-lore`; the game-design pieces are cribbed from `the-glass-frontier`. Neither repo's code is being ported.

## What's Here

- [docs/principles/](docs/principles/) — the deep "why" of the project; the artifact-first principle; codify-only-what-drifts; resist-generic-drift; non-negotiable design commitments
- [docs/design/](docs/design/) — concrete designs for the orchestrator, agents, turn loop, modes, mechanics, context packages, messaging, instruction surface, [game start](docs/design/game-start.md), and (deferred) closure; plus [open questions](docs/design/open-questions.md) we want real play to settle
- [docs/research/](docs/research/) — summaries of the supporting repos and a place to drop future research notes
- [docs/backlog.md](docs/backlog.md) — active deferred work and larger out-of-scope systems
- [src/cli/](src/cli/) — the `glass` CLI (in-play tool surface). Spec at [src/cli/SPEC.md](src/cli/SPEC.md).
- [src/orchestrator/](src/orchestrator/) — the Python orchestrator + the `aog` operator CLI. Spec at [src/orchestrator/SPEC.md](src/orchestrator/SPEC.md).
- [frontend/](frontend/) and [src/webui/](src/webui/) — the read-only campaign
  viewer. The viewer may expose the whole campaign workspace for operator and
  audience inspection, but its **Active Table** surface is restricted to
  `campaigns/<id>/table/**`, because that is the construct projected into
  player-agent CWDs. See [src/webui/SPEC.md](src/webui/SPEC.md).
- [templates/](templates/) — authored baseline content: personas, instructions, methodologies, SRD, how-to guidance, and character templates. Copied to a campaign at start. See [templates/README.md](templates/README.md).
- `campaigns/<id>/` — runtime per-campaign root, created by `aog campaign new`. Mutates during play. Three-level player-facing context plus DM workspace plus per-arc and per-scene state. See [docs/design/game-start.md](docs/design/game-start.md).
- [CLAUDE.md](CLAUDE.md) / [codex.md](codex.md) — agent instructions for AI assistants working in this repo.
- [agents-of-glass.toml.example](agents-of-glass.toml.example) — config template; copy to `agents-of-glass.toml`.

## Status

Active prototype. The orchestrator, CLI, persistence, and local web UI exist
and are being exercised against `campaigns/test-7`.
