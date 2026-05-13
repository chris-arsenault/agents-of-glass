---
title: Methodologies
target: executing-agent
authority: binding
---

# Methodologies

Methodologies are mandatory ordered sequences. TURN_START selects exactly one
methodology for the current role and turn type. Follow that document in order.

## Contract

1. Read the selected methodology.
2. Execute its numbered sequence.
3. Use `glass` commands for hard state, summaries, table state, clocks,
   messages, scenes, arcs, and turn closeout.
4. Commit authored markdown with `glass sync apply`.
5. Write public prose to `TURN.md`.
6. Run `glass turn audit`, then end with `glass turn end`.

Methodologies are not tool manuals, SRD text, craft essays, or branch routers.
If a step cannot be completed, run `glass turn audit`, say what blocked it in
`glass turn end --state`, and hand off with `--next` only when another actor is
required.

## Selected Turn Methodologies

- `organization-bootstrap.md`: single-turn DM org build before characters exist.
- `scene-play-character.md`: character-framed full turn in free scene play.
- `scene-play-player.md`: player full turn in free scene play.
- `scene-play-dm.md`: DM full turn in free scene play.
- `scene-transition-dm.md`: DM scene boundary turn.
- `scene-housekeeping-player.md`: player cleanup between scenes.
- `rapid-response-character.md`: short character-framed answer to a DM prompt.
- `rapid-response-player.md`: short player answer to a DM prompt.
- `action-scene-opening-dm.md`: DM opens quickfire action.
- `action-scene-dm.md`: DM turn inside quickfire action.
- `action-scene-character.md`: character-framed turn inside quickfire action.
- `action-scene-player.md`: player turn inside quickfire action.
- `character-creation-dm-setup.md`: DM setup when character creation lacks a brief.
- `character-creation-player-build.md`: player character build turn.
- `character-creation-dm-relationship-setup.md`: DM bridge into relationships.
- `character-creation-player-relationship.md`: player relationship authoring turn.
- `character-creation-dm-ratification.md`: final DM lock-in after relationships.

## Prep and Lifecycle Methodologies

- `campaign-planning.md`: post-character campaign foundation, opening arc, and prelude shell.
- `arc-creation.md`: multi-scene pressure unit.
- `character-creation.md`: overview of PC creation, relationship round, and DM ratification.
- `prelude-arc.md`: exactly two-scene prelude.
- `scene-prep.md`: stage a scene and enter actual play.
- `intermission.md`: table planning between acts.
- `closeout.md`: required scene and act closeout sequence.

## Reference Indexes

`scene-play.md` and `action-scene.md` are reference indexes with craft links.
Generated TURN_START files select the role-specific documents above.

## CLI Encoding Rule

When a methodology starts carrying a checklist that can be validated, prefer a
new `glass` command over more prose. Existing opportunities are listed in the
individual methodologies under "CLI Encoding Opportunities"; those entries are
operator design notes, not commands agents can call today.
