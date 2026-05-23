-- Track repeated failed rolls against a scene beat so the beat can hand
-- control back to the DM before play narrows into retries.

ALTER TABLE scene_beats
    ADD COLUMN IF NOT EXISTS failure_ticks int NOT NULL DEFAULT 0;

ALTER TABLE scene_beats
    DROP CONSTRAINT IF EXISTS scene_beats_failure_ticks_check;

ALTER TABLE scene_beats
    ADD CONSTRAINT scene_beats_failure_ticks_check
    CHECK (failure_ticks >= 0);
