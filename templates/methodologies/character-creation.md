---
title: Character Creation Methodology
status: authored
audience: players, dm
---

# Character Creation

The methodology you read during the `character_creation` phase. The DM has already finished campaign-planning and authored the party's organization, the campaign question, and an opening arc with hooks and NPCs. Now you build the character who lives inside that.

This methodology has **two rounds**:

1. **Character round** — each player builds their PC and writes their public intro.
2. **Relationship round** — once all four PCs are authored, each player adds 1-2 relationship ties to other PCs.

Don't start round 2 until round 1 is fully done. Relationships only make sense when there are characters to relate to.

For the mechanical layer (attribute budget, skill budget, HP, inventory rules), read [`character-creation-system.md`](character-creation-system.md). This doc is the *process*. That doc is the *rules*. You need both.

## Trust yourself, follow the rules

You are not asking the DM for permission at each step. There is no propose / ratify loop on character intros, character sheets, or relationships. Read the methodology and the system reference, follow them, and write your files directly.

The DM gets one turn at the end of each round to read what the party authored and transition the phase forward. If a player produces something off-spec — a non-existent species, an attribute budget that doesn't add up, a generic-fantasy backstory that ignored the web pull — the DM can push back via `glass msg secret <player>` and ask for a revision in a follow-up turn. But the default is "you make your character; the DM is not your editor."

This applies to the rest of play too. Make your own rolls via `glass roll`. Take your own HP changes via `glass character set-hp`. Spend your own momentum. The system is the system — don't ask the DM to confirm each mechanical step. Propose / ratify is reserved for **public journal entries** during play (canonical, party-shared lore that the DM might want to fold into the campaign record).

### Things you must run via `glass` (not narrate, not Write-tool)

- `glass character new` — your character row in Postgres. **If you skip this, every later `glass roll` will error: there's no character to roll for.**
- `glass character inventory-add` / `inventory-rm` — items. Inventory is a jsonb column on your character row, not a markdown file.
- `glass roll <skill> <attribute> --risk <level> --character <id>` — every uncertain action. Don't narrate "I rolled a 9"; the dice are the dice.
- `glass character set-hp <id> <delta>` — when you take damage or heal. The number that lives in the DB is the number that's true.
- `glass character set-momentum <id> <value>` — momentum changes from rolls happen automatically; only call this for narrative resets.

Things you write as markdown via your file-write tool (no `glass` involvement):
- `players/<your-id>/public/intro.md`
- `players/<your-id>/public/relationships.md`
- `players/<your-id>/public/character.md` (optional cached display)
- `players/<your-id>/secrets/<name>.md` (optional, DM-readable only)
- Your private journal/drafts/notes/scratchpad — anything under `players/<your-id>/` that isn't `public/`.

### Where files live in your player dir

```
players/<your-id>/
  persona.md            you (the player) — provided by the operator
  scratchpad.md         your working notes — overwrite freely
  public/               party-readable: intros, relationships, cached character display
  secrets/              DM-readable, other-player-private: hidden knowledge files
  drafts/, journal/, notes/, inbox/   private to you
```

Anything you put in `public/` is automatically party-readable (filesystem permissions handle this). Anything you put in `secrets/` is DM-readable but not visible to other players. You don't have to chmod anything — drop the file in the right subdir and the perms follow.

## Round 1: Build your character

### 1. Read before you write

Before authoring anything, read in this order:

- **Your persona** at `players/<your-id>/persona.md` — who you are as a *player*, what you like, what kind of PC you tend to build.
- **The campaign context** at `context.md` (campaign root) — the Question, the Scarcity, the setting, the party's organization, the opening arc summary.
- **The party's organization** at `shared/lore/organization.md` — what the org does, the capabilities it typically needs, the reason the party operates together.
- **The system reference** at [`character-creation-system.md`](character-creation-system.md) — attribute budget, skill budget, inventory rules.
- **Species lore** at `shared/lore/species/` — read the index, then read each species's full page. Don't skim. The texture matters.
- **Cultures and naming** at `shared/lore/cultures/` — both the culture descriptions and the naming conventions. Names follow culture, not species.
- **Whatever lore the DM has curated** at `shared/lore/` — locations, factions, NPCs, concepts.

Reading takes time. Read first. Don't start building while you're still discovering the world.

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
- A signature inventory item (something specific from that world)
- A line or image in your backstory

Generic-fantasy drift is obvious from the page. The DM will see it.

### 3. Choose species and culture

Pick a species from `shared/lore/species/`. Pick a culture (or hybrid) from `shared/lore/cultures/`. These are independent choices — a Sithari orc is a different person from a Hab-Worlder orc.

**Pick the species whose texture you actually want to play with.** Not the one that sounds coolest. The orc whose pain response is muted will play differently than the gnome who feels resonance like temperature. Decide what kind of *experience* you want to inhabit.

Pick a name that follows your culture's naming convention exactly. See `shared/lore/cultures/naming-conventions.md`. Be specific. No "Thorgrim." No "Aelaria." Use the cultural pattern.

### 4. Invent a class / role

There is no class system. Don't pick a class.

Read the org's "capabilities the party typically needs" section in `shared/lore/organization.md`. Those are guidance, not slots. They tell you *what kinds of leverage the org operates by* — not what archetype you have to play.

Invent who your character is. **Capabilities-not-roles.** Examples:

- "Lapsed Tuner who runs supplies into the Shear because she can't get certified work after the Conclave hearing."
- "Hab-Worlder ex-medic, now running a back-channel pharmacy for migrants who can't get processed."
- "Sithari archivist who got reassigned to the field after one too many letters to the wrong person."
- "Orc smith from a Karet route family who took the org job because his sister did."

Notice: each one names a profession (real or invented but world-grounded), gives a reason they're not in their default lane, and points at something specific in the world. None of them is "fighter" or "mage."

The character.md `archetype` field is a short string version of this — "Lapsed Tuner," "Sithari archivist on rotation," "Karet smith on the org payroll." Descriptive, not categorical.

### 5. Allocate attributes and skills

Per [`character-creation-system.md`](character-creation-system.md):

- 7 attributes default to `standard`. Bump 2 to `advanced`, 1 to `superior` (optional). Optionally drop 1 to `rudimentary` as a flaw.
- 5 skills total: 1 `virtuoso`, 2 `artisan`, 2 `apprentice`. Be specific with skill names; pull at least one from your web-search texture.

Choose attributes that match the character you're building. A Lapsed Tuner whose `attunement` is still `superior` makes sense — that's why the loss is sharp. A Hab-Worlder ex-medic with `vitality` at `rudimentary` because chronic exposure has cost her makes sense — the flaw is the story.

### 6. Pick HP and inventory

HP defaults to 10. Take 8 if you're fragile/specialized; take 12 if physical robustness is a defining trait.

Inventory: 3-5 items. **One must be a signature item** with a specific story. The rest are tools-of-trade or sentimental. Read the system reference's inventory examples — generic gear is bounceable.

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

- **Backstory: 3-4 paragraphs.** Where the character is from. What shaped them. How they ended up at the org. **Reference at least one of the DM's planning-phase hooks, NPCs, factions, or locations by name.** This is the connective tissue that makes the campaign actually feel like a place this character lives in.
- **Goals: 2-3 specific goals.** Present-tense. Achievable but with friction. Not "save the world." Not "get rich." Specific things this character is *currently trying to do*. The DM may or may not weave them into the campaign — that's their judgment call. Goals you don't reach are fine.

Examples of good goals:
- "Find out what happened to Rin's last route. Officially I'm not asking. Unofficially I won't stop until I know."
- "Convince my mother to leave the hab before the council certifies it for decommissioning."
- "Earn enough off-the-books to pay back the Karet family I owe."
- "Find someone who knew my old name and wants to know me anyway."

### 9. The org tie

Your intro must explain **why this character is in this organization**, in a way that holds up. Recruited, drafted, owed a debt, ran out of options, was already inside before the campaign starts, family connection, romantic connection, true believer — any narrative reason works as long as it makes coherent sense for who the character is.

The character.md `org_tie` field is a one-line free-form description: what this PC brings to the org and how they got there. Example: `"Tuning expertise the org can't get certified channels for; she joined after the Conclave hearing barred her."`

### 10. Optional: hidden knowledge

You may write **hidden knowledge** to a file the DM can read but other players can't. Drop it under `players/<your-id>/secrets/<name>.md` (the `secrets/` subdir is provisioned DM-readable but party-private) and message the DM via `glass msg secret dm <one-line summary>` so they know to read it. Use it for:

- Alternative motivations (something your character is *also* doing while in the org)
- Backstory the character hasn't told anyone (an old name, a buried debt, a relationship the org doesn't know about)
- Knowledge the character has from before the campaign that the others don't (a face they'd recognize, a place they've been, a phrase that means something specific)
- A skill or capability the character is hiding

**Constraint:** alternative motivations are fine; **direct adversarial relationships with other PCs are not.** Your character can have agendas the party doesn't know about. Your character cannot be planning to betray the party, sell them out, or work against them in a way that would harm another player's enjoyment of the game. The line is: friction enriches play, sabotage breaks it.

If you're not sure where the line is, ask the DM via `glass msg secret dm <reason>` before writing the secret.

### 11. Write your files

**First, announce to the party** so the others know what's being built (avoids two players accidentally building near-identical PCs):

```bash
glass msg table-talk party "I'm building <name>, a <species> <archetype>. <one-line concept>."
```

Then create the character row + inventory:

```bash
# Create the character row in Postgres.
glass character new <character-id> --player <your-agent-id> \
    --name "<full-name>" --archetype "<short-string>" \
    --hp <8|10|12> \
    --attribute <name>=<tier> --attribute <name>=<tier> ... \
    --skill <name>=<tier> --skill <name>=<tier> ... \
    --tag <tag> --tag <tag>

# Add inventory items one at a time.
glass character inventory-add <character-id> <slug> --qty 1
glass character inventory-add <character-id> <slug> --qty 1
```

Then write your intro markdown directly to `players/<your-id>/public/intro.md` using your file-write tool. The `public/` subdir is party-readable; this is the file your fellow PCs will read in round 2. Include:

- Frontmatter with at least `title:` (your character's name) and `type: character`
- A Traits section listing your 3-5 traits
- A Backstory section (3-4 paragraphs)
- A Goals section (2-3 goals)
- An Org Tie line

Optionally write a short cached display at `players/<your-id>/public/character.md` with attribute/skill/inventory summary for quick reference. The canonical numbers are in Postgres; this is just a human-readable mirror.

When your turn ends, that's it for round 1. The other players take their turns; the DM reviews after.

---

## Round 2: Relationship round

Once all four PCs are authored — visible at `players/*/public/intro.md` — each player adds 1-2 relationship ties to other PCs. This is the round that turns four strangers into a party with shared history.

### Process

1. **Read all four intros** at `players/*/public/intro.md`. You're now writing as someone who can see the others' characters.
2. **Pick 1-2 relationship seeds** from the list below. Each seed must name a *specific other PC* — not a generic placeholder. You cannot point both at the same PC if you pick two; each seed must name a different other PC.
3. **Write a paragraph for each seed** filling it in with specifics. Names, places, the particular thing that happened, the particular feeling that lingers. Use the same anti-sameness rigor you used for your backstory — this is shared canon, it should have texture.
4. **Coordinate via the message bus.** If you're picking a seed about a shared event with another PC (the Shear incident, the Reconnection split), fire a `glass msg banter <other-player> "..."` to nail down the basic facts before you write your paragraph. Both your account and theirs should reference the same names, place, and rough sequence of events. If two players write contradictory specifics, the DM may flag it on their round-end turn — you may need to revise on a follow-up turn.
5. **Write the file** directly to `players/<your-id>/public/relationships.md`. Use frontmatter with `title:` (e.g., "<your character>'s relationships") and `type: relationships`.

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

The character_creation phase ends. The DM signals phase-complete and the campaign moves to active play.

---

## What the DM does

The orchestrator gives you a turn after each pass through the players. What you do with it is up to you. Read what's been authored. Push back on anything off-spec via `glass msg secret <player> "revise: ..."`. Write whatever campaign-level prose feels right (`shared/campaign-framing.md` updates, DM notes, secret messages).

You're not pre-approving every character. You're reviewing the party as it forms.

**Closure: end the mode (`glass mode end`) only when both rounds — character build *and* relationships — are genuinely done.** Until then, leave the mode open and the players will get more turns. The phase is over when you say it is.
