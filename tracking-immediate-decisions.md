# Tracking — Immediate Decisions

A working list of decisions we're holding off until they come up naturally during build. These aren't problems we're avoiding; they're problems where pre-deciding would be bureaucracy. When the build hits one of these, decide and commit. Move resolved items down to "Done."

## Held for organic resolution (decide as the build hits them)

- **Glass CLI surface in detail.** Flags, return formats, error codes — decided as we add subcommands.
- **Postgres schema.** Tables and columns — decided as the orchestrator and CLI need them.
- **FalkorDB session-graph schema.** Node/edge taxonomy for Session/Scene/Turn/Beat — decided as we upsert real entities.
- **DM workspace structure.** What lives in `agents/dm/workspace/` — decided as the DM agent first uses it.
- **Scene framing / campaign framing format and update cadence.** DM owns these. Format and refresh policy decided when the first DM turn produces them.
- **Note ratification flow mechanics.** Direction is set (encyclopedia entries, `glass note` signals DM to canonize or reject). Pin the mechanics during the first ratification path.

## Held for first-real-session learning

- **Closure (v0 and beyond).** Hard turn caps + DM voluntary wrap is enough for v0. Real closure design after we see what runaway sessions look like. See [`docs/design/scene-ending.md`](docs/design/scene-ending.md).
- **Death saves / 0-HP semantics.** Atomic combat has no bearing on death saves; figure out the policy when a PC actually drops.
- **NPC speech in combat.** Whether NPCs speak only on DM turns or can be inserted mid-player-turn — decide when the first instance comes up.

## Held for an intentional pre-build design round

- **Bootstrap / session zero.** First session has no transcript, no scene-framing, no characters. We need a "campaign init" + opening flow before worldbuilding mode can run. Decide before the first build session.

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
