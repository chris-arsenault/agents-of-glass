---
title: Character State Instructions
target: executing-agent
authority: binding
---

# Character State Instructions

Character hard state lives in Postgres. Markdown character displays are cached
references, not canonical numbers.

Use `glass` for:

```bash
glass character new <id> --player <player-id> ...
glass character get <id>
glass character set-hp <id> <delta>
glass character set-momentum <id> <value>
glass character inventory-add <id> <item-id> [--effect-tag TEXT]
glass character inventory-rm <id> <item-id>
glass character consequence-add <id> <label>
glass character consequence-list <id>
glass character consequence-resolve <id> <consequence-id>
```

Roll-induced momentum changes are automatic. Inventory effect tags are free
text reminders, not rules the CLI interprets.

Players may write their own character-adjacent prose and mutate their own
character state. The DM can mutate any character state when adjudicating the
world.
