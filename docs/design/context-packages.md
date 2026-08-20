# Context Packages

What each agent receives in the injected prompt, and what it can query through
`glass`.

## Single Entry Point

The orchestrator no longer writes a per-turn context file. It builds one
injected prompt for the provider invocation. That prompt is the entry point for
the turn and contains the command contract, but it is not itself a state store.

The provider starts in `templates/` so durable methodology, rules, how-to, and
style references are discoverable with ordinary reads. Those files are
read-only reference. Campaign continuity and mutation happen through `glass`.

## Always Included

Every injected prompt includes:

- active table identity: Mara, Tev, Sumi, Renno, or Kit
- character identity and current hard state when the actor is a player
- campaign id, mode, arc, scene, generated turn type, and speaker role
- the selected methodology for this invocation
- current neutral continuity facts
- relevant hard-state summaries from `glass` commands
- message cues and any required message reads
- allowed command surface
- output contract: `glass done`, then `glass turn append --body`

The prompt should include enough current fact state for the agent to start
cleanly, but the agent can refresh with:

```bash
glass check
glass fact pack --format markdown
glass turns find ...
glass find ...
```

## Queryable Through `glass`

Agents query durable state through the CLI:

- neutral continuity facts: `glass fact pack`
- character state: `glass character get` / `glass character bulk-get`
- messages: `glass msg read`
- clocks: `glass clock ...`, `glass scene clock ...`
- rolls and mechanics: `glass roll`, `glass scene pressure`, HP, inventory, and consequences
- past turns and prose recall: `glass turns find`, `glass find`
- public turn feed: `glass turns feed`

Agents do not open SQLite, query local HTTP endpoints, or read campaign files
directly as a live state interface.

## Writable Through `glass`

Durable agent writes are also CLI-only:

- public prose: `glass turn append --body`
- closeout: `glass done`
- neutral facts: `glass fact set` or `glass done --fact`
- messages: `glass msg`
- mechanics and character state: purpose-built `glass` commands
- scene and mode state: purpose-built DM-authorized `glass` commands

If the desired write cannot be expressed by an allowed `glass` command, the
agent should record a blocker in `glass done` or message the DM/operator. It
should not create a file workaround.

## Role Differences

Player prompts include the player's table identity, their character identity,
their character's hard-state summary, and player-authorized commands.

DM prompts include Mara's table identity, scene and mode control cues, DM-only
state that is safe to expose to the DM agent, and DM-authorized commands.

Both roles use the same output contract and the same fact/prose split.

## Facts vs Prose

The context package intentionally separates neutral facts from viewer prose:

- Facts tell future agents what is concretely true.
- Public prose tells the human viewer how the turn reads.
- Search and past-turn lookup are recall aids, not the continuity source of
  record.

When a phrase from prior prose is colorful but not factual, it should stay in
prose. When it is load-bearing, it must become a neutral fact through `glass`.

## No Runtime File Surface

There is no per-player runtime working directory, no projected campaign tree, no
turn file, no closeout file, and no markdown sync layer in the agent contract.
Files under `templates/` are methodology/reference only. Files under
`campaigns/<id>/` are operator/debug/export surfaces unless a `glass` command
explicitly reads or writes them as part of its implementation.

## Turn History Policy

The prompt should not dump full prior narration by default. It should provide
current facts and compact hard-state cues, then let agents request bounded
recall through `glass turns find`, `glass turns feed`, or `glass find`.

The final public prose of each turn lives in SQLite `turns.prose` after
`glass turn append --body`. Markdown transcripts are generated exports for
humans.
