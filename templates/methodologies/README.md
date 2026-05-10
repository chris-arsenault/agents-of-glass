# Methodologies

The instruction documents the agents read to know *how* a phase runs. **The real instructions** for each bootstrap phase plus regular play.

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

A methodology is **prose instructions for agents**, not a schema. It tells the DM (or the players) what they're doing during this phase, what counts as good output, what to avoid, what the boundary conditions are.

Think of it the way a human GM might read a craft article from a TTRPG blog before running a phase they haven't done before — guidance that shapes their decisions but doesn't dictate every word.

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
- Mechanical schemas. Methodologies explain table procedure; mechanical terms
  and numbers belong in the shared vocabulary and CLI output.
- Lore content. Methodologies tell agents *how* to engage with the lore, not what the lore is.

## Status

Campaign planning, arc creation, and scene prep are authored. Character creation is still a stub — needs a co-author pass before the first real campaign can run end to end. Arc creation and scene prep are intentionally separate from campaign planning so each can be re-invoked during active play when needed.
