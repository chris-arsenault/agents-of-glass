---
title: Arc Creation Methodology
---

# Arc Creation

The companion to [`campaign-planning.md`](campaign-planning.md). An arc is the **unit of pressure that runs across multiple scenes**. Different traditions call it a *front* (PbtA), a *scenario* (Alexandrian), a *score-cluster* (Blades). Same idea: a coherent thing that can play out over a handful of scenes, with internal escalation and multiple plausible endings.

This methodology is invoked:

1. **During campaign planning** — to author the opening arc(s). Called from [`campaign-planning.md`](campaign-planning.md).
2. **During active play** — when a new arc has emerged from what the players are doing, and you want to formalize it before it runs.

Either way, the principle is the same: **shape, not script**. An arc has a silhouette — pressure, escalation, branching ends — but the path through it is play.

## Scaffolding the arc directory

Before you write anything, scaffold the arc with:

```
glass arc create <slug>
```

The CLI creates `arcs/<slug>/` with:
- `plan.md` — DM-only working document (the seven sections below).
- `context.md` — player-facing summary, populated as the arc develops.
- `scenes/` — empty directory; scenes get scaffolded with `glass scene create` later.

Write into the new directory. Commit the arc documents with
`glass sync apply arcs/<slug>` when the draft is ready.

## Read first

1. Your own [`persona.md`](../../dm/persona.md).
2. The campaign foundation: `shared/campaign-framing.md`, `dm/notes/factions/`, `dm/notes/npcs/`, `dm/notes/philosophy/`, `dm/notes/creatures/`, `dm/notes/artifacts/`, `dm/notes/ships/`.
3. If you're authoring this arc mid-campaign: the recent transcript and any threads the arc emerged from.
4. The world bible's DM-facing threads and loops. Use `glass lore search <query>` to locate candidates in the configured lore repo; these are authorial scaffolding patterns the lore explicitly invites you to use.

## On-demand lore imports

If this arc surfaces world-bible content not yet in the campaign's curated lore (a faction the players are about to deal with, a creature that shows up in the strong start, an artifact a threat is chasing), call:

```
glass lore import <world-bible-path>
```

Curate as you author. Don't pre-import speculatively. Per the [campaign-planning curation principle](campaign-planning.md#curate-dont-copy) — the campaign lore is a deliberate subset, not a snapshot of the bible.

## Anti-sameness pulls (required)

Same principle as in [`campaign-planning.md`](campaign-planning.md#anti-sameness-pulls-do-this--it-is-not-optional) — generic arcs collapse to the same handful of attractors (the noble sacrifice, the betrayal twist, the mysterious cabal). Two pulls protect against this. Both are required.

- **Lore pull (3-4 across this arc).** Before authoring the stakes question, the threats list, and the strong start, read something in the world bible you weren't planning to use. Pull one specific detail; let it land in the arc as texture.
- **Creative web pull (1-2 across this arc).** A short web search on something unrelated to TTRPGs and unrelated to fantasy. Pull one texture — a sensory detail, a fragment of language, a piece of human-scale truth — and let it inform a threat's impulse, a clock's middle segment, or the strong start's atmosphere. Texture, not content.

Mid-campaign arcs especially: the easy attractor is to mirror what already happened in earlier arcs. Pull aggressively to push the new arc somewhere the campaign hasn't been.

## Outputs

You produce **two related documents** for each arc, both inside the directory `arcs/<slug>/` that `glass arc create` scaffolded:

- **`plan.md`** (DM-only) — the working arc plan. Encyclopedia-shaped, the nine sections below. One to two pages — long enough to be coherent, short enough that you'll actually re-read it before each scene.
- **`context.md`** (player-facing) — a short summary of what the players know about this arc. Initially terse — what they've seen so far, who's involved, what's at stake from their POV. You update it as the arc plays out and the players discover more.

The plan has the full picture. The context has only what the players have been shown.

`plan.md` has these sections:

### 1. The stakes question

One sentence. The question this arc is asking that **you, the DM, do not yet know the answer to** (Apocalypse World, *play to find out what happens*).

> *Will the patrol leader betray the Accord, or hold the line?*
> *Can the party convince the Tuner Conclave to act before the Bloom escapes containment?*
> *Who actually has the cord — and who's willing to die for it?*

If you can answer the stakes question right now, you don't have an arc. You have a planned scene. Reshape until you have a real question.

### 2. The threats (2-4 of them)

Each threat is a person, place, faction, or condition with **its own impulse** — what it wants to do if no one stops it. Threats are how Apocalypse World structures pressure: a coherent bundle of forces with active agency.

Each threat:

- Name (existing NPC, faction, antagonist, creature, named thing, or location from `dm/notes/`, or new — if new, also draft a stub for the appropriate directory).
- One-sentence identity in the context of *this arc*.
- **Impulse** — what it wants. Verb-shaped. ("To consume." "To isolate and dominate." "To get out and never come back." "To prove the Conclave wrong.")
- **What it does between scenes** if the players don't engage.

Threats are linked — they share scarcity, contested territory, or interlocking goals. Loose collections of unrelated threats are not an arc.

A note on antagonists: if this arc has a **specific recurring antagonist**, they are usually one of the threats. Their entry in `dm/notes/npcs/` (with the `antagonist: true` flag) is the canonical home — the threat reference here is just a pointer plus the arc-specific impulse.

### 3. Clocks (1-3 of them)

A clock is escalation as a track. **3-5 segments per clock**, each segment a specific advance, not vague pressure. Clocks tick when the players don't intervene — and may tick from off-screen events the players caused obliquely.

Examples:

- *The Bloom containment cracks*: pressure rises in the array → a maintenance crew goes silent → the array's southern lattice fails → resonance bleeds into the Keel → containment fails entirely.
- *The patrol leader's loyalty*: she takes a meeting with Coremark → she briefs her squad → she gives the order → she's gone.

A clock is what makes the world feel like it's moving. Without one, the arc is static and waits for the players to poke it.

If a clock should survive across scenes, create it with `glass clock`.
Public clocks appear in `shared/clocks.md` and `arcs/<arc>/clocks.md` for
players to reference.

```bash
glass clock set accord-crackdown --scope arc --anchor <arc-slug> \
  --label "Accord crackdown" --max 5 --public
```

### 4. Possible end-states (3-5 of them)

Brainstorm the **shapes the arc could resolve into**. Not "what will happen" — what *could* happen, given the threats and clocks. Three to five options, each one or two sentences.

> *Patrol leader publicly defects; the Accord absorbs her surviving squad; Coremark loses its inside angle.*
> *Patrol leader dies covering the party; her replacement is worse.*
> *Coremark gets the lease but loses public legitimacy; arc continues into a containment-failure arc next.*
> *Party never engages; Bloom escapes; this arc ends as a campaign-shifting failure.*

These are not your script. You will not pick one. They are the **silhouette** — the outer shape of what's plausible, which keeps you grounded when the table goes somewhere unexpected. If the actual end isn't in the list, that's fine; the list was for thinking.

### 5. The strong start

One scene the arc could *open with* — the entry point. Sly Flourish: arrive at the table with a strong start ready. This is *not* the arc's plot; it's the first scene that puts the threats in motion in a way the party can hook into.

Concrete: locale, who's there, what's about to happen, the hook the party will see. One paragraph.

### 6. Nodes (3-5 of them)

Justin Alexander's node-based scenario design. A node is a **place, person, or situation the players might investigate**. Each node has clues that point to other nodes — the players navigate by information, not by your sequence.

Each node:

- One-line identifier.
- What's there (people, things, atmosphere — short).
- What can be learned here.
- **Clues to other nodes** — at least two outbound, ideally to two different nodes.

For any conclusion the arc *requires* the players reach (a reveal that has to land for the arc to function), the **Three Clue Rule** applies: plant three independent clues across the nodes. For everything else, less density is fine.

You are *not* authoring the order of visits. You are authoring the graph.

### 7. What from the curated lists is in play

Pointers, not new authoring. List which existing entries from `dm/notes/` this arc draws on:

- **Antagonists** — which NPC(s) flagged `antagonist: true` are recurring opposition here.
- **Creatures** — which `dm/notes/creatures/` entries might be encountered.
- **Named things** — which `dm/notes/artifacts/` or `dm/notes/ships/` entries are present, contested, or sought.
- **Locations** — which named locales the arc moves through.

If the arc *needs* a thing or a creature that doesn't exist on the curated list,
draft a stub for the appropriate directory and reference it here. Specific named
things are a defense against generic drift — reach for the list before
improvising.

### 8. Arc-specific secrets

**Three to seven** atomic facts about this arc that the players don't know yet. Same shape as `dm/notes/secrets.md` — short bullet-point facts, deliberately unattached to specific scenes. Mix world-knows-but-hidden, DM-knows-but-saving, and play-to-find-out blanks.

### 9. Done criteria

When does the arc end? In one short paragraph: name the conditions under which you will declare the arc resolved. Usually it's *the stakes question gets answered* (any way) — but spelling it out in advance helps you spot the moment when it lands.

You may also note the conditions under which you'd **abandon** the arc — the players obviated it, ignored it long enough that it ran its course off-screen, or pivoted to something the table cared more about. An arc that should have ended but didn't is a closure failure.

When the arc/act closes, follow [`closeout.md`](closeout.md) in order, then call:

```bash
glass arc close <arc-id> --summary "..." --outcome "..."
```

Use one or two `--outcome` bullets. Write them in universe: what became true,
what changed hands, who paid, who gained leverage, what scar or obligation now
exists. Hidden mysteries can remain hidden, but the arc's core tension cannot
close as "unknown"; commit to the consequence and impact.

## What you do NOT prep

- **A scripted progression.** The players move; the arc reacts. The reverse is railroading.
- **NPC dialogue.** Improvise at the table from the NPC's wants and fears.
- **The end-state you secretly want.** Brainstorm 3-5; commit to none.
- **The scene-by-scene sequence.** Scenes emerge from where the players are; arcs run over many of them in unpredictable order.
- **The "right" outcome.** Some end-states will be sad. Some will be unjust. Some will reshape the campaign. Let them.

## Tone

`plan.md` is your working document — you will re-read it before each scene that touches the arc. Keep entries short and concrete. Players never see `plan.md`.

`context.md` is the player-facing summary. Keep it terse and updated. Show only what the players have been shown.

Specificity always. Threats and clocks grounded in this world. No "ancient evil
rising." No "shadowy cabal." When in doubt about a thing, name it from your
curated list before reaching for a generic.
