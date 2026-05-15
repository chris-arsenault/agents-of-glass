# Future Run Watchlist

This note tracks issues to watch in future autonomous campaign runs. It is not
an implementation plan and should not be treated as a request to enforce new
orchestrator behavior.

## Current Read

In `team-alpha-2`, the prelude was planned as two scenes: a normal opening scene
and a follow-up action scene. The run only created and played
`prelude-opening`. The intended second pressure, the sealed service locker and
wall-cache problem, entered and resolved inside the first scene instead of being
staged as `prelude-action`.

This may be a one-run artifact. The first scene absorbed several problems:
missing or evolving beat/clock requirements, closeout corrections, recovery from
validation behavior, and a long proof/custody thread. The result may have made
the DM reasonably conclude that the prelude question had already resolved.

## Watchpoints

1. Do future preludes also collapse planned second-scene pressure into the first
  scene, or was this caused by `team-alpha-2`'s overloaded first scene?
2. When scene prep says "this sets up scene two," does the DM preserve that
  pressure for a later scene, or immediately spend it in the active scene?
3. Do beat/clock checks help agents maintain active play, or do they encourage
  premature closure when the scene has no active beat?
4. Do recovery DM turns actually repair missing scene/mode state, or do they
  summarize the problem without issuing the needed CLI commands?
5. Are scene clocks and beats being created because the scene needs them, or only
  because the audit requires them?
6. Does the message bus carry correction instructions clearly enough for Mara to
  course-correct without hidden orchestrator warnings?

## Potential Follow-Ups

None currently.

## Completed Follow-Ups

Closed on 2026-05-14:

1. Roll outcome consequences: `glass turn audit` now surfaces
   `stall`/`regress`/`collapse` rolls that have no follow-up consequence
   command, and `glass done` rejects closing those turns unless the closeout
   records a concrete state, position, pressure, or open-question consequence.
   Methodologies and SRD roll guidance now state that failed rolls must keep
   the scene moving rather than produce no change.
2. Scene clock semantics: scene clocks now carry `objective|threat|timer`
   polarity, `glass check`/`glass beat check` render grouped clock semantics and
   warnings, `glass scene clock tick` records direct clock movement, and audits
   warn when several beat closes happen with no scene clock movement. Guidance
   now frames the primary scene clock as the party objective, with separate
   threat/timer clocks when pressure moves independently.
3. Situation prep and variety: scene prep, scene transition, closeout, and
   TURN_START now require the DM scene brief to name the scene verb, active
   antagonist move, concrete physical danger, three interactable scene toys, why
   the party's default extraction/load-path/proof answer is insufficient or
   costly, the objective clock, any threat/timer clock, and the novelty note
   versus the last two scenes.
4. Problem family variety: scene creation now uses `--type <problem-family>` in
   the agent-facing surface, `how-to/problem-families.md` defines broad families,
   and scene prep/transition prohibit "knowledge" as a family while requiring a
   variation note against the last two scenes.
5. Arc closure close-check: `glass arc close-check` exists, reports required and
   recommended closeout blockers, asks for `continue|close|reframe`, and is
   injected into DM scene-transition, scene-prep, and intermission TURN_START
   surfaces.
6. Long-game threads and callbacks: scene prep, scene transition, closeout, and
   TURN_START now surface `glass thread current` and `glass thread advance` for
   concrete table-visible callbacks and recurring campaign handles.

Closed on 2026-05-15:

1. Scene-boundary gaps after `glass scene end`: retired as a standing watchpoint
   because scene transition, arc close-check, intermission, and scene-prep
   command surfaces now force the DM to choose close/continue/reframe, stage the
   next scene when needed, and avoid leaving an open active arc with no mode.
2. Turn-audit usefulness before closeout: retired as a standing watchpoint
   because `glass done` now runs the audit directly, active-play turns require
   `glass check`, and the audit reports scene contract, pass/closure pressure,
   roll-consequence gaps, and clock/beat movement warnings before closeout.
3. Validation failures surfacing to the right actor: retired as a standing
   watchpoint because invalid closeouts now return actionable fixes, recoverable
   scene-contract failures route to DM repair turns, and tests cover those
   recovery paths.
4. `scene-prep` as the bridge after arc closure: retired as a standing
   watchpoint because TURN_START now injects `glass arc close-check`,
   scene-prep/scene-transition tooling, problem-family scene creation, thread
   surfaces, scene clock/beat setup, and mode-start commands at the boundary.

## Guardrails For Later Decisions

1. Do not make the orchestrator enforce narrative structure like "the prelude must
  have exactly two scenes." The orchestrator should keep the process recoverable
  and route invalid state to the appropriate actor.
2. Prefer CLI/audit surfaces for table-contract guidance, because those are
  visible to agents at the decision boundary.
3. Treat failed narrative-methodology expectations as recoverable DM-facing
  instructions unless there is corrupted or non-recoverable runtime state.
4. Do not overfit to this prelude until another run shows whether the collapse is
  systematic.
5. If this repeats, consider a DM-visible prelude audit/check that reports planned
  scene expectations and asks the DM either to stage the missing scene or record
  why the pressure was resolved inside the first scene.
