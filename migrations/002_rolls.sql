-- Rolls: every dice event with full context. Append-only audit trail
-- consulted by `glass turns find` and the inline transcript event lines.
--
-- Schema follows docs/design/mechanics.md (the dice CLI output shape).

CREATE TABLE IF NOT EXISTS rolls (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id         text NOT NULL,
    session_id          text NOT NULL,
    scene_id            text,
    -- Soft FK; SET NULL on character delete so historical rolls survive
    -- character cleanup.
    character_id        uuid REFERENCES characters(id) ON DELETE SET NULL,
    skill               text NOT NULL,
    attribute           text NOT NULL,
    risk                text NOT NULL CHECK (risk IN ('controlled','standard','risky','desperate')),
    dice                int[] NOT NULL,
    skill_modifier      int NOT NULL,
    attribute_modifier  int NOT NULL,
    momentum_in         int NOT NULL,
    total               int NOT NULL,
    target              int NOT NULL,
    margin              int NOT NULL,
    outcome             text NOT NULL CHECK (outcome IN ('breakthrough','advance','stall','regress','collapse')),
    momentum_delta      int NOT NULL,
    momentum_out        int NOT NULL,
    -- Optional combat target (NPC id, character id, etc.). String to keep
    -- it open across reference types.
    target_id           text,
    -- Free-form for narrative tags, weapon used, etc. Not validated.
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS rolls_campaign_idx ON rolls (campaign_id, created_at DESC);
CREATE INDEX IF NOT EXISTS rolls_character_idx ON rolls (character_id, created_at DESC);
CREATE INDEX IF NOT EXISTS rolls_session_idx ON rolls (session_id, created_at);
CREATE INDEX IF NOT EXISTS rolls_scene_idx ON rolls (campaign_id, scene_id, created_at);
