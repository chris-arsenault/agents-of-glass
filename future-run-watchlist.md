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
3. After `glass scene end`, does the next DM turn stage the next scene, close the
  arc, or leave a boundary gap?
4. Does `glass turn audit` give enough useful guidance before closeout, or do
  agents still discover recoverable problems only after `glass turn end`?
5. Do beat/clock checks help agents maintain active play, or do they encourage
  premature closure when the scene has no active beat?
6. Do validation failures become visible to the right actor through actionable DM
  instructions, without pausing the campaign or crashing the run?
7. Do recovery DM turns actually repair missing scene/mode state, or do they
  summarize the problem without issuing the needed CLI commands?
8. Are scene clocks and beats being created because the scene needs them, or only
  because the audit requires them?
9. Does the message bus carry correction instructions clearly enough for Mara to
  course-correct without hidden orchestrator warnings?
10. Does `scene-prep` get used as the bridge after an arc closes with a known next
  arc but no staged active scene?

## Potential Follow-Ups

1. Roll outcome consequences: watch whether `stall`, `regress`, and `collapse`
  results reliably move the board forward. A failed roll should produce a
  concrete consequence, narrower choice, worse position, visible cost, clock
  tick, beat movement, or durable state change. If future runs keep absorbing
  failed rolls as caution/procedure, consider strengthening the roll/scene-play
  guidance and adding an audit warning when a failed roll reports no clock,
  pressure, position, consequence, beat, or state delta. Avoid auto-ticking every
  roll for now; prefer "tick the active scene clock on failure when the failure
  directly engages that clock's danger, unless a more concrete consequence is
  recorded."
2. Scene clock semantics: current CLI capability is broader than current usage.
  Durable clocks support `fills`/`drains`; scene clocks support
  `progress`/`countdown`, but live scenes have mostly phrased progress clocks as
  bad things filling up. That makes successful play look like clocks staying at
  `0/4` instead of visible progress. Consider shifting guidance so the primary
  scene clock is usually the party objective, e.g. "Make Hold Seven boundary
  honest 0/4 progress", with a separate threat/timer clock when the antagonist
  or hazard is advancing. Potential CLI work: add `objective|threat|timer`
  polarity, render `glass beat check` grouped by polarity, add direct
  `glass scene clock tick`, warn when a scene has only threat clocks, and warn
  when several beats close without any scene clock movement. Do not auto-tick
  every roll until we have stronger evidence; clock movement should attach to
  beat resolution, meaningful failure, DM moves, or explicit consequences.
3. Situation prep and variety: the strongest current campaign risk is not lack of
  action, but repeated use of the same party solution language at increasing
  scale: extraction, load path, line, evidence, comparator. Live-table lesson:
  preserve the toolkit, change the situation. Consider adding a DM scene-brief
  requirement that names the scene verb, active antagonist move, concrete
  physical danger, 3 concrete interactable scene toys, why the party's default
  extraction/load-path answer is insufficient or costly here, the objective
  clock, the threat/timer clock if any, and a novelty note explaining how this
  scene differs from the last two. Avoid enums and constrained taxonomies; use
  this to make Mara throw substantively different problems while leaving player
  solutions open.
4. Problem family variety: test a scene-prep requirement that every scene names
   a primary problem family such as environment/traversal, social
   pressure/coercive bargain, investigation/clue trail, fight/monster pressure,
   chase/escape, extraction/rescue, breach/infiltration,
   disaster/containment, puzzle/weird mechanism, or triage/impossible choice.
   This should be a broad prompt nudge, not a hard taxonomy. Mara should state
   how the selected family differs from the last two scenes and what part of the
   party toolkit it pressures differently. Do not use "knowledge" as a family;
   knowledge is an output, not the scene problem.
5. Arc closure close-check: the system has `glass arc close` and an Act Close
   Sequence, but Mara is likely to keep staging the next scene unless the
   decision is surfaced at the scene boundary. Consider requiring a scene-close
   arc decision of `continue`, `close`, or `reframe`, with a short reason tied
   to done criteria, arc clocks, antagonist position, and why another scene is
   still needed. Longer-term CLI idea: implement `glass arc close-check`.
6. Long-game threads and callbacks: Mara needs a simple habit for turning
   organic play into an overarching campaign spine. After each arc, promote one
   or two concrete consequences, symbols, NPC moves, faction moves, repeated
   harm patterns, or unresolved questions into a long-term thread. During scene
   prep, seed at most one visible callback or hint when it fits: a mark, object,
   NPC behavior, damage pattern, phrase, route, faction resource, or repeated
   method. Prefer concrete table-visible callbacks like "another crate carries
   the scorpion symbol" over abstract mystery language.

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
