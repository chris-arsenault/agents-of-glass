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
   answers, a non-adjacent pull utilization note, and the starting skill budget:
   exactly two `apprentice` skills and one `artisan` skill.

   ```bash
   glass character new <id> --player <player-id> \
     --primary-drive "<required drive>" \
     --positive-trait "<visible positive/quirky/playful/warm/funny trait>" \
     --table-presence "<recurring social bit another player can use>" \
     --non-work-want "<want unrelated to profit, safety, mission, or job competence>" \
     --opening-social-action "<direct action toward another PC for the intro>" \
     --life-prompt "<prompt>=<concrete behavior answer>" \
     --life-prompt "<prompt>=<concrete behavior answer>" \
     --pull-utilization "Source: <real-world domain/source>; used in <character detail>."
   ```

3. Use `archetype` for class-like identity. Use `organization_role` for current
   membership, status, or responsibility inside the party organization.
4. The character must read as a table-facing person, not only a reserved
   professional. Record a social bit, a non-work want, and an opening action
   toward another PC.
5. The pull utilization note must name the source/domain and where a concrete
   detail appears: skill, trait, inventory item, signature move, backstory detail,
   visible habit, or social behavior.
6. Add starting inventory, consequences, and signature moves with
   `glass character bulk-update --json '<payload>'` or the specific commands.
7. Mirror the result with `glass character mirror <id>` unless the bulk update
   already used `"mirror": true`.
8. Verify the row with `glass character get <id>`.

## Inventory Boundary

Inventory is for carried assets that can affect future action: tools, weapons,
protective gear, consumables, permits, keys, samples, maps, documents, leverage
tokens, specialist instruments, or portable resources. Personal relics belong in
bio, traits, notes, or journal unless they can plausibly affect a future roll,
access, cost, risk, or choice.

Effect tags should name affordances. Prefer tags like `opens dock cabinets`,
`counts as courier authority`, `one use: reduce diffuse return cost`, or
`cuts fouled kite line under load` over tags that only describe mood or origin.

## Mutation Sequence

1. Gather every character mutation required by this turn before writing commands.
2. Use `glass character bulk-update --json '<payload>'` for multiple characters
   or multiple fields.
3. Use a single-purpose command for a single direct mutation:

   ```bash
   glass character set-hp <id> <delta>
   glass character set-momentum <id> <value>
   glass character inventory-add <id> <item-id> [--effect-tag TEXT]
   glass character inventory-rm <id> <item-id>
   glass character signature-add <id> <name> [--look TEXT --use TEXT --tell TEXT]
   glass character consequence-add <id> <label>
   glass character consequence-resolve <id> <consequence-id>
   ```

4. Let roll commands handle roll-induced momentum changes. Do not duplicate
   automatic momentum effects with a second character mutation.
5. Use inventory commands when a meaningful portable asset is taken, spent,
   received, broken, or kept for later leverage.
6. Mirror public character displays after visible sheet changes.
7. Name the changed character ids and fields in `glass turn end --state`.

## Bulk Payload Shape

`bulk-update` accepts JSON shaped like:

```json
{
  "characters": [
    {
      "character_id": "vel",
      "inventory_add": [
        {"id": "route-seal", "qty": 1, "effect_tags": ["passes casual review"]}
      ],
      "signature_moves": [
        {
          "name": "Quiet Door",
          "look": "Vel touches the latch like checking a pulse.",
          "use": "Entering a place where asking would fail.",
          "tell": "Leaves wax dust on the thumb."
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
budget (2 `apprentice` + 1 `artisan`).

To put a new skill on the sheet during play:

- **On a roll**: pass a fresh skill name to `glass roll` or `glass scene
  pressure`. If a free slot exists, the CLI auto-declares the skill at `fool`
  and proceeds with the roll. The roll output reports
  `skill_auto_declared: true` and an event is queued for the transcript. If
  the cap is full, the command errors — pick an existing skill or wait for
  the next level.
- **Without a roll** (e.g., intermission training):

  ```bash
  glass character skill-declare <character-id> <skill-name>
  ```

  Errors if the cap is full or the skill is already declared. The new skill
  starts at `fool` with 0 skill xp.

Successful rolls grow the declared skill: `advance` grants +1 skill xp,
`breakthrough` grants +2. Auto-promotion thresholds are 5 / 15 / 30 xp
(`apprentice` / `artisan` / `virtuoso`). Do not use notes or prose to
fabricate skill promotions; let the roll path do it.

## Authority

Players can mutate their own character state. The DM can mutate any character
state while adjudicating the world.
