---
title: Character-Branch Workspace Authoring Instructions
target: executing-agent
authority: binding
---

# Character-Branch Workspace Authoring

Your turn workspace contains readable campaign files and a reduced writable
surface. Use workspace-relative paths exactly as they appear in `TURN_START`.

## Sequence

1. Read the output paths and writable roots named in `TURN_START`.
2. Read normal campaign files directly:

   ```text
   table/scene.md
   players/<id>/public/character.md
   players/<id>/signature-moves.md
   shared/lore/
   srd/
   instructions/
   ```

3. Edit authored markdown only where this branch allows it.
4. Commit authored markdown with `glass sync apply`:

   ```bash
   glass sync apply players/<id>/secrets
   ```

5. Use dedicated commands instead of sync for hard state: `glass character`,
   `glass scene`, `glass clock`, `glass entity`, `glass roll`, `glass table`,
   and `glass msg`.
6. Read back command-created files or command output when verification is
   needed.
7. Write final public prose to the `TURN.md` path from `TURN_START`.
8. Run `glass done --summary ... --state ... --rolls ...`.

## Boundary

In this branch, player persona files, player notes, journals, drafts, and other
players' public files are intentionally outside the writable surface. Do not
sync turn artifact paths such as `players/<id>/turns/<n>/TURN.md` or
`players/<id>/turns/<n>/turn-closeout.json`; the runner copies those back
automatically.
