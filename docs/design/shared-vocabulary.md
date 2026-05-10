# Shared Terms

This design note is retained for history. The old single shared-terms
runtime surface has been retired in favor of the intentional instruction
surface described in [`instruction-surface.md`](instruction-surface.md).

The concerns that used to live here now have separate homes:

- Message-bus types live in `templates/instructions/message-bus.md` and are
  copied into each campaign as `instructions/message-bus.md`. The CLI validates
  `glass msg <type>` against the explicit type headings in that file.
- Public game terms live in the SRD, especially `templates/srd/glossary.md`.
- Optional table technique and examples live in `templates/how-to/`.
- In-fiction names, places, factions, and concepts live in `shared/lore/` or
  the table's immediate markdown files.

The rule is still the same: codify only the small pieces that need machine
agreement, and leave the rest as readable prose. The reorg makes the target
persona explicit instead of mixing agent instructions, table rules, examples,
and lore in one bucket.
