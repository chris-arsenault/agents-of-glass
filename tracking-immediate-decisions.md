# Tracking — Immediate Decisions

A working list of decisions we're holding off until they come up naturally during build. These aren't problems we're avoiding; they're problems where pre-deciding would be bureaucracy. When the build hits one of these, decide and commit. Move resolved items down to "Done."

## Held for organic resolution (decide as the build hits them)

- **Curate-don't-copy enforcement in `context.py`.** The orchestrator's
  `_copy_shared_context` still bulk-copies the entire world bible
  (`../the-glass-frontier-lore/player/`) into every agent CWD. Per the curation
  principle, players should only see `campaigns/<id>/shared/lore/` (the curated
  subset). Update when the campaigns/ layout becomes the canonical orchestrator
  read-from path.

- **Glass CLI surface in detail.** Flags, return formats, error codes — decided as we add subcommands.
- **Postgres schema.** Tables and columns — decided as the orchestrator and CLI need them.
- **FalkorDB graph schema.** Node/edge taxonomy for Campaign/Arc/Scene/Turn/Beat/NPC/Faction/etc. — decided as we upsert real entities.
- **DM workspace structure.** What lives in `agents/dm/workspace/` — decided as the DM agent first uses it.
- **Scene framing / campaign framing format and update cadence.** DM owns these. Format and refresh policy decided when the first DM turn produces them.
- **Note ratification flow mechanics.** Direction is set (encyclopedia entries, `glass note` signals DM to canonize or reject). Pin the mechanics during the first ratification path.

## Held for first-play learning

- **Closure (v0 and beyond).** Hard turn caps + DM voluntary scene end is enough for v0. Real closure design after we see what runaway scenes look like. See [`docs/design/scene-ending.md`](docs/design/scene-ending.md).
- **Death saves / 0-HP semantics.** Atomic combat has no bearing on death saves; figure out the policy when a PC actually drops.
- **NPC speech in combat.** Whether NPCs speak only on DM turns or can be inserted mid-player-turn — decide when the first instance comes up.

## Held for an intentional pre-build design round

- **Methodology doc content.** Stubs at [`templates/methodologies/`](templates/methodologies/)
  with shape outlined. The real instructions need to be co-authored.
- **Hard caps per bootstrap phase and per scene.** Campaign planning, character
  creation, and per-scene-type need turn caps. Pin during build.
- **Character creation: sequential or parallel?** Each player runs in turn (orchestrator
  cycles through them) is the simpler v1. Parallel speeds it up but complicates DM ratification.

## Done — items previously on this list, now resolved

- Claude invocation: `claude -p --dangerously-skip-permissions` with all tools. (See [`docs/design/architecture.md`](docs/design/architecture.md).)
- World bible vs campaign lore vs personal notes — three-layer split. (See [`docs/design/architecture.md`](docs/design/architecture.md).)
- Orchestrator resumable + clear command. (See [`docs/design/architecture.md`](docs/design/architecture.md).)
- Audit log. (See [`docs/design/architecture.md`](docs/design/architecture.md).)
- Foreground monitoring; ops CLI separate from `glass`. Real logs post-MVP. (See [`docs/design/architecture.md`](docs/design/architecture.md).)
- Tests are CLI-only against data stores. No orchestrator tests.
- Config in TOML; secrets via external secrets management.
- DM owns scene framing and campaign framing.
- Lore is encyclopedia-shaped; player/DM personal notes are journal-style.
- Turn artifact contract: agents write public prose to `TURN.md`; stdout is the
  fallback. The orchestrator owns the transcript header.
- Bootstrap state: `glass` owns scene state files; until Postgres exists, the
  state files live in `campaigns/<id>/arcs/<arc>/scenes/<scene>/state.json`.
- Sessions removed: scenes are the unit of play. The agents play as long as the
  operator runs the orchestrator. Scene types (town, exploration, combat, social,
  investigation, travel) replace mode-as-fuzzy-concept.
- Three-level player-facing context: `campaigns/<id>/context.md`,
  `arcs/<arc>/context.md`, `arcs/<arc>/scenes/<scene>/context.md`. Each authored
  by the DM during the relevant prep methodology, projected into player CWDs as
  `campaign-context.md`, `arc-context.md`, `scene-context.md`. Glass CLI
  (`glass arc create`, `glass scene create`) manages the directory hierarchy.
- Templates vs runtime split: authored content lives in `templates/`; runtime
  state lives in `sessions/<id>/` (and the future per-campaign live root).
- Unix security model: each player agent runs as a dedicated Unix user
  (`aog-tev`, `aog-sumi`, `aog-renno`, `aog-kit`); the DM runs as the operator.
  Filesystem access enforced via group-based chmod on the campaign workspace
  and per-turn CWDs. Provisioned via `sudo bash scripts/provision-agents.sh`
  (creates users + groups + sudoers + permset helper). Falls through silently
  when not provisioned (orchestrator runs everyone as operator).
- Bootstrap flow: 2 agent-driven phases (campaign-planning, character-creation)
  before regular sessions start. Each phase = its own session running a
  phase-specific mode. After character-creation, the campaign is `active` and
  the first session is just the first session. Campaign-level state machine in
  `campaigns/<name>/state.json`. See [`docs/design/game-start.md`](docs/design/game-start.md).
- Per-campaign live root: `campaigns/<name>/` containing copies of `dm/`, `players/`,
  `shared/` plus the campaign's `sessions/`. Methodologies snapshot frozen per
  campaign so editing templates does not retroactively change a running campaign.
