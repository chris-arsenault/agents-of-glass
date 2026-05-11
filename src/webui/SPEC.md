# `webui` — Spec

A read-only campaign viewer for the operator and anyone the operator lets watch.
It is not a player-agent projection. Human viewers may inspect the whole
campaign workspace: DM notes, lore, messages, narrations, table files, graph
state, and operational debug surfaces as the UI grows.

## Visibility Model

There are two different visibility questions, and the UI must not blur them:

1. **What can the human viewer inspect?** Potentially everything in the campaign
   workspace and backing stores. The viewer is an observation/debug surface.
2. **What did the player agents have visibility into?** Only what was projected
   into their per-turn CWD plus what their authorized `glass` commands could
   read.

The **Active Table** panel answers the second question for shared scene state.
It renders only `campaigns/<id>/table/**`:

- `table/index.md`
- `table/scene.md`
- `table/handouts/**`
- freeform markdown files under `table/`

Do not populate Active Table from graph entities, DM notes, hooks, NPC notes,
monster files, messages, transcript text, clocks, rolls, or the viewer's file
browser. Those may be visible elsewhere in the web UI, but they are not on the
player-agent table unless the DM explicitly puts or links them under `table/`.

## Current Local Architecture

- REST API: `src/cli/web_api_server.py`, under `/v1/campaigns/<id>/...`.
- Frontend: `frontend/`, Vite/React.
- Local helper: `scripts/run-webui-local.sh`, which starts the read-only web API
  and frontend in the mapped Docker port range.
- Source of truth:
  - Postgres for turns, messages, rolls, characters, hard state, and runtime.
  - Markdown for campaign files.
  - FalkorDB for graph mirrors of authored lore/notes.

## Viewer Surfaces

- **DM row:** current scene/play DM surface. This is the counterpart to Active
  Table, not a document browser. It may show active clocks, scene trackers,
  explicit beats, current scene prep cues, DM-facing tarot, live hooks, and
  recent play-control events. It should not become a long-term journal, lore, or
  file-reading surface.
- **Active Table:** only the player-agent table directory, as defined above.
- **Narrations:** turn rows in turn order.
- **Messages:** message bus rows.
- **File browser / DM notes / lore:** inspection surfaces for human viewers,
  not evidence that a player agent saw the file.
- **Graph summaries:** coherence/debug surfaces, not table state unless a table
  file links or summarizes the relevant entity.

## Deployment Notes

A later hosted version can mirror the same resources to a service behind
CloudFront or another static host. That deployment decision must preserve the
visibility model above: broad human inspection is allowed, but Active Table is
still exactly the player-agent table construct.
