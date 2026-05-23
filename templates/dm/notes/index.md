---
title: DM Notes
status: retired-for-agent-turns
---

# DM Notes

Operator-curated DM notes may exist outside the live turn loop, but they are not
an agent interaction mode.

During orchestrated turns, Mara does not create, edit, or sync note files. She
uses:

- `glass_state_update` for durable continuity
- purpose-built `glass_*` MCP tools for hard state
- `glass_message_send` for private communication
- `glass_turn_append` for public prose

If a durable note-like idea matters to future agents, encode the neutral fact in
the graph. If it is only operator reference, curate it outside the agent turn.
