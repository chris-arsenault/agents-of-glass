# Creative Influences

Creative influences are actual-play anti-degeneracy nudges. They exist to push
agents away from stale phrasing and overfamiliar choices without becoming
mechanics.

They are only injected during play modes. Non-play bootstrap and prep modes
such as campaign planning, character creation, the prelude coordinator, arc
creation, and scene prep do not use them. Prelude `scene-play` and `action`
child modes do use them because the characters are actually on screen.

## The Four Active Influences

During an actual-play turn, an agent is shaped by four things:

- persona: who the table actor is
- character sheet: who the character is and what hard state says
- tarot: a persisted multi-turn mood or ethos
- verse phrase: a one-turn literary phrase used as a small creative bump

Persona, character sheet, table state, rolls, and rules always outrank tarot
and verse. Tarot and verse are texture, attention, rhythm, and interpretation.
They do not grant permissions, impose mechanics, or override the fiction.

## Verse Phrase

Each TURN_START in actual play includes a short phrase pulled from a small
public-domain literary corpus: KJV Bible, Shakespeare, Legge-era Chinese
classics, and other public-domain sources.

Initial source anchors:

- [King James Bible, Project Gutenberg](https://m.gutenberg.org/files/7999/7999-h/7999-h.htm)
- [Complete Works of William Shakespeare, Project Gutenberg](https://www.gutenberg.org/ebooks/100)
- [The Analects of Confucius, Project Gutenberg](https://www.gutenberg.org/ebooks/3330)
- [Bhagavad-Gita, Project Gutenberg](https://www.gutenberg.org/files/2388/2388-h/2388-h.htm)
- [Tao Te Ching translation index, Wikisource](https://en.wikisource.org/wiki/Tao_Te_Ching)
- [The Pictorial Key to the Tarot, Wikimedia Commons](https://commons.wikimedia.org/wiki/File:The_Pictorial_Key_to_the_Tarot.pdf)

The verse phrase is not persisted. It is deterministic per campaign, actor, and
turn number so rerendered turn starts are stable. It is debug context only:
viewers may eventually see it in debug output, but it is not public table state
and should not be quoted or announced unless it naturally belongs in the turn.

The instruction is deliberately vague: let the phrase influence word choice,
attention, risk appetite, or interpretation at the margins.

## Tarot

Tarot is the longer-running creative influence. The default draw lasts 25
global agent turns, which is about five turns for one actor in the normal
five-actor rotation. TURN_START renders it as a compact instruction, for
example:

```markdown
Tarot: you are currently under The Jester (Table Deck). Begin without
over-explaining. Let curiosity and a little risk move before the stale answer
arrives.
```

The tarot text is project-authored archetype language, not copied deck text.
It is stored in Postgres so it can be queried by `glass tarot` and later shown
in viewer UI. Tarot affects how the player or DM approaches a turn; it does
not create a status effect, compel action, or change dice.

## Persistence

Postgres owns tarot because it is ordered, turn-scoped runtime state. The
canonical table is `tarot_influences`.

Markdown does not project tarot yet. The phrase corpus is code/data and is not
state. The graph database is not involved because tarot is not an entity
relationship.

## CLI Surface

```bash
glass tarot current [actor]
glass tarot list [--actor <actor>] [--all]
glass tarot draw <actor> [--turns N]   # DM only
```

The orchestrator normally draws tarot automatically when a play turn has no
active persisted influence. The manual `draw` command is for DM override and
debugging.
