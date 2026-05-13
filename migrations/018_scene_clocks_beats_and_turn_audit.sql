-- Scene-local clocks and beats, plus active-turn audit/beat-check markers.

ALTER TABLE campaign_runtime_states
    ADD COLUMN IF NOT EXISTS active_turn_beat_checked_at timestamptz,
    ADD COLUMN IF NOT EXISTS active_turn_audit_ran_at timestamptz;

CREATE TABLE IF NOT EXISTS scene_clocks (
    campaign_id       text NOT NULL,
    scene_id          text NOT NULL,
    clock_id          text NOT NULL,
    label             text NOT NULL,
    goal              text NOT NULL,
    value             int NOT NULL DEFAULT 0,
    max_value         int NOT NULL,
    direction         text NOT NULL
                     CHECK (direction IN ('progress', 'countdown')),
    visibility        text NOT NULL DEFAULT 'public'
                     CHECK (visibility IN ('public', 'dm')),
    status            text NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active', 'resolved', 'dropped')),
    created_by        text NOT NULL,
    created_turn_id   text,
    resolved_turn_id  text,
    outcome           text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    resolved_at       timestamptz,
    PRIMARY KEY (campaign_id, scene_id, clock_id),
    CHECK (max_value > 0),
    CHECK (value >= 0 AND value <= max_value)
);

CREATE INDEX IF NOT EXISTS scene_clocks_scene_status_idx
    ON scene_clocks (campaign_id, scene_id, status);
CREATE INDEX IF NOT EXISTS scene_clocks_visibility_idx
    ON scene_clocks (campaign_id, scene_id, visibility, status);

CREATE TABLE IF NOT EXISTS scene_beats (
    campaign_id             text NOT NULL,
    scene_id                text NOT NULL,
    beat_id                 text NOT NULL,
    clock_id                text NOT NULL,
    label                   text NOT NULL,
    question                text NOT NULL,
    status                  text NOT NULL DEFAULT 'active'
                           CHECK (status IN ('active', 'closed', 'converted', 'dropped')),
    non_pass_turns          int NOT NULL DEFAULT 0,
    created_by              text NOT NULL,
    created_turn_id         text,
    closed_by               text,
    closed_turn_id          text,
    outcome                 text,
    converted_to_clock_id   text,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),
    closed_at               timestamptz,
    PRIMARY KEY (campaign_id, scene_id, beat_id),
    FOREIGN KEY (campaign_id, scene_id, clock_id)
        REFERENCES scene_clocks (campaign_id, scene_id, clock_id)
        ON DELETE CASCADE,
    CHECK (non_pass_turns >= 0)
);

CREATE INDEX IF NOT EXISTS scene_beats_scene_status_idx
    ON scene_beats (campaign_id, scene_id, status);
CREATE INDEX IF NOT EXISTS scene_beats_clock_idx
    ON scene_beats (campaign_id, scene_id, clock_id, status);
