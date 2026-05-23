# `webui` — Spec

A read-only campaign viewer for the operator and anyone the operator lets watch.
It is not an agent context surface and it is not an agent interaction mode.
Human viewers may inspect campaign files, database-backed state, narrations,
messages, and operational debug surfaces as the UI grows.

## Visibility Model

There are two different visibility questions, and the UI must not blur them:

1. **What can the human viewer inspect?** Potentially every operator/debug
   surface and backing store. The viewer is an observation/debug surface.
2. **What did the player agents have visibility into?** The injected prompt plus
   the output of their authorized `glass` commands.

The **Active Table** panel must not imply a second agent state surface. If it is
present, it is a viewer rendering of CLI-readable state such as graph facts,
scene trackers, clocks, and committed public prose. It must not be treated as
something agents read or write directly.

Do not infer agent visibility from DM notes, hooks, NPC notes, monster files,
messages, transcript text, clocks, rolls, or the viewer's file browser. A fact
is agent-visible only when it is in the injected prompt or returned by an
authorized `glass` command.

## Current Local Architecture

- REST API: `src/cli/web_api_server.py`, under `/v1/campaigns/<id>/...`. This
  is for the read-only viewer, not for agent turns.
- Campaign selection: the frontend lists campaigns from `/v1/campaigns` and
  lets the viewer switch between them in the top bar. The selected campaign is
  UI state, not a build-time or runtime config value.
- Frontend: `frontend/`, Vite/React.
- Local helper: `scripts/run-webui-local.sh`, which starts the read-only web API
  and frontend in the mapped Docker port range.
- Source of truth:
  - Postgres for turns, messages, rolls, characters, hard state, and runtime.
  - Markdown for campaign files.

## Viewer Surfaces

- **DM row:** current scene/play DM surface. This is the counterpart to Active
  Table, not a document browser. It may show active clocks, scene trackers,
  explicit beats, current scene prep cues, DM-facing tarot, live hooks, and
  recent play-control events. It should not become a long-term journal, lore, or
  file-reading surface.
- **Active Table:** a viewer rendering of CLI-readable current state, as defined
  above.
- **Narrations:** turn rows in turn order.
- **Messages:** message bus rows.
- **File browser / DM notes / lore:** inspection surfaces for human viewers,
  not evidence that a player agent saw the file.
- **Lore/debug summaries:** coherence/debug surfaces, not agent-visible state
  unless the relevant content is in graph facts or authorized command output.

## Deployment Notes

A later hosted version can mirror the same resources to a service behind
CloudFront or another static host. That deployment decision must preserve the
visibility model above: broad human inspection is allowed, but agent visibility
still comes only from injected prompt content and authorized `glass` command
output.
