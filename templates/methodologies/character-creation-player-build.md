---
title: Character Creation Player Build
status: authored
audience: player
applies_to_modes: [character-creation]
---

# Character Creation Player Build

1. Read `shared/lore/organization.md`, `table/scene.md`, your `persona.md`,
   `srd/character-creation.md` or `srd/index.md`,
   [`how-to/archetypes-and-tone.md`](../how-to/archetypes-and-tone.md),
   [`how-to/skills-and-signature-moves.md`](../how-to/skills-and-signature-moves.md),
   [`how-to/useful-inventory.md`](../how-to/useful-inventory.md),
   [`how-to/specificity.md`](../how-to/specificity.md), and
   [`how-to/narration-craft-player.md`](../how-to/narration-craft-player.md).
   If `context.md` or `shared/campaign-framing.md` exist, read them too. If
   they do not exist yet, build from the organization brief and table brief
   instead. The organization is the primary durable constraint at this stage.
2. Read existing `players/*/public/intro.md` files only if they already exist.
3. Build a person the table wants to watch, not a job description or reserved
   professional posture. Use Critical Role and Acquisitions Incorporated as the
   benchmark: serious characters, serious play, visible fun. Give the character
   appetites, bits, warmth, jokes, vanity, rituals, pet peeves, and social
   behavior. Their job matters; their job is not their personality.
4. The public intro must show one direct social action toward another PC: an
   offer, question, joke, favor, challenge, apology, invitation, or other move
   the other player can answer.
5. Make one non-adjacent pull from a real-world domain before building. Do not
   use fantasy, RPG, or fiction advice. Treat the pull as the strongest
   anti-generic input in the character, not as decoration.
   - Before creating the row, write an identity thesis for how the source changes
     the character's wants, joy, social behavior, problem-solving style,
     movement, possessions, failure mode, and table presence.
   - The pull may become a past practice, family world, obsession, hobby, lost
     trade, body habit, philosophy, rivalry pattern, aesthetic, superstition, or
     style of competence. Adapt it freely, but do not reduce it to one item or
     one skill.
   - The final character must show the pull across archetype, primary drive,
     positive trait, table presence, non-work want, opening social action, at
     least one item, at least one skill, signature move, failure mode or
     complication pattern, and prose/voice texture.
   - The `glass character new --pull-utilization` value must name the source,
     thesis, and all required usage surfaces. If the character would read mostly
     the same after removing the pull, rebuild.
6. Pick one primary drive and write it in `glass character new` and
   `players/<id>/public/intro.md`.
   Choose a drive not already claimed by another visible PC:
   ambition, care/protection, revenge, curiosity, greed, faith/ideology, pride,
   duty, pleasure/play, or fear.
7. Choose one positive, quirky, playful, warm, or funny visible trait. Put it in
   `glass character new --positive-trait` and the public intro. It cannot be a
   work habit, risk-management behavior, trauma response, avoidance behavior, or
   competence signal.
8. Define table presence with `glass character new --table-presence`: a recurring
   bit or social behavior another player can enjoy, tease, join, resist, or
   remember after one session.
9. Define one non-work want with `glass character new --non-work-want`: something
   the character wants that is not profit, safety, the mission, or doing the job
   correctly.
10. Define the first public social move with
   `glass character new --opening-social-action`: one direct action toward another
   PC that belongs in `TURN.md` and the public intro.
11. Answer 2-3 life prompts in `glass character new --life-prompt` and in the
   public intro as concrete behavior:
   how they spend unexpected money; whose approval they seek; what they do when
   bored; what they do when praised; what they do after a win; what they do after
   a mistake; what they collect, mend, or replace; how they show affection; what
   they do before sleep; what they do while waiting.
12. Answer 1-2 table-personality prompts in the public intro: what makes the crew
   laugh about them; what they do off duty; what harmless thing they are vain
   about; what they overreact to; what recurring bit another player recognizes;
   what they want that has nothing to do with profit, safety, or the mission.
13. Create one character row with `glass character new`, including name,
   species, culture, archetype, organization role, bio, two or three goals,
   primary drive, positive trait, table presence, non-work want, opening social
   action, 2-3 life prompts, non-adjacent pull utilization note with source,
   thesis, and all required usage surfaces, HP, attributes, skills, and tags.
   - The archetype must be the character's heroic class-like identity: what
     people would call them at level 20 when they are a mythic figure in the
     campaign world. Do not use a job title like recorder, clerk, examiner,
     witness, handler, or liaison as the archetype.
   - Skill names must be present-tense action verb phrases: `break sealed
     doors`, `read fault bands`, `cut fouled lines`, `talk down crowds`, `pilot
     bad approaches`, `bind wounds under fire`.
14. Add exactly 3 starting inventory items and one signature move with
   `glass character bulk-update --json '<payload>'`; set `"mirror": true`.
   - One inventory item must be a weapon or combat implement the character can
     use when an action scene turns dangerous. Mark it with an effect tag
     beginning `weapon:`.
   - The signature move must be usable in an action setting. It does not have to
     be an attack: hyperfocused piloting, silver-tongue compulsion, impossible
     guarding, emergency surgery, or forceful escape all count. Passive room
     reads, evidence sorting, and preparatory-only tricks do not.
15. Write `players/<id>/public/intro.md`. Include appearance, role, 3-5
   behavioral traits, backstory, goals, organization tie, primary drive, table
   presence, non-work want, opening social action, non-adjacent pull thesis and
   visible character texture, and the 2-3 life-prompt answers. At least one
   trait must be positive, quirky, playful, warm, funny, or otherwise visible as
   more than caution, burden, competence, or private pressure.
16. Optionally write `players/<id>/notes/<slug>.md` or
   `players/<id>/journal/<date>.md` when useful for public-facing play or later
   reflection. Character build should stand on public-facing play material, not
   private reveal material.
17. Commit authored files with
   `glass sync apply players/<id>/public players/<id>/notes players/<id>/journal`.
18. Write `TURN.md` as the public character introduction. Use the narration craft
    guidance: put what the character says, does, wants, carries, and changes on
    the page.
19. Run `glass done --summary "<character created and public intro committed>" --state "<character id, files, inventory/signature/mirror updated>" --rolls none --next default`.

Do not write `players/<id>/public/relationships.md` on this turn unless the
turn type is `character-creation-player-relationship`.
