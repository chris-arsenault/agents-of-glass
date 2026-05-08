# the-glass-frontier-lore

Located: `/home/dev/repos/the-glass-frontier-lore`

## What It Is

A canonical worldbuilding wiki for the Kaleidos system. One file per entry, cross-linked like a wiki. Markdown with YAML frontmatter. A FalkorDB graph mirrors the prose: every entity becomes a node, every section becomes a sub-node with a 768-dim embedding, every cross-reference becomes a typed edge.

The world is a shattered ring world (the rings broke 130 years ago), a planet beneath dusted in crystal, and a solar system relearning how to be one civilization. **Tone:** "serious hopecore" — Firefly scrappiness + Iain M. Banks Culture-tier survivals + Sanderson-grade hard systems. Not Discworld, not winking, not whimsical. Earnest, lived-in, fundamentally hopeful.

## Architecture We're Cribbing

- **Markdown + graph mirror.** Prose lives in markdown. The graph is a structural mirror — entities, sections, typed edges. No free text in the graph itself. We use this exact pattern.
- **Typed edge taxonomy.** No generic relationships (`RELATED_TO` is banned). Edges have semantic types: `LOCATED_IN`, `GOVERNS`, `CAUSED`, `MEMBER_OF`, etc. We start with their taxonomy and trim/extend as needed.
- **Entity + Section unified node pattern.** Every entity has the same shape (id, title, type, attributes, embedding-bearing sections). No special node types per content kind.
- **DM/player separation in the wiki.** `dm/` content (themes, threads, loops, secret truths) is excluded from the player-facing layer. We mirror this — players see player-facing lore; the DM agent has DM-only access.
- **Themes / threads / loops as DM scaffolding.** These are authorial generators, not in-universe knowledge:
  - **Themes** = questions the world asks ("what do you build when the blueprints are gone?")
  - **Threads** = multi-beat narrative arcs (Reconnection has 10 beats; Bloom Containment has its own sequence)
  - **Loops** = recurring patterns (cooperation-fracture cycle)

  We use these in worldbuilding mode and during DM scene framing.
- **CLI-only graph mutations.** The lore repo enforces "never write ad-hoc Python that touches the graph" — all writes through `graph_cli.py`. We adopt the same rule via the `glass` CLI.
- **Embedding-backed semantic search.** 768-dim nomic embeddings on every section enable "find things like this." We can do this for free since FalkorDB supports it.

## What We're Explicitly Not Cribbing

- **The wiki publication pipeline.** They generate a GitHub wiki; we don't need that.
- **The review tooling** (`review.py`, the React review app, voice-review prompts). Useful for human authors; we have agents.
- **The full lint suite.** We'll want lints, but theirs are tuned for human-written prose; ours will need to check agent-emitted notes for different things.
- **The narrative-role distinction (`viewpoint` / `titan`).** Useful for hand-authored fiction; not yet clear if it's useful for agentic generation.
- **Their graph snapshot/restore workflow as-is.** Our needs differ — we'll want session snapshots, not authoring-protection snapshots.

## What We Read From It at Runtime

The lore repo is **read-only at session time.** Player agents and the DM consult lore entries to ground their notes and decisions. We don't write back to it from our orchestrator — anything new an agent invents goes into our own graph (`agents/dm/canonical-notes/`), which can reference lore entities by ID.

## Open Questions

- **Should our session graph and the lore graph share a FalkorDB instance, with a namespace separator?** Or separate databases? Sharing means cross-graph queries (an NPC the DM created can edge to a canonical lore location) but also means we could pollute the lore graph if we're sloppy.
- **How aggressively do we surface lore in agent prompts?** Stuffing every prompt with relevant lore is expensive; relying on the agent to query is brittle. Probably some pre-fetched "scene-relevant lore digest" the orchestrator assembles per turn.
- **Do we want the embeddings reusable across both graphs?** Probably yes — same embedding model, same dimension.

## Key Files to Re-Read When Designing

- `CLAUDE.md` — authoring conventions, especially the "in-universe voice" rules
- `SYSTEM.md` — graph schema, embedding pipeline, contradiction checks
- `dm/themes/`, `dm/threads/`, `dm/loops/` — the DM scaffolding shapes
- `player/cosmology/resonance.md` — exemplar of "hard system" worldbuilding to model our agent-emitted notes after
- `player/design-principles.md` — the meta-principles that govern lore writing; many transfer to ours
