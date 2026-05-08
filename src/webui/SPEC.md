# `webui` — Spec

A read-only public website that streams a running session as the agents play. Deployed to the operator's AWS account. Anyone with the URL can watch the four players and the DM take their turns, see the rolls, see mode transitions, see the messages they choose to surface.

**Status:** Not started. This directory exists as a home for the spec until we pick it up. See [`/docs/backlog.md`](../../docs/backlog.md) for where this sits in the priority order — current recommendation is map → image gen → live site, in that order.

## What It Shows

Strictly things that are already in the corpus:

- Per-turn prose with the orchestrator-supplied header (speaker, role, mode, scene, turn number, timestamp)
- Inlined mechanical events (dice rolls, HP changes, mode transitions)
- Mode boundaries as visual scene breaks
- Optional sidebar surfaces if/when those backlog items ship: the map, generated images, current scene framing
- Session list (opt-in — operator marks a session "public" before/during the run)

What it does **not** show:

- Agent prompts / role files
- Orchestrator internals
- Private journals, secret notes, DM-only messages, monster stat blocks
- Anything outside what `glass turn append` has committed to the public transcript

## Architecture (Sketched)

Per the [backlog entry](../../docs/backlog.md#live-session-website):

- The orchestrator emits structured events to a write-side service (probably an S3-backed event log behind a Lambda) every time a turn appends, a mode transitions, an image is generated, dice rolls.
- The frontend is a static SPA served from S3 + CloudFront that subscribes to the event log via WebSocket or polling.
- Per-session URLs (`/sessions/<id>`); session list is opt-in.
- Optional 30-second delay before public visibility — buys a sanity-check window without committing to "instant whatever the agents emit."

## Open When We Build

- **Tech stack.** Static SPA (TS/React/Vite, mirroring `the-glass-frontier`'s client) or a Python-served alternative? Lean TS/React if we want anything resembling the Glass Frontier client experience; Python if we want one stack across the project.
- **Real-time-ish vs delayed.** 30-second buffer or instant?
- **Auth model.** Public + unlisted (share-link), or fully discoverable? Default unlisted.
- **Image and map rendering.** Inline or sidebar? Depends on the map and image-gen backlog items shipping first.
- **AWS region / deployment specifics.** Operator's account.

## Why It's Out of Scope for v1

The transcript is the product; the webui is a viewer for the product. We need transcripts before the viewer means anything. Once the agentic loop produces sessions worth watching, the viewer becomes the showcase — but premature webui work risks shaping the corpus around presentation instead of the other way around.

When we do pick this up, the first iteration is: render the markdown transcript with header styling and inlined event lines. Everything else is enhancement.
