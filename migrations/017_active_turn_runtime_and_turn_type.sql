-- Canonical active-turn runtime context and staged closeout metadata.

ALTER TABLE campaign_runtime_states
    ADD COLUMN IF NOT EXISTS active_turn_id text,
    ADD COLUMN IF NOT EXISTS active_turn_number int,
    ADD COLUMN IF NOT EXISTS active_turn_actor text,
    ADD COLUMN IF NOT EXISTS active_turn_role text,
    ADD COLUMN IF NOT EXISTS active_turn_mode text,
    ADD COLUMN IF NOT EXISTS active_turn_scene_id text,
    ADD COLUMN IF NOT EXISTS active_turn_character_id text,
    ADD COLUMN IF NOT EXISTS active_turn_kind text,
    ADD COLUMN IF NOT EXISTS active_turn_turn_type_required boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS active_turn_allow_player_scene_close boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS closeout_summary text,
    ADD COLUMN IF NOT EXISTS closeout_next_speaker text,
    ADD COLUMN IF NOT EXISTS closeout_scene_status text,
    ADD COLUMN IF NOT EXISTS closeout_state_changes jsonb,
    ADD COLUMN IF NOT EXISTS closeout_rolls text,
    ADD COLUMN IF NOT EXISTS closeout_open_questions jsonb,
    ADD COLUMN IF NOT EXISTS closeout_position text,
    ADD COLUMN IF NOT EXISTS closeout_pressure text,
    ADD COLUMN IF NOT EXISTS closeout_turn_type text,
    ADD COLUMN IF NOT EXISTS closeout_valid boolean,
    ADD COLUMN IF NOT EXISTS closeout_problems jsonb,
    ADD COLUMN IF NOT EXISTS closeout_updated_at timestamptz;

ALTER TABLE turns
    ADD COLUMN IF NOT EXISTS turn_type text
        CHECK (turn_type IS NULL OR turn_type IN ('act', 'answer', 'support', 'pass'));

CREATE INDEX IF NOT EXISTS campaign_runtime_states_active_turn_idx
    ON campaign_runtime_states (active_turn_id)
    WHERE active_turn_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS turns_campaign_turn_type_idx
    ON turns (campaign_id, turn_type, turn_id);
