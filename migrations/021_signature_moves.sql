-- Signature moves are typed character state, not markdown files.
--
-- A move has a display name for when it is named aloud, a generic descriptor
-- for ordinary narration, and structured prose describing its use/cost. The
-- slot cap remains level-driven in the CLI.

CREATE TABLE IF NOT EXISTS signature_moves (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id     text NOT NULL,
    character_id    text NOT NULL,
    name            text NOT NULL,
    descriptor      text NOT NULL,
    body            text NOT NULL DEFAULT '',
    visibility      text NOT NULL DEFAULT 'public'
                    CHECK (visibility IN ('public', 'dm')),
    created_by      text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (campaign_id, character_id)
        REFERENCES characters (campaign_id, character_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS signature_moves_character_name_idx
    ON signature_moves (campaign_id, character_id, lower(name));

CREATE INDEX IF NOT EXISTS signature_moves_character_idx
    ON signature_moves (campaign_id, character_id, created_at);

CREATE OR REPLACE FUNCTION signature_moves_set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS signature_moves_updated_at ON signature_moves;
CREATE TRIGGER signature_moves_updated_at
    BEFORE UPDATE ON signature_moves
    FOR EACH ROW EXECUTE FUNCTION signature_moves_set_updated_at();
