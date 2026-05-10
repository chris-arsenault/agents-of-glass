# Post-Prelude Followups

Items to review after the `inspect-1` prelude finishes. Do not interrupt a live
prelude run to address these unless one becomes a hard blocker.

## State and Persistence Rectification

The manual campaign repair was too hard. The campaign currently has too many
state-shaped artifacts that can disagree:

- Postgres runtime state.
- `campaigns/<id>/state.json`.
- `campaigns/<id>/aog-state.json`.
- Arc registry/current arc projections.
- Table markdown such as `table/index.md` and `table/scene.md`.
- Arc/scene markdown projections such as `arcs/<id>/context.md`,
  `arcs/<id>/summary.md`, and `arcs/<id>/clocks.md`.

Post-prelude goal:

- Make Postgres the source of truth for runtime state wherever possible.
- Eliminate vestigial JSON runtime files where possible.
- Where JSON or markdown projections must remain, expose a single projection API
  that rewrites them from the source of truth.
- Add a single operator command that checks and reconciles campaign state across
  Postgres, projections, and filesystem permissions.
- Add first-class checkpoints and restore. Checkpoints should be cheap to create
  and safe to restore without hand-editing Postgres, JSON exports, transcripts,
  tables, arc projections, and per-turn files independently.

Checkpoint candidates:

- after campaign planning / before character creation
- after character creation / before prelude
- beginning of every act
- beginning of every scene
- every few rounds in long scenes or action scenes
- explicit operator checkpoints before risky resume/replay/debug work

Restore semantics:

- restore Postgres runtime and durable state to the checkpoint
- truncate turns, events, search chunks, action orders, scene trackers, and other
  turn-derived rows after the checkpoint
- restore or regenerate `state.json`, `aog-state.json`, table projections, arc
  projections, transcripts, and per-turn filesystem artifacts
- archive discarded artifacts for debugging, but remove them from live campaign
  discovery and agent context
- run validation after restore and report every remaining state surface that was
  checked

Observed during `inspect-1`:

- `state.json`, Postgres, `aog-state.json`, the active arc surface, and
  `table/index.md` all needed separate inspection during repair.
- `aog-state.json` still described `character-creation` as the initial mode
  after the durable campaign phase had moved to `prelude`.
- `table/index.md` still described character creation after character creation
  had completed.
- `glass arc current` reports `the-fourth-audit`, while the active prelude table
  now says `arc: prelude` and the DM created `arcs/prelude/`.
- `arcs/prelude/` exists on disk but is not registered in `glass arc list`.
- `arcs/prelude/context.md`, `arcs/prelude/plan.md`, and
  `arcs/prelude/scenes/prelude-opening/context.md` are currently mode `0700`,
  so player agents cannot read them even though `table/index.md` links to them.

## Signature Move Progression

Current behavior pushes players toward a full list of 3-6 signature moves during
character creation. That is too much at level 1 and makes signature moves feel
fully designed instead of discovered through play.

Post-prelude goal:

- Update the SRD and character creation methodology so a new character normally
  starts with one simple signature move.
- Let players and the DM add moves during play when a repeated action becomes
  identity-defining: "I think this is becoming a signature move."
- Tie available move slots to level. Candidate: one slot at level 1, then one
  additional slot every two levels, reaching five slots around level 9 or 10.
- Let later moves be broader, stranger, or more powerful in fiction. Early moves
  should look like "read resonance" or "crackling punch"; high-level moves can
  become things like "omega-class resonance projection."
- Keep signature moves as narrative consistency tools, not guaranteed powers or
  locked mechanical actions.

Observed during `inspect-1`:

- Tev, Sumi, Renno, and Kit each authored five signature moves immediately.
- The turn prompt currently says signature moves are a maintained list of 3-6
  recurring moves, which implies starting near full capacity.
- The repaired signature move files include "Usual roll" lines. Review whether
  those are useful examples or whether they overstate mechanical binding.

## Other Bootstrap Inconsistencies

These are not hard blockers, but they should be reviewed after the prelude.

- Early turns show agents hitting `EACCES` on shared instructions, SRD, lore,
  table, and signature move files. The group/preflight fix addresses the operator
  side, but the transcript still shows the agents working around missing access.
- Player turns explicitly say they could not write `signature-moves.md`; those
  notes now live permanently in the transcript even though the files were later
  repaired.
- Character public mirrors are inconsistent in format and completeness. Examples:
  some say `type: character-sheet`, others `type: character-display` or
  `type: character-cache`; Murvak's public sheet says `HP: 12` instead of
  `12/12`; canonical Postgres `pronouns` and `bio` are blank for characters that
  have prose identity details.
- Character role labels drift slightly between surfaces. Example: Vel is
  "route and contact broker" in the table, but "Informal transit coordinator" in
  canonical Postgres.
- `table/index.md` mixes durable numeric public clocks with freeform public
  pressures such as `Transit Advisory: standard review`. Decide whether that is
  desired table prose or should be projected from durable trackers/clocks.
- Prelude may need a clearer state model: either it is a real registered arc, a
  child scene under `the-fourth-audit`, or a special bootstrap phase with its own
  projection rules. The current run has pieces of more than one model.
- The first prelude attempt let the DM take turns 12-16 without player turns.
  Root causes: `prelude` is a DM-only coordinator mode, and the DM wrote
  `glass ...` command lines into public prose instead of executing them. The
  orchestrator should fail fast on both patterns rather than letting the DM keep
  narrating.
- Resetting `inspect-1` back to turn 11 required manual edits/deletes across
  Postgres turns/events/search chunks/runtime state, `state.json`,
  `aog-state.json`, `transcript.md`, `table/`, `arcs/prelude/`, and
  `dm/turns/0012-0017/`.

## Character Sheet Schema and Creation Context

The `inspect-1` characters are creatively strong, but character creation exposed
schema and prompt-shaping problems.

Post-prelude goal:

- Add discrete canonical fields for species/race, archetype, and role in the
  organization. Do not leave these only in prose or tags.
- Require `bio` to be filled during character creation. It can be concise, but
  it should not be blank in Postgres.
- Review whether `pronouns` should also be required or explicitly optional with
  a visible "unspecified" value.
- Separate character goals from campaign-solving goals. Character goals should
  be personal, professional, relational, organizational, or value-driven. They
  can point toward campaign material, but they should not read like the player
  already knows the campaign's mystery board.
- Rework character public mirrors so all characters project from the same
  canonical fields and use one consistent display format.

Creation-context questions:

- Consider having the DM provide only setting, organization, premise, and tone
  before character creation, not the full campaign structure, antagonist map,
  major mystery chain, and intended arc.
- Character creation may need a reduced context package that excludes prior
  player turn summaries until after each player has made their initial character.
- Another option is a two-pass structure: blind independent character pitch
  first, then visible relationship/party-cohesion pass second.
- The relationship pass can still let players build on each other intentionally,
  but the first pass should prevent every character from optimizing around the
  same revealed campaign mechanism.

Observed during `inspect-1`:

- Characters explicitly referenced the previous character creation turns while
  designing themselves.
- Goals frequently point straight at campaign mysteries, e.g. the Array baseline,
  Buoy Seven-Nine, Sable Crescent, Ternisk filings, or the missing runner.
- That produced a very coherent party, but it risks "poisoning" character
  context: characters are optimized for a plot the players arguably should not
  know yet.
