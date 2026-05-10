-- Actual-play creative influences.
--
-- Verse phrases are deterministic prompt nudges and are not persisted. Tarot
-- influences last across multiple turns and need a durable, queryable home for
-- turn-start context and eventual viewer surfaces.

CREATE TABLE IF NOT EXISTS tarot_influences (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id  text NOT NULL,
    actor        text NOT NULL,
    deck_id      text NOT NULL,
    deck_name    text NOT NULL,
    card_id      text NOT NULL,
    card_name    text NOT NULL,
    influence    text NOT NULL,
    source_note  text NOT NULL DEFAULT '',
    starts_turn  int NOT NULL,
    expires_turn int NOT NULL,
    active       boolean NOT NULL DEFAULT true,
    created_at   timestamptz NOT NULL DEFAULT now(),
    CHECK (starts_turn > 0),
    CHECK (expires_turn >= starts_turn)
);

CREATE INDEX IF NOT EXISTS tarot_influences_current_idx
    ON tarot_influences (campaign_id, actor, active, starts_turn DESC);

CREATE INDEX IF NOT EXISTS tarot_influences_campaign_turn_idx
    ON tarot_influences (campaign_id, starts_turn, expires_turn);
