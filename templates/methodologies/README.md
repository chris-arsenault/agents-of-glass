# Methodologies

The ordered workflow documents the executing agents read to know *how* a phase
or mode runs.

These get copied into each campaign at creation as `campaigns/<name>/methodologies/`, frozen against the campaign so editing the template here doesn't retroactively change a running campaign.

## The methodologies

Three nested levels of DM prep, plus bootstrap play:

- **[`campaign-planning.md`](campaign-planning.md)** — the **world** level. Solo DM authoring during the `campaign_planning` phase. Outputs: the Question, the Scarcity, factions, NPCs (with antagonist flags), recurring creatures, named things (artifacts/ships/relics), locations, secrets, hooks, philosophy, the opening arc(s). The principle: **prep situations, not plots**. Authored.
- **[`arc-creation.md`](arc-creation.md)** — the **multi-scene-pressure** level. Called from campaign-planning to author the opening arc(s), and re-invoked during active play whenever the DM formalizes a new arc. Outputs: stakes question, threats, clocks, possible end-states, nodes, what from the curated lists is in play, arc-specific secrets. **Shape, not script.** Authored.
- **[`scene-prep.md`](scene-prep.md)** — the **single-scene** level. Run before each new scene in active play. Outputs: recap, strong start, 3-5 possible directions, NPCs/antagonists/creatures/named-things in play, secrets that might surface, open questions to be answered through play, and the opening player-agent-visible table state. Closely follows Sly Flourish's *Lazy Dungeon Master*. Authored.
- **[`closeout.md`](closeout.md)** — the mandatory ordered workflow before `glass scene end` or `glass arc close`. Outputs: closeout checklist, outcomes, consequence/state updates, NPC carry-forward, summaries, lore/journal decisions, quest beats, rewards. Authored.
- **[`scene-play-player.md`](scene-play-player.md)** / **[`scene-play-dm.md`](scene-play-dm.md)** — role-specific full-turn sequences for free-form scenes.
- **[`scene-transition-dm.md`](scene-transition-dm.md)** — the DM scene-boundary turn that closes one scene, stages the next, and queues player cleanup.
- **[`scene-housekeeping-player.md`](scene-housekeeping-player.md)** — the one non-plot player cleanup turn between scenes after the DM has wrapped the old scene and staged the next one.
- **[`rapid-response-player.md`](rapid-response-player.md)** — the short player answer turn queued by the DM for one prompt.
- **[`action-scene-opening-dm.md`](action-scene-opening-dm.md)** / **[`action-scene-dm.md`](action-scene-dm.md)** / **[`action-scene-player.md`](action-scene-player.md)** — quickfire contested scenes using action order and short in-world time. Combat, chase, and social pressure are toolkit examples, not an exhaustive mode list.
- **[`character-creation.md`](character-creation.md)** — the `character_creation` phase. DM writes a public campaign-intro; each player authors their character and a public intro entry; DM ratifies. Multi-agent.
- **[`prelude-arc.md`](prelude-arc.md)** — the `prelude` bootstrap phase. DM runs a short two-scene first incident after character creation: one normal scene and one action scene, then a time jump into the main campaign.
- **[`intermission.md`](intermission.md)** — the player-facing planning room between major sections. Mara sets broad tone, players name wants and requests, and the table captures collaborative mid- to long-term priorities before the next act.

After the prelude, the campaign is `active` and the main opening arc begins.
The prelude gives the party a first shared consequence before the campaign opens
at full speed.

## What a methodology document is

A methodology is a binding sequence for an invocation: what to read first, what
to produce, what order matters, and what done means.

Actual-play methodologies are one contract per role and turn type. The
orchestrator selects the active document in TURN_START from role, mode, and turn
metadata; methodology documents do not route agents to a different actual-play
turn type.

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

Campaign planning, arc creation, scene prep, scene closeout, scene play, action
scenes, character creation, the prelude arc, and intermission are authored
enough for first-play iteration. Arc creation and scene prep are intentionally
separate from campaign planning so each can be re-invoked during active play
when needed.
