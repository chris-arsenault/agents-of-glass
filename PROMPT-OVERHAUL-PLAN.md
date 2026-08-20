# Prompt-System Overhaul — Implementation Plan

Replace the default coding system prompt with per-role, persona-carrying system prompts;
slim the injected turn prompt through a guard disposition ledger; rewrite the creative
methodologies as gated creative contracts; and make outcome narration fair by instruction.
For the orchestrator/CLI runtime only — no SRD dice-math changes, no viewer work, no Agent
SDK migration, no codex-branch changes. The goal is a corpus a stranger reads for pleasure;
the test is a fresh campaign read against ash-ledger.

## Confirmed decisions

- Agents keep running as `claude -p` subprocesses under the subscription pricing model.
  No Agent SDK migration; it returns only if subscription billing is retained **and** a
  concrete benefit is demonstrated.
- System prompts are delivered per-invocation via `--system-prompt-file` (full
  replacement, not append) on the claude branch only. The codex branch is left
  byte-identical — no prompt-prefix fallbacks; codex-native support is future work
  (backlog entry, not this plan).
- No mechanism may add turn interruptions. Turn start / context gathering is the
  dominant system cost; all new gates, antagonist moves, and genre selection live inside
  existing turns and modes.
- Outcome adjudication authority does not move. Players keep rolling and narrating;
  the system prompts instruct fair narration (failures, costs, and world pushback
  narrated honestly). No DM-gating of `glass_roll`/`glass_scene_pressure`.
- Existing prompt guards are regression fixes. None is deleted without a ledger
  disposition arguing the upstream fix removes its cause; survivors relocate to the
  per-role system prompt (cheap, stable) rather than staying in the per-turn prompt.
- Ledger seeding is source-extraction plus an operator pass for historical failure
  modes that were never prompted out (e.g. game-rules vs in-game-rules bleed).
- Persona and style *contents* are inlined into system prompts. No file-path
  references in prompts (per the backlog's planned prompt lint).
- Genre/problem-family variety is codified (recency-tracked state), consistent with
  codify-only-what-drifts: this drift is proven across campaigns.

## Context / reuse map

Reused as-is (verified against current code):

- **Personas** `templates/dm/persona.md`, `templates/players/*/persona.md` — authored,
  copied per-campaign by `CampaignManager.create` copytree, currently surfaced nowhere.
- **Narrative styles** `templates/styles/*.md` — five authored styles, assigned via
  persona frontmatter `narrative_style:`, currently unwired (zero refs in `src/`).
- **Command assembly site** `src/orchestrator/runner.py:1544-1562` (claude branch);
  codex branch `:1563-1581` untouched.
- **Config plumbing** `src/orchestrator/config.py` — `[claude]` table, `_resolve_path`
  helper, deep-merged toml loading.
- **Turn-type selection** `src/orchestrator/context.py:1854` `_turn_type_for` →
  one methodology file per role×turn-type in `templates/methodologies/`.
- **Bootstrap validation hooks** `src/orchestrator/main.py` `_run_bootstrap_phase`
  `validate=` callbacks — the enforcement point for M3's creative gates.
- **Operator org-direction** stored as a dm-visible `meta` fact
  (`main.py:1011-1057`); its prompt section is a dead placeholder
  (`context.py:277`) — wired in M3.
- **Prompt-assembly tests** `tests/test_runner.py` (existing precedent; the two
  persona-absence assertions at `:736`, `:834` invert in M1).
- **Design research** `docs/research/persona-prompting.md` (embodied identity,
  domain priming) and `docs/design/prompt-writing.md` (stale; updated in M2).

Built new: per-role base prompt documents, the system-prompt assembler, the guard
ledger, rewritten methodology contracts, problem-family recency state.

Source-of-truth for current guard text: `src/orchestrator/context.py`
(`_scene_framing_discipline_section`, `_codified_handles_vs_fiction_language_section`,
identity sections, authoring-surface block, output contracts) plus
`templates/instructions/` and `templates/methodologies/`.

## Cross-cutting constraints

- Subscription-priced `claude` subprocess invocation is load-bearing; nothing may
  change the auth/billing path.
- Zero added turn interruptions in any phase.
- `templates/` is authored input only; assembled runtime prompts are written outside it.
- All state mutations via `glass`; CLI-only tests against real data stores; no
  orchestrator-loop or agent-behavior tests.
- Branch discipline: `main`. Verify: `uv run pytest -q` (Makefile
  `python-test` is the unittest-discover equivalent).
- Prose rules for authored prompt content follow the operator's register (no slop
  lexicon, concrete over abstract).

## Milestones

### M0 — Guard disposition ledger
Catalog every guard so later phases delete nothing blind.
- Extract every prohibition/guard from `context.py` prompt sections,
  `templates/instructions/`, and `templates/methodologies/` into
  `prompt-guard-ledger.md` (repo root, working doc): guard text, failure mode it
  fixed, cause hypothesis, proposed disposition (drop / relocate-to-system-prompt /
  keep-in-turn-prompt).
- **[DECISION]** Operator pass: correct dispositions and add historical failure
  modes never prompted out; these become ledger rows with `unprompted` origin so
  M2 can address them deliberately.
- Exit: operator signs off on the ledger; every guard has a disposition.

### M1 — System-prompt infrastructure [depends on nothing; parallel with M0]
Thread `--system-prompt-file` through config → assembly → claude invocation.
- Config: per-role base-prompt paths (new `[prompts]` table or `[claude]` extension).
- Assembler: base role document + persona contents + assigned narrative style
  inlined into one file per actor at spawn (runtime location, not `templates/`);
  argv untouched except the new flag pair.
- Claude branch only; codex actors' command line stays byte-identical.
- Flip/extend `tests/test_runner.py` prompt-assembly assertions (persona present in
  system prompt file, absent as file references).
- Add backlog entry: codex-native system-prompt support.
- Exit: `uv run pytest -q` green; a dry-run claude command carries
  `--system-prompt-file` whose content includes persona + style text; codex
  command assembly provably unchanged.

### M2 — Author system prompts, slim the turn prompt [depends on M0, M1]
Move identity, craft, and surviving guards into the cached per-role layer; cut the
per-turn layer to situation + job + compact tool card.
- Author base DM prompt (writer-GM identity, genre space, craft principles, fair
  and consequential narration) and base player prompt (persona bridge, character
  knowledge boundary, fair self-narration of outcomes including failure and cost).
- Apply ledger dispositions: relocate survivors into base prompts; keep
  turn-specific guards in the turn prompt; drop only ledger-approved rows.
- Shrink `_render_turn_start`: situation, what changed, this turn's job,
  methodology pointer, compact tool contract; process reporting routed to
  messages, never `glass_turn_append` prose.
- Update `docs/design/prompt-writing.md` to the new stack; note the system-prompt
  layer in `docs/design/architecture.md`.
- Exit: `uv run pytest -q` green; every ledger-relocated section absent from the
  slim-path turn prompt and present in a system prompt; rendered scene-play turn
  prompt at least a third shorter (revised from "half" after measuring: the
  remaining bulk is the per-turn-type tool card, which teaches exact call shapes
  and is deliberately kept); ledger audit shows zero silently-lost guards.

### M3 — Creative methodology contracts [depends on M2]
Rewrite the generative methodologies as gated creative contracts, enforced inside
existing turns via bootstrap `validate=` checks and required facts.
- `organization-bootstrap.md`: premise gate — the org wants something guarded,
  hidden, or contested; service-provider premises rejected. Wire the dead
  `operator_org_direction_section` (`context.py:277`) so the stored fact renders.
- `arc-creation.md`: named antagonist with goal, resources, and next move, plus
  inaction consequence — required facts, validated before the mode ends.
- `scene-prep.md`: opposing will on screen, a thing irrevocably losable this
  scene, and a problem family selected under recency-tracked variety state.
- `character-creation-*`: each PC gets a want the job can't satisfy and one
  intra-party conflict of interest; relationship phase capped and pointed at
  friction.
- "Neutral" removed as a spec adjective across methodologies where it means
  bland rather than non-narrative.
- Exit: `uv run pytest -q` green; each gate enforceable from facts (CLI-level
  tests where a `glass` surface changes); no new turn types, no added rotations.

### M4 — Fresh campaign A/B + guard regression pass [depends on M3]
The corpus is the test.
- Run a fresh campaign end-to-end on the new stack.
- Read it against ash-ledger on: voice distinctiveness, antagonist presence,
  genre variety, sentence legibility without a glossary, process leakage,
  outcome fairness.
- Check every retired guard's failure mode for recurrence; restore recurrences in
  the cheapest layer that holds; record outcomes in the ledger.
- **[DECISION]** Operator verdict on corpus quality; decides what iterates next.
- Exit: operator has read the corpus; ledger updated with observed outcomes;
  restored guards (if any) merged.

### Decisions needing your input

| Where | Decision you own |
| ----- | ---------------- |
| M0 | Final guard dispositions + historical failure modes to add |
| M4 | Corpus quality verdict against ash-ledger; next iteration |
