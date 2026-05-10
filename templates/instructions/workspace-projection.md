---
title: Workspace Projection Instructions
target: executing-agent
authority: binding
---

# Workspace Projection

Your turn runs in a campaign-shaped workspace whose relative paths match the
canonical campaign tree. It is a read-only projection of the files you are
allowed to see.

Read files directly from normal paths such as `table/scene.md`,
`players/<id>/public/intro.md`, `shared/lore/`, `srd/`, and `instructions/`.

Do not rely on direct file writes for persistent state. Persistent mutations
must go through `glass`: `glass note write`, `glass table write`, `glass lore`,
`glass character`, `glass scene`, `glass clock`, `glass entity`, and related
commands.

Use `scratch/` for temporary drafts during the turn. For example:

```bash
glass note write public/intro.md --from scratch/intro.md
glass note write secrets/debt.md --from scratch/debt.md
glass table write index.md --from scratch/table-index.md
```

At turn end, write final public prose to the `out.md` path named in
TURN_START. That file is copied into the canonical turn record by the
orchestrator.
