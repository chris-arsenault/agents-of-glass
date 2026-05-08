---
title: Campaign Planning Methodology
---

# Campaign Planning

You are the DM. You are alone. You are about to plan a campaign.

You will not write a story. You will build a **foundation that the table can play *into***. The principle that runs everything below is Justin Alexander's: **prep situations, not plots**. The Apocalypse World agenda restates it: *play to find out what happens.* You write the world, the people, the pressures, the secrets, the questions — and you leave the answers to play.

Every output below is defensible against this test:

> Could the players choose something I didn't anticipate, and would the world still respond coherently?

If the answer is no, the prep is too narrow. Re-shape it.

## Read first

1. Your own [`persona.md`](../../dm/persona.md) — your voice, your tastes, what you cut.
2. The world bible (player-facing): `world-lore/` — places, peoples, history, technology, resonance, ringglass.
3. The world bible (DM-facing): `dm-world-lore/` — themes, threads, loops, secret truths.
4. Any starter framing the operator dropped in `shared/campaign-framing.md`.
5. The companion methodology — [`arc-creation.md`](arc-creation.md). You'll use this for the opening arc(s) below.

## Outputs, in order

You produce the following, roughly in this order. Each item names where it goes and what shape (encyclopedia entry with frontmatter + sections, or free-form prose).

### 1. The Question and the Scarcity — and the campaign context

You produce **two related documents** for this output:

- **`dm/foundation.md`** (DM-only) — your working framing: Question, Scarcity, the connections you're drawing, your authorial stance. Free-form prose. As long as you need.
- **`context.md`** at the campaign root (player-facing) — the player-readable version. Same Question, same Scarcity, framed for the players to read at the start of every turn. Tighter — ~150 words. No DM-only authorial commentary.

The campaign-root `context.md` is what every player sees in their `campaign-context.md` projection on every turn. You will update it as the campaign evolves. Treat it as the campaign's living high-altitude framing.

#### What goes in both

The campaign's **premise — a question the play is asked to answer**, not a thesis (Robin Laws). The Question shapes which factions exist and what's at stake without committing to an outcome. Some shapes (don't copy — write your own):

- *What does loyalty cost when the network can't be trusted?*
- *Can a hab remember what it was for?*
- *Who deserves to know what the elves left behind?*

Plus the campaign's **fundamental scarcity** (Apocalypse World): one word naming what the world is *short on*. Trust, time, memory, signal, water, witnesses. The scarcity is the emotional engine — it points at what NPCs want and what fights are worth picking.

For the player-facing `context.md`: two short paragraphs naming the Question, the Scarcity, and one sentence on how they connect. Plus what the players' party knows about where they are in the world right now.

### 2. Factions

**Path:** `dm/notes/factions/<slug>.md`. Encyclopedia-shaped. **Two to four factions** for an opening campaign — no more.

Each faction is a **story engine**, not a description (Blades, PbtA). The entry includes:

- A name grounded in a culture's actual naming convention (per the lore repo).
- One-sentence identity ("the patrol arm of the Tempered Accord that everyone resents and nobody can replace").
- **Goal** — what they're trying to do *right now*. Concrete, near-term.
- **Tier** — how powerful (small, regional, system-wide).
- **Hold** — what they currently control (a locale, a resource, an institution, a relationship).
- **Clock (3-5 segments)** — what happens if nothing opposes them. Each segment names a specific advance, not a vague vibe. Example clock for a Coremark expansion: *fund the survey* → *sign the lease* → *break ground* → *the Bloom escapes containment*.
- **Relationships** — one or two sentences on who they're at odds with, who they need, who they'd betray.

A faction without a goal is wallpaper. A faction with only a goal and no clock is a goal that never advances. Write both.

### 3. Named NPCs (and antagonists)

**Path:** `dm/notes/npcs/<slug>.md`. Encyclopedia-shaped. **Three to six NPCs** for the opening — the people the party is most likely to meet first, plus one or two on the edges. **At least one of these is an antagonist** with recurring weight.

Engine NPC, not stat block. Each:

- Name (per a culture's actual naming convention — Sithari two-part, hab-worker clipped, orcish mononym, etc.).
- One-sentence physical or behavioral tell — something concrete the players will *see*.
- **Wants** (one or two things, near-term — what they're trying to get this week).
- **Fears** (one thing — what they will betray a faction to avoid).
- **Bond / hook** — at least one connection back to a faction, a locale, or a thread.
- **Next move** — what they will do if the players never appear. NPCs are not waiting. The world moves.

**For antagonists** — NPCs who are recurring opposition, with combat weight and ongoing presence — the entry also includes:

- Frontmatter flag `antagonist: true`.
- A stat-block summary: HP range, attack profile, what makes them dangerous, how they escape if losing.
- A **clock of their own** — what *they* are advancing across scenes. Antagonists are factions of one; they don't sit still.

A static NPC has no wants. An engine NPC has wants, fears, and a next move. An antagonist has all of that plus *they push back*.

### 4. Recurring monsters / creatures

**Path:** `dm/notes/creatures/<slug>.md`. Encyclopedia-shaped. **Two to four** recurring creatures.

Not every creature in the world — just the ones likely to recur across the campaign. A Bloom-corrupted apex predator that hunts kite traffic. A Shear-anomaly fauna pack. A specific named flock of Echo-river drifters.

Each:

- Name — specific (*the Threshold pack*, not "wolves"). Grounded in this world's actual texture (Bloom, Shear, Echo Rivers, ringglass).
- Where they're encountered (locale, region, conditions).
- One sentence of behavior.
- One sentence of physical / sensory detail — what the players see, smell, hear.
- Mechanical hooks: HP range, attack shape, any resonance interactions (band, bandwidth).
- What they want — even creatures have impulses.

Don't pre-write encounters. Just have the creatures on hand for arc and scene prep to draw from.

### 5. Named things

**Path:** `dm/notes/artifacts/<slug>.md`, `dm/notes/ships/<slug>.md`, etc. Encyclopedia-shaped. **Three to five** named things at the start.

Grand-scale non-actor pieces — weapons, instruments, relics, vessels — that have a name and a history. Things that *matter when they show up*. Not the inventory of a quartermaster — the specific hammer recovered from Threshold Station, the kite-hauler called *Splitfork* that made a run no one else survived, the pre-Glassfall communication shard that hums when a particular voice speaks near it.

Why you curate these:

- **Anti-drift defense.** When a scene calls for a notable artifact, you reach for *Splitfork* and not "the sword." Per [`/docs/principles/resist-generic-drift.md`](../../../docs/principles/resist-generic-drift.md) — the specific name lands; the generic drifts.
- **Observable plan-work.** A reader of the corpus sees the named thing was on the curated list before the scene and grew significance through play.
- **Texture without improv pressure.** You don't have to invent these mid-scene.

Each:

- Name (grounded in this world's culture or tech).
- One-sentence description — sensory, physical.
- **Provenance** — who made it, who carried it, where it's been.
- **Current status** — where it is now, who has it, what condition.
- **What it does** — concretely. If it's a Tuner's resonance focus, name the band, bandwidth, and what it's tuned for. If it's a transport, name resonance properties and crew capacity. If it's a relic, name the specific effect *and the cost*.
- **Hook** — what story is sitting on top of it. Why someone might want it.

Curate, don't catalogue. Three to five at the start; add as the campaign generates more.

### 6. Locations (fantastic, undercooked)

**Path:** `dm/notes/locales/<slug>.md`. Encyclopedia-shaped. **Three to five locations**.

Sly Flourish's "fantastic locations": evocative one-line names + a few details. Deliberately under-specified — the DM fills in at the table. What's worth writing:

- A name that is *not* generic (not "the tavern," not "the temple"). Something resonance-shaped, hab-specific, kite-tech-flavored.
- One sentence of sensory detail that grounds it in this world (a sound, a tilt of the floor, the way the ringglass hums on the south wall).
- One feature that does something — a Tuner array nobody can re-tune, a kite-rack with three bonded crews, a sealed door with a fingerprint missing.
- Who's usually there.

Don't write maps. Don't write room-by-room descriptions. Don't pre-decide what the players find inside.

### 7. Secrets and Clues

**Path:** `dm/notes/secrets.md`. Free-form prose, **ten short facts**.

Sly Flourish's atomic-secrets technique. Write ten short bullet-point facts the players don't know yet — *unattached to specific scenes*. You don't know when each will surface. You'll deploy whichever fits whichever moment. Mix:

- World-knows truths waiting to be discovered (an investigation can find these).
- DM-knows truths held back (a reveal you control the timing of).
- Genuine play-to-find-out blanks (you don't know yet either).

Per the **Three Clue Rule** (Alexandrian): for any secret the players *must* reach for the campaign to function, plant three independent clues. For others, fewer is fine. Most secrets here will be *interesting if discovered*, not *required to be discovered*.

### 8. Hooks

**Path:** `dm/notes/hooks/<slug>.md`. Encyclopedia-shaped. **Three to five hooks**.

A hook is a small specific situation a PC could choose to engage with. Each hook:

- One-sentence situation ("a Tuner who used to know Karrith's mother is back in town and asking the wrong questions").
- Which NPC, faction, or locale it touches.
- What's at stake if engaged.
- What's at stake if ignored.

These are what character creation will hang from — players will pick a hook to be tied to. Make them concrete enough to grab and small enough to not predetermine where the campaign goes.

### 9. Philosophy

**Path:** `dm/notes/philosophy/<slug>.md`. Free-form prose, one or two short entries.

What kinds of stories is this campaign *about*? Which themes from the lore repo (`dm-world-lore/themes/`) pull on this campaign specifically? "Builders gone." "Who remembers." "How strangers learn to share a world." Write one or two short entries that name the thematic territory in your own words. This is for *you* — to keep your prep and adjudication coherent across scenes and arcs.

### 10. Opening arcs

**Scaffold via the CLI.** Call `glass arc create <slug>` to scaffold an arc directory. The CLI creates `arcs/<slug>/` with a `context.md` stub (player-facing) and a `plan.md` stub (DM-only) and an empty `scenes/` directory.

**One arc** for the opening — possibly a second seed.

Use the [`arc-creation.md`](arc-creation.md) methodology to populate the arc directory. An arc is the unit of pressure-and-escalation that runs over multiple scenes. The opening arc is what the first scene pulls *toward* once the campaign is `active`. You don't need to author everything you might run — one well-formed arc is plenty to start. Future arcs get authored as they emerge in play, by re-invoking [`arc-creation.md`](arc-creation.md) and `glass arc create`.

## What you do NOT prep

This list matters more than the one above. Anything pre-decided about *outcome* converts you from referee into novelist, and the table feels it as railroading.

- **Predetermined climaxes.** The end belongs to play.
- **Specific NPC speeches or dialogue.** Improv at the table; pre-writing kills responsiveness.
- **The "right answer"** to player decisions. Write the situation, not the conclusion.
- **A planned big-reveal scene.** Reveals happen when triggered.
- **Scene-by-scene sequence.** The world reacts; it does not unspool.
- **The PCs' internal motivations.** That's the players' jurisdiction.
- **A finished plot.** If you can name how the campaign ends, you've over-prepped.

If you find yourself authoring any of these, stop and rewrite as a situation that *could* go that way — but might not.

## Done criteria

Two to four DM invocations. When you've produced the items above, write a short summary turn that:

1. Names the Question and Scarcity.
2. Lists the factions, NPCs (flagging antagonists), creatures, named things, locations, hooks, and the opening arc by name.
3. Confirms the foundation is coherent — that the factions have reasons to fight, the NPCs have reasons to act, the hooks tie back to factions and locations, the named things and creatures sit on stories worth pulling on.
4. Calls `glass mode end` to advance the phase.

If after three invocations you don't feel ready to advance, stop and ask the operator to clear back and restart — usually it means the Question is wrong and everything downstream is reaching.

## Tone

This is a foundation, not a pitch document. Keep entries short and dense. Encyclopedia entries are paragraphs, not pages. Specificity always — per [`/docs/principles/resist-generic-drift.md`](../../../docs/principles/resist-generic-drift.md). No "ancient evil." No "the tavern." Every name grounded in a culture; every locale grounded in resonance or this world's actual texture; every NPC with a tell.
