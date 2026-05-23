# Orchestrator Spec

The orchestrator picks the next agent, builds one injected prompt, spawns the provider, and verifies that the agent committed the turn through `glass`.

## Canonical Turn Contract

There is one agent runtime path:

1. Build an injected prompt containing identity, mode, scene, methodology, allowed command surface, fact graph continuity, message roster, trackers, and output contract.
2. Stage the active turn with `glass turn begin`.
3. Mint a short-lived signed Glass API grant for the CLI proxy. The grant is an implementation detail behind `glass`; it is not an agent interaction mode, contains no workspace paths, and writes no grant file.
4. Spawn the provider with `cwd = templates/`, which is read-only methodology/how-to reference for agents, not campaign state.
5. The agent reads facts and hard state through `glass check`, `glass fact pack`, and the commands named in the prompt.
6. The agent mutates durable state only through `glass` commands and graph facts.
7. The agent closes with `glass done`.
8. The agent submits public prose with `glass turn append --body`.
9. The orchestrator verifies the committed turn row exists and uses that row for post-turn bookkeeping.

No agent turn creates turn files, prose files, closeout files, actor workspaces, per-player cwd trees, markdown sync manifests, or alternate API/file state channels.

## State Boundary

Agent-readable continuity is the fact graph plus hard-state command output, accessed through `glass`. Public prose is viewer/archive material after commit. Files under `templates/` are durable reference methodology, instructions, rules, and examples.

## Failure Handling

A turn fails if the provider exits non-zero, times out, fails to stage a valid `glass done` closeout, or fails to submit public prose with `glass turn append --body`. The orchestrator stops at the last committed state boundary.
