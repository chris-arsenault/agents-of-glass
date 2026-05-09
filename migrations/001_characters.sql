-- Characters: per-PC state. The hard-stat side of a character; canonical
-- numbers live here, the markdown character.md in the campaign workspace
-- is a cached display.
--
-- Schema follows docs/design/mechanics.md.

CREATE TABLE IF NOT EXISTS characters (
    campaign_id         text NOT NULL,
    character_id        text NOT NULL,
    player_id           text NOT NULL,
    name                text NOT NULL,
    archetype           text NOT NULL DEFAULT '',
    pronouns            text NOT NULL DEFAULT '',
    bio                 text NOT NULL DEFAULT '',
    -- Attribute tier per attribute name. Tier strings validated by the CLI
    -- against the AttributeTier enum (rudimentary/standard/advanced/superior/transcendent).
    attributes          jsonb NOT NULL DEFAULT '{}'::jsonb,
    -- Free-form skill names mapped to tier strings (fool/apprentice/artisan/virtuoso/legend).
    skills              jsonb NOT NULL DEFAULT '{}'::jsonb,
    momentum_current    int NOT NULL DEFAULT 0,
    momentum_floor      int NOT NULL DEFAULT -2,
    momentum_ceiling    int NOT NULL DEFAULT 3,
    hp_current          int NOT NULL DEFAULT 10,
    hp_max              int NOT NULL DEFAULT 10,
    -- List of {id: text, qty: int} objects.
    inventory           jsonb NOT NULL DEFAULT '[]'::jsonb,
    tags                text[] NOT NULL DEFAULT '{}',
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (campaign_id, character_id)
);

CREATE INDEX IF NOT EXISTS characters_player_idx ON characters (campaign_id, player_id);

-- Auto-bump updated_at on row changes.
CREATE OR REPLACE FUNCTION characters_set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS characters_updated_at ON characters;
CREATE TRIGGER characters_updated_at
    BEFORE UPDATE ON characters
    FOR EACH ROW EXECUTE FUNCTION characters_set_updated_at();
