---
title: Kit's Notes
status: stub
---

# Kit's Notes

Personal reference encyclopedia. **One file per topic.**

## How to use this directory

This is your private encyclopedia — things you want to remember in structured form. NPCs you've met, locations you've been, theories you're working on, character backstory deeper than your sheet, anything you want to refer back to in your own words.

### Format

Lightweight encyclopedia entries — frontmatter + sections. One file per topic.

```markdown
---
title: Patrol Leader at the Ringglass Market
type: npc        # or location, faction, theory, observation, ...
---

# Patrol Leader at the Ringglass Market

[A few paragraphs of what you know — observed details, context, what they want, where they showed up. Specific. No generic-fantasy framing.]

[Cross-link to other notes with relative links: see [the corruption theory](theory-corruption-residue.md).]
```

### Conventions

- **One file per topic.** Don't accumulate a single mega-file.
- **Encyclopedia-shaped, not journal-shaped.** Journal entries (chronological reflection, "today the party did X") go in `../journal/`. Current working notes go in `../scratchpad.md`. This directory is for *reference material* you maintain.
- **Link freely.** Markdown relative links between files are encouraged. Future-you and the analysis pipeline both benefit.
- **Subdirectories** are fine when a topic has obvious children (`npcs/`, `locations/`, `theories/`).
- **Update, don't append.** When your understanding of something changes, update the relevant entry. The note is the *current state* of your knowledge, not a log.
- **Specificity always.** Per [`/docs/principles/resist-generic-drift.md`](../../../../docs/principles/resist-generic-drift.md), every entry should be defensible against the world's actual texture. No "the tavern," no "the wizard," no "Thorgrim."

### Proposing a note to the DM

If a note here is something you think should become campaign canon (an NPC the whole party recognizes, a location the campaign should remember), call:

```
glass note propose <path-to-this-file>
```

The DM will read it, ratify (canonize into shared lore) or reject. Either way, your local copy stays.

### Difference from `drafts/`

- `notes/` — your personal encyclopedia. Yours, for your reference. May or may not ever be proposed.
- `../drafts/` — encyclopedia entries you are *intentionally writing for proposal*. The shape is the same; the intent differs.

Use `notes/` by default. Move into `drafts/` when you're polishing a specific entry for the DM.

### Visibility

Your notes are private from other players. **The DM can read them** — that's part of the table arbitration role. Don't write things here you would not want the DM to know.
