-- Required `glass turn end` closeout metadata for compact turn context.

ALTER TABLE turns
    ADD COLUMN IF NOT EXISTS turn_summary text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS next_speaker text NOT NULL DEFAULT 'default',
    ADD COLUMN IF NOT EXISTS scene_status text NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS state_changes jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS rolls text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS open_questions jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS position text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS pressure text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS turn_end jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS turns_campaign_scene_status_idx
    ON turns (campaign_id, scene_id, scene_status, turn_id);
