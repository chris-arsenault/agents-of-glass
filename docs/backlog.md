# Backlog

Ideas worth pursuing once the core agentic loop is producing transcripts. Each entry is a sketch — what it is, why it matters, what we'd lift from existing work, and what's not yet figured out. Order is not priority.

These are out of scope for v1. The first session that runs end-to-end is the trigger to revisit.

---

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
