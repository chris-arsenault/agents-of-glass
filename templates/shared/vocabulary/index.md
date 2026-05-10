---
title: Shared Vocabulary
---

# Shared Vocabulary

The agents' shared dialect. Read this for terms that recur in turns and in the
messaging system. **Reference, not validation** — except where noted.

## Files

- [`turn-verbs.md`](turn-verbs.md) — `action`, `inquiry`, `possibility`, `planning`, `reflection`, `prepare`, `address`. Words you can use in turn prose to flag what kind of turn this is.
- [`message-types.md`](message-types.md) — `table-talk`, `banter`, `instruction`, `plot-hint`, `secret`. The types accepted by `glass msg <type>`. **CLI-validated** — unknown types are rejected.
- [`mechanical-terms.md`](mechanical-terms.md) — `check`, `risk level`, `outcome tier`, `pressure target`, `durable clock`, `resistance`, `impact die`, `attribute`, `skill`, `tier`, `momentum`, `signature move`, `effect tag`, `consequence`, plus world-mechanical terms (resonance, ringglass, band, bandwidth, attunement, Tuner).

## Conventions

- **Reference, not validation.** Except `message-types.md` — typed messages are the indexable signal, so the CLI validates them.
- **Build entries as the need shows up.** This vocabulary is intentionally small. Resist adding generic two-word entries.
- **Skills and actions stay free-form.** Any string works as a skill name, and
  players describe actions in prose. We do not maintain a canonical list of
  action verbs.
- **Specificity over generic.** Vocabulary entries should land in *this world*,
  not in a generic-fantasy template.

## Adding to the vocabulary

A new entry earns its way in when:

- We see agents struggling to communicate without it
- A class of action recurs and gets named differently each time, and the corpus would be cleaner with one name
- A new world-mechanical concept becomes load-bearing in actual sessions

Add the entry to the relevant file. Keep the entry shape consistent: name, one or two lines, one example sentence. No essays. Update this index if a new file appears.

This index file is read into every agent's TURN_START. The detail files are read on demand.
