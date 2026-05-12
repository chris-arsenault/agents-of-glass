---
title: Glass CLI Instructions
target: executing-agent
authority: binding
---

# Glass CLI Instructions

`glass` is the persistent mutation boundary. If a command owns a kind of state,
use the command instead of prose or ad hoc markdown.

## Turn Sequence

1. Read workspace files directly.
2. Make hard-state changes with the specific `glass` command.
3. Edit authored markdown at its real workspace path.
4. Commit authored markdown with `glass sync apply <path-or-directory> ...`.
5. Read the same path or command output only when verification is needed.
6. Write `TURN.md`.
7. Run `glass turn end`.

## Read Commands

```bash
glass character bulk-get <id>... [--all]
glass clock list [--all]
glass scene current
glass table show [path]
glass summary show campaign|arc|scene [id]
glass turns find --text "<query>"
glass turns feed --after-turn <n>
glass search text "<query>"
glass search semantic "<query>"
glass entity relations <id>
glass tarot current
```

## Mutation Commands

```bash
glass roll <skill> <attribute> --risk <level> --character <id>
glass scene pressure <target> <skill> <attribute> --risk <level> --character <id> --impact <d6|d8|d10>
glass character bulk-update --json '<payload>'
glass character mirror <id>
glass character set-hp <id> <delta>
glass character set-momentum <id> <value>
glass character inventory-add <id> <item-id>
glass character consequence-add <id> <label>
glass character skill-declare <id> <skill-name>
glass clock set <id> --max <n> [--scope <scope>] [--anchor <id>] [--public]
glass clock tick <id> [delta] [--note "<note>"]
glass table write <path> --body "<markdown>"
glass table append <path> --body "<markdown>"
glass table use <campaign-markdown-path> --as <table-artifact>.md
glass summary write campaign|arc|scene [id] --body "<markdown>"
glass summary append campaign|arc|scene [id] --body "<markdown>"
glass lore import <world-bible-path>
glass lore promote table/<artifact>.md --to shared/lore/<path>.md
glass lore upsert <path>
glass entity claim <a> <REL> <b> --summary "<summary>"
glass msg <type> <recipient> <body>
glass turn handoff <agent-id>
glass turn rapid-round "<prompt>"
glass turn housekeeping-round --previous-scene "<closed>" --next-scene "<next>"
glass sync apply [path-or-directory ...]
```

## Workspace Sync

Use `glass sync apply` only for authored markdown files and directories:

```bash
glass sync apply players/<id>/public players/<id>/notes
glass sync apply arcs/<arc> table shared
glass sync apply
```

Do not sync turn artifact paths such as `dm/turns/<n>/TURN.md` or
`players/<id>/turns/<n>/TURN.md`; the runner collects turn prose and closeout
automatically.

## Turn End

Every turn ends with:

```bash
glass turn end \
  --summary "<compact continuity for the next actor>" \
  --state "<durable updates or no state change>" \
  --rolls "<rolls/checks used or none>" \
  --next default
```

Use `--next <agent-id>` only when normal rotation or action order must be
overridden. Use `--open-question`, `--position`, and `--pressure` when those
fields changed.

## Command Failure

Read the error, make one clear correction, and retry when the fix is obvious.
If the command still fails, continue only if the turn remains coherent and
report the failed command in `glass turn end --state`.
