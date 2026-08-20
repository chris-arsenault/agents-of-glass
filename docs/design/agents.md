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
- **Character state is separate from table persona.** Players each have durable persona reference, while their PCs live in character records updated through the `glass` CLI. The player voice and the character voice are distinct, but neither is maintained by file edits during an agent turn.

## The DM Is Also A Person

Mara has likes and dislikes. She prefers ambiguity over reveals, hates combat that drags, runs NPCs with flaws, lets players drive. She has a voice — dry, specific, sparing with adjectives.

The DM is constrained by its role (gatekeeper of canonical state, scene framer, check adjudicator) but the *style* is hers. Two different DM agents with the same role would produce different sessions. We're committing to Mara.

## The DM's Dual-Purpose Turn

The DM's role prompt instructs them to do two things on every turn — not enforced by schema, communicated as standing instructions:

1. **Player response and active scene upkeep.** Respond to what just happened. Narrate NPCs, environment, the consequences of player actions. Advance the current beat. The thing a real GM does at the table.
2. **Mid- and long-term planning.** Look ahead. The party is heading toward the Keel — flesh out the harbormaster NPC who's currently a stub. The plot wants a complication two scenes from now — sketch it. The thread's beat-3 is approaching — write the seed.

Both happen during the DM's turn. The first lands in the public turn feed as prose through `glass turn append --body`. The second lands in neutral facts or hard state through `glass` commands. If a future agent must rely on it, Mara records it with `glass fact set` or `glass done --fact`; she does not maintain a parallel file surface during the turn.

This is how the DM stays ahead of the players. Without it, the world ends one scene past the present and the DM is reactive; with it, the DM is preparing material faster than the players can consume it. Real GMs do this between sessions; our DM does it inside each turn because we don't have between-sessions.

The injected prompt makes this explicit. The expected discipline is light - not every turn needs heavy planning - but planning never being zero is the point.

## Invocation

Each person is invoked as a separate `claude -p` subprocess per turn. The
orchestrator may track one Claude Code session id per actor, but remembered
provider context is never canonical. Current state comes from the injected
prompt and `glass`.

The orchestrator builds one injected prompt:

```
[ROLE]              <- the person's prompt (their identity)
[MODE FRAMING]      <- what mode we're in, what's the budget, what's expected
[CONTEXT WINDOW]    <- neutral facts, recent committed turns, messages, hard state
[PRIVATE STATE]     <- role-authorized facts and character state
[CURRENT PROMPT]    <- "it's your turn"
[TOOL ALLOWLIST]    <- which glass subcommands they can call
```

The agent's tool loop runs until it has closed with `glass done` and submitted public prose with `glass turn append --body`. The orchestrator verifies the committed turn row and moves on. Agents do not emit structured delta blocks - see [`turn-loop.md`](turn-loop.md) for the prose-first principle.

**Agents do not share canonical context with each other.** Provider session
history may help an actor sound continuous, but durable continuity comes from:

- continuity facts
- embedded hard state and turn rows
- bounded CLI recall over committed prose
- character records for players

Claude Code session history is optional short-term actor continuity, not
canonical campaign state. An agent should still be re-invokable from the prompt
and `glass` command output.

## Per-Agent State

The runtime state layout is in [`context-packages.md`](context-packages.md). Quick summary of the player vs DM split:

- **Player-private visibility:** character state, player-addressed messages, and any role-authorized facts exposed by `glass`.
- **DM visibility:** DM-authorized facts, messages, scene/mode control state, and the hard-state surfaces needed to adjudicate play.
- **Shared visibility:** committed public turns, public facts, public hard state, and the reference instructions/methodologies/rules.

Operator-curated lore can still be encyclopedia-shaped outside live turns, but
agents do not author lore files as part of the runtime contract. If a piece of
lore matters to the next turn, encode the neutral fact through `glass`.

The `glass` CLI is the only path to state mutation. Nobody writes directly to
SQLite, local APIs, or campaign files during agent turns.

## Tool Allowlists

Roughly (refined in [`architecture.md`](architecture.md) and [`messaging.md`](messaging.md)):

| Tool | DM | Players |
|------|----|----|
| `glass roll` | yes | yes |
| `glass character bulk-get` / `bulk-update` | yes | read all; mutate own only |
| `glass character get` | yes | own + party-public |
| `glass character set-hp` | yes | own only |
| `glass character set-momentum` | yes | own only |
| `glass character consequence-*` | yes | add/resolve own public; read public |
| `glass clock *` | yes | read public clocks |
| `glass fact pack` | yes | yes |
| `glass fact set` / `glass done --fact` | yes | yes, within allowed scope |
| `glass search text` / `semantic` | yes | yes |
| `glass search reindex` | yes | no |
| `glass mode start` / `mode end` | yes | no |
| `glass thread beat` | yes (read+advance) | yes (read) |
| `glass msg <type> <recipient> <body>` | yes | yes |
| `glass msg read` | yes (all) | yes (own inbox) |
| `glass turns find` / `feed` | yes | yes |
| `glass done` | yes | yes |
| `glass turn append --body` | yes | yes |

The DM has broader authority over scene and world state. Players act on their
own characters, send messages, and record scoped facts when their turn creates
durable continuity.

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
