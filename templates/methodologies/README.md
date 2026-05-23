# Methodologies

Methodologies are mandatory ordered sequences selected by the injected prompt.
They are runtime contract documents, and they never create an alternate state
channel.

Every methodology uses the same output and state contract:

1. Read the injected prompt and this methodology.
2. Run the required `glass_*` MCP checks and state tools.
3. Record durable continuity as neutral graph facts.
4. Do not write files, sync markdown, call local APIs directly, or use stdout as state.
5. Close with `glass_done(..., scene_status="<enum from tools/list>")`.
6. Submit public prose with `glass_turn_append(body="...")`.

Mode-specific methodology files only define what decisions and MCP tools belong in that sequence.
