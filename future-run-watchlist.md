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

- Do future preludes also collapse planned second-scene pressure into the first
  scene, or was this caused by `team-alpha-2`'s overloaded first scene?
- When scene prep says "this sets up scene two," does the DM preserve that
  pressure for a later scene, or immediately spend it in the active scene?
- After `glass scene end`, does the next DM turn stage the next scene, close the
  arc, or leave a boundary gap?
- Does `glass turn audit` give enough useful guidance before closeout, or do
  agents still discover recoverable problems only after `glass turn end`?
- Do beat/clock checks help agents maintain active play, or do they encourage
  premature closure when the scene has no active beat?
- Do validation failures become visible to the right actor through actionable DM
  instructions, without pausing the campaign or crashing the run?
- Do recovery DM turns actually repair missing scene/mode state, or do they
  summarize the problem without issuing the needed CLI commands?
- Are scene clocks and beats being created because the scene needs them, or only
  because the audit requires them?
- Does the message bus carry correction instructions clearly enough for Mara to
  course-correct without hidden orchestrator warnings?
- Does `scene-prep` get used as the bridge after an arc closes with a known next
  arc but no staged active scene?

## Guardrails For Later Decisions

- Do not make the orchestrator enforce narrative structure like "the prelude must
  have exactly two scenes." The orchestrator should keep the process recoverable
  and route invalid state to the appropriate actor.
- Prefer CLI/audit surfaces for table-contract guidance, because those are
  visible to agents at the decision boundary.
- Treat failed narrative-methodology expectations as recoverable DM-facing
  instructions unless there is corrupted or non-recoverable runtime state.
- Do not overfit to this prelude until another run shows whether the collapse is
  systematic.
- If this repeats, consider a DM-visible prelude audit/check that reports planned
  scene expectations and asks the DM either to stage the missing scene or record
  why the pressure was resolved inside the first scene.
