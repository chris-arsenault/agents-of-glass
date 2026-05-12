---
title: Workspace Authoring Instructions
target: executing-agent
authority: binding
---

# Workspace Authoring

Your turn workspace contains readable campaign files and writable projected
documents. Use workspace-relative paths exactly as they appear in `TURN_START`.

## Sequence

1. Read the output paths and writable roots named in `TURN_START`.
2. Read normal campaign files directly:

   ```text
   table/scene.md
   players/<id>/public/intro.md
   shared/lore/
   srd/
   instructions/
   ```

3. Edit authored markdown at the real relative path where the document belongs.
4. Commit authored markdown with `glass sync apply`:

   ```bash
   glass sync apply players/<id>/public/intro.md
   glass sync apply players/<id>/notes/route-ledger.md
   glass sync apply table/<meaningful-slug>.md
   ```

5. Commit several authored paths together when the turn creates a package:

   ```bash
   glass sync apply players/<id>/public players/<id>/notes
   glass sync apply arcs/<arc> table
   ```

6. Run `glass sync apply` with no path arguments only after all intended
   writable markdown edits are ready.
7. Use dedicated commands instead of sync for hard state: `glass character`,
   `glass scene`, `glass clock`, `glass entity`, `glass roll`, `glass table`,
   `glass lore`, and `glass note`.
8. Read back command-created files or command output when verification is
   needed.
9. Write final public prose to the `TURN.md` path from `TURN_START`.
10. Run `glass turn end --summary ... --state ... --rolls ...`.

## Boundary

Do not sync turn artifact paths such as `dm/turns/<n>/TURN.md` or
`dm/turns/<n>/turn-closeout.json`; the runner copies those back automatically.
Do not use markdown edits as substitutes for hard-state commands.
