---
title: Character State Instructions
target: executing-agent
authority: binding
---

# Character State Instructions

Character hard state lives in Postgres. Markdown character displays are readable
mirrors, not canonical numbers.

## Read Sequence

1. Use one command for the needed character set:

   ```bash
   glass character bulk-get <id>...
   glass character bulk-get --all
   glass character get <id>
   ```

2. Read slot and consequence state with dedicated commands when they matter:

   ```bash
   glass character signature-status <id>
   glass character consequence-list <id>
   ```

3. Treat `players/<id>/public/character.md` as display text only. Do not infer
   HP, momentum, inventory, consequences, or slot availability from a mirror.

## Creation Sequence

1. Read the active character-creation methodology and `srd/character-creation.md`.
2. Run `glass character new` with canonical species, culture, archetype,
   organization role, bio, two or three goals, primary drive, positive trait,
   table presence, non-work want, opening social action, two or three life-prompt
   answers, a non-adjacent pull utilization note with source, thesis, and all
   required usage surfaces, and the starting skill budget: exactly two
   `apprentice` skills and one `artisan` skill.

   ```bash
   glass character new <id> --player <player-id> \
     --name "<full name>" \
     --species "<species>" \
     --culture "<culture>" \
     --archetype "<level-20 mythic archetype>" \
     --org-role "<organization role>" \
     --bio "<public bio>" \
     --goal "<goal one>" \
     --goal "<goal two>" \
     --primary-drive "<required drive>" \
     --positive-trait "<visible positive/quirky/playful/warm/funny trait>" \
     --table-presence "<recurring social bit another player can use>" \
     --non-work-want "<want unrelated to profit, safety, mission, or job competence>" \
     --opening-social-action "<direct action toward another PC for the intro>" \
     --life-prompt "<prompt>=<concrete behavior answer>" \
     --life-prompt "<prompt>=<concrete behavior answer>" \
     --pull-utilization "Source: <real-world domain/source>; Thesis: <identity thesis>; Used in: archetype, drive, trait, table presence, non-work want, opening social action, item, skill, signature move, failure mode, voice." \
     --attribute <name>=<tier> \
     --skill "<skill>=artisan" \
     --skill "<skill>=apprentice" \
     --skill "<skill>=apprentice"
   ```

3. Use `archetype` for class-like identity. Use `organization_role` for current
   membership, status, or responsibility inside the party organization.
   Archetype should be the heroic identity that would still describe the
   character at level 20 as a mythic figure in the campaign world, not a current
   job title like recorder, clerk, examiner, witness, handler, or liaison.
4. The character must read as a table-facing person, not only a reserved
   professional. Record a social bit, a non-work want, and an opening action
   toward another PC.
5. The pull utilization note must name the source/domain and identity thesis, and
   show where the pull appears across archetype, primary drive, positive trait,
   table presence, non-work want, opening social action, at least one item, at
   least one skill, signature move, failure mode or complication pattern, and
   prose/voice texture.
6. Add starting inventory, consequences, and signature moves with
   `glass character bulk-update --json '<payload>'` or the specific commands.
   Starting inventory must be exactly 3 items, and one item must be a weapon or
   combat implement. The starting signature move must be usable in an action
   setting, even if it is social, protective, piloting, rescue, or magical rather
   than an attack. Mark the weapon item with an effect tag beginning `weapon:`.
7. Mirror the result with `glass character mirror <id>` unless the bulk update
   already used `"mirror": true`.
8. Verify the row with `glass character get <id>`.

## Inventory Boundary

Starting inventory is exactly 3 carried assets that can affect future action:
one weapon or combat implement, plus two tools, protective gear, consumables,
keys, samples, maps, leverage tokens, specialist instruments, or portable
resources. Personal relics, permits, and documents belong in bio, traits, notes,
or journal unless they are one of the three items and can plausibly affect a
future roll, access, cost, risk, or choice. The weapon item should have an
effect tag beginning `weapon:`.

Effect tags should name affordances. Prefer tags like `weapon: blocks or breaks
a close rush`, `crosses gaps or snags loose cargo`, `detects unstable wall
stress`, or `cuts fouled kite line under load` over tags that only describe mood
or origin.

## Item Ids Name Affordances, Not Status

Item ids name the affordance class. They must not encode transient status. The
CLI rejects ids ending in `-spent`, `-broken`, `-lost`, or `-sealed`. Use
`glass character inventory-rm` for permanent removal; narrative state like
jammed, sealed, or expended is recorded in scene prose and reconciled at the
next use, not by mutating the item id.

## Mutation Sequence

1. Gather every character mutation required by this turn before writing commands.
2. Use `glass character bulk-update --json '<payload>'` for multiple characters
   or multiple fields.
3. Use a single-purpose command for a single direct mutation:

   ```bash
   glass character set-hp <id> <delta>
   glass character set-momentum <id> <value>
   glass character level-up <id> [--attribute <name>]
   glass character inventory-add <id> <item-id> [--effect-tag TEXT]
   glass character inventory-rm <id> <item-id>
   glass character signature-add <id> <name> [--look TEXT --use TEXT --tell TEXT]
   glass character consequence-add <id> <label>
   glass character consequence-resolve <id> <consequence-id>
   ```

4. Let roll commands handle roll-induced momentum changes. Do not duplicate
   automatic momentum effects with a second character mutation.
5. Use inventory commands when a portable asset is gained or permanently lost.
   Transient narrative state (jammed, sealed away, lent out, expended charges)
   stays in scene prose; do not encode it in the item id.
6. Mirror public character displays after visible sheet changes.
7. Name the changed character ids and fields in `glass done --state`.

## Level-Up Sequence

When `TURN_START.md` reports a pending level-up, run
`glass character level-up <id>` once per pending level before the normal turn
action. Each call resolves exactly one level. If the level being reached is 4,
8, or another multiple of 4, include `--attribute <name>` for the attribute
bump. Record the result in `glass done --state`, then continue the turn.

## Bulk Payload Shape

`bulk-update` accepts JSON shaped like:

```json
{
  "characters": [
    {
      "character_id": "vel",
      "inventory_add": [
        {"id": "ringglass-baton", "qty": 1, "effect_tags": ["weapon: blocks or breaks a close rush"]},
        {"id": "grapnel-spool", "qty": 1, "effect_tags": ["crosses gaps or snags loose cargo"]},
        {"id": "route-seal", "qty": 1, "effect_tags": ["opens one cautious checkpoint"]}
      ],
      "signature_moves": [
        {
          "name": "Hard Left Through Fire",
          "look": "Vel drops one shoulder, points the baton at the exit, and moves before the room finishes deciding.",
          "use": "Breaking a path through danger for one other person.",
          "tell": "Leaves Vel exposed to the nearest counterattack."
        }
      ],
      "mirror": true
    }
  ]
}
```

Signature moves live in `players/<id>/signature-moves.md`, but slot progression
is enforced by `glass character signature-status` and
`glass character signature-add`. Level 1 has one slot; levels 3, 5, 7, and 9
each add one slot. Do not use notes to bypass signature move slot limits.

## Skill Slots and Declaration

Declared skills are capped at `3 + character_level` (4 at level 1, 5 at
level 2, etc.). Character creation fills the first 3 slots with the starting
budget (2 `apprentice` + 1 `artisan`). Skill names should be present-tense
action verb phrases such as `break sealed doors`, `read fault bands`, `cut
fouled lines`, `talk down crowds`, `pilot bad approaches`, or `bind wounds
under fire`.

To put a new skill on the sheet during play:

- If a check uses a skill not on the sheet, `glass roll` and `glass scene
  pressure` can still roll it as an improvised `fool` skill. Improvised skills
  do not become durable and do not gain skill xp.
- To save a new skill while rolling, use `--save-skill`:

  ```bash
  glass roll <skill-name> <attribute> --risk <level> --character <id> --save-skill
  ```

- `--save-skill` declares the skill at `fool` before the roll if a slot is
  available. If the cap is full, the command errors; roll without
  `--save-skill` to keep the check improvised.
- To declare without rolling, use
  `glass character skill-declare <character-id> <skill-name>`.

Successful rolls grow the declared skill: `advance` grants +1 skill xp,
`breakthrough` grants +2. Auto-promotion thresholds are 5 / 15 / 30 xp
(`apprentice` / `artisan` / `virtuoso`). Do not use notes or prose to
fabricate skill promotions; let the roll path do it.

## Authority

Players can mutate their own character state. The DM can mutate any character
state while adjudicating the world.
