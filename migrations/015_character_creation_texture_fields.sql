-- Character creation anti-sameness fields.
--
-- Existing rows receive empty/default values; `glass character new` enforces
-- non-empty values for new characters.

ALTER TABLE characters
    ADD COLUMN IF NOT EXISTS primary_drive text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS positive_trait text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS life_prompt_answers jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS pull_utilization_note text NOT NULL DEFAULT '';
