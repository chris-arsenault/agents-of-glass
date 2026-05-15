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

3. Use the unified search facade for most lookup:

   ```bash
   glass find "<query>"
   glass find "<query>" --mode semantic
   glass find "<query>" --mode turns --scene <scene-id>
   ```

4. Use lower-level search commands only when TURN_START or a command response
   names the exact command. Do not browse the full CLI looking for alternate
   search tools.

5. Use graph commands for relationships between named things when TURN_START
   exposes them or the methodology requires them:

   ```bash
   glass entity relations <entity-id>
   glass entity between <a> <b>
   glass entity stance <a> <b>
   ```

6. Act on the retrieved context in the same turn or state the remaining blocker
   in `glass done --state`.
