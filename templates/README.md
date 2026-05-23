# Templates

This tree is the runtime reference surface. Active agent turns do not mutate it
and do not use it as campaign state.

Agent-facing durable reference lives here:

- `instructions/` - binding runtime and tool contract
- `methodologies/` - required workflows by mode and role
- `srd/` - public rules
- `how-to/` - optional examples and craft guidance
- `styles/` - optional prose craft references

Runtime continuity does not live in markdown files. Agents read continuity from
the fact graph and hard-state Glass MCP tools, mutate state only through `glass`
commands, close with `glass_done`, and submit public prose with
`glass_turn_append`.

Design docs explain rationale for developers. They are not runtime authority for
agents. If a design doc and `templates/instructions/` disagree, follow
`templates/instructions/`.
