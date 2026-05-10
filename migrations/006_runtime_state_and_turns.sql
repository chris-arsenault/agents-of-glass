-- Runtime state + structured public turn corpus.
--
-- state.json/transcript.md remain useful local cache/export files, but these
-- tables are the canonical query surface for resume and viewer/UI work.

CREATE TABLE IF NOT EXISTS campaign_runtime_states (
    campaign_id           text PRIMARY KEY,
    status                text NOT NULL DEFAULT 'active',
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    wrapped_at            timestamptz,
    summary               text NOT NULL DEFAULT '',
    turn_counter          int NOT NULL DEFAULT 0,
    mode_stack            jsonb NOT NULL DEFAULT '[]'::jsonb,
    pending_events        jsonb NOT NULL DEFAULT '[]'::jsonb,
    note_intake           jsonb NOT NULL DEFAULT '[]'::jsonb,
    entities              jsonb NOT NULL DEFAULT '{}'::jsonb,
    threads               jsonb NOT NULL DEFAULT '{}'::jsonb,
    next_speakers         jsonb NOT NULL DEFAULT '[]'::jsonb,
    scene_closing_turns   int,
    state_extra           jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS campaign_runtime_states_updated_idx
    ON campaign_runtime_states (updated_at DESC);


CREATE TABLE IF NOT EXISTS turns (
    campaign_id       text NOT NULL,
    turn_id           int NOT NULL,
    session_id        text NOT NULL,
    scene_id          text NOT NULL,
    mode              text NOT NULL,
    speaker           text NOT NULL,
    role              text NOT NULL,
    character_id      text,
    source_path       text,
    prose             text NOT NULL,
    event_summaries   jsonb NOT NULL DEFAULT '[]'::jsonb,
    events            jsonb NOT NULL DEFAULT '[]'::jsonb,
    markdown          text NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (campaign_id, turn_id)
);

CREATE INDEX IF NOT EXISTS turns_campaign_created_idx
    ON turns (campaign_id, created_at, turn_id);
CREATE INDEX IF NOT EXISTS turns_campaign_scene_idx
    ON turns (campaign_id, scene_id, turn_id);
CREATE INDEX IF NOT EXISTS turns_campaign_speaker_idx
    ON turns (campaign_id, speaker, turn_id);
CREATE INDEX IF NOT EXISTS turns_campaign_mode_idx
    ON turns (campaign_id, mode, turn_id);
