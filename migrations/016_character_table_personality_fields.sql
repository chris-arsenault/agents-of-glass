-- Character creation fields that force table-facing personality over reserved
-- professional posture.

ALTER TABLE characters
    ADD COLUMN IF NOT EXISTS table_presence text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS non_work_want text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS opening_social_action text NOT NULL DEFAULT '';
