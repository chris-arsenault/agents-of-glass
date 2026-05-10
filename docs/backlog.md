# Backlog

Active deferred work for Agents of Glass. Completed tracking items are removed
from this file once the implementation and docs land; this is not a changelog.

Order is approximate priority, not a commitment.

## Next Run Follow-Ups

### Prelude And Turn-Order Guardrails

The first prelude attempt exposed that the `prelude` coordinator can leave the
DM taking repeated turns instead of handing play to the players. It also exposed
that a DM can write `glass ...` command lines into public prose instead of
executing them.

Do next:

- Decide whether prelude is a real registered arc, a child scene under the
  opening arc, or a special bootstrap phase with explicit projection rules.
- Fail fast if bootstrap/prelude/action modes produce an invalid speaker loop,
  especially repeated DM turns where player turns are expected.
- Fail fast or warn loudly when a bootstrap-critical turn writes executable
  `glass ...` lines into `out.md` without the corresponding state mutation.
- Decide whether freeform table pressures such as "Transit Advisory: standard
  review" are authored table prose or should project from durable
  trackers/clocks.

### Character Creation Context Isolation

New character rows now require species, culture, archetype, organization role,
bio, and character goals. The remaining issue is context shaping: characters
should not be optimized around a campaign mystery board the players arguably
should not know yet.

Do next:

- Consider giving players only setting, party organization, premise, tone, and
  curated player-visible lore before the first character pass.
- Hide prior player turn summaries until each player has made an initial pitch,
  or implement a two-pass flow: blind independent pitch first, relationship and
  party-cohesion pass second.
- Decide whether `pronouns` should be required, explicitly optional, or
  rendered as a visible "unspecified" value.

### State Projection Hardening

Campaign checkpointing and restore now snapshot the filesystem, Postgres
runtime/search/vector rows, and FalkorDB graph nodes/edges. Keep this item open
only for defects discovered during real recovery work.

Do next:

- Exercise `aog campaign restore` during the next genuine failed run, not only a
  synthetic smoke test.
- Tighten projection-specific repair cases that appear in real use.
- Continue reducing vestigial runtime JSON where practical; if a JSON or
  markdown projection must remain, make one projection API responsible for
  rewriting it from the source of truth.

### Projection / Durable Workspace Parity

The `test-4` Turn 3 debug output exposed a brittle split between the agent's
projected cwd and the durable campaign workspace. `glass arc create
halsworn-edge` created canonical files under `campaigns/test-4/arcs/`, but the
new arc did not appear in the current projection (`.glass-cwd/.../arcs` was
missing). Mara then tested whether the canonical arc directory was writable,
found that it was, and used the Claude `Write` tool against absolute durable
paths for `arcs/halsworn-edge/plan.md` and `context.md`. That was a rational
response to the workspace shape, not a prompt wording problem.

The same turn also showed a state-source mismatch: `glass arc create` returned
success and created files, but `glass arc list` returned `arcs: []`. This points
at arc lifecycle state still relying on vestigial JSON while runtime state is
Postgres-backed, or at least at projections/state refreshes not sharing one
canonical source.

Default debugging checklist:

- Inspect the agent transcript for actual tool calls, not just
  `claude-debug.log`; the debug log records dispatch/failure but not full Bash
  command text.
- Compare `glass <command>` output, canonical filesystem paths, projected cwd
  paths, Postgres runtime rows, Falkor graph rows, and `audit.jsonl`.
- Treat "agent wrote absolute canonical path" as evidence that the projection
  lacked a valid mutation/readback loop, not primarily as an instruction
  compliance issue.
- Confirm whether a CLI mutation is visible inside the same turn's projection
  before expecting the agent to continue from the new files.

Do next:

- Make `glass arc create` and related lifecycle commands update the same
  canonical state store used by `glass arc list`, the orchestrator, and
  checkpoint/restore. Prefer Postgres-backed runtime state; eliminate or
  project any remaining JSON state instead of letting commands mutate it
  independently.
- Provide a robust projection refresh or parity mechanism for files created by
  Glass during a turn. If a command creates `arcs/<slug>/plan.md`, the current
  agent should be able to read and continue from `arcs/<slug>/plan.md` in its
  cwd without falling back to absolute canonical paths.
- Design a `glass sync` / `glass commit`-style surface only if it preserves the
  mutation choke point: copy intended cwd changes or scratch drafts into durable
  markdown, update Postgres, graph, text search, vector search, and audit in one
  operation. Do not make agents manually coordinate separate filesystem, graph,
  and DB commands.
- Decide the supported write workflow for scaffolded files. Either commands
  like `glass arc create` should accept `--plan-from` / `--context-from`, or
  `glass note write arcs/<slug>/plan.md --from scratch/plan.md` should be the
  blessed durable writer and should also update indexes/audit consistently.
- Add a post-turn parity check that flags durable files written outside Glass
  and flags Glass-created files that were not visible in the projection when
  later turn steps needed them.

### DM Mutation Discipline

The `test-4` bootstrap showed that the DM projection is read-only, but the DM
process still runs as the operator user and can address canonical campaign paths
outside the projection. Turn 2 also appeared to create canonical lore and graph
state without matching `glass lore import` / `glass lore upsert` audit entries.
That means the projection limits accidental writes, but it does not yet make
Glass the single mutation choke point for the DM.

Do next:

- Run the DM under a restricted campaign role instead of the operator user, or
  otherwise make canonical campaign files non-writable except by the Glass
  daemon/API.
- Keep the projected workspace as the agent's readable view, with only
  `scratch/` and the current turn output/debug paths writable.
- Require all durable DM mutations to go through one Glass command/API surface;
  agents should not have to run separate commands to write markdown, update
  Postgres, upsert graph entities/edges, refresh text/semantic indexes, and
  append audit records.
- Replace split write flows such as "write note, then lore upsert" with unified
  commands whose semantics are explicit: one invocation commits the prose,
  metadata, graph projection, search/vector projection, and audit entry
  together.
- Audit every mutating Glass path consistently; investigate why imported lore
  and graph rows can appear without corresponding audit entries, and make graph
  projection a default part of durable lore/note writes where applicable.
- Add a post-turn integrity check that compares canonical file changes,
  Postgres mutations, graph mutations, and audit records; fail or flag any
  durable mutation that bypassed Glass.
- Add a scratch-promotion check for bootstrap/planning turns: important
  `scratch/*.md` drafts should either be imported into durable state,
  explicitly referenced as temporary working notes, or left with a visible
  warning before the turn is accepted.
- Fix markdown search/indexing for imported lore; live inspection found durable
  lore that did not appear through `glass search text --type markdown`.

## Deferred Until Demonstrated

### Hard Closure Backstop

Soft closing exists: `glass scene closing-down`, final rounds, scene overrun
warnings, action-scene visible endpoints, and `glass scene end`. Do not build
hard forced closure, twist budgets, or a closer agent until transcripts show
that soft closure still lets scenes run away. See
[`design/scene-ending.md`](design/scene-ending.md).

### Death Saves / 0-HP Policy

0 HP means out of the action, not automatic death. Lasting consequences are
already supported. Do not design death saves until a real campaign creates the
need.

### NPC Speech In Action Scenes

Leave open whether NPCs speak only on DM turns or can be inserted
mid-player-turn. Decide when a real action scene demands it.

### Travel / Montage Protocol

Travel and montage can run as ordinary scene play for now. Add a dedicated
protocol only after transcripts show repeated drift or awkwardness.

## Future Systems

## Map Integration (Hex Boards)

**What:** Spatial state for scenes that need it — combat, exploration of a structured space, party positioning. Hex grid with terrain tags, occupant tracking, line-of-sight, and a basic distance/movement model. The map is a queryable surface the DM can consult ("how far from Karrith to the gantry?") and player agents can reason about ("can I get to cover this turn?").

**Why it matters:**
- Combat without a map is exactly where the agentic loop loses cohesion — every agent has its own mental picture of where things are, and they drift apart inside three turns.
- A hex map is also an analysis surface — replay paths, reach metrics, "did the party ever actually explore the back of the locale?"
- It's another thing the live-session site (see below) can render.

**Source to crib from:** `/home/dev/repos/the-canonry-game` — a Godot/.NET civilization sim with a hex grid, terrain coverage, and structured world generation. Specifically:
- `Engine.WorldGen` — hex grid + terrain + coverage + map generation
- `docs/architecture.md` and `docs/game-systems.md` for the spatial model
- The deterministic-kernel mutation discipline is overkill for us, but the *hex math* and *terrain tagging* are directly transferable

**Sketch of integration:**
- A new mode (or a parameter on existing modes) declares "this scene has a map." On entry the DM seeds a small grid with terrain tags and occupant placements.
- Map state lives in Postgres (hard state — positions are facts) with a serialized snapshot in the session dir for replay.
- New `glass` subcommands: `glass map show`, `glass map move <occupant> <hex>`, `glass map distance <a> <b>`, `glass map reach <occupant>`.
- DM and player agents both can call read commands; only the DM mutates.

**What's not figured out:**
- How tightly should map state couple to combat mechanics? Does line-of-sight gate certain checks?
- Do we want a shared coordinate system across modes (so a town's map and a combat's map are subsets of one larger map), or per-scene maps? Probably per-scene for v1.
- Rendering format for the live site: ASCII art, SVG, image gen?

---

## Image Generation (Illuminator-Backed)

**What:** The DM can request an illustration during a scene — an NPC portrait, a locale establishing shot, a key artifact, a map overhead. The image is generated, attached to the transcript, and made available in the live session view (see below). Players see it as part of the scene context the next turn.

**Why it matters:**
- Visual grounding keeps the agents anchored to the same scene. Five separate text descriptions of an NPC drift toward five separate NPCs; one shared image holds them in place.
- The transcript with embedded images is a much richer corpus artifact than prose alone. Narrative-weaving passes can use the images, image-based analysis becomes possible, the live site has actual visuals.
- It mirrors the table experience — at a real game, the DM sometimes drops a physical printout. The agentic version can do the same.

**Source to crib from:** `/home/dev/repos/illuminator` — a CLI for generating cohesive illustration batches from TOML packs. Specifically:
- The pack format (named styles, palettes, type-specific production guidance) gives us a way to keep visuals consistent across a session
- The provenance metadata model (PNG sidecars, embedded provenance) is exactly the kind of structured artifact this project values
- Atlas export for sprites/icons is potentially useful for the map system above

**Sketch of integration:**
- We seed a `pack.toml` per session with the campaign's visual style locked in (palette, art direction).
- New `glass` subcommand: `glass image request <subject> --kind <portrait|locale|item|overhead>`. The DM calls this; the orchestrator queues a generation and proceeds.
- Generation is async — the next turn doesn't block on the image. Once ready, the image lands in `sessions/<id>/images/` with provenance and is referenced from the transcript at the correct turn.
- Players see images via their tool surface: `glass image list <session>` returns recent images with descriptions; they can fetch by id.
- Failed generations are transcript events (per [`principles/transcripts-as-corpus.md`](principles/transcripts-as-corpus.md) — failures are corpus data).

**What's not figured out:**
- Cost/rate-limit policy. Image gen isn't free; the DM needs a budget the way they have a twist budget.
- Style continuity across sessions — does a campaign get a single style pack, refined over time?
- Whether player agents should be able to *request* images (they ask in-character "what does she look like?") or only *consume* them.
- How images affect agent context — do we describe images textually for agents, or do we send them as multimodal input?

---

## Live Session Website

**What:** A read-only public website that streams the session transcript as it's generated. Deployed to the user's AWS account. Anyone with the URL can watch the four agents play in real time, see the dice roll, see the map (if the map idea ships), see the images (if that idea ships), see the mode transitions and the budget pressure.

**Why it matters:**
- Watching is the whole appeal for an audience. The transcript is *good* on its own, but a live unfolding session has narrative tension that a static log doesn't.
- It's also a debugging aid — when a session goes off the rails, we can scrub back through the live timeline and see exactly when.
- It's a portfolio surface — "here's what an agentic TTRPG looks like" with a permalink, not an asciinema.

**Sketch of integration:**
- The orchestrator emits structured events to a small write-side service (probably an S3-backed event log behind a Lambda) every time a turn appends, a mode transitions, an image is generated, dice roll.
- The frontend is a static SPA (served from S3 + CloudFront) that subscribes to the event log via WebSocket or polling.
- The site only displays what's *already in the transcript* — no agent context, no prompts, no orchestrator internals. Everything visible to the audience is also corpus.
- Per-session URLs (`/sessions/<id>`); session list is opt-in (the user marks a session "public" before/during the run).

**What's not figured out:**
- Real-time-ish vs strictly post-hoc. A 30-second delay buys us a sanity-check window before agent output goes public; instant streaming feels more alive but commits us to whatever the agents emit.
- Whether to render images and maps inline or as a sidebar.
- Auth model for "public but discoverable" vs "public but unlisted." Probably unlisted with a share-link by default.
- Cost — CloudFront + Lambda + an event store is cheap, but bursty image rendering can add up.
- AWS region / account where this deploys (the user has an account; specifics are an implementation detail).

---

## How the Three Relate

These are independent enough to ship in any order, but they amplify each other:

- The **live site** without **image gen** is text-only — fine, but flatter.
- **Image gen** without the **live site** means images live in the corpus but no one watches them happen.
- The **map** is the highest-leverage bridge — it makes combat make sense (by itself), it gives the live site a primary visual surface, and it gives image gen a concrete subject to render.

If we're picking an order when these come up: **map first**, then **image gen**, then **live site**. The map fixes the most painful current gap (spatial coherence in combat); image gen builds on the map; the live site is the showcase that depends on having something visual to show.
