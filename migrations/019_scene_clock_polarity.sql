-- Scene clock polarity distinguishes party objectives from threat/timer clocks.

ALTER TABLE scene_clocks
    ADD COLUMN IF NOT EXISTS polarity text NOT NULL DEFAULT 'objective';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'scene_clocks_polarity_check'
    ) THEN
        ALTER TABLE scene_clocks
            ADD CONSTRAINT scene_clocks_polarity_check
            CHECK (polarity IN ('objective', 'threat', 'timer'));
    END IF;
END $$;

UPDATE scene_clocks
SET polarity = CASE
    WHEN direction = 'countdown' THEN 'timer'
    ELSE polarity
END
WHERE polarity = 'objective'
  AND direction = 'countdown';
