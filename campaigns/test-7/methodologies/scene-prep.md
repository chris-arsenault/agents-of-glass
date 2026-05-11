---
title: Scene Prep Methodology
---

# Scene Prep

Third level of DM prep, beneath [`campaign-planning.md`](campaign-planning.md) (the world) and [`arc-creation.md`](arc-creation.md) (multi-scene pressure units). Scene prep is **what you bring to the next scene**.

A scene has a protocol/toolkit label. Use common labels when they fit
(`scene-play`, `action`, `travel`, `montage`, `town`, `combat`, `chase`,
`social-pressure`), but the list is not exhaustive. The label points the DM
toward a turn protocol; it does not define every possible kind of scene.

This methodology is invoked **before each new scene** in active play. The orchestrator can run it on demand or fold it into the DM's first turn of the scene. Light, short, re-readable.

The principle remains the same: **prep situations, not plots**. At the campaign and arc level the unit is "the world is set up to react"; at the scene level the unit is "I have a strong start and a handful of things in play." Sly Flourish's *Lazy Dungeon Master* is the direct ancestor of this layer.

## Command discipline

When `scene-prep` is the active mode, use it as a DM-only handoff into actual
table play. Before ending the turn, create the scene, commit the scene/table
files, end `scene-prep`, and start the scene's actual play mode:

```
glass scene create <slug> --type <protocol-or-toolkit-label> --arc <arc-if-needed>
glass sync apply arcs/<arc>/scenes/<slug> table
glass mode end
glass mode start <protocol-or-toolkit-label> <slug>
```

If the next act follows an intermission, read the intermission turns first and
let player requests affect emphasis, rewards, unresolved threads, and what gets
summarized rather than played. Do not treat requests as binding outcomes.

## Scaffolding the scene directory

Before you write anything, scaffold the scene with:

```
glass scene create <slug> --type <protocol-or-toolkit-label>
```

The CLI creates `arcs/<active-arc>/scenes/<slug>/` with:
- `prep.md` — DM-only working document (the eight sections below).
- `context.md` — player-facing scene framing.
- `transcript.md` — empty; gets populated as the scene plays.
- `audit.jsonl` — empty; populated by `glass` calls during the scene.

It also resets the live public table at campaign root:

- `table/index.md` — at-a-glance visible state.
- `table/scene.md` — the scene kickoff description.
- `table/handouts/` — in-game handouts.

Everything else at `table/` root is freeform and created only when useful.
The table is the player-agent-visible board. It is not an automatic projection
of DM notes, graph entities, hooks, NPC files, or monster files; if players
should reason from one of those during the scene, place the visible part under
`table/`.

If the scene belongs to a different arc, pass `--arc <arc-slug>` explicitly.
Write into the new scene directory, then commit the scene documents and table
with `glass sync apply arcs/<arc>/scenes/<slug> table`.

## Read first

1. Your own [`persona.md`](../../dm/persona.md).
2. The campaign foundation: `context.md` at the campaign root, `dm/notes/philosophy/`.
3. The active arc(s): `arcs/<active>/plan.md`. If multiple arcs are in play, all of their plans.
4. The most recent scene's transcript and audit log.
5. The curated lists in `dm/notes/`: NPCs (especially antagonists), factions, creatures, artifacts, ships, locales. You are pulling *from* these for what's in play this scene.

## On-demand lore imports

If this scene surfaces world-bible content not yet in `shared/lore/` — the players walk into a locale that's only sketched in canon, an NPC references a creature the campaign hasn't met before — call:

```
glass lore import <world-bible-path>
```

Just-in-time curation. The world bible is your reference; campaign lore is the curated subset. See the [campaign-planning curation principle](campaign-planning.md#curate-dont-copy).

## Anti-sameness pulls (required, light at this scale)

The scene level needs less of this than campaign or arc, but it's not zero — back-to-back scenes with the same texture is the most common drift failure. Two small pulls. (Full principle: [`campaign-planning.md`](campaign-planning.md#anti-sameness-pulls-do-this--it-is-not-optional).)

- **Lore pull (1-2 entries you weren't planning to use).** Use `glass lore search <query>` to find something in the configured lore repo that doesn't directly touch this scene's locale or NPCs. Take one concrete detail — a sensory fact, a piece of history, a name. Land it somewhere in the scene's strong start, an NPC tell, or the locale framing.
- **Creative web pull (1, optional but encouraged).** A short web search on something *outside fantasy and outside TTRPGs*. Current events, an architectural detail, a recipe, an obituary, a science article — anything specific from the real non-fictional world. Pull one texture (a sensory detail, a fragment of language). Let it inform the strong start's atmosphere or one NPC's behavioral tic. Texture, not content.

If the prior scene already had the pulls done and the new scene is a continuation in the same locale with the same NPCs, one pull is enough. If you're moving to a new locale, NPCs, or arc focus, do both.

## Outputs

You produce **two documents** in `arcs/<arc>/scenes/<slug>/`:

- **`prep.md`** (DM-only) — your working scene prep. Encyclopedia-shaped. Eight sections below. Short. You will re-read this during the scene and update during play.
- **`context.md`** (player-facing) — what the players see when the scene starts, and what stays in their CWD as `scene-context.md` while the scene runs. Locale, who's there, what's happening. No DM-only secrets, no prep, no hooks-not-yet-revealed.

The prep has the full picture. The context has only what's framed for the table.
The scene `summary.md` starts as a stub and is finalized by
`glass scene end --summary --outcome`; do not use it as scene framing while
play is still moving.

You also update the live table when the scene begins:

- Put the opening scene description in `table/scene.md`.
- Keep `table/index.md` short and current: what is visible now, what files are
  relevant, public trackers, immediate questions.
- Add freeform table-root files only for immediate visible references players
  are likely to need during play.
- Put notices, pictures, maps, letters, diagrams, and other in-game handouts in
  `table/handouts/`.
- Do not rely on DM notes or graph state being "active" to put something on the
  table; the table is exactly the files under `table/`.

`prep.md` has these sections:

### 1. Recap

One paragraph summarizing what happened in the previous scene — concrete, not vibes. What did the party do, where did they end up, what's in motion.

This text feeds into the player-facing `context.md` for the new scene.

### 2. Strong start

The opening of the scene. Sly Flourish: *arrive at the table with a strong start ready*. One paragraph: the locale, who's present, what's about to happen, the hook the party will see in the first thirty seconds.

A strong start is not a teaser; it's the actual first action the players walk into. Specific named locale, specific named NPC or thing in motion.

### 3. Possible directions (3-5)

Where the scene could go from here. Unranked, ungrouped, not sequenced. Each:

- **What might happen** (the situation).
- **Who's there** (named NPCs from your list).
- **What's at stake** if it plays out.
- **The hook** that opens it.

Don't author the order. Don't author conclusions. The players choose; you respond. Some of these directions will not be played this scene — that's fine, they live forward.

### 4. NPCs in play

Pointers, not new authoring. List the NPCs from `dm/notes/npcs/` you expect to surface — link by name. For each, one line of *what they want this scene*. If a new NPC is needed, draft a short stub here and migrate to `dm/notes/npcs/` after the scene.

### 5. Antagonists, creatures, threats

Pointers from your curated lists. Which `antagonist: true` NPCs are pushing on the scene. Which `dm/notes/creatures/` entries might be encountered. Which arc clocks might tick during this scene, and what segment.

For each: one line. The detail lives in their existing entry; you read that during play if needed.

If this may become an action scene, prep the honest tracker shape now: what
numeric endpoint would players see, what hidden danger clock might tick, and
what happens when each fills. Do not wait until the third action turn to decide
what "winning" means. For pressure targets, also decide any known resistance:
how hard the target is to affect, and whether it rarely reduces impact.

If the pressure is supposed to survive this scene, use a durable clock instead
of a scene tracker:

```bash
glass clock set <clock-id> --scope arc --anchor <arc-id> --max 5 --public
```

### 6. Named things in play

Pointers to artifacts, ships, instruments, relics that might surface — from
`dm/notes/artifacts/` and `dm/notes/ships/`. Reach for the curated list. **This
is the anti-drift defense in action**: when a scene calls for a notable item,
you reach for *Splitfork* or the *Threshold hammer*, not "the ship" or "the
sword."

If the scene requires a new named thing, draft a short stub here and migrate to the appropriate directory after the scene.

### 7. Secrets that might surface

From `dm/notes/secrets.md` and the active arc's secret list, name **one to three** that could plausibly surface this scene. You don't have to use them; they're at hand. Sly Flourish's atomic-secrets technique — deploy whichever fits.

### 8. Open questions

What you, the DM, are *genuinely unsure of* heading into this scene. Apocalypse World agenda: *play to find out what happens*. Naming the questions explicitly is how you commit to not pre-deciding their answers.

> *Will Sumi's PC actually side with the patrol leader, or has the table moved past that?*
> *If the players go to the Keel before checking on Mork's contact, does the contact still survive?*
> *Has anyone noticed that Karrith's been hiding the cord?*

These are notes to yourself. The questions get answered through play — not by you, in advance.

## What you do NOT prep

- **The conclusion of the scene.** Conclusions are emergent.
- **NPC dialogue.** One line of voice flavor max — improvise the rest at the table.
- **The players' reactions or decisions.** Their jurisdiction.
- **"How the scene ends."** The end belongs to play.
- **A new arc.** If a scene seems to want a new arc, note it for after — go through [`arc-creation.md`](arc-creation.md) deliberately, not in passing.

If you find yourself authoring more than two pages, you're over-prepping. Stop, trim, leave room.

## Done criteria

Single invocation, usually. When you've got the strong start, 3-5 possible directions, the things-in-play lists, and a tight `context.md` for the players, stop. Exit; the orchestrator advances to running the scene.

## Tone

`prep.md` is a working document. You will read it during the scene. Keep it short and concrete.

`context.md` is the player-facing framing — the locale, the situation, who's here, what just happened. Players see it as `scene-context.md` in their CWD throughout the scene. Update it if the scene shifts substantially mid-play.

Names everywhere — pull from the curated lists. Specificity always. Generic
prep produces generic scenes; specific prep produces scenes worth a transcript.
