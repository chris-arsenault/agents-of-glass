-- Durable clocks: cross-scene pressure that should survive beyond a scene.
--
-- Scene trackers remain short-term scene math. Clocks are campaign/arc/thread/
-- faction/NPC/custom pressure, stored in Postgres so they are durable and
-- queryable. Public clocks are also projected to markdown for player reference.

CREATE TABLE IF NOT EXISTS clocks (
    campaign_id      text NOT NULL,
    clock_id         text NOT NULL,
    scope            text NOT NULL DEFAULT 'campaign',
    anchor_id        text,
    label            text NOT NULL,
    description      text NOT NULL DEFAULT '',
    value            int NOT NULL DEFAULT 0,
    max_value        int NOT NULL,
    direction        text NOT NULL DEFAULT 'fills'
                     CHECK (direction IN ('fills', 'drains')),
    visibility       text NOT NULL DEFAULT 'dm'
                     CHECK (visibility IN ('public', 'dm')),
    status           text NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active', 'resolved', 'archived')),
    created_by       text NOT NULL,
    updated_by       text NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    resolved_at      timestamptz,
    resolution_note  text,
    PRIMARY KEY (campaign_id, clock_id),
    CHECK (max_value > 0),
    CHECK (value >= 0 AND value <= max_value)
);

CREATE INDEX IF NOT EXISTS clocks_campaign_scope_idx
    ON clocks (campaign_id, scope, anchor_id, status);
CREATE INDEX IF NOT EXISTS clocks_campaign_visibility_idx
    ON clocks (campaign_id, visibility, status);


CREATE TABLE IF NOT EXISTS clock_events (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id  text NOT NULL,
    clock_id     text NOT NULL,
    actor        text NOT NULL,
    event_type   text NOT NULL,
    delta        int,
    value_before int,
    value_after  int,
    note         text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (campaign_id, clock_id)
        REFERENCES clocks (campaign_id, clock_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE INDEX IF NOT EXISTS clock_events_clock_idx
    ON clock_events (campaign_id, clock_id, created_at);


CREATE OR REPLACE FUNCTION clocks_set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS clocks_updated_at ON clocks;
CREATE TRIGGER clocks_updated_at
    BEFORE UPDATE ON clocks
    FOR EACH ROW EXECUTE FUNCTION clocks_set_updated_at();
