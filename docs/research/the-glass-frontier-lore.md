# the-glass-frontier-lore

Located: `/home/dev/repos/the-glass-frontier-lore`

## What It Is

A canonical worldbuilding wiki for the Kaleidos system. One file per entry, cross-linked like a wiki. Markdown with YAML frontmatter and structured metadata.

The world is a shattered ring world (the rings broke 130 years ago), a planet beneath dusted in crystal, and a solar system relearning how to be one civilization. **Tone:** "serious hopecore" — Firefly scrappiness + Iain M. Banks Culture-tier survivals + Sanderson-grade hard systems. Not Discworld, not winking, not whimsical. Earnest, lived-in, fundamentally hopeful.

## Architecture We're Cribbing

- **Markdown authoring pattern.** Prose lives in one entry per file, with frontmatter and stable headings. We keep this file shape for campaign lore.
- **Typed relationship vocabulary.** No generic relationships (`RELATED_TO` is banned). Relationship prose should use concrete language such as located in, governs, caused, or member of.
- **Entry + section consistency.** Every durable entry has a consistent shape: id, title, type, attributes, and prose sections. No special file shape per content kind.
- **DM/player separation in the wiki.** `dm/` content (themes, threads, loops, secret truths) is excluded from the player-facing layer. We mirror this — players see player-facing lore; the DM agent has DM-only access.
- **Themes / threads / loops as DM scaffolding.** These are authorial generators, not in-universe knowledge:
  - **Themes** = questions the world asks ("what do you build when the blueprints are gone?")
  - **Threads** = multi-beat narrative arcs (Reconnection has 10 beats; Bloom Containment has its own sequence)
  - **Loops** = recurring patterns (cooperation-fracture cycle)

  We use these in worldbuilding mode and during DM scene framing.
- **Embedding-backed semantic search.** Section-level embeddings enable "find things like this." We implement semantic recall through the local search path.

## What We're Explicitly Not Cribbing

- **The wiki publication pipeline.** They generate a GitHub wiki; we don't need that.
- **The review tooling** (`review.py`, the React review app, voice-review prompts). Useful for human authors; we have agents.
- **The full lint suite.** We'll want lints, but theirs are tuned for human-written prose; ours will need to check agent-emitted notes for different things.
- **The narrative-role distinction (`viewpoint` / `titan`).** Useful for hand-authored fiction; not yet clear if it's useful for agentic generation.
- **Their structured mirror and snapshot/restore workflow.** Our current persistence is markdown plus Postgres/search.

## What We Read From It at Runtime

The lore repo is **read-only at session time.** Player agents and the DM consult lore entries to ground their notes and decisions. We don't write back to it from our orchestrator — anything new an agent invents goes into campaign markdown (`shared/lore/`, `dm/notes/`, or table artifacts as appropriate).

## Open Questions

- **How aggressively do we surface lore in agent prompts?** Stuffing every prompt with relevant lore is expensive; relying on the agent to query is brittle. Probably some pre-fetched "scene-relevant lore digest" the orchestrator assembles per turn.

## Key Files to Re-Read When Designing

- `CLAUDE.md` — authoring conventions, especially the "in-universe voice" rules
- `SYSTEM.md` — entry schema, embedding pipeline, contradiction checks
- `dm/themes/`, `dm/threads/`, `dm/loops/` — the DM scaffolding shapes
- `player/cosmology/resonance.md` — exemplar of "hard system" worldbuilding to model our agent-emitted notes after
- `player/design-principles.md` — the meta-principles that govern lore writing; many transfer to ours
