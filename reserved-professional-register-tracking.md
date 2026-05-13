# Reserved Professional Register Tracking

## Problem

The current character-creation changes improved differentiation, openness, and
table-facing hooks. The remaining issue is not mainly the withholding tic. That
is at a tolerable level for now. The sharper problem is that play keeps turning
characters into restrained professionals: competent, procedural, inwardly
controlled people whose quirks become diagnostic habits instead of social play.

Target outcome: characters should still take the game and fiction seriously,
but should read more like actual-play PCs with appetites, jokes, irritations,
warmth, vanity, petty preferences, offers, and visible table behavior.

## Hypotheses Worth Testing

### 1. Character Persona Prompting In Scene Play

Most worth testing.

Current scene play asks the agent to act as a player, then embody the character,
while also carrying player persona and style-file pressure. That stack may bias
the model toward "competent author writing a competent professional."

Test: in scene play, reduce or remove player persona emphasis and prompt from
the character persona / character sheet directly.

Prompt shape to test:

- You are playing `<character>`, not writing about `<character>`.
- This turn must include one visible social behavior from the character sheet.
- Before solving the work problem, make one characterful move: joke, complaint,
  offer, petty preference, appetite, ritual, warmth, vanity, or overreaction.
- Do not turn the trait into analysis or calibration. Let it be socially
  playable.

Expected effect: stronger character-level behavior, less default professional
competence, more opportunities for other players to respond.

### 2. Mixed Model Table

Worth testing second.

Have half the players use Codex and half use Claude. This may expose whether the
register is partly model-native. Claude is strong at polished dramatic restraint;
Codex may be more blunt, direct, and less likely to turn every trait into
literary-professional control.

Risk: noisy test. Model swap changes prose style, tool behavior, initiative,
and turn shape all at once.

Expected effect: useful contrast data, even if not immediately adopted.

### 3. Drop Session ID

Worth testing third.

Dropping persistent session memory may reduce accumulated campaign register. If
a session learns "this is serious procedural survey fiction," it can keep
recreating that register even after templates change.

Risk: if the turn prompt still centers player persona, restrained style, and
professional context, the model may recreate the same behavior from scratch.

Expected effect: possible reduction in style lock-in, but probably weaker than
direct character-persona prompting.

### 4. More Thinking / Model Upgrade

Least worth testing for this specific issue.

The reserved-professional register is not primarily a reasoning-depth problem.
More capable or more literary models may simply produce better reserved
professionals unless the prompt redirects the performance target.

Expected effect: maybe marginal instruction compliance, but not likely to
create more fun characters by itself.

## Metrics

Track these per player turn and per scene:

- Does the PC make a direct social offer, reaction, joke, complaint, or bid?
- Does a character quirk appear as social play rather than job procedure?
- Could another player respond to the behavior without needing plot knowledge?
- Does the turn include any want besides doing the mission correctly?
- Does the PC show a petty preference, appetite, warmth, vanity, or overreaction?
- Does the prose convert the character's fun trait into calibration, restraint,
  or professional analysis?

Secondary metric:

- Count withholding / not-saying constructions per 1,000 words, but do not make
  zero withholding the target. The target is preventing withheld material from
  being the default engine of character depth.

## Proposed Test Order

1. Scene play with direct character persona prompting.
2. Mixed model table: half Codex, half Claude.
3. No persistent session id.
4. More thinking / model upgrade only after the above.

## Current Judgment

Start with character persona prompting. It is the most targeted intervention
for reserved-professional drift and should be easier to evaluate than model
switching or persistence changes.
