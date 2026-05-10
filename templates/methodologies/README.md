# Methodologies

The ordered workflow documents the executing agents read to know *how* a phase
or mode runs.

These get copied into each campaign at creation as `campaigns/<name>/methodologies/`, frozen against the campaign so editing the template here doesn't retroactively change a running campaign.

## The methodologies

Three nested levels of DM prep, plus character creation:

- **[`campaign-planning.md`](campaign-planning.md)** — the **world** level. Solo DM authoring during the `campaign_planning` phase. Outputs: the Question, the Scarcity, factions, NPCs (with antagonist flags), recurring creatures, named things (artifacts/ships/relics), locations, secrets, hooks, philosophy, the opening arc(s). The principle: **prep situations, not plots**. Authored.
- **[`arc-creation.md`](arc-creation.md)** — the **multi-scene-pressure** level. Called from campaign-planning to author the opening arc(s), and re-invoked during active play whenever the DM formalizes a new arc. Outputs: stakes question, threats, clocks, possible end-states, nodes, what from the curated lists is in play, arc-specific secrets. **Shape, not script.** Authored.
- **[`scene-prep.md`](scene-prep.md)** — the **single-scene** level. Run before each new scene in active play. Outputs: recap, strong start, 3-5 possible directions, NPCs/antagonists/creatures/named-things in play, secrets that might surface, open questions to be answered through play, and the opening public table state. Closely follows Sly Flourish's *Lazy Dungeon Master*. Authored.
- **[`action-scene.md`](action-scene.md)** — quickfire contested scenes using action order and short in-world time. Combat, chase, and social pressure are toolkit examples, not an exhaustive mode list. Outputs: tight move/action/housekeeping turns, frequent checks without extra handoffs, public trackers/clocks, HP/effect consequences. Drafted.
- **[`character-creation.md`](character-creation.md)** — the `character_creation` phase. DM writes a public campaign-intro; each player authors their character and a public intro entry; DM ratifies. Multi-agent. Stub.

After character creation, the campaign is `active` and scenes begin. The first scene is just the first scene — the DM does scene prep for it like any other.

## What a methodology document is

A methodology is a binding sequence for an invocation: what to read first, what
to produce, what order matters, and what done means.

It is not the whole instruction surface. Mechanical tool behavior lives in
`instructions/`. Public game rules live in `srd/`. Examples and craft advice
live in `how-to/`.

## What goes in one

Working shape (the actual content lands when we co-author):

- **What this phase is for** — one paragraph stating the goal.
- **Agents involved** — DM only? DM + players? Sequential or parallel?
- **What the agent reads first** — pointers to the persona, world bible, prior phases' output.
- **What the agent produces** — files written, messages sent, lore canonized.
- **Constraints and prohibitions** — generic-fantasy traps to avoid, output-shape requirements, length guidance.
- **Done criteria** — when the phase is complete, signaled how.

## What does *not* go in one

- Scene-by-scene scripts. Methodologies are not adventure modules.
- Mechanical schemas. Methodologies explain sequence; terms and numbers belong
  in the SRD.
- Tool manuals. `glass` mechanics and file-write rules belong in
  `instructions/`.
- Lore content. Methodologies tell agents *how* to engage with the lore, not what the lore is.

## Status

Campaign planning, arc creation, scene prep, scene play, action scenes, and
character creation are authored enough for first-play iteration. Arc creation
and scene prep are intentionally separate from campaign planning so each can be
re-invoked during active play when needed.
