---
title: Glass CLI Instructions
target: executing-agent
authority: binding
---

# Glass CLI Instructions

`glass` is the only state mutation surface. Do not write raw SQL or raw Cypher.
Do not invent mechanical state in prose when a `glass` command owns it.

Use `glass --help` and command-specific `--help` when unsure.

## Common Read Commands

```bash
glass character get <id>
glass clock list
glass summary show campaign
glass table current
glass turns find --text "<query>"
glass search text "<query>"
glass entity relations <id>
glass tarot current
```

## Common Mutation Commands

Players may mutate only their own character state and private notes. The DM may
mutate campaign, scene, lore, clock, tracker, and graph state.

```bash
glass roll <skill> <attribute> --risk <level> --character <id>
glass scene pressure <target> <skill> <attribute> --risk <level> --character <id> --impact <d6|d8|d10>
glass character set-hp <id> <delta>
glass character inventory-add <id> <item-id>
glass msg <type> <recipient> <body>
glass note propose <path>
```

If a command fails, read the error, adjust, and retry only when the correction
is clear.
