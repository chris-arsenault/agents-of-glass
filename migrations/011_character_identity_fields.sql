-- Character identity fields required by character creation.
--
-- These are canonical character facts that were drifting between prose mirrors,
-- tags, and Postgres rows. Existing rows get empty/default values; the CLI
-- enforces non-empty values for newly created characters.

ALTER TABLE characters
    ADD COLUMN IF NOT EXISTS species text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS culture text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS organization_role text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS goals jsonb NOT NULL DEFAULT '[]'::jsonb;
