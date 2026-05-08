---
title: Scene Prep Methodology
---

# Scene Prep

Third level of DM prep, beneath [`campaign-planning.md`](campaign-planning.md) (the world) and [`arc-creation.md`](arc-creation.md) (multi-scene pressure units). Scene prep is **what you bring to the next scene**.

A scene is a typed unit of play — town, exploration, combat, social, investigation, travel/montage, wrap. The type determines the turn protocol (see [`/docs/design/modes.md`](../../../docs/design/modes.md)). One scene runs as long as it runs; there's no session boundary forcing it to end at the four-hour mark.

This methodology is invoked **before each new scene** in active play. The orchestrator can run it on demand or fold it into the DM's first turn of the scene. Light, short, re-readable.

The principle remains the same: **prep situations, not plots**. At the campaign and arc level the unit is "the world is set up to react"; at the scene level the unit is "I have a strong start and a handful of things in play." Sly Flourish's *Lazy Dungeon Master* is the direct ancestor of this layer.

## Scaffolding the scene directory

Before you write anything, scaffold the scene with:

```
glass scene create <slug> --type <town|exploration|combat|social|investigation|travel|wrap>
```

The CLI creates `arcs/<active-arc>/scenes/<slug>/` with:
- `prep.md` — DM-only working document (the eight sections below).
- `context.md` — player-facing scene framing.
- `transcript.md` — empty; gets populated as the scene plays.
- `audit.jsonl` — empty; populated by `glass` calls during the scene.

If the scene belongs to a different arc, pass `--arc <arc-slug>` explicitly. The orchestrator picks up the new directory automatically; you don't manage it by hand.

## Read first

1. Your own [`persona.md`](../../dm/persona.md) and [`scratchpad.md`](../../dm/scratchpad.md).
2. The campaign foundation: `context.md` at the campaign root, `dm/notes/philosophy/`.
3. The active arc(s): `arcs/<active>/plan.md`. If multiple arcs are in play, all of their plans.
4. The most recent scene's transcript and audit log.
5. The curated lists in `dm/notes/`: NPCs (especially antagonists), factions, creatures, artifacts, ships, locales. You are pulling *from* these for what's in play this scene.

## Outputs

You produce **two documents** in `arcs/<arc>/scenes/<slug>/`:

- **`prep.md`** (DM-only) — your working scene prep. Encyclopedia-shaped. Eight sections below. Short. You will re-read this during the scene and update during play.
- **`context.md`** (player-facing) — what the players see when the scene starts, and what stays in their CWD as `scene-context.md` while the scene runs. Locale, who's there, what's happening. No DM-only secrets, no prep, no hooks-not-yet-revealed.

The prep has the full picture. The context has only what's framed for the table.

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

### 6. Named things in play

Pointers to artifacts, ships, instruments, relics that might surface — from `dm/notes/artifacts/` and `dm/notes/ships/`. Reach for the curated list. **This is the anti-drift defense in action**: when a scene calls for a notable item, you reach for *Splitfork* or the *Threshold hammer*, not "the ship" or "the sword." Per [`/docs/principles/resist-generic-drift.md`](../../../docs/principles/resist-generic-drift.md).

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
- **"How the scene ends."** The end belongs to play (per the closure design — see [`/docs/design/scene-ending.md`](../../../docs/design/scene-ending.md), deferred).
- **A new arc.** If a scene seems to want a new arc, note it for after — go through [`arc-creation.md`](arc-creation.md) deliberately, not in passing.

If you find yourself authoring more than two pages, you're over-prepping. Stop, trim, leave room.

## Done criteria

Single invocation, usually. When you've got the strong start, 3-5 possible directions, the things-in-play lists, and a tight `context.md` for the players, stop. Exit; the orchestrator advances to running the scene.

## Tone

`prep.md` is a working document. You will read it during the scene. Keep it short and concrete.

`context.md` is the player-facing framing — the locale, the situation, who's here, what just happened. Players see it as `scene-context.md` in their CWD throughout the scene. Update it if the scene shifts substantially mid-play.

Names everywhere — pull from the curated lists. Specificity always — per [`/docs/principles/resist-generic-drift.md`](../../../docs/principles/resist-generic-drift.md). Generic prep produces generic scenes; specific prep produces scenes worth a transcript.
