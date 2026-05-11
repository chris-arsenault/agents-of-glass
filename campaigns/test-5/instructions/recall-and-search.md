---
title: Recall and Search
target: executing-agent
authority: binding
---

# Recall and Search

Do not spend actor transitions asking another agent to repeat information that
is already recorded.

Use bounded recall:

```bash
glass turns find --text "<query>"
glass turns find --scene <scene-id>
glass turns feed --after-turn <n>
glass search text "<query>"
glass search semantic "<query>"
glass entity relations <entity-id>
glass entity between <a> <b>
glass entity stance <a> <b>
glass summary show campaign
glass summary show arc <arc-id>
glass summary show scene <scene-id>
```

Use the table for immediate visible scene state. Use summaries for continuity
compression. Use search for older prose. Use the graph for relationships
between named things.
