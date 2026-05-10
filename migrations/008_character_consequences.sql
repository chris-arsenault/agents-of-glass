-- Character consequences: lasting fictional state that should not drift.
--
-- These are deliberately not a status-condition engine. A consequence is a
-- named, prose description with severity, scope, visibility, and resolution.

CREATE TABLE IF NOT EXISTS character_consequences (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id      text NOT NULL,
    character_id     text NOT NULL,
    label            text NOT NULL,
    description      text NOT NULL DEFAULT '',
    severity         text NOT NULL DEFAULT 'minor'
                     CHECK (severity IN ('minor', 'serious', 'critical')),
    scope            text NOT NULL DEFAULT 'scene'
                     CHECK (scope IN ('scene', 'arc', 'campaign')),
    visibility       text NOT NULL DEFAULT 'public'
                     CHECK (visibility IN ('public', 'dm')),
    status           text NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active', 'resolved')),
    created_by       text NOT NULL,
    resolved_by      text,
    resolution_note  text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    resolved_at      timestamptz,
    FOREIGN KEY (campaign_id, character_id)
        REFERENCES characters (campaign_id, character_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE INDEX IF NOT EXISTS character_consequences_character_idx
    ON character_consequences (campaign_id, character_id, status, created_at);
CREATE INDEX IF NOT EXISTS character_consequences_visibility_idx
    ON character_consequences (campaign_id, visibility, status);
