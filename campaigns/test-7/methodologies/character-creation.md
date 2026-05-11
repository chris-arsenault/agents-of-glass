---
title: Character Creation Methodology
status: authored
audience: players, dm
---

# Character Creation

The methodology you read during the `character_creation` phase. The DM has
already finished campaign-planning, but player-facing character creation should
use only the setting, party organization, premise/question, scarcity, tone, and
public lore. The DM may have a deeper campaign structure, antagonist map,
opening arc, and mystery chain; those are not character-creation inputs unless
they have already been made public in `context.md`, `shared/lore/`, or the
table.

This methodology has **two rounds**:

1. **Character round** — each player builds their PC and writes their public intro.
2. **Relationship round** — once all four PCs are authored, each player adds 1-2 relationship ties to other PCs.

Don't start round 2 until round 1 is fully done. Relationships only make sense when there are characters to relate to.

For the mechanical layer (attribute budget, skill budget, HP, inventory rules),
read [`srd/character-creation.md`](../srd/character-creation.md). For command
and file behavior, read [`instructions/character-state.md`](../instructions/character-state.md).
This doc is the process.

## Trust yourself, follow the rules

You are not asking the DM for permission at each step. There is no propose / ratify loop on character intros, character sheets, or relationships. Read the methodology and SRD, follow them, and persist your authored files with `glass sync apply`.

The DM gets one turn at the end of each round to read what the party authored and transition the phase forward. If a player produces something off-spec — a non-existent species, an attribute budget that doesn't add up, a generic-fantasy backstory that ignored the web pull — the DM can push back via `glass msg secret <player>` and ask for a revision in a follow-up turn. But the default is "you make your character; the DM is not your editor."

This applies to the rest of play too. Make your own rolls via `glass roll`. Take your own HP changes via `glass character set-hp`. Spend your own momentum. The system is the system — don't ask the DM to confirm each mechanical step. Propose / ratify is reserved for **public journal entries** during play (canonical, party-shared lore that the DM might want to fold into the campaign record).

### State and file boundaries

Follow [`instructions/character-state.md`](../instructions/character-state.md)
for character rows, inventory, HP, momentum, and consequences. Follow
[`instructions/lore-and-notes.md`](../instructions/lore-and-notes.md) for notes
and canon proposals.

Write public character prose directly under `players/<your-id>/public/` in the
workspace, then commit it with `glass sync apply`. Add signature moves with `glass character bulk-update` or
`glass character signature-add`; direct note writes to
`players/<your-id>/signature-moves.md` are rejected so the level-based slot
limit stays honest.
Read workspace files normally, edit writable document paths in place, then use
`glass` for anything that must survive the turn.

The canonical character row must include non-empty `species`, `culture`,
`archetype`, `organization_role`, and `bio` fields, plus 2-3 canonical goals.
Pronouns are optional; if unspecified, the public mirror will say
`unspecified`.

### Where files live in your player dir

```
players/<your-id>/
  persona.md            you (the player) — provided with the campaign template
  signature-moves.md    recurring prose moves; one simple move at level 1
  public/               party-readable: intros, relationships, cached character display
  secrets/              DM-readable, other-player-private: hidden knowledge files
  drafts/, journal/, notes/, inbox/   private to you
```

Anything you persist in `public/` is party-readable. Anything you persist in
`secrets/` is DM-readable but not visible to other players. Edit the right
workspace path and commit it with `glass sync apply`.

## Round 1: Build your character

### 1. Read before you write

Before authoring anything, read in this order:

- **Your persona** at `players/<your-id>/persona.md` — who you are as a *player*, what you like, what kind of PC you tend to build.
- **The campaign context** at `context.md` (campaign root) — the Question, the Scarcity, the setting, tone, and what the party knows.
- **The party's organization** at `shared/lore/organization.md` — what the org does, the capabilities it typically needs, the reason the party operates together.
- **The SRD character creation rules** at [`srd/character-creation.md`](../srd/character-creation.md).
- **Species lore** at `shared/lore/species/` — read the index, then read each species's full page. Don't skim. The texture matters.
- **Cultures and naming** at `shared/lore/cultures/` — both the culture descriptions and the naming conventions. Names follow culture, not species.
- **Whatever lore the DM has curated** at `shared/lore/` — locations, factions, NPCs, concepts.

Reading takes time. Read first. Don't start building while you're still discovering the world.

### Round 1 independence

During Round 1, do not read previous character-creation turns as design input
and do not build your PC as an answer to another player's PC. Build from your
persona, the public setting/org context, the SRD, and your non-adjacent pull.

It is fine to send a one-line table-talk concept announcement to avoid exact
duplication. Save intentional party weaving for Round 2, after every player has
an independent character on the table.

### 2. Required: non-adjacent web pull

This is the same anti-sameness mechanism the DM uses during campaign-planning, applied to character creation. **You must do at least one non-adjacent web search before building your character.** Skip this step and your character will drift toward generic fantasy archetypes.

**Non-adjacent means:** not fantasy fiction, not other RPGs, not "character creation tips," not anything in the orbit of TTRPGs or sci-fi. You are pulling texture from a real-world domain that interests you and using it to ground your character.

Examples of good pulls:

- A retired Antarctic radio operator's account of long-dark-season communication routines
- The training regimen of an Olympic shot-putter
- How hospice nurses talk to patients about death
- The specific hand vocabulary of butchers, tailors, surgeons, glassblowers
- What a deep-sea ROV pilot does during a 16-hour cable inspection
- How blind people navigate unfamiliar buildings
- The professional jargon of a niche field (lighthouse keeping, court interpretation, archive conservation, mortuary cosmetics)

Pick something **specific** that actually interests you (or your persona). Search for one or two specific articles, skim them, and **write down 2-3 concrete textures** you found — phrases, routines, observations, professional tics. These are your raw material.

You will use these textures to ground:
- A skill or two (the "how" of what your character does, not just the label)
- A trait (a specific habit or tic the real-world domain gave you)
- A signature inventory item (something specific from that world, ideally
  useful under pressure)
- A line or image in your backstory

Generic-fantasy drift is obvious from the page. The DM will see it.

### 3. Choose species and culture

Pick a species from `shared/lore/species/`. Pick a culture (or hybrid) from `shared/lore/cultures/`. These are independent choices — a Sithari orc is a different person from a Hab-Worlder orc.

**Pick the species whose texture you actually want to play with.** Not the one that sounds coolest. The orc whose pain response is muted will play differently than the gnome who feels resonance like temperature. Decide what kind of *experience* you want to inhabit.

Pick a name that follows your culture's naming convention exactly. See `shared/lore/cultures/naming-conventions.md`. Be specific. No "Thorgrim." No "Aelaria." Use the cultural pattern.

### 4. Choose archetype and organization role

There is no fixed class list. Instead, choose a class-like **archetype** and a
separate **organization role**.

Read the org's "capabilities the party typically needs" section in `shared/lore/organization.md`. Those are guidance, not slots. They tell you *what kinds of leverage the org operates by* — not what archetype you have to play.

The `archetype` field is your broad adventuring identity: the portable label
someone could use for what kind of character you are. It should be generic
enough to make sense outside this specific organization, but still grounded in
the Glass Frontier. Think "class without a fixed class list." For tone and
examples, see [`how-to/archetypes-and-tone.md`](../how-to/archetypes-and-tone.md).

Useful archetype shapes:

- "Resonance Knight"
- "Glasswright"
- "Document examiner"
- "Legendary Trombonist"
- "Waystation scout"
- "Witness-Binder"

Bad archetypes:

- "Ex-Conclave intake clerk on the Ledger Run" — backstory plus org, not class.
- "Splitfork drop-pilot hired after the 2432 vacancy" — current job plus history.
- "Mereth's trusted refusal-log clerk" — organization status, not archetype.
- "The one who knows what happened at Thornvault" — secret/hook, not archetype.

The `organization_role` field is separate. It answers: *how does this person
belong to the party organization?* It can be status, tenure, trust, social
place, daily responsibility, or odd membership niche. It should not merely
repeat the archetype.

Good organization roles:

- "founder of the independent crew"
- "long-time member with high trust"
- "probationary hire"
- "crew cook and morale center"
- "quartermaster"
- "route contact"
- "family legacy member"
- "outside specialist on retainer"
- "officially a porter, unofficially the person everyone asks"

Orthogonal examples:

- Archetype "Warrior"; organization role "cook and long-time member."
- Archetype "Document examiner"; organization role "probationary hire."
- Archetype "Kite-wright"; organization role "founder's nephew and maintenance lead."
- Archetype "Tuner"; organization role "outsider specialist on retainer."

Invent who your character is from both axes. **Capabilities-not-slots.**
Examples:

- "Lapsed Tuner who runs supplies into the Shear because she can't get certified work after the Conclave hearing."
- "Hab-Worlder ex-medic, now running a back-channel pharmacy for migrants who can't get processed."
- "Sithari archivist who got reassigned to the field after one too many letters to the wrong person."
- "Orc smith from a Karet route family who took the org job because his sister did."

Notice: each one names a profession (real or invented but world-grounded), gives a reason they're not in their default lane, and points at something specific in the world. None of them is "fighter" or "mage."

When you run `glass character new`, make `--archetype` the broad class-like
identity and `--org-role` the orthogonal organization membership/standing. If
the two fields are basically the same sentence, revise one of them.

### 5. Allocate attributes and skills

Per [`srd/character-creation.md`](../srd/character-creation.md):

- 7 attributes default to `standard`. Bump 2 to `advanced`, 1 to `superior` (optional). Optionally drop 1 to `rudimentary` as a flaw.
- 3 trained skills total: 1 `artisan`, 2 `apprentice`. Do not start with `virtuoso`; unlisted skills default to `fool`.

Choose attributes that match the character you're building. A Lapsed Tuner whose `attunement` is still `superior` makes sense — that's why the loss is sharp. A Hab-Worlder ex-medic with `vitality` at `rudimentary` because chronic exposure has cost her makes sense — the flaw is the story.

Skills are orthogonal to archetype, organization role, and signature moves. The
archetype is who the story might someday call you. Skills are the specific
trained competencies you can roll. A signature move is one recognizable thing
you do under pressure. Use skill names that are narrow enough to create choices
and broad enough to recur; pull at least one from your web-search texture.

### 6. Pick HP and inventory

HP defaults to 10. Take 8 if you're fragile/specialized; take 12 if physical robustness is a defining trait.

Inventory: 3-5 items. **One must be a signature item** with a specific story.
At least one item should be useful under pressure: a favored weapon,
instrument, special apparatus, field tool, restraint, protective rig, leverage
token, or other thing you would plausibly reach for during play. This can be
the signature item. Keepsakes and relics are good texture, but do not make the
whole inventory keepsakes. Read the SRD's inventory examples — generic gear is
bounceable.

Also start `players/<your-id>/signature-moves.md` with **one simple move** your
character can actively do under pressure: a spell, combat maneuver, search
style, social tactic, chase technique, ritual, or other repeatable move. This
is not a guaranteed power or a mechanical button. It is a consistency anchor
the table can recognize, and the DM can eventually let the world react to it.
Direct spell-like resonance moves are good choices: a Fireball-shaped harmonic
blast, a Cutting Words-shaped disruptive overtone, a Sanctuary-shaped hush, a
Shield-shaped glassward, or any other named technique with a clear look, use,
and cost.

Do not make the starting signature move a tic, personality trait, backstory
fact, or generic routine. "Reads the document sideways in raking light to catch
hidden marks" is a move. "Walks around the ship" is only a tic unless it is
reframed as an actionable technique with a pressure use.

You gain additional signature move slots at levels 3, 5, 7, and 9. Later moves
can be broader, stranger, or more powerful in the fiction.

### 7. Pick traits to RP imperfectly

Pick **3-5 traits** that make this character a recognizable person. Each trait should be:

- **Specific.** Not "loyal." "Won't leave a meal half-eaten — finishes everyone else's plates too if she can get away with it." Not "brave." "Never says 'I'm scared' out loud, even when she clearly is."
- **Behavioral.** Something the character *does*, not something they *are*. Habits, tics, verbal patterns, physical mannerisms.
- **Imperfect-able.** A trait you want to play but might not always succeed at. The character *tries* to be the patient mentor; sometimes she snaps anyway. The character *believes* in the org's mission; sometimes he resents it. Failed-trait moments are the best character moments.

Examples of good traits:

- "Always finishes other people's sentences. Sometimes wrongly."
- "Refuses to call her former Conclave mentors by their titles, but slips when she's tired."
- "Will eat anything you put in front of her. Has feelings about people who are picky."
- "Holds grudges over specific phrasing — not what someone said, what words they used."
- "Apologizes constantly for small things. Stops apologizing entirely when the situation is actually her fault."
- "Touches every surface in a new room before sitting down. Doesn't realize she does it."

These go in your `intro.md` under a "Traits" section. The DM uses them for adjudication ("would your character actually do that?") and for character-voice work in transcripts.

### 8. Write backstory and goals

In `players/<your-id>/public/intro.md`, write:

- **Backstory: 3-4 paragraphs.** Where the character is from. What shaped them. How they ended up at the org. Reference public setting, org, faction, location, or profession details by name when they fit, but do not assume hidden campaign answers.
- **Goals: 2-3 specific goals.** Present-tense. Achievable but with friction. Not "save the world." Not "solve the campaign mystery." Not "get rich." Specific things this character is *currently trying to do*: personal, professional, relational, organizational, or value-driven. The DM may or may not weave them into the campaign — that's their judgment call. Goals you don't reach are fine.

Examples of good goals:
- "Find out what happened to Rin's last route. Officially I'm not asking. Unofficially I won't stop until I know."
- "Convince my mother to leave the hab before the council certifies it for decommissioning."
- "Earn enough off-the-books to pay back the Karet family I owe."
- "Find someone who knew my old name and wants to know me anyway."

### 9. The org tie

Your intro must explain **why this character is in this organization**, in a way that holds up. Recruited, drafted, owed a debt, ran out of options, was already inside before the campaign starts, family connection, romantic connection, true believer — any narrative reason works as long as it makes coherent sense for who the character is.

The `organization_role` field names how this PC belongs to the org. Your intro's
Org Tie line explains how they got there and why they stay. Example:
`archetype="Tuner"` and `organization_role="outside specialist on retainer"`,
with an Org Tie like `"The org needs Tuning expertise it can't get through
certified channels; she joined after the Conclave hearing barred her."`

### 10. Optional: hidden knowledge

You may write **hidden knowledge** to a file the DM can read but other players can't. Write it under `players/<your-id>/secrets/<name>.md`, commit it with `glass sync apply players/<your-id>/secrets/<name>.md`, and message the DM via `glass msg secret dm <one-line summary>` so they know to read it. Use it for:

- Alternative motivations (something your character is *also* doing while in the org)
- Backstory the character hasn't told anyone (an old name, a buried debt, a relationship the org doesn't know about)
- Knowledge the character has from before the campaign that the others don't (a face they'd recognize, a place they've been, a phrase that means something specific)
- A skill or capability the character is hiding

**Constraint:** alternative motivations are fine; **direct adversarial relationships with other PCs are not.** Your character can have agendas the party doesn't know about. Your character cannot be planning to betray the party, sell them out, or work against them in a way that would harm another player's enjoyment of the game. The line is: friction enriches play, sabotage breaks it.

If you're not sure where the line is, ask the DM via `glass msg secret dm <reason>` before writing the secret.

### 11. Write your files

**First, announce to the party** so the others know what's being built (avoids two players accidentally building near-identical PCs):

```bash
glass msg table-talk party "I'm building <name>, a <species> <archetype>. Org role: <orthogonal org role>. <one-line concept>."
```

Then create the character row + inventory:

```bash
# Create the character row in Postgres.
glass character new <character-id> --player <your-agent-id> \
    --name "<full-name>" --species "<species>" --culture "<culture>" \
    --archetype "<broad class-like identity>" --org-role "<org membership/status/responsibility>" \
    --bio "<concise public identity summary>" \
    --goal "<personal/professional/org goal>" \
    --goal "<second goal>" \
    --hp <8|10|12> \
    --attribute <name>=<tier> --attribute <name>=<tier> ... \
    --skill "<artisan-skill>=artisan" \
    --skill "<apprentice-skill>=apprentice" \
    --skill "<apprentice-skill>=apprentice" \
    --tag <tag> --tag <tag>

# Add inventory, one starting signature move, and the public mirror in one call.
glass character bulk-update --json '{
  "characters": [
    {
      "character_id": "<character-id>",
      "inventory_add": [
        {"id": "<pressure-use-item-slug>", "qty": 1, "effect_tags": ["<specific story or use>"]},
        {"id": "<tool-or-apparatus-slug>", "qty": 1},
        {"id": "<sentimental-item-slug>", "qty": 1}
      ],
      "signature_moves": [
        {
          "name": "<simple move name>",
          "look": "<what it looks/sounds/feels like>",
          "use": "<what kind of problem you reach for it against>",
          "tell": "<trace, cost, risk, or who might recognize it>"
        }
      ],
      "mirror": true
    }
  ]
}'
```

Then write your intro markdown at its real workspace path and commit it:

```bash
glass sync apply players/<your-id>/public/intro.md
```

The `public/` subdir is party-readable; this is the file your fellow PCs will read in round 2. Include:

- Frontmatter with at least `title:` (your character's name) and `type: character`
- A Traits section listing your 3-5 traits
- A Backstory section (3-4 paragraphs)
- A Goals section (2-3 goals)
- An Org Tie line that explains organization membership/standing separately
  from archetype

Do not hand-author `players/<your-id>/public/character.md`. It is generated by
`glass character mirror`.

If you later need to add a move by itself, prefer checking status first:

```bash
glass character signature-status <character-id>
glass character signature-add <character-id> "<move name>" \
    --look "<what it looks/sounds/feels like>" \
    --use "<what kind of problem you reach for it against>" \
    --tell "<trace, cost, risk, or who might recognize it>"
```

Keep it current during play as your character's habits settle. New moves should
be added when repeated play makes them identity-defining, not because an empty
future slot exists.

When your turn ends, that's it for round 1. The other players take their turns; the DM reviews after.

---

## Round 2: Relationship round

Once all four PCs are authored — visible at `players/*/public/intro.md` — each player adds 1-2 relationship ties to other PCs. This is the round that turns four strangers into a party with shared history.

### Process

1. **Read all four intros** at `players/*/public/intro.md`. You're now writing as someone who can see the others' characters.
2. **Pick 1-2 relationship seeds** from the list below. Each seed must name a *specific other PC* — not a generic placeholder. You cannot point both at the same PC if you pick two; each seed must name a different other PC.
3. **Write a paragraph for each seed** filling it in with specifics. Names, places, the particular thing that happened, the particular feeling that lingers. Use the same anti-sameness rigor you used for your backstory — this is shared canon, it should have texture.
4. **Coordinate via the message bus.** If you're picking a seed about a shared event with another PC (the Shear incident, the Reconnection split), fire a `glass msg banter <other-player> "..."` to nail down the basic facts before you write your paragraph. Both your account and theirs should reference the same names, place, and rough sequence of events. If two players write contradictory specifics, the DM may flag it on their round-end turn — you may need to revise on a follow-up turn.
5. **Write the file** at `players/<your-id>/public/relationships.md`, then run `glass sync apply players/<your-id>/public/relationships.md`. Use frontmatter with `title:` (e.g., "<your character>'s relationships") and `type: relationships`.

### The seed list

Pick seeds that *actually fit* the characters involved. Don't shoehorn. If none fit, ask the DM for a custom seed via `glass msg secret dm <reason>`.

1. **The Reconnection split.** We came up through the Reconnection together. You took one path — Conclave, syndicate, independent, something. I took another. We're polite about it now. We don't talk about the year we stopped talking.
2. **The Shear incident.** We were both in the Shear when something went wrong. Neither of us has talked about it to anyone, including each other. We're going to have to eventually.
3. **The off-the-books job.** You owe me for a tuning job / route run / favor I did under the table. I haven't called it in. I'm not sure if I will.
4. **Inherited rivalry.** Your mentor and mine were rivals. We've inherited the awkwardness. Neither of us started it. Neither of us is sure how to end it.
5. **Glasswake recovery.** We were close — friends, lovers, collaborators — before glasswake hit one or both of us. Recovery changed us. We're still figuring out who we are to each other now.
6. **The aborted apprenticeship.** I was your apprentice once. We don't talk about why I left. You think you know. You don't, fully.
7. **The diagnostic I shouldn't have read.** I saw something on a Stillwater diagnostic / Conclave intake / hab record that named you. You don't know I saw it. It's why I trust you. (Or why I don't.)
8. **The Karet route.** Someone you cared about died on a Karet route. I was there. You don't know the whole story. Maybe you should.
9. **The manifest pick.** I picked your name from the manifest for this team. I'll be honest about why if you ask. I've been hoping you wouldn't.
10. **The cultural slip.** We're both Sithari-trained / Hab-Worlder-raised / from the same culture, but you went a different direction after. I notice when you slip back into the formal register / the clipped consonants / the old habits.
11. **The decommissioned hab.** Your hab was decommissioned the year I started running supplies into it. I remember your face from then. You don't remember mine. I'm not sure if I should tell you.
12. **The passage debt.** I owed your family a passage debt. It's settled now, but we both know it shaped us.
13. **The children's choir.** We played together in a children's resonance choir / class / training cohort. The recording / record / photo still exists somewhere. Neither of us mentions this.
14. **The taught thing.** You taught me one specific thing — a knot, a phrase, a tuning trick, a way to hold a tool — that I use every day. I haven't told you it's still yours.
15. **The Echo River disagreement.** We both heard the same Echo River fragment / station-broadcast / overheard conversation last year. We disagree about what it said. The disagreement matters more than either of us admits.

These are seeds, not scripts. Take the structure, fill in the world-specific details (names, places, frequencies, factions). Two players can pick the same seed pointing at each other if it fits — overlapping accounts of the same event are good texture.

### Constraint, restated

**No party-adversarial relationships.** Friction is the goal. Sabotage is not. If your relationship paragraph contains "I'm planning to" or "I'm going to use this against," reframe or pick a different seed. Hidden context is fine; weaponized hidden context is not.

If a relationship pulls in a direction that worries you, message the DM before writing it.

### Done criteria

All four PCs have between 1 and 2 relationships pointing at other PCs. Every PC is referenced by at least one other PC's relationship (no orphan PCs). The DM ends the mode on their round-end turn.

The character_creation phase ends. The DM signals phase-complete and the
campaign moves to the prelude phase. The next DM-facing workflow is
[`prelude-arc.md`](prelude-arc.md): a short two-scene first incident before the
main campaign begins.

---

## What the DM does

The orchestrator gives you a turn after each pass through the players. What you do with it is up to you. Read what's been authored. Push back on anything off-spec via `glass msg secret <player> "revise: ..."`. Write whatever campaign-level prose feels right (`shared/campaign-framing.md` updates, DM notes, secret messages).

You're not pre-approving every character. You're reviewing the party as it forms.

**Closure: end the mode (`glass mode end`) only when both rounds — character build *and* relationships — are genuinely done.** Until then, leave the mode open and the players will get more turns. The phase is over when you say it is.
