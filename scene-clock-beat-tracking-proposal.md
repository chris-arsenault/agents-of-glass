# Scene Clock And Beat Tracking Proposal

## Problem

Current scene closure depends too much on DM judgment and prompt guidance. The
agents can keep generating locally plausible turns even after the dramatic unit
has already resolved. Clocks and scene trackers exist, but a scene is not
currently required to declare a scene-specific endpoint surface before play.

We need the CLI to make the scene's live clock and beat duration visible every
turn, without adding a large prompt burden.

## Goals

- Every active scene has at least one concrete scene-specific clock.
- Every active scene has at least one live beat started by the DM.
- Any agent can start a beat when they create a new dramatic unit.
- A beat can last at most 10 non-pass turns.
- A scene can have at most 3 active beats at once.
- Passed turns do not count against beat turn budgets.
- After 4-5 completed beats, `glass beat check` should say the scene has enough
  resolved material to close when the current scene clock lands. This is a soft
  availability signal, not a length warning or hard cap.
- Prompt updates should stay small: agents are told to run `glass beat check`
  and follow the CLI output.

## Terms

**Scene clock** is the scene-specific progress or countdown surface that makes
the scene worth playing. It can be material, immaterial, or abstract:

- material: make it to Pelhari, cross the Saltrun apron, keep the case contained
- immaterial: find 6 clues, win 4 concessions, establish 3 safe witnesses
- abstract: 10 hours to explore before nightfall, 6 exchanges before the hearing
  recesses, 4 warnings before the storm breaks

Longer-running clocks are still valid. This proposal requires at least one clock
owned by the current scene so everyone knows what the scene is trying to move.

**Beat** is a dramatic unit inside the scene: one problem, exchange, reveal,
choice, reaction, or action sequence that should land before the scene moves on.

A beat is not a whole subplot. It should be small enough to resolve within 10
non-pass turns.

## Required CLI Behavior

### Scene Clock

The DM must declare at least one scene-specific clock before an active play
scene can proceed.

Proposed command:

```bash
glass scene clock declare <clock-id> \
  --label "<player-facing label>" \
  --goal "<what progress, countdown, or endpoint this clock represents>" \
  --value <n> \
  --max <n> \
  --direction progress|countdown \
  --visibility public|dm
```

Examples:

```bash
glass scene clock declare apron-run \
  --label "Clear the Saltrun apron" \
  --goal "Bring the cold-pulling case through the apron without losing control" \
  --value 0 \
  --max 6 \
  --direction progress \
  --visibility public

glass scene clock declare clue-map \
  --label "Map the fungal intelligence" \
  --goal "Find enough clues to understand what the cargo wants" \
  --value 0 \
  --max 6 \
  --direction progress \
  --visibility public

glass scene clock declare nightfall \
  --label "Hours until nightfall" \
  --goal "Explore the ruins before nightfall changes the danger" \
  --value 10 \
  --max 10 \
  --direction countdown \
  --visibility public
```

This should reuse or wrap the existing clock/tracker machinery where practical.
The important new rule is that the clock is scene-local and required. Longer
running campaign, arc, faction, or threat clocks can still exist, but they do not
satisfy the active scene requirement unless the DM explicitly links a
scene-specific clock to them.

### Beat Start

Anyone can start a beat.

```bash
glass beat start <beat-id> \
  --clock <clock-id> \
  --label "<player-facing beat label>" \
  --question "<what must land before this beat is done?>"
```

The DM must start at least one beat when opening a scene. If an active scene has
no live beats, the next DM turn should be blocked until the DM starts one or
ends/transitions the scene.

Examples:

```bash
glass beat start first-shove \
  --clock apron-run \
  --label "Read the false shove" \
  --question "Can the crew identify which pull belongs to the case before Mox commits to the apron line?"
```

### Beat Progress

Every non-pass turn in an active scene increments the age of all active beats by
one, unless the beat was started on that same turn.

Player turns with `--turn-type pass` do not increment beat age.

This should be handled by the turn closeout path. Agents should not manually
count beat turns.

### Beat Check

All active-play turn prompts should tell the agent to run:

```bash
glass beat check
```

`glass beat check` prints:

- active scene clocks
- active beats
- each beat's age as `N/10`
- beats at warning level
- beats that must be closed or converted
- clock progress or countdown state
- completed beat count for the scene
- soft scene-close suggestion after 4-5 completed beats

Example output:

```text
Scene clocks:
- apron-run: Clear the Saltrun apron [3/6 progress]
  Goal: Bring the cold-pulling case through the apron without losing control.

Active beats:
- first-shove: Read the false shove [8/10]
  Clock: apron-run
  Question: Can the crew identify which pull belongs to the case before Mox commits to the apron line?
  Status: close soon; do not add another diagnostic layer unless it resolves this beat.

Completed beats this scene: 4
Scene note: this scene has enough resolved material to close when the current scene clock lands; keep any next clock choice deliberate.
```

### Beat Close

Any agent can close a beat if their turn resolves it.

```bash
glass beat close <beat-id> \
  --outcome "<what landed or changed>" \
  --clock-delta <n>
```

Closing a beat increments the scene's completed beat count. If the beat changed
the scene clock, the CLI should apply the clock delta in the same command so the
endpoint surface stays current.

A closed beat should remain visible in `glass beat check` as recent context for
one round, then drop into normal scene summary/history.

### Beat Limit

The CLI should reject starting a fourth active beat:

```text
Cannot start beat: this scene already has 3 active beats.
Close or resolve an existing beat first with `glass beat close <beat-id>`.
```

This prevents scene sprawl.

### Beat Expiry

At 8/10, `glass beat check` should warn all agents to resolve or narrow the beat.

At 10/10, the next non-pass turn should be forced into one of:

```bash
glass beat close <beat-id> --outcome "<partial or complete resolution>"
glass beat convert <beat-id> --to-clock <clock-id> --reason "<why this is no longer a beat>"
glass scene end --outcome "<scene closes with this unresolved or partially resolved>"
```

The exact forced behavior can be phased in. The first implementation can warn at
8/10 and hard-block starting new beats when any beat is at 10/10.

## Prompt Changes

Keep prompt updates deliberately small.

Add this to active play methodologies:

```text
Run `glass beat check` before writing your turn. Treat the listed scene
clock and active beats as the current dramatic contract. If a beat is near
10/10, resolve it, close it, or pass unless you have a concrete action that
lands it. Do not start a fourth active beat.
```

Add this to DM scene opening / scene prep:

```text
Declare at least one scene-specific clock and start the first beat before active play.
Use `glass beat check` to see current beats, their turn counts, and whether the
scene should start closing.
```

Avoid long negative examples in prompt copy. The CLI output should carry the
operational detail.

## Data Model

New tables or equivalent runtime state:

```text
scene_clocks
- campaign_id
- scene_id
- clock_id
- label
- goal
- value
- max
- direction: progress|countdown
- visibility
- status: active|resolved|dropped
- created_by
- created_turn_id
- resolved_turn_id
- outcome

scene_beats
- campaign_id
- scene_id
- beat_id
- clock_id
- label
- question
- status: active|closed|converted|dropped
- non_pass_turns
- created_by
- created_turn_id
- closed_by
- closed_turn_id
- outcome
```

The orchestrator should also be able to compute:

- active beat count
- completed beat count for current scene
- oldest active beat
- whether any active beat is at 8/10 or 10/10
- whether the scene clock is resolved, stalled, or still live

## Turn Integration

On `glass turn end`:

- read `--turn-type`
- if `--turn-type pass`, do not increment beat ages
- otherwise increment active beat ages after the turn commits
- if the turn started a beat, do not count that same turn against that new beat
- if any beat reaches 8/10, queue a warning event
- if any beat reaches 10/10, mark the scene as requiring beat resolution before
  new beat starts or unrelated action
- if the scene clock resolves, tell the next DM turn to consider scene closure

This makes pass useful as pacing relief without letting agents hide behind
procedural non-actions.

## Enforcement

Hard rules:

- active play cannot proceed without at least one scene-specific clock
- DM must start at least one beat for the scene
- no more than 3 active beats
- pass turns do not count toward beat age
- active beats cannot exceed 10 non-pass turns without resolution, conversion, or
  scene closure

Soft rules:

- after 4 completed beats, `glass beat check` says the scene has enough resolved
  material to close when the current scene clock lands
- after 5 completed beats, the suggestion should be stronger but still framed as
  closure availability, not "this is too long"
- scene closure is still DM judgment unless a separate hard scene budget is
  implemented later

## Suggested Implementation Phases

1. Add scene clock and beat storage, commands, and `glass beat check`.
2. Wire turn closeout to increment active beat ages, skipping pass turns.
3. Add hard limit of 3 active beats.
4. Add DM opening validation: active scene needs one scene clock and one beat.
5. Add warning/blocking behavior for 8/10 and 10/10 beats.
6. Add minimal prompt lines telling agents to use `glass beat check`.
7. Add tests around pass turns, active beat caps, DM-required first beat, and
   scene-close suggestions after 4-5 completed beats.

## Expected Effect

This should reduce scenes where every turn invents another local procedure. The
agents will see that a beat is aging out and that the job is to land it, not
decorate it. It also gives the DM a visible reason to close the scene after a
handful of landed beats without forcing a brittle universal scene length.
