# Migrations

SQL files applied by `glass db migrate`. Files run in lexicographic order. Each migration is recorded in the `_migrations` table (id = filename, checksum = sha256 of file contents) so re-running is idempotent.

Conventions:

- **Numeric prefix.** `NNN_short_name.sql`. Padding to 3 digits for the foreseeable future. New migration goes at the next free number.
- **Idempotent SQL.** `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, etc. — so a partially-applied migration can be re-run. The migration runner also wraps each file in a transaction; on failure, nothing is committed and the migration stays unapplied.
- **No edits to applied migrations.** Once a migration is in production (i.e. anyone's database has it recorded), don't change the file. Add a new migration to alter the schema.
- **Checksum mismatch is reported, not auto-corrected.** If the file changes after being applied, `glass db status` flags it. Decide deliberately.

## Current migrations

| File | Adds |
|------|------|
| `001_characters.sql` | `characters` table — per-PC state per `docs/design/mechanics.md` |
| `002_rolls.sql` | `rolls` table — every dice event with full context (audit trail) |
| `003_messages.sql` | `messages` + `message_reads` tables — typed inter-agent message bus per `docs/design/messaging.md` |
| `004_xp_levels.sql` | character XP and level columns |
| `005_skill_xp_and_logs.sql` | skill-by-use XP plus XP/level-up history |
| `006_runtime_state_and_turns.sql` | Postgres runtime state and structured turns |
| `007_durable_clocks.sql` | durable cross-scene clocks and clock event history |
| `008_character_consequences.sql` | lasting character consequences |
| `009_persistence_outputs_and_search.sql` | turn metadata, event log, scene trackers, action orders, search chunks |
| `010_creative_influences.sql` | persisted tarot influences for actual-play creative nudges |

## Running

```
glass db migrate                 # apply pending migrations
glass db status                  # list applied + pending + checksum mismatches
```

Connection details come from `[postgres]` in `agents-of-glass.toml` (or `agents-of-glass.local.toml`). Password from the env: `AOG_PG_PASSWORD` (preferred) or `PGPASSWORD` (libpq default). Other libpq env vars (`PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`) are read as fallbacks.

In the `with-cred` workflow on this machine:

```
with-cred -- glass db migrate
```
