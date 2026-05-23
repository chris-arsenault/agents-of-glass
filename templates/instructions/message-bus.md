# Message Bus

Use messages for durable questions, offers, warnings, coordination, private intent, and concrete blockers.

Choose recipients from the roster in the injected prompt. Prefer the narrowest recipient that matches visibility. Messages can coordinate state changes, but the state change itself still belongs in the owning `glass_*` MCP tool or a neutral fact.

Do not use files as a side channel for messages.
