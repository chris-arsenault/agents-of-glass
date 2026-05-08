# Graph Coherence Checks

**Status:** Placeholder. Linked to architectural choices in [`../design/architecture.md`](../design/architecture.md).

## What We Want to Know

The lore repo runs a suite of graph contradiction checks (G1–G8 + L2 in `the-glass-frontier-lore/SYSTEM.md`):

| Check | What it catches |
|-------|----------------|
| G1: Dangling references | MENTIONS edges to titleless entities |
| G2: Causal cycles | CAUSED chain cycle detection |
| G3: Temporal paradox | Entity with valid_to causes entity with later valid_from |
| G4: Attribute collision | Prose frontmatter vs graph property mismatches |
| G5: Antisymmetry | Directional rels (GOVERNS, LEADS) can't be bidirectional |
| G6: Spatial cycles | PART_OF cycle detection |
| G7: Orphan detection | Complete entities with zero edges |
| G8: Edge temporal coherence | Temporal edges missing valid_from; edge bounds exceeding entity bounds |
| L2: Section similarity | Same-heading sections from different entities with cosine > 0.92 |

Which of these apply to our agentic-session graph? Which need adaptation? Are there agent-specific checks the lore repo doesn't have?

Candidate agent-specific checks:

- **DM contradiction** — DM canonical notes that conflict with prior canonical notes (e.g. NPC's faction changed without an explanatory edge)
- **Player-DM contradiction** — a player journal entry stating something the DM has explicitly contradicted
- **Beat-advancement consistency** — `ADVANCES_BEAT` edge to a beat that's already past
- **Mode-graph consistency** — an entity tagged with a mode that doesn't exist
- **Speaker attribution drift** — a transcript turn attributed to a speaker not in the session

## Why It Matters

The graph is the coherence layer. If the agents are introducing contradictions faster than they're noticed, the world breaks down across sessions. Lints catch this cheaply.

## To Do

- Read `the-glass-frontier-lore/lint.py` to see how each check is implemented
- Decide which transfer directly, which need adaptation, which we add new
- Implement as part of the `glass` CLI (`glass check` analogous to `graph_cli.py check`)
- Update this file with the final check list
