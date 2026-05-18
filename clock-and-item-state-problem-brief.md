# Clock And Item State Problem Brief

This is a handoff brief for rethinking two related failures in `glass`:
clock lifecycle drift and item continuity drift. The goal is not to add another
command. The goal is to understand the actual design problem before proposing a
fix.

## Core Problem

Campaign agents are not reliable users of a broad custom CLI. `glass` has many
commands, and the agents do not have training data for this tool. Every added
command, option, or mini-language increases the chance that agents ignore it,
misuse it, or half-use it.

At the same time, deterministic CLI code cannot interpret narrative prose. If a
turn says "the witness bell cane is jammed under the sled," normal code cannot
safely infer whether that means a permanent inventory mutation, a temporary
scene cost, a table-visible fact, or just narration.

The current system sits between those two bad boundaries:

- Agents are asked to remember too much state machinery.
- Deterministic code cannot recover when they express state changes only in
  prose.
- Adding more syntax or commands makes the agent problem worse.
- Adding LLM interpretation inside the orchestrator is not valid for the
  current deployment model.

## Deployment Constraint

The current system runs through Codex/Claude subscription accounts, not a
pay-per-token API pipeline. A solution that adds additional LLM calls from the
orchestrator is not acceptable.

## Clock Lifecycle Failure

The system currently supports durable clocks and scene clocks. In play, this
creates stale or confusing state.

Example from `campaigns/the-revengers`:

- `Cinder Cascade Reaches The Docks` remained active at `0/4` after several
  scenes.
- `Bloom Edge Strains At Cordon Twelve` was resolved at `0/4`.
- The fiction had moved through Skiffmoor, Red Thread, and Cordon Twelve, but
  the durable clock state no longer clearly communicated whether a danger was
  active, prevented, obsolete, or merely forgotten.

Relevant files:

- `campaigns/the-revengers/arcs/cinderwake/clocks.md`
- `campaigns/the-revengers/arcs/cinderwake/summary.md`
- `revengers-followup-tracker.md`

Observed design issue:

Durable numeric clocks require lifecycle management: tick, resolve, archive,
carry forward, or retire. That management is exactly the kind of custom command
work agents are likely to skip.

## Item Continuity Failure

Character inventory is currently treated like exact object custody, but agents
do not consistently mutate inventory when fiction changes object availability.

Example from `campaigns/the-revengers`:

- Duva's `ringglass-witness-bell-cane` was jammed under the reset sled and later
  sealed inside Ladder Throat Three.
- Her public character sheet still listed the cane as carried equipment.
- Later play used the witness bell cane again.
- A player note had to paper over the contradiction by treating the sheet as
  canonical unless Mara reopened the evidence state.

Relevant files:

- `campaigns/the-revengers/arcs/prelude/scenes/prelude-opening/transcript.md`
- `campaigns/the-revengers/players/sumi/public/character.md`
- `campaigns/the-revengers/players/sumi/notes/cinderwake-proof-chain.md`

Second example:

- Yoss's `pocket-flare-gun` was fired.
- The sheet later represented this as `pocket-flare-gun-spent`.
- This preserves some continuity but mutates item identity to encode temporary
  status, which is brittle and clutters inventory.

Relevant files:

- `campaigns/the-revengers/players/kit/public/character.md`
- `campaigns/the-revengers/players/kit/notes/c12-three-shell-public-signal.md`

Observed design issue:

Exact custody of items is probably too fine-grained for autonomous agents using
a custom CLI. Agents can narrate item loss or expenditure, but they do not
reliably update structured inventory.

## Rejected Solution Shapes

These ideas were considered and rejected as invalid or counterproductive.

1. Add new commands such as `glass clock settle` or
   `glass character inventory-status`.

   This makes the command surface larger. The agents already struggle with the
   existing command surface.

2. Leave legacy commands alive while adding better commands.

   This creates multiple valid paths and increases inconsistency. Legacy paths
   are a known source of failure because agents will continue to find or use
   them.

3. Add a typed mini-language inside `glass done --state`.

   This is just another custom command syntax. Agents are likely to ignore or
   malformed it, and it shifts the complexity without reducing it.

4. Let `glass done` infer state changes from prose.

   Deterministic code cannot safely interpret narrative text.

5. Add an LLM reconciliation pass in the orchestrator.

   This violates the current deployment constraint: no pay-per-token LLM calls
   inside the orchestrator.

## Current Best Understanding

The likely fix is subtractive, not additive.

For clocks:

- Consider removing durable numeric clocks from normal agent play.
- Treat scene clocks as temporary pacing aids, not lasting truth.
- Scene clocks can be created during scene prep, advanced by beat closure, and
  cleared when the scene ends.
- Long-running danger may belong in summaries, threads, arc prep, or Mara's
  scene design, not as a numeric clock agents must lifecycle-manage.
- `glass arc close-check` should probably not be blocked by stale numeric
  clocks unless a human/operator is explicitly managing those clocks.

For items:

- Consider redefining inventory as loadout, not exact object custody.
- A character's listed item means the character normally has access to that
  affordance.
- Scene-local use, expenditure, damage, or loss can be fiction and table state,
  not sheet mutation.
- Persistent loss should be modeled as a character consequence, not item status.
  Example: `No flare ordnance until dock requisition` or
  `Down a witness bell until resupplied`.
- Avoid item IDs that encode transient status, such as `-spent`, `-broken`,
  `-lost`, or `-sealed`.

## What A Good Proposal Should Optimize For

- Fewer agent-facing commands.
- Fewer valid ways to mutate the same state.
- No LLM calls inside deterministic orchestration.
- No prose inference inside deterministic CLI code.
- State models that match what agents can reliably maintain.
- Clear deletion or hiding of legacy paths when a new model replaces them.
- Tolerance for imperfect precision when precision creates more failures than
  it solves.

## Open Question

Should `glass` keep trying to model clock and item lifecycle as hard state, or
should those concepts be intentionally softened into scene-local pacing,
loadout, consequences, summaries, and Mara's prep?

