-- Items, skills, and signature moves all carry three labels now: a slug
-- for CLI bookkeeping, a prose name for the moment a character names the
-- thing aloud, and a generic descriptor for ordinary narration.
--
-- Items already live in `inventory` (jsonb list of dicts); the new `name`
-- and `descriptor` keys are added to those dicts in-place by the CLI.
-- Skills need a parallel jsonb column to avoid restructuring the existing
-- `{slug: tier}` lookup shape.

ALTER TABLE characters
    ADD COLUMN IF NOT EXISTS skill_meta jsonb NOT NULL DEFAULT '{}'::jsonb;
