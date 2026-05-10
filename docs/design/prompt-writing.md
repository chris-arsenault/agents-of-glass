# Prompt Writing Guidance

Runtime prompts should make agents inhabit the correct table role. Do not make
them reason from a detached file inventory when the prompt can state the active
identity directly.

## Persona Stack

Agents of Glass has four layers that must stay distinct:

- **Executing agent:** the subprocess invoked for one turn. It follows
  `TURN_START.md`, `instructions/`, and `methodologies/`.
- **Table person:** Mara, Tev, Sumi, Renno, or Kit. This is the player or DM
  personality the model should embody at the table.
- **Character:** the in-fiction PC a player controls. The character has limited
  knowledge and acts inside the world.
- **World state:** table, scene, transcript, lore, graph, rolls, clocks, and
  Postgres-backed hard state.

The prompt should tell the model which layer is active before listing files.

## Required Runtime Pattern

Start every full `TURN_START.md` with an identity paragraph.

For the DM:

```markdown
You are Mara, the DM for a Glass Frontier TTRPG campaign. Run the table as this
person: use the voice, tastes, pacing, and table habits in `dm/persona.md`. You
keep your attention on the table, the scene, and the players' choices.
```

For a player:

```markdown
You are Tev, a player in a Glass Frontier TTRPG session. Act as this player at
the table, using the personality, voice, tastes, and habits in
`players/tev/persona.md`. You are playing the character summarized in your
player workspace. Make choices as the player, and when you speak or act in
fiction, embody only what the character knows and can do.
```

Then list the mode, scene, output contract, message bus, table, context, recent
turns, methodology, and tools.

## Wording Rules

- Use "You are..." for the active table person.
- Use "You are playing..." for the player-to-character bridge.
- Use "Run the table as..." for the DM-to-table bridge.
- Prefer "use the personality/voice/tastes/habits in..." over "here is a
  persona file."
- Keep persona language subordinate to rules, table state, rolls, and output
  contract.
- Put operator, inspection, shakedown, evaluation, and implementation language
  only in operator/coder-facing docs.
- If a method is a bootstrap or validation tool for the human operator, phrase
  the runtime job in table terms: first incident, first mission, time jump,
  party consequence, scene wrap.

## Bad And Better

Bad:

```markdown
Your persona is at `players/tev/persona.md`.
```

Better:

```markdown
You are Tev, a player in a Glass Frontier TTRPG session. Use
`players/tev/persona.md` as your personality, voice, table habits, and tastes.
```

Bad:

```markdown
Run a short inspectable shakedown so the operator can decide whether to keep the
campaign.
```

Better:

```markdown
Run a short first incident: one normal scene, one action scene, then a time jump
into the main campaign.
```

## Proposed Follow-Up Pass

1. Audit generated `TURN_START.md` output from one DM and one player turn after
   bootstrap.
2. Replace remaining runtime-facing "see file" language with embodied identity
   language where it appears in methodologies or instructions.
3. Keep design docs explicit about operator/coder intent, but prevent those
   phrases from being copied into `templates/methodologies/`, `templates/srd/`,
   `templates/how-to/`, or generated turn prompts.
4. Add a small prompt lint check for runtime templates that flags
   `operator`, `inspection`, `shakedown`, and `persona file` unless the file is
   documented as coder/operator-facing.
