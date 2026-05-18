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
2. Run `glass check` on full turns.
3. Make hard-state changes with the specific `glass` command.
4. Edit authored markdown at its real workspace path.
5. Commit authored markdown with `glass sync apply <path-or-directory> ...`.
6. Read the same path or command output only when verification is needed.
7. Write `TURN.md`.
8. Run `glass done`.

## TURN_START Command Surface

Use the `## Your tools` section in TURN_START as the command surface for the
current turn. It is generated from role, mode, turn type, active arc/scene, and
pending upkeep. Do not browse the full CLI or repo source from inside a
campaign turn.

Every full turn starts and ends through the facade:

```bash
glass check
glass done --summary "<compact continuity>" --state "<durable updates or no state change>" --rolls "<rolls/checks used or none>" [--turn-type act|answer|support|pass] [--next default]
glass find "<query>" [--mode text|semantic|turns] [--scene <scene-id>]
```

`glass check` drains unread messages, prints the active scene clock/beat
contract, lists table files, shows durable clocks, and reports pending
level-ups. On active-play turns, it also satisfies the required beat check when
the scene contract is live. `glass done` runs the turn audit and stages the
turn closeout in one command.

TURN_START injects lower-level commands only when the current situation needs
them. Examples:

```bash
# Active play
glass roll <skill> <attribute> --risk <level> --character <id> [--save-skill]
glass scene pressure <target> <skill> <attribute> --risk <level> --character <id> --impact <d6|d8|d10> [--save-skill]
glass table write <path> --body "<markdown>"
glass table append <path> --body "<markdown>"
glass summary write campaign|arc|scene [id] --body "<markdown>"
glass summary append campaign|arc|scene [id] --body "<markdown>"
glass msg <type> <recipient> <body>

# Beat/clock upkeep
glass scene clock declare <id> --label "<label>" --goal "<goal>" --value <n> --max <n> --direction progress|countdown --polarity objective|threat|timer [--visibility public|dm]
glass scene clock tick <id> [delta] --outcome "<visible progress or consequence>"
glass beat start <id> --clock <clock-id> --label "<label>" --question "<question>"
glass beat close <id> --outcome "<outcome>" --clock-delta <n>   # n required, 0 valid
glass beat convert <id> --to-clock <clock-id> --reason "<reason>"

# Scene transition / prep
glass scene transition <next-scene-id> --new|--nested|--return [--close-parent] --type <problem-family> [--arc <arc-id>] [--new-mode scene-play|action|combat|chase|social-pressure] --summary "<closing summary>" --outcome "<outcome>" --xp "tev=3,sumi=3,renno=3,kit=3" [--carry-clock <id>=<reason>]... [--retire-clock <id>=<reason>]... [--parent-summary "<...>"] [--parent-outcome "<...>"] [--parent-carry-clock <id>=<reason>]... [--parent-retire-clock <id>=<reason>]...
# Single atomic transition. --new closes current + opens next at same stack level. --nested keeps current alive and pushes a sub-scene. --return <parent-id> closes current and pops back to a named parent on the stack. --new --close-parent closes both the current and its immediate parent before opening the next.
glass scene end --summary "<summary>" --outcome "<outcome>" --xp "tev=3,sumi=3,renno=3,kit=3" [--carry-clock <id>=<reason>]... [--retire-clock <id>=<reason>]...
# scene end is the low-level "close current scene without a successor" command; prefer scene transition during active play.
glass arc close-check [<arc-id>]
glass arc close <arc-id> --summary "<arc summary>" --outcome "<outcome>" [--carry-clock <id>=<reason>]... [--retire-clock <id>=<reason>]...
# arc close refuses if active arc-scoped clocks lack a disposition.
glass scene create <scene-slug> --type <problem-family> [--arc <arc-id>]
glass mode start <scene-play|action|combat|chase|social-pressure> <scene-slug>
# scene create + mode start are low-level recovery primitives. mode start refuses duplicate (mode, scene_id) frames on the stack.
glass thread current
glass thread advance <thread-id> --note "<concrete visible beat>"
glass next housekeeping-round --previous-scene "<closed>" --next-scene "<next>"
glass next handoff <agent-id>
glass next rapid-round "<prompt>"
glass next restart-order <agent-id>

# Character creation / upkeep
glass character new <character-id> --player <player-id> --name "<name>" --species "<species>" --culture "<culture>" --archetype "<level-20 mythic archetype>" --org-role "<organization role>" --bio "<public bio>" --goal "<goal>" --goal "<goal>" --primary-drive "<drive>" --positive-trait "<fun trait>" --table-presence "<recurring social bit>" --non-work-want "<want>" --opening-social-action "<direct PC action>" --life-prompt "<prompt>=<answer>" --life-prompt "<prompt>=<answer>" --pull-utilization "Source: <domain>; Thesis: <identity thesis>; Used in: archetype, drive, trait, table presence, non-work want, opening social action, item, skill, signature move, failure mode, voice." --attribute <name>=<tier> --skill "<skill>=artisan" --skill "<skill>=apprentice" --skill "<skill>=apprentice"
glass character signature-add <character-id> "<move name>" --look "<what it looks like>" --use "<when you use it>" --tell "<risk, cost, or trace>"
glass character bulk-get <id>... [--all]
glass character bulk-update --json '<payload>'
glass character mirror <id>
glass character level-up <id> [--attribute <name>]

# Authored markdown
glass sync apply [path-or-directory ...]
```

If TURN_START does not list a lower-level command, do not go looking for one.
Use `glass check`, `glass find`, `glass done`, or ask/close with a blocker.

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
glass done \
  --summary "<compact continuity for the next actor>" \
  --state "<durable updates or no state change>" \
  --rolls "<rolls/checks used or none>" \
  --next default
```

For normal active-play player turns, also include:

```bash
--turn-type "<act|answer|support|pass>"
```

Use `--next <agent-id>` only when normal rotation or action order must be
overridden. Use `--open-question`, `--position`, and `--pressure` when those
fields changed. `pass` requires `--state "no state change"` and `--rolls none`.
If a roll produced `stall`, `regress`, or `collapse`, `glass done` will require
a visible consequence through state, position, pressure, open question, beat
movement, or scene clock movement.
Roll output may also include a `momentum_effect`. Treat it as narrative only:
`additional_good` means add one extra good visible consequence;
`additional_complication` means add one extra visible complication.
On active-play turns, run `glass check` before writing and `glass done` at
closeout; if the beat check is still missing, `glass done` will say so
explicitly. If `glass check` or `glass done` reports no active scene clock or
no active beat after completed beats, treat that as a closure gap: players
should hand to the DM with `--next dm` instead of opening a replacement beat
unless the DM explicitly instructed it. The DM should usually keep 2-3 active
beats live across distinct problem lanes; one closed beat is not a scene ending
by itself. After eight or more completed beats, prefer a short visible `pass`
and `--next dm` unless you have a decisive blockbuster-scale contribution.

## Command Failure

Read the error, make one clear correction, and retry when the fix is obvious.
If the command still fails, continue only if the turn remains coherent and
report the failed command in `glass done --state`.
