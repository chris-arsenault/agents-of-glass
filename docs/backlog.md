# Backlog

Active deferred work for Agents of Glass. Completed tracking items are removed
once implementation and docs land; this is not a changelog.

## Agent Runtime Contract

The current contract is CLI-only: agents read and write state through `glass`,
close with `glass done`, and submit public prose through
`glass turn append --body`.

Follow-ups:

- Add a prompt/template lint that fails on agent-facing references to file
  authoring, stdout prose, direct API calls, markdown sync, or per-agent working
  directories.
- Add a post-turn integrity check that reports any file changes made during an
  orchestrated agent turn.
- Keep API/grant implementation details out of injected prompts except as
  environment plumbing for the `glass` command.

## Codex System-Prompt Support

Claude-provider actors run with a per-role custom system prompt
(`--system-prompt-file`, assembled from base document + persona + narrative
style). The codex branch is unchanged and codex actors still run with codex's
default instructions.

Follow-ups:

- Verify whether `codex exec` supports a base-instructions override compatible
  with full replacement, and thread the same assembled document through it.
- Until then, expect voice/register differences between providers in
  mixed-codex campaigns.

## Continuity Fact Adoption

The embedded facts table is the permanent home for arbitrary continuity facts.

Follow-ups:

- Review real campaign turns for facts that stayed trapped in prose and add
  methodology guidance where agents missed `glass fact set`.
- Improve fact-pack formatting so scoped facts, relationships, and current-scene
  facts are easy for agents to scan.
- Add focused commands for common fact shapes only after repeated drift proves a
  need. Do not reintroduce JSON or markdown as the agent-facing store.

## Character Creation Context Isolation

Character creation should use the same CLI-only contract as scene play.

Follow-ups:

- Give players only organization facts, setting brief, party premise, tone, and
  curated player-visible facts before the first character pass.
- Hide prior player turn prose until each player has made an initial pitch, or
  implement a two-pass flow: blind independent pitch first, relationship and
  party-cohesion pass second.
- Decide whether `pronouns` should be required, explicitly optional, or rendered
  as a visible "unspecified" value.

## Viewer And Corpus Work

The viewer is an operator/audience surface, not an agent context surface.

Follow-ups:

- Render a current-state panel from facts and hard state without implying that
  agents read files.
- Keep broad human file inspection visually distinct from agent-visible state.
- Continue improving transcript and turn-feed views for narrative review.

## Generated Media

Generated images remain out of the critical turn path.

Follow-ups:

- Queue image generation asynchronously so the next turn does not block.
- Store provenance and attach generated assets to committed turn rows or viewer
  surfaces after generation completes.
