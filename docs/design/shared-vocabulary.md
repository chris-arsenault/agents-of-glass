# Shared Vocabulary

A controlled-vocabulary reference the agents share for clarity and analysis. *Vocabulary, not validation.*

The DM and players use these terms in their prose to flag what they're doing — "I'll spend this turn on an inquiry" — so the table has a common dialect. The orchestrator does not parse turn prose for these terms. They are not enforced. They exist because consistent terminology produces:

- Clearer communication between agents (less ambiguity in prose)
- Cleaner corpus analysis (terms cluster meaningfully)
- A shared reference that role prompts and people files can point at instead of re-explaining

This doc describes the *theory*. The actual vocabulary lives at runtime under `campaigns/<id>/shared/vocabulary/` and gets built up over time.

## Layout

Same TOC + supporting-files pattern used in the lore repo:

```
campaigns/<id>/shared/vocabulary/
  index.md                  # TOC — all terms, brief entries, links to detail
  turn-verbs.md             # what kinds of turns players take
  combat-moves.md           # attack, prepare, hold, retreat, etc.
  social-moves.md           # negotiate, intimidate, persuade, etc.
  message-types.md          # the schema for `glass msg <type>`
  mechanical-terms.md       # advantage, push, momentum, attunement, ...
```

`index.md` is the always-on file — included in the agent's context every turn (via [`context-packages.md`](context-packages.md)). Detail files are read on demand when an agent wants to refresh on a specific term.

## What's In and What's Not

**In:** verbs and concepts that recur across many turns and benefit from being said the same way.

**Not in:** **skills.** The skill system stays free-form (cribbed from Glass Frontier). A character can have a skill called anything; skill *tier* modifiers are codified, but skill *names* are author-chosen prose. Don't pre-enumerate.

**Not in:** the Glass Frontier intent set verbatim. Several entries (`clarification`, `wrap`) are 1:1-AI-engine specific and don't translate to a five-person table. Trim and rename as the actual usage shows what matters. Likely starting set:

- `action` — doing a thing in the world
- `inquiry` — asking the DM about the world
- `possibility` — exploring options before committing
- `planning` — coordinating with the party
- `reflection` — in-character thought
- `prepare` — declaring a preparatory ability for later
- `address` — directing speech at another player or NPC

We'll iterate. The point is that the words exist for the agents to grab; the orchestrator never enforces them.

## Building It Up

Add to vocabulary as the need shows up in real sessions, not in advance. A new term goes in when:

- We see agents struggling to communicate without it
- A class of action recurs and gets named differently each time
- The corpus would be more analyzable with a consistent term

Don't pre-populate from imagination. Vocabulary that's never used is clutter.

## The One Validated Subset

Most vocabulary is reference-only. The exception: `glass msg <type> ...` validates `<type>` against `message-types.md`, because typed messages are the indexable signal that matters most for cross-agent analysis. See [`messaging.md`](messaging.md) for the message-bus details.

## Cross-References

- The DM's role prompt references vocabulary for narration consistency.
- Player role prompts reference it for turn-shape clarity.
- [`turn-loop.md`](turn-loop.md) explains why we use vocabulary instead of a parsed enum.
- [`../principles/codify-only-what-drifts.md`](../principles/codify-only-what-drifts.md) is the principle this doc operationalizes — vocabulary is the *prose* counterpart to schema enforcement.
