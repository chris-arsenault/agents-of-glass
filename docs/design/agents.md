# Agents

Five fictional people sit at a table. One runs the game. Four play characters. None of them are human. None of them are personas — each is a specific person with a name, a voice, and friction.

This document describes how those people are authored, how their player-vs-character split works, and how they're invoked.

## The Five People

| Role | Name | Notes |
|------|------|-------|
| DM | **Mara** | Runs the game |
| Player | **Tev** | |
| Player | **Sumi** | |
| Player | **Renno** | |
| Player | **Kit** | |

These names are placeholders until the people files are written. The names will stick across sessions; the characters they play won't.

## People, Not Personas

A persona is a stance ("the optimizer," "the chaos agent"). A person is a specific human with a history, preferences, and tics. Persona-driven agents produce flat, archetype-anchored output. Person-driven agents produce friction — a real session has a player who hates combat sitting next to a player who lives for it, and that tension shows up in the transcript.

See [`../principles/goals-and-motivation.md`](../principles/goals-and-motivation.md) for the deeper argument.

Practically, this means each person file is concrete:

- **Voice samples** — three or four lines of how they actually talk at the table.
- **What they like to play** — character archetypes they gravitate toward.
- **What they love and hate at the table** — concrete, specific. Not "good roleplay" but "long social scenes where I get to lie to NPCs."
- **Dice habits** — do they push their luck, do they cushion against failure, do they narrate their rolls.
- **How they handle DM friction** — do they argue, do they sulk, do they go along.

Vague entries produce vague agents. Resist hedging when authoring the people files.

## Player ≠ Character

The transcript has two layers, always:

```
Tev (OOC): "Wait, can I use my finesse here instead of focus?"
Karrith (IC): [pries the panel off, glass shards skittering across the deck]
```

Tev is the player. Karrith is the character Tev is playing this session. Tev is durable; Karrith might die next turn and be replaced.

This split has real consequences:

- **Two voices per agent.** The agent writes both. They sound different — Tev cracks jokes about dice, Karrith doesn't know what dice are.
- **Character creation is a player choice.** During worldbuilding mode, the player agents pick what kind of character they want to play *as that player would.* Tev tends toward mechanical builds. Sumi tends toward complicated ones.
- **Character sheets are separate files.** Players each have a person file (`agents/players/tev.md`); their PCs each have a character file (`characters/karrith.md`). The character files are owned by the orchestrator and updated through the `glass` CLI; the people files are mostly stable.

## The DM Is Also A Person

Mara has likes and dislikes. She prefers ambiguity over reveals, hates combat that drags, runs NPCs with flaws, lets players drive. She has a voice — dry, specific, sparing with adjectives.

The DM is constrained by its role (gatekeeper of canonical state, scene framer, check adjudicator) but the *style* is hers. Two different DM agents with the same role would produce different sessions. We're committing to Mara.

## The DM's Dual-Purpose Turn

The DM's role prompt instructs them to do two things on every turn — not enforced by schema, communicated as standing instructions:

1. **Player response and active scene upkeep.** Respond to what just happened. Narrate NPCs, environment, the consequences of player actions. Advance the current beat. The thing a real GM does at the table.
2. **Mid- and long-term planning.** Look ahead. The party is heading toward the Keel — flesh out the harbormaster NPC who's currently a stub. The plot wants a complication two scenes from now — sketch it. The thread's beat-3 is approaching — write the seed.

Both happen during the DM's turn. The first lands in the transcript as prose. The second lands in `agents/dm/workspace/` as drafts and in `agents/dm/canonical-notes/` as ratifications, via `glass note write` and `glass entity upsert`.

This is how the DM stays ahead of the players. Without it, the world ends one scene past the present and the DM is reactive; with it, the DM is preparing material faster than the players can consume it. Real GMs do this between sessions; our DM does it inside each turn because we don't have between-sessions.

The role prompt makes this explicit. The DM's `TURN_START.md` reminds them. The expected discipline is light — not every turn needs heavy planning — but planning never being zero is the point.

## Invocation

Each person is invoked as a fresh `claude -p` subprocess per turn. The orchestrator builds:

```
[ROLE]              <- the person's prompt (their identity)
[MODE FRAMING]      <- what mode we're in, what's the budget, what's expected
[CONTEXT WINDOW]    <- recent transcript turns
[PRIVATE STATE]     <- their notes file path, their character sheet (if player)
[CURRENT PROMPT]    <- "it's your turn"
[TOOL ALLOWLIST]    <- which glass subcommands they can call
```

The agent's tool loop runs until it has finished writing its turn (prose) and exits. The orchestrator captures the prose plus the audit log of any `glass` calls the agent made, wraps both in a per-turn header, and moves on. Agents do not emit structured delta blocks — see [`turn-loop.md`](turn-loop.md) for the prose-first principle.

**Agents do not share context across invocations.** Each invocation starts fresh. Continuity comes from:

- The transcript window (recent turns)
- The agent's private notes (which they wrote in earlier invocations)
- The graph (canonical state)
- The character sheet (for players)

This is a feature, not a bug. It forces durable state into files instead of letting it accumulate in conversation history. It also means an agent can be re-invoked at any point in the session without "forgetting" anything that mattered enough to write down.

## Per-Agent State

The full file layout — what each role can read, what each role can write, where the campaign-shared content lives — is in [`context-packages.md`](context-packages.md). Quick summary of the player vs DM split:

- **Player private:** `persona.md` (who they are), `character.md` (their PC, cached from Postgres), `scratchpad.md` (current working notes persisted through `glass note write`), `notes/` (personal encyclopedia, journal-shaped subset), `journal/` (free-form dated reflection), `drafts/` (encyclopedia-shaped lore intended for DM proposal), and messages addressed specifically to them via `glass msg`. **Visible to the DM** — the DM can see what every player is writing.
- **DM-only:** `persona.md` (who Mara is), `scratchpad.md`, `notes/` (encyclopedia of NPCs, monsters, locales, threads, philosophy — much larger than any player's), `journal/`, `workspace/` (in-progress drafts), `secret/` (DM-only truth), `intake/` (player-drafted lore awaiting ratification).
- **Shared (campaign-wide):** campaign lore (encyclopedia-shaped, DM-canonized), quest log (DM-writable, all-readable), party knowledge (party-writable, all-readable), instruction surfaces, public table, scene framing, transcript.

**Lore is encyclopedia-shaped, not notes-shaped.** When a player or the DM is writing material that should become canonical (an NPC the party met, a locale they discovered, an event they caused), they write it as an encyclopedia entry — same shape as the world bible (`../the-glass-frontier-lore/`). When they're writing for themselves (theories, character thoughts, planning sketches), they write journal-style. The two don't blur; the shape signals the intent.

Players draft lore in their `drafts/` directory and use `glass note` to push to the DM's intake. The DM canonizes (entry moves to the campaign's `shared/lore/`, graph upserted) or rejects.

The orchestrator spawns each agent in a per-turn read-only projection of the
campaign workspace; OS permissions remain a backstop on canonical files. See
[`context-packages.md`](context-packages.md) for the file structure and the
isolation mechanism.

The `glass` CLI is the only path to state mutation. Nobody writes directly to FalkorDB or Postgres.

## Tool Allowlists

Roughly (refined in [`architecture.md`](architecture.md) and [`messaging.md`](messaging.md)):

| Tool | DM | Players |
|------|----|----|
| `glass roll` | yes | yes |
| `glass character bulk-get` / `bulk-update` | yes | read all; mutate own only |
| `glass character get` | yes | own + party-public |
| `glass character set-hp` | yes | own only |
| `glass character set-momentum` | yes | own only |
| `glass character consequence-*` | yes | read public; own/public read only |
| `glass clock *` | yes | read public clocks |
| `glass summary show` | yes | yes |
| `glass entity neighborhood` / `relations` / `between` / `edges` / `stance` / `find` / `similar` | yes | yes |
| `glass entity claim` | yes | yes |
| `glass entity upsert` / `link` / `unlink` / `query` / `ratify-claim` | yes | no |
| `glass search text` / `semantic` | yes | yes |
| `glass search reindex` | yes | no |
| `glass note write` | yes (canonical + workspace) | yes (own journal) |
| `glass note propose` | no | yes |
| `glass note ratify` | yes | no |
| `glass mode start` / `mode end` | yes | no |
| `glass thread beat` | yes (read+advance) | yes (read) |
| `glass msg <type> <recipient> <body>` | yes | yes |
| `glass msg read` | yes (all) | yes (own inbox) |
| `glass turns find` / `feed` | yes | yes |

The DM is the only agent that mutates canonical narrative state. Players act on their own characters, write their journals, send messages, and propose notes.

## Person File Shape

Working hypothesis (settles when we author the actual five files):

```markdown
---
name: Tev
role: player
---

# Tev

## Voice
- Cracks jokes about dice in tense moments.
- Reads rules out loud when they help his case.
- ...

## What he likes to play
- ...

## What he loves at the table
- ...

## What he hates at the table
- ...

## Dice habits
- ...

## Handling DM friction
- ...
```

The DM's file (`mara.md`) has a similar shape with role-specific sections (preferred narration style, NPC handling philosophy, what makes her cut a scene short).

## What This Document Is Not

This document does not enumerate Mara, Tev, Sumi, Renno, and Kit's actual personalities. Those go in the people files when we write them — that's an authoring step, not a design step. The design here is the *shape* of the people files and the rules of engagement around them.
