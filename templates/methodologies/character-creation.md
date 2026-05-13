---
title: Character Creation Methodology
status: authored
audience: dm-and-players
applies_to_modes: [character-creation]
---

# Character Creation

Run character creation as a fixed multi-turn sequence. Hard character state is
created with `glass character`; authored prose is committed with
`glass sync apply`.

## Fixed Sequence

1. Player build turns create one character row, one public mirror, one public
   intro, inventory, and one signature move for each PC.
2. The next DM turn opens the relationship round. It may compare notes,
   update the visible party situation, and send relationship prompts. It does
   not ratify the party and does not run `glass mode end`.
3. Player relationship turns create
   `players/<id>/public/relationships.md` for each PC.
4. The final DM ratification turn happens only after every relationship file
   exists and is non-empty. That is the only character-creation turn that runs
   `glass mode end`.

## DM Setup Turn

1. **Prepare the public brief.**
   - Verify `context.md`, `shared/campaign-framing.md`,
     `shared/lore/organization.md`, and `table/scene.md` exist.
   - Read [`how-to/narration-craft-dm.md`](../how-to/narration-craft-dm.md)
     before writing public prose.
   - Put the character creation brief on the table with
     `glass table write scene.md --body "<who the party is, what choices matter now>"`.

2. **Verify reference surfaces.**
   - Run `glass lore list`.
   - Run `glass summary show campaign`.
   - Run `glass arc current`.

3. **Close the setup turn.**
   - Write `TURN.md` with the player-facing creation brief.
   - Run `glass turn end --summary "character creation brief is ready" --state "table and public campaign context prepared" --rolls none --next default`.

## Player Build Turn

1. **Read before writing.**
   - Read `context.md`, `shared/campaign-framing.md`,
     `shared/lore/organization.md`, `table/scene.md`, your `persona.md`, and
     `srd/character-creation.md` or `srd/index.md`.
   - Read [`how-to/specificity.md`](../how-to/specificity.md) and
     [`how-to/narration-craft-player.md`](../how-to/narration-craft-player.md).
   - Read existing public intros if other players have already created theirs.
   - Run `glass character bulk-get --all` if existing character rows matter.

2. **Build a person, not a reserved professional.**
   - Benchmark: Critical Role and Acquisitions Incorporated. Those players take
     the game seriously and play serious characters, but the characters are
     people the table enjoys watching. They have appetites, bits, jokes,
     rituals, wants, warmth, vanity, pet peeves, and visible social behavior.
     Their jobs matter; their jobs are not their personalities.
   - The public intro must put a direct social action toward another PC on the
     page: an offer, question, joke, favor, challenge, apology, invitation, or
     other table-facing move.
   - The character must visibly want something that is not profit, safety, the
     mission, or doing the job correctly.

3. **Make the anti-sameness choices.**
   - Make one non-adjacent pull from a real-world domain before building. Do not
     use fantasy, RPG, or fiction advice. Capture 2-3 concrete textures from
     that domain and use at least one in a skill, trait, inventory item,
     signature move, backstory detail, or social habit. Record the source/domain
     and the exact utilization in `glass character new --pull-utilization`.
   - Pick one primary drive and write it in `glass character new` and
     `players/<id>/public/intro.md`. Choose a drive not already claimed by
     another visible PC: ambition, care/protection, revenge, curiosity, greed,
     faith/ideology, pride, duty, pleasure/play, or fear.
   - Choose one positive, quirky, playful, warm, or funny visible trait and put
     it in `glass character new --positive-trait`. It cannot be a work habit,
     risk-management behavior, trauma response, avoidance behavior, or competence
     signal.
   - Define table presence with `glass character new --table-presence`: a
     recurring bit or social behavior another player can enjoy, tease, join,
     resist, or remember after one session.
   - Define a non-work want with `glass character new --non-work-want`: what
     they want when nobody is paying them, chasing them, or grading their job.
   - Define the first public social move with
     `glass character new --opening-social-action`: one direct action toward
     another PC that belongs in `TURN.md` and the public intro.
   - Answer 2-3 life prompts as concrete behavior in both `glass character new
     --life-prompt` and the public intro: how they spend unexpected money; whose
     approval they seek; what they do when bored; what they do when praised; what
     they do after a win; what they do after a mistake; what they collect, mend,
     or replace; how they show affection; what they do before sleep; what they do
     while waiting.
   - Also answer 1-2 table-personality prompts in the public intro: what makes
     the crew laugh about them; what they do off duty; what harmless thing they
     are vain about; what they overreact to; what recurring bit another player
     recognizes; what they want that has nothing to do with profit, safety, or
     the mission.

4. **Choose the required identity fields.**
   - Character id.
   - Full name.
   - Species and culture from the campaign/SRD.
   - Archetype.
   - Organization role.
   - Short public bio.
   - Two or three goals.
   - Primary drive from the required drive list, not already used by another PC.
   - One positive/quirky/playful/warm/funny trait.
   - One table presence bit.
   - One non-work want.
   - One opening social action toward another PC.
   - Two or three life-prompt answers as `prompt=answer`.
   - One non-adjacent pull utilization note naming source/domain and exact use.
   - HP value.
   - Attribute and skill allocation.

5. **Create the character row.**

```bash
glass character new <character-id> --player <your-agent-id> \
  --name "<full-name>" \
  --species "<species>" \
  --culture "<culture>" \
  --archetype "<archetype>" \
  --org-role "<organization role>" \
  --bio "<public bio>" \
  --goal "<goal one>" \
  --goal "<goal two>" \
  --primary-drive "<drive from required list>" \
  --positive-trait "<visible fun/warm/playful trait, not job competence>" \
  --table-presence "<recurring social bit another player can use>" \
  --non-work-want "<want unrelated to profit, safety, mission, or job competence>" \
  --opening-social-action "<direct action toward another PC for the intro>" \
  --life-prompt "<prompt>=<concrete behavior answer>" \
  --life-prompt "<prompt>=<concrete behavior answer>" \
  --pull-utilization "Source: <real-world domain/source>; used in <skill, trait, item, signature move, backstory detail, or social habit>." \
  --hp <8|10|12> \
  --attribute <name>=<tier> \
  --attribute <name>=<tier> \
  --skill "<skill>=artisan" \
  --skill "<skill>=apprentice" \
  --skill "<skill>=apprentice" \
  --tag <tag>
```

6. **Add inventory, one signature move, and the public mirror.**
   - Inventory is for assets that can change future action: working tools,
     weapons, protective gear, consumables, keys, samples, maps, leverage
     tokens, specialist instruments, or portable resources.
   - Starting inventory must include exactly 3 items. One must be a weapon or
     combat implement usable when violence, pursuit, monsters, or immediate
     physical danger enter the scene. Mark it with an effect tag beginning
     `weapon:`.
   - At most one item should be a document, credential, leverage token, or
     sentimental object, and only if the player expects it to matter in play.
   - Effect tags should name affordances, not only mood: what the item opens,
     proves, protects, detects, cuts, spends, hides, or changes.
   - The signature move must be usable in an action setting. It can be a spell,
     social compulsion, piloting focus, rescue move, guard, escape, chase trick,
     or control move; it should not be only a room read, evidence sort, or
     preparatory observation.

```bash
glass character bulk-update --json '{
  "characters": [
    {
      "character_id": "<character-id>",
      "inventory_add": [
        {"id": "<weapon-slug>", "qty": 1, "effect_tags": ["weapon: <specific action affordance>"]},
        {"id": "<tool-or-asset-slug>", "qty": 1, "effect_tags": ["<specific affordance>"]},
        {"id": "<consumable-or-leverage-slug>", "qty": 1, "effect_tags": ["<specific affordance>"]}
      ],
      "signature_moves": [
        {
          "name": "<move name>",
          "look": "<what it looks/sounds/feels like>",
          "use": "<when you reach for it>",
          "tell": "<trace, cost, risk, or who recognizes it>"
        }
      ],
      "mirror": true
    }
  ]
}'
```

7. **Write authored player files.**
   - `players/<id>/public/intro.md`: public appearance, role, 3-5 behavioral
     traits, backstory, goals, organization tie, primary drive, table presence,
     non-work want, opening social action, non-adjacent pull texture, and the 2-3
     life-prompt answers. At least one trait must be positive, quirky, playful,
     warm, funny, or otherwise visible as more than caution, burden, competence,
     or private pressure.
   - The intro must show one direct social action toward another PC and give the
     other player something concrete to answer.
   - `players/<id>/notes/<slug>.md` or `players/<id>/journal/<date>.md` only
     when useful for public-facing play or later reflection. Character build
     should stand on public-facing play material, not private reveal material.
   - Commit with `glass sync apply players/<id>/public players/<id>/notes players/<id>/journal`.

8. **Close the build turn.**
   - Write `TURN.md` as the public character introduction. Use the narration
     craft guidance: put what the character says, does, wants, offers, jokes
     about, asks for, carries, and changes on the page.
   - Run `glass turn end --summary "<character created and public intro committed>" --state "<character id, files, inventory/signature/mirror updated>" --rolls none --next default`.

## Relationship Round

The relationship round begins after all four player build turns and the DM's
relationship setup turn. Missing relationship files mean character creation is
still in progress.

1. **Read the party.**
   - Read every `players/*/public/intro.md`.
   - Run `glass character bulk-get --all`.
   - Read any unread messages with `glass msg read --since-checkpoint`.

2. **Author relationship material.**
   - Add or update `players/<id>/public/relationships.md`.
   - Use messages for proposals that need another player or the DM:
     `glass msg banter <recipient> "<specific relationship proposal or question>"`.
   - Commit with `glass sync apply players/<id>/public/relationships.md`.

3. **Close the relationship turn.**
   - Write `TURN.md` with only the public relationship commitments.
   - Run `glass turn end --summary "<relationship commitments updated>" --state "players/<id>/public/relationships.md updated or no state change" --rolls none --next default`.

## DM Ratification Turn

Start this turn only after every `players/<id>/public/relationships.md` exists
and is non-empty. If any relationship file is missing, run the relationship
setup/relationship turns instead.

1. **Inspect all public characters.**
   - Run `glass character bulk-get --all` and verify every row has non-empty
     `primary_drive`, `positive_trait`, `table_presence`, `non_work_want`,
     `opening_social_action`, 2-3 `life_prompt_answers`, and
     `pull_utilization_note`.
   - Read `players/*/public/intro.md` and `players/*/public/relationships.md`.
   - Read [`how-to/narration-craft-dm.md`](../how-to/narration-craft-dm.md)
     before writing the public party lock-in.

2. **Fix hard-state drift with CLI commands.**
   - Use `glass character bulk-update --json '<payload>'` for corrections.
   - Use `glass character mirror <id>` after changes that affect public display.
   - Use `glass sync apply` for authored markdown corrections.

3. **Summarize the party.**
   - Update `shared/party-knowledge.md` or `shared/quest-log.md` if needed.
   - Run `glass summary append campaign --body "<party created summary>"`.

4. **End character creation.**
   - Write `TURN.md` with the public party lock-in.
   - Run `glass turn end --summary "character creation complete" --state "<party state and summaries updated>" --rolls none --next default`.
   - Run `glass mode end`. This command refuses to end character creation while
     relationship files are missing or empty.

## Prohibitions

- Do not hand-author `players/<id>/public/character.md`; it is generated by
  `glass character mirror`.
- Do not invent hard-state numbers in prose.
- Do not hide required character facts only in messages, notes, or journals.
- Do not create a character row without primary drive, positive trait, table
  presence, non-work want, opening social action, 2-3 life-prompt answers, and a
  non-adjacent pull utilization note.
- Do not make job competence, tactical caution, or inward pressure the
  character's main public trait. Their visible table presence must be a social
  behavior another player can answer.
- Do not start play until every PC has a character row, public intro, and
  mirrored public character display.
- Do not end character creation until every PC has a non-empty
  `players/<id>/public/relationships.md`.

## CLI Encoding Opportunities

These are not commands yet:

- `glass character creation-check` for required rows, mirrors, public intros,
  relationships, and missing goals.
- `glass character relationship-add` for structured relationship commitments.
- `glass party summarize` for public party knowledge and campaign summary.
