---
title: Workspace Authoring Instructions
target: executing-agent
authority: binding
---

# Workspace Authoring

Your turn has a workspace with files you can read and document surfaces you can
author. Use workspace-relative paths exactly as they appear in the files and in
TURN_START.

Read files directly from normal paths such as `table/scene.md`,
`players/<id>/public/intro.md`, `shared/lore/`, `srd/`, and `instructions/`.

File edits are drafts until committed. Persistent mutations must go through
`glass`: `glass sync apply`, `glass character`, `glass scene`, `glass clock`,
`glass entity`, and related commands.

Edit authored markdown at the real relative path, then sync that path:

```bash
glass sync apply players/<id>/public/intro.md
glass sync apply players/<id>/secrets/debt.md
glass sync apply table/index.md
```

When you have several edits, sync files or directories together:

```bash
glass sync apply players/<id>/public players/<id>/notes
glass sync apply arcs/<arc> table
```

With no path arguments, `glass sync apply` commits changed writable markdown
files. It does not commit hard state; use the dedicated `glass` commands for
rolls, HP, clocks, trackers, inventory, graph edges, and character mechanics.

After a successful `glass` command, files created through `glass` are readable
at the same relative paths.

At turn end, write final public prose to the `out.md` path named in
TURN_START.
