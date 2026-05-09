-- Skill-by-use progression + history tables for XP awards and level-ups.
--
-- skill_xp tracks cumulative XP per skill. Earned via successful rolls
-- (advance: +1, breakthrough: +2). Crossing thresholds auto-bumps the
-- skill's tier in the skills jsonb: 5 -> apprentice, 15 -> artisan,
-- 30 -> virtuoso. Virtuoso -> legend stays plot-only.
--
-- xp_awards is the append-only history of glass character award-xp.
-- level_ups is the append-only history of glass character level-up.

ALTER TABLE characters
    ADD COLUMN IF NOT EXISTS skill_xp jsonb NOT NULL DEFAULT '{}'::jsonb;


CREATE TABLE IF NOT EXISTS xp_awards (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id     text NOT NULL,
    character_id    text NOT NULL,
    actor           text NOT NULL,
    delta           int NOT NULL,
    xp_before       int NOT NULL,
    xp_after        int NOT NULL,
    reason          text,
    session_id      text,
    scene_id        text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (campaign_id, character_id)
        REFERENCES characters (campaign_id, character_id)
        ON DELETE NO ACTION ON UPDATE CASCADE
);

CREATE INDEX IF NOT EXISTS xp_awards_character_idx
    ON xp_awards (campaign_id, character_id, created_at DESC);


CREATE TABLE IF NOT EXISTS level_ups (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id              text NOT NULL,
    character_id             text NOT NULL,
    actor                    text NOT NULL,
    from_level               int NOT NULL,
    to_level                 int NOT NULL,
    hp_roll                  int NOT NULL,
    hp_max_before            int NOT NULL,
    hp_max_after             int NOT NULL,
    attribute_bumped         text,
    attribute_to_tier        text,
    momentum_ceiling_before  int NOT NULL,
    momentum_ceiling_after   int NOT NULL,
    session_id               text,
    scene_id                 text,
    created_at               timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (campaign_id, character_id)
        REFERENCES characters (campaign_id, character_id)
        ON DELETE NO ACTION ON UPDATE CASCADE
);

CREATE INDEX IF NOT EXISTS level_ups_character_idx
    ON level_ups (campaign_id, character_id, created_at DESC);
