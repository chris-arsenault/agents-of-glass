# Codex Findings

## What The Repo Describes

This repo designs a research system for fully agentic tabletop play: one DM agent and four player agents run a session with no human at the table. The output is not a game app; it is the transcript plus the structured state and corpus created along the way.

The core architecture is:

- A Python orchestrator owns turn order, mode state, context packaging, and transcript append.
- Agents are fresh `claude -p` subprocesses each turn.
- `glass` is the only state mutation surface.
- Markdown holds prose, FalkorDB mirrors canonical narrative entities, and Postgres holds hard state plus query metadata.
- The guiding rule is: codify dice, numbers, IDs, inventory, mode/turn metadata, and event timing; leave most play in prose.

The design is coherent. The strongest idea is the separation between agent prose and orchestrator/CLI structure. That fits the research goal well.

## Major Blind Spots

### 1. Turn Commit / Failure Atomicity

The largest missing design is what happens when a turn partially succeeds. Agents can call `glass` during a turn, mutating Postgres, the graph, or audit logs, and only afterward does the orchestrator append the prose transcript. If the agent times out, crashes, emits malformed prose, or the orchestrator dies between a roll and transcript append, the system can get state changes with no transcript record, or a transcript with missing canonical events.

For this project, that is not a small implementation detail. The transcript is the corpus, and every mutation is supposed to be captured inline. The design needs a turn-scoped commit protocol before build starts: reserved `turn_id`, staged tool events, explicit commit on transcript append, and a system-authored failure turn if the agent fails.

"Failures are preserved" is the right principle, but the failure still needs to be represented as a coherent committed event.

### 2. The Final Turn Artifact Contract Is Underspecified

The docs say agents emit prose and exit, while also mentioning `glass turn append`, orchestrator wrapping, and in one place "structured output" that the rest of the design has rejected.

Before coding, define exactly how an invocation returns its turn:

- Does the agent write `TURN.md`?
- Is stdout ignored, captured, or considered the turn?
- Can agents call `glass turn append`, or only the orchestrator?
- What happens on nonzero exit?
- What is the minimum validation before committing?

This does not need rich schema. It does need a narrow, boring contract.

### 3. `GLASS_ROLE` Is Not A Security Boundary

The docs rely on per-subcommand permissions enforced by an environment variable, plus ephemeral CWD isolation. If an agent has shell-like tool access, it can spoof `GLASS_ROLE=dm` unless `glass` has a stronger credential model. If the subprocess can reach absolute paths outside the CWD, symlink or bind-mount isolation may also be weaker than intended.

Because DM-only secrets, private messages, and player separation are part of the fiction engine, this deserves real design. Use per-turn capability tokens, OS users, containers, or a local daemon that authenticates orchestrator-spawned processes. If v1 assumes Claude cannot run arbitrary shell, state that explicitly.

### 4. Canonicalization / Graph Write Lifecycle Is Too Vague

The repo says the graph mirrors markdown, the DM ratifies player proposals, and canonical notes become graph entities. But the lifecycle is not yet designed deeply enough for a core artifact.

The design needs the minimum contract for:

- entity IDs and frontmatter shape
- entity identity resolution and dedupe
- note revision history
- when transcript facts become canonical
- how player proposals are accepted, rejected, or partially ratified
- how graph upsert failures are surfaced in the transcript or audit trail

The graph is one of the project's success criteria, so this cannot be entirely deferred to "we'll see after a session."

### 5. Prompt-Injection From Corpus Content Is Not Addressed

A lot of generated text becomes future context: transcript excerpts, messages, journals, party knowledge, summaries, and canonical notes. The design treats filesystem visibility carefully, but not instruction/data separation. A player message or journal entry can contain text that looks like an instruction to the next agent.

This matters because the system intentionally feeds agent-authored prose back into prompts. Context packages should render prior transcript, messages, notes, and summaries as quoted data, with strong role instructions that only `TURN_START.md`, role files, and mode framing are instructions.

This is not product security; it is protecting the experiment from self-poisoning.

### 6. Combat Mechanical Authority Is Not Yet Buildable

The mechanics define checks, momentum, attributes, skills, HP, and inventory, but not the authoritative consequence path from outcome tier to damage, status, or target mutation. Combat examples show targets and damage, but the CLI sketch does not really define target state mutation.

If combat is in v1, decide who can mutate monster HP, how damage is derived, whether `glass roll` can include a target, and whether outcome narration can claim consequences not recorded mechanically. Otherwise combat will be the first mode to corrupt itself.

### 7. Run Metadata / Experimental Reproducibility Is Underdesigned

The project is framed as research, but the docs mostly capture the fiction corpus, not the run conditions. The system should record model IDs, prompt/template hashes, mode file versions, context package manifests, CLI version, token/cost/time usage, DB namespace, and random seeds for dice.

This does not belong in the public transcript, but it does belong in the run ledger.

Without that, later comparisons across sessions will be muddy: it will be hard to know whether a behavioral change came from mode design, agent files, model changes, context window changes, or tooling.

## Bottom Line

I would not redesign the concept. The main architecture is sound for the stated experiment.

The build should not start by deepening lore, modes, or prose rules. Start by locking the runtime invariants: turn artifact contract, turn-scoped commit/failure handling, stronger `glass` authorization, and the minimal canonical note/graph lifecycle. Those are the places where an otherwise good design can lose its corpus.
