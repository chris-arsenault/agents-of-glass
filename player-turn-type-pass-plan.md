# Player Turn Type / Pass Plan

## Purpose

Reduce forced-turn filler in scene play without changing the orchestrator's
speaker scheduler yet.

The immediate problem is not that every player gets called. The immediate
problem is that, when a player has no meaningful contribution, the agent still
tries to fill the turn with procedure, withholding prose, or atmospheric
minutia. This plan makes "nothing worth adding right now" a valid player turn.

## Core Rule

Every normal active-play player turn must choose one turn type:

- `act`
- `answer`
- `support`
- `pass`

The chosen type is formal closeout metadata, not just prose guidance.

```bash
glass turn end \
  --summary "<1-3 sentence compact continuity>" \
  --state "<durable updates or no state change>" \
  --rolls "<rolls/checks used or none>" \
  --turn-type act|answer|support|pass \
  --scene-status active \
  --next default
```

## Turn Types

`act` means the player changes the situation.

`answer` means the player responds because another character, NPC, danger, or
scene pressure directly called for a response.

`support` means the player visibly backs another character's action without
adding a second plan. Do not add a target field for support. If the support
needs a target, the prose can make that clear naturally.

`pass` means the player has no blockbuster-cut contribution this beat. The
player gives one short table-visible cue and yields.

## Pass Definition

A pass is still a real player turn. It does not end the scene, does not force a
DM turn, and does not change the orchestrator's default order.

Operational closeout for a pass:

```bash
glass turn end \
  --summary "<character visibly yields the beat>" \
  --state "no state change" \
  --rolls none \
  --turn-type pass \
  --scene-status active \
  --next default
```

A pass must be table-visible only: a small physical cue, brief line, or clear
yield. It must not become internal withholding prose, unnamed significance,
symbolic compression, or a paragraph about what the character does not say.

Good pass shape:

> Step keeps working the reed pipe between his fingers, shakes his head once,
> and lets Pell answer.

Bad pass shape:

> Step thinks of three things he could say, names none of them, and stores the
> silence beside the old debt.

## Blockbuster Cut Rule

Use the broad reference directly: **blockbuster cut**.

Do not expand this into a long checklist for agents. The point is to pull the
turn toward the intended play space with a low-token, high-signal reference. If
the turn would mostly consist of minutia, it should be compressed or become a
pass.

## CLI Implementation Plan

Add `--turn-type` to `glass turn end`.

Allowed values:

```text
act
answer
support
pass
```

Validation:

- Required for player turns in normal active play.
- Not required for DM turns.
- Not required for character creation, campaign planning, scene prep,
  housekeeping, or other setup/maintenance turns.
- `pass` should require `--state "no state change"` and `--rolls none`.
- `pass` should keep `--scene-status active` unless the active methodology
  explicitly allows a player to close a scene.
- `support` gets no structured target field.

Persistence:

- Include `turn_type` in the `turn-closeout.json` payload.
- Store it in `turn_end` JSON immediately.
- Add a first-class `turn_type` column only if querying/reporting needs it after
  the experiment.

Context rendering:

- Include recent turn types in compact recent-turn context so the DM can see
  whether recent player turns were mostly `act`, `answer`, `support`, or `pass`.
- Do not make the orchestrator branch on this metadata in the first experiment.

## DM Handling

The DM should treat recent `pass` and support-only turns as pacing information.
When the normal order reaches the DM, it should not squeeze those characters
for more. It should move the scene to the next meaningful beat, consequence, or
decision point.

This is DM behavior, not an orchestrator scheduler feature.

## Explicit Non-Goals

- No spotlight scheduler in this experiment.
- No prose parsing for intent.
- No support target field.
- No automatic scene ending when a player passes.
- No special `--next dm` behavior for passes.
- No additional pass taxonomy beyond `act`, `answer`, `support`, `pass`.

## Test Question

Does making `pass` a formal, acceptable player turn reduce procedural filler and
reserved-professional drift during scene play while preserving the existing
round-robin scheduler?
