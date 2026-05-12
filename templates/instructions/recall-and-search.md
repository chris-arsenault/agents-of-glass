---
title: Recall and Search
target: executing-agent
authority: binding
---

# Recall and Search

Do not spend actor transitions asking another agent to repeat information that
is already recorded.

## Sequence

1. Read `table/` first for immediate visible scene state.
2. Read summaries for compressed continuity:

   ```bash
   glass summary show campaign
   glass summary show arc <arc-id>
   glass summary show scene <scene-id>
   ```

3. Read recent or scene-bound prose with turns commands:

   ```bash
   glass turns find --text "<query>"
   glass turns find --scene <scene-id>
   glass turns feed --after-turn <n>
   ```

4. Search older prose only after the bounded surfaces above:

   ```bash
   glass search text "<query>"
   glass search semantic "<query>"
   ```

5. Use graph commands for relationships between named things:

   ```bash
   glass entity relations <entity-id>
   glass entity between <a> <b>
   glass entity stance <a> <b>
   ```

6. Act on the retrieved context in the same turn or state the remaining blocker
   in `glass turn end --state`.
