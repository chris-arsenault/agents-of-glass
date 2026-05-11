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
glass character bulk-get <id>... [--all]
glass character bulk-update --json '<payload>'  # or --from scratch/update.json
glass character new <id> --player <player-id> ...
glass character get <id>
glass character mirror <id>
glass character set-hp <id> <delta>
glass character set-momentum <id> <value>
glass character inventory-add <id> <item-id> [--effect-tag TEXT]
glass character inventory-rm <id> <item-id>
glass character signature-status <id>
glass character signature-add <id> <name> [--look TEXT --use TEXT --tell TEXT]
glass character consequence-add <id> <label>
glass character consequence-list <id>
glass character consequence-resolve <id> <consequence-id>
```

Roll-induced momentum changes are automatic. Inventory effect tags are free
text reminders, not rules the CLI interprets.

Prefer `bulk-get` and `bulk-update` when you need multiple character facts or
multiple mutations in one turn. The single-purpose commands remain convenience
wrappers, but repeated one-field calls are slower and create needless
agent/tool back-and-forth.

During character creation, `glass character new` requires canonical species,
culture, archetype, organization role, bio, 2-3 goals, and the starting skill
budget: exactly two `apprentice` skills and one `artisan` skill. `glass
character mirror` writes the consistent public
`players/<id>/public/character.md` display from Postgres; do not hand-maintain
that mirror.

Use `archetype` for the broad class-like identity and `organization_role` for
the PC's orthogonal membership, status, or responsibility inside the party
organization. Do not collapse backstory, old job, current org membership, and
class identity into one field.

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
is checked by `glass character signature-status` and `glass character
signature-add`. Level 1 has one slot; levels 3, 5, 7, and 9 each add one slot.
They should be active pressure-ready moves, not traits, tics, possessions, or
backstory facts. Do not use `glass note write` to bypass signature move slot
limits.

Players may write their own character-adjacent prose and mutate their own
character state. The DM can mutate any character state when adjudicating the
world.
