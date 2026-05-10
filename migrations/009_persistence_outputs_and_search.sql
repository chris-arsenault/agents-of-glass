-- Intentional persistence model: public turn corpus, event log, relational
-- scene/action state, and a searchable content index.

ALTER TABLE turns
    ADD COLUMN IF NOT EXISTS arc_id text,
    ADD COLUMN IF NOT EXISTS scene_type text,
    ADD COLUMN IF NOT EXISTS turn_number_in_scene int,
    ADD COLUMN IF NOT EXISTS visibility text NOT NULL DEFAULT 'public'
        CHECK (visibility IN ('public', 'dm', 'private'));

CREATE INDEX IF NOT EXISTS turns_campaign_arc_idx
    ON turns (campaign_id, arc_id, turn_id);
CREATE INDEX IF NOT EXISTS turns_campaign_scene_number_idx
    ON turns (campaign_id, scene_id, turn_number_in_scene);
CREATE INDEX IF NOT EXISTS turns_campaign_visibility_idx
    ON turns (campaign_id, visibility, turn_id);


CREATE TABLE IF NOT EXISTS events (
    event_id    text PRIMARY KEY,
    campaign_id text NOT NULL,
    scene_id    text,
    turn_id     int,
    actor       text NOT NULL,
    event_type  text NOT NULL,
    visibility  text NOT NULL DEFAULT 'public'
                CHECK (visibility IN ('public', 'dm', 'private')),
    summary     text NOT NULL DEFAULT '',
    payload     jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at  timestamptz NOT NULL DEFAULT now(),
    claimed_at  timestamptz
);

CREATE INDEX IF NOT EXISTS events_campaign_created_idx
    ON events (campaign_id, created_at);
CREATE INDEX IF NOT EXISTS events_campaign_turn_idx
    ON events (campaign_id, turn_id);
CREATE INDEX IF NOT EXISTS events_campaign_pending_idx
    ON events (campaign_id, scene_id, created_at)
    WHERE turn_id IS NULL;
CREATE INDEX IF NOT EXISTS events_campaign_type_idx
    ON events (campaign_id, event_type, created_at);


CREATE TABLE IF NOT EXISTS scene_trackers (
    campaign_id       text NOT NULL,
    tracker_id        text NOT NULL,
    scene_id          text NOT NULL,
    label             text NOT NULL,
    value             int NOT NULL DEFAULT 0,
    max_value         int NOT NULL,
    resistance        int NOT NULL DEFAULT 0,
    impact_resistance int NOT NULL DEFAULT 0,
    visibility        text NOT NULL DEFAULT 'public'
                      CHECK (visibility IN ('public', 'dm')),
    status            text NOT NULL DEFAULT 'active'
                      CHECK (status IN ('active', 'resolved', 'archived')),
    updated_by        text NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (campaign_id, tracker_id),
    CHECK (max_value > 0),
    CHECK (value >= 0 AND value <= max_value)
);

CREATE INDEX IF NOT EXISTS scene_trackers_scene_idx
    ON scene_trackers (campaign_id, scene_id, status);
CREATE INDEX IF NOT EXISTS scene_trackers_visibility_idx
    ON scene_trackers (campaign_id, visibility, status);


CREATE TABLE IF NOT EXISTS action_orders (
    campaign_id  text NOT NULL,
    mode         text NOT NULL,
    scene_id     text NOT NULL,
    label        text NOT NULL DEFAULT 'initiative',
    round        int NOT NULL DEFAULT 1,
    cursor       int NOT NULL DEFAULT 0,
    order_agents jsonb NOT NULL DEFAULT '[]'::jsonb,
    rolls        jsonb NOT NULL DEFAULT '[]'::jsonb,
    active       boolean NOT NULL DEFAULT true,
    created_by   text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (campaign_id, mode, scene_id)
);

CREATE INDEX IF NOT EXISTS action_orders_active_idx
    ON action_orders (campaign_id, active, scene_id);


CREATE TABLE IF NOT EXISTS search_chunks (
    chunk_id      text PRIMARY KEY,
    campaign_id   text NOT NULL,
    source_type   text NOT NULL,
    source_id     text NOT NULL,
    visibility    text NOT NULL DEFAULT 'public'
                  CHECK (visibility IN ('public', 'dm', 'private')),
    owner_actor   text,
    path          text,
    title         text NOT NULL DEFAULT '',
    body          text NOT NULL,
    metadata      jsonb NOT NULL DEFAULT '{}'::jsonb,
    embedding     double precision[],
    updated_at    timestamptz NOT NULL DEFAULT now(),
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(title, '') || ' ' || coalesce(body, ''))
    ) STORED
);

CREATE INDEX IF NOT EXISTS search_chunks_campaign_idx
    ON search_chunks (campaign_id, source_type, visibility);
CREATE INDEX IF NOT EXISTS search_chunks_owner_idx
    ON search_chunks (campaign_id, owner_actor);
CREATE INDEX IF NOT EXISTS search_chunks_vector_idx
    ON search_chunks USING GIN (search_vector);
