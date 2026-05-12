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

## Archetype And Organization Role

There is no fixed class list, but every character still has a class-like
**archetype**. The archetype is the broad adventuring identity other people
could understand at a glance: Tuner, wright, scout, archivist, examiner,
drop-pilot, medic, courier, negotiator, warrior, fixer, witness, route-walker,
or another world-grounded type.

The archetype should be portable. It should not include the party
organization's name, the character's whole backstory, or their current rank in
the group. "Document examiner" is an archetype. "Ex-Conclave intake clerk on
the Ledger Run" is backstory. "Warrior" can be an archetype even if the
character's job inside the organization is cook.

The character row also has a separate **organization role** field. This is how
the PC belongs to the party's organization: founder, long-time member,
probationary hire, high-status officer, hanger-on, cook, quartermaster,
route contact, witness handler, crew lead, family legacy, outsider specialist,
or another social/operational place in the group.

Organization role is intentionally orthogonal to archetype. It can name status,
trust, history, social position, or day-to-day responsibility. It should not
just repeat the archetype unless that overlap is the point.

## Canonical Identity

Character creation records these canonical fields in Postgres:

- `species` / `race` — use the setting's species terminology.
- `culture` — naming, social habits, and upbringing; independent of species.
- `archetype` — a short class-like identity, broad and portable.
- `organization_role` — the PC's membership, status, or responsibility inside
  the party's organization; orthogonal to archetype.
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

- one `artisan`
- two `apprentice`

Unlisted skills default to `fool`.

Skill names should be specific, world-grounded, and broad enough to matter
without becoming universal.

Characters can declare additional skills during play, up to a cap of
`3 + character_level` declared skills total (4 at level 1, 5 at level 2,
etc.). New declarations start at `fool` and grow by use. See
[`skill-advancement.md`](skill-advancement.md).

## HP

Starting HP defaults to 10. Take 8 for a fragile or specialized character. Take
12 when physical robustness is a defining trait.

## Inventory

Pick 3-5 items. One must be a signature item with a specific story. Items are
descriptive, not stat blocks.

At least one item should be useful under pressure: a favored weapon, instrument,
special apparatus, field tool, restraint, protective rig, leverage token, or
other thing the character would plausibly reach for during play. Keepsakes and
relics are welcome, but the whole inventory should not be keepsakes.

## Signature Move

Start with **one** simple signature move at level 1. It should be something the
character can actively do under pressure: a technique, spell, maneuver, search
pattern, social tactic, chase trick, ritual, or other repeatable move the table
can recognize. It is not a guaranteed power or a locked mechanical action.

Spell-like moves are valid. In the Glass Frontier, "magic" usually means
resonance: harmonic force, sound, vibration, ringglass response, signal,
memory, pressure, and pattern. A move can be a named resonance spell or
technique, but it still works through the normal fiction and roll flow.

A signature move is not just a trait, tic, or possession. "Walks around the
ship" is a habit; "Ground the rig by checking three load points before forcing
a dangerous launch" is a move.

Signature move slots grow with level:

- Level 1: 1 slot.
- Levels 3, 5, 7, and 9: +1 slot each, for 5 total slots by level 9.

Later moves can be broader, stranger, or more consequential in the fiction.
Early moves should be simple and legible. As a rough D&D power-scale analogy,
the level-1 move is cantrip or 1st-level in scope; later slots can feel more
like higher-level spell permissions, with the fifth slot near level 9-10
allowed to be much more dramatic. This is not a spell slot system.

## Tags

Pick 2-4 short labels that capture demographic or role facts: species, culture,
profession, hab of origin, or similar search keys.
