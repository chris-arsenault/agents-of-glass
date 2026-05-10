---
title: Character Creation Rules
target: player-dm
authority: rules
---

# Character Creation Rules

## Species

Pick one species from `shared/lore/species/`. Species effects are narrative,
not numerical. There is no orc strength bonus or gnome attunement bonus.

Read the species page and play its texture.

## Culture

Culture is independent of species. Names follow culture, not species. Use
`shared/lore/cultures/` and the naming conventions.

## Class / Role

There is no class system. Invent what the character does in the world: Tuner,
dock-runner, archivist, route-walker, hab medic, fixer, witness, or another
world-grounded role.

The archetype field is descriptive, not categorical.

The character row also has a separate **organization role** field. This is what
the PC does for the party's organization: route contact, field medic,
resonance reader, quartermaster, witness handler, fixer, or another concrete
function. It can overlap with archetype, but it answers a different question:
"why does this organization keep this person on the team?"

## Canonical Identity

Character creation records these canonical fields in Postgres:

- `species` / `race` — use the setting's species terminology.
- `culture` — naming, social habits, and upbringing; independent of species.
- `archetype` — a short descriptive concept, not a class.
- `organization_role` — what the PC does for the party's organization.
- `bio` — concise but non-empty public identity summary.
- `goals` — 2-3 personal, professional, relational, organizational, or
  value-driven goals.

Goals may touch campaign material, but they should not read like a solved
mystery board. A good goal says what the character wants and what pressure
makes it hard.

## Attributes

Seven attributes: `vitality`, `finesse`, `focus`, `resolve`, `attunement`,
`ingenuity`, `presence`.

Starting budget:

- all seven default to `standard`
- bump two to `advanced`
- optionally bump one to `superior`
- optionally drop one to `rudimentary` as a flaw

`transcendent` is plot-only.

## Skills

Skills are arbitrary strings. There is no skill list.

Starting budget:

- one `virtuoso`
- two `artisan`
- two `apprentice`

Unlisted skills default to `fool`.

Skill names should be specific, world-grounded, and broad enough to matter
without becoming universal.

## HP

Starting HP defaults to 10. Take 8 for a fragile or specialized character. Take
12 when physical robustness is a defining trait.

## Inventory

Pick 3-5 items. One must be a signature item with a specific story. Items are
descriptive, not stat blocks.

## Signature Move

Start with **one** simple signature move at level 1. It should be a recurring
habit, technique, spell, search pattern, or social tactic the table can
recognize. It is not a guaranteed power or a locked mechanical action.

Signature move slots grow with level:

- Level 1: 1 slot.
- Levels 3, 5, 7, and 9: +1 slot each, for 5 total slots by level 9.

Later moves can be broader, stranger, or more consequential in the fiction.
Early moves should be simple and legible.

## Tags

Pick 2-4 short labels that capture demographic or role facts: species, culture,
profession, hab of origin, or similar search keys.
