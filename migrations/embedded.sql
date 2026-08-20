PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS _migrations (
    id TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    checksum TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS characters (
    campaign_id TEXT NOT NULL,
    character_id TEXT NOT NULL,
    player_id TEXT NOT NULL,
    name TEXT NOT NULL,
    archetype TEXT NOT NULL DEFAULT '',
    species TEXT NOT NULL DEFAULT '',
    culture TEXT NOT NULL DEFAULT '',
    organization_role TEXT NOT NULL DEFAULT '',
    pronouns TEXT NOT NULL DEFAULT '',
    bio TEXT NOT NULL DEFAULT '',
    goals JSON NOT NULL DEFAULT '[]',
    primary_drive TEXT NOT NULL DEFAULT '',
    positive_trait TEXT NOT NULL DEFAULT '',
    table_presence TEXT NOT NULL DEFAULT '',
    non_work_want TEXT NOT NULL DEFAULT '',
    opening_social_action TEXT NOT NULL DEFAULT '',
    life_prompt_answers JSON NOT NULL DEFAULT '[]',
    pull_utilization_note TEXT NOT NULL DEFAULT '',
    attributes JSON NOT NULL DEFAULT '{}',
    skills JSON NOT NULL DEFAULT '{}',
    momentum_current INTEGER NOT NULL DEFAULT 0,
    momentum_floor INTEGER NOT NULL DEFAULT -2,
    momentum_ceiling INTEGER NOT NULL DEFAULT 3,
    hp_current INTEGER NOT NULL DEFAULT 10,
    hp_max INTEGER NOT NULL DEFAULT 10,
    inventory JSON NOT NULL DEFAULT '[]',
    tags JSON NOT NULL DEFAULT '[]',
    xp INTEGER NOT NULL DEFAULT 0,
    level INTEGER NOT NULL DEFAULT 1,
    skill_xp JSON NOT NULL DEFAULT '{}',
    skill_meta JSON NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (campaign_id, character_id)
);
CREATE INDEX IF NOT EXISTS characters_player_idx ON characters (campaign_id, player_id);

CREATE TABLE IF NOT EXISTS campaign_runtime_states (
    campaign_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    wrapped_at TEXT,
    summary TEXT NOT NULL DEFAULT '',
    turn_counter INTEGER NOT NULL DEFAULT 0,
    mode_stack JSON NOT NULL DEFAULT '[]',
    pending_events JSON NOT NULL DEFAULT '[]',
    note_intake JSON NOT NULL DEFAULT '[]',
    entities JSON NOT NULL DEFAULT '{}',
    threads JSON NOT NULL DEFAULT '{}',
    next_speakers JSON NOT NULL DEFAULT '[]',
    scene_closing_turns INTEGER,
    active_turn_id TEXT,
    active_turn_number INTEGER,
    active_turn_actor TEXT,
    active_turn_role TEXT,
    active_turn_mode TEXT,
    active_turn_scene_id TEXT,
    active_turn_character_id TEXT,
    active_turn_kind TEXT,
    active_turn_turn_type_required INTEGER NOT NULL DEFAULT 0,
    active_turn_allow_player_scene_close INTEGER NOT NULL DEFAULT 0,
    active_turn_beat_checked_at TEXT,
    active_turn_audit_ran_at TEXT,
    closeout_summary TEXT,
    closeout_next_speaker TEXT,
    closeout_scene_status TEXT,
    closeout_state_changes JSON,
    closeout_rolls TEXT,
    closeout_open_questions JSON,
    closeout_position TEXT,
    closeout_pressure TEXT,
    closeout_turn_type TEXT,
    closeout_valid INTEGER,
    closeout_problems JSON,
    closeout_updated_at TEXT,
    state_extra JSON NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS campaign_runtime_states_updated_idx ON campaign_runtime_states (updated_at DESC);

CREATE TABLE IF NOT EXISTS turns (
    campaign_id TEXT NOT NULL,
    turn_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    scene_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    speaker TEXT NOT NULL,
    role TEXT NOT NULL,
    character_id TEXT,
    source_path TEXT,
    prose TEXT NOT NULL,
    event_summaries JSON NOT NULL DEFAULT '[]',
    events JSON NOT NULL DEFAULT '[]',
    markdown TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    arc_id TEXT,
    scene_type TEXT,
    turn_number_in_scene INTEGER,
    visibility TEXT NOT NULL DEFAULT 'public',
    turn_summary TEXT,
    next_speaker TEXT,
    scene_status TEXT,
    state_changes JSON NOT NULL DEFAULT '[]',
    rolls TEXT,
    turn_type TEXT,
    open_questions JSON NOT NULL DEFAULT '[]',
    position TEXT,
    pressure TEXT,
    turn_end JSON NOT NULL DEFAULT '{}',
    PRIMARY KEY (campaign_id, turn_id)
);
CREATE INDEX IF NOT EXISTS turns_campaign_created_idx ON turns (campaign_id, created_at, turn_id);
CREATE INDEX IF NOT EXISTS turns_campaign_scene_idx ON turns (campaign_id, scene_id, turn_id);
CREATE INDEX IF NOT EXISTS turns_campaign_speaker_idx ON turns (campaign_id, speaker, turn_id);
CREATE INDEX IF NOT EXISTS turns_campaign_mode_idx ON turns (campaign_id, mode, turn_id);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    campaign_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    type TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS message_reads (
    agent_id TEXT NOT NULL,
    message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    read_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (agent_id, message_id)
);

CREATE TABLE IF NOT EXISTS rolls (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    campaign_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    scene_id TEXT,
    character_id TEXT NOT NULL,
    actor TEXT NOT NULL,
    skill TEXT NOT NULL,
    attribute TEXT NOT NULL,
    risk TEXT NOT NULL,
    dice JSON NOT NULL,
    skill_tier TEXT NOT NULL,
    skill_modifier INTEGER NOT NULL,
    attribute_tier TEXT NOT NULL,
    attribute_modifier INTEGER NOT NULL,
    momentum_in INTEGER NOT NULL,
    total INTEGER NOT NULL,
    target INTEGER NOT NULL,
    margin INTEGER NOT NULL,
    outcome TEXT NOT NULL,
    momentum_delta INTEGER NOT NULL,
    momentum_out INTEGER NOT NULL,
    target_id TEXT,
    metadata JSON NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id, character_id) REFERENCES characters (campaign_id, character_id)
);

CREATE TABLE IF NOT EXISTS xp_awards (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    campaign_id TEXT NOT NULL,
    character_id TEXT NOT NULL,
    actor TEXT NOT NULL,
    delta INTEGER NOT NULL,
    xp_before INTEGER NOT NULL,
    xp_after INTEGER NOT NULL,
    reason TEXT,
    session_id TEXT,
    scene_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id, character_id) REFERENCES characters (campaign_id, character_id)
);

CREATE TABLE IF NOT EXISTS level_ups (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    campaign_id TEXT NOT NULL,
    character_id TEXT NOT NULL,
    actor TEXT NOT NULL,
    from_level INTEGER NOT NULL,
    to_level INTEGER NOT NULL,
    hp_roll INTEGER NOT NULL,
    hp_max_before INTEGER NOT NULL,
    hp_max_after INTEGER NOT NULL,
    attribute_bumped TEXT,
    attribute_to_tier TEXT,
    momentum_ceiling_before INTEGER NOT NULL,
    momentum_ceiling_after INTEGER NOT NULL,
    session_id TEXT,
    scene_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id, character_id) REFERENCES characters (campaign_id, character_id)
);

CREATE TABLE IF NOT EXISTS signature_moves (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    campaign_id TEXT NOT NULL,
    character_id TEXT NOT NULL,
    name TEXT NOT NULL,
    descriptor TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    visibility TEXT NOT NULL DEFAULT 'public',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id, character_id) REFERENCES characters (campaign_id, character_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS signature_moves_character_name_idx ON signature_moves (campaign_id, character_id, lower(name));

CREATE TABLE IF NOT EXISTS character_consequences (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    campaign_id TEXT NOT NULL,
    character_id TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    severity TEXT NOT NULL DEFAULT 'minor',
    scope TEXT NOT NULL DEFAULT 'scene',
    visibility TEXT NOT NULL DEFAULT 'public',
    status TEXT NOT NULL DEFAULT 'active',
    created_by TEXT NOT NULL,
    resolved_by TEXT,
    resolution_note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT,
    FOREIGN KEY (campaign_id, character_id) REFERENCES characters (campaign_id, character_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS clocks (
    campaign_id TEXT NOT NULL,
    clock_id TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'campaign',
    anchor_id TEXT,
    label TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    value INTEGER NOT NULL DEFAULT 0,
    max_value INTEGER NOT NULL,
    direction TEXT NOT NULL DEFAULT 'fills',
    visibility TEXT NOT NULL DEFAULT 'dm',
    status TEXT NOT NULL DEFAULT 'active',
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT,
    resolution_note TEXT,
    PRIMARY KEY (campaign_id, clock_id)
);
CREATE TABLE IF NOT EXISTS clock_events (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    campaign_id TEXT NOT NULL,
    clock_id TEXT NOT NULL,
    actor TEXT NOT NULL,
    event_type TEXT NOT NULL,
    delta INTEGER,
    value_before INTEGER,
    value_after INTEGER,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id, clock_id) REFERENCES clocks (campaign_id, clock_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    scene_id TEXT,
    turn_id INTEGER,
    actor TEXT NOT NULL,
    event_type TEXT NOT NULL,
    visibility TEXT NOT NULL DEFAULT 'public',
    summary TEXT NOT NULL DEFAULT '',
    payload JSON NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    claimed_at TEXT
);

CREATE TABLE IF NOT EXISTS scene_trackers (
    campaign_id TEXT NOT NULL,
    tracker_id TEXT NOT NULL,
    scene_id TEXT NOT NULL,
    label TEXT NOT NULL,
    value INTEGER NOT NULL DEFAULT 0,
    max_value INTEGER NOT NULL,
    resistance INTEGER NOT NULL DEFAULT 0,
    impact_resistance INTEGER NOT NULL DEFAULT 0,
    visibility TEXT NOT NULL DEFAULT 'public',
    status TEXT NOT NULL DEFAULT 'active',
    updated_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (campaign_id, tracker_id)
);

CREATE TABLE IF NOT EXISTS action_orders (
    campaign_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    scene_id TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT 'initiative',
    round INTEGER NOT NULL DEFAULT 1,
    cursor INTEGER NOT NULL DEFAULT 0,
    order_agents JSON NOT NULL DEFAULT '[]',
    rolls JSON NOT NULL DEFAULT '[]',
    active INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (campaign_id, mode, scene_id)
);

CREATE TABLE IF NOT EXISTS search_chunks (
    chunk_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    visibility TEXT NOT NULL DEFAULT 'public',
    owner_actor TEXT,
    path TEXT,
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL,
    metadata JSON NOT NULL DEFAULT '{}',
    embedding_vector JSON,
    embedding_model TEXT,
    embedding_provider TEXT,
    embedding_dim INTEGER,
    embedded_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS search_chunks_campaign_idx ON search_chunks (campaign_id, source_type, visibility);

CREATE TABLE IF NOT EXISTS tarot_influences (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    campaign_id TEXT NOT NULL,
    actor TEXT NOT NULL,
    deck_id TEXT NOT NULL,
    deck_name TEXT NOT NULL,
    card_id TEXT NOT NULL,
    card_name TEXT NOT NULL,
    influence TEXT NOT NULL,
    source_note TEXT NOT NULL DEFAULT '',
    starts_turn INTEGER NOT NULL,
    expires_turn INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scene_clocks (
    campaign_id TEXT NOT NULL,
    scene_id TEXT NOT NULL,
    clock_id TEXT NOT NULL,
    label TEXT NOT NULL,
    goal TEXT NOT NULL,
    value INTEGER NOT NULL DEFAULT 0,
    max_value INTEGER NOT NULL,
    direction TEXT NOT NULL,
    polarity TEXT NOT NULL DEFAULT 'objective',
    visibility TEXT NOT NULL DEFAULT 'public',
    status TEXT NOT NULL DEFAULT 'active',
    created_by TEXT NOT NULL,
    created_turn_id TEXT,
    resolved_turn_id TEXT,
    outcome TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT,
    PRIMARY KEY (campaign_id, scene_id, clock_id)
);

CREATE TABLE IF NOT EXISTS scene_beats (
    campaign_id TEXT NOT NULL,
    scene_id TEXT NOT NULL,
    beat_id TEXT NOT NULL,
    clock_id TEXT NOT NULL,
    label TEXT NOT NULL,
    question TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    non_pass_turns INTEGER NOT NULL DEFAULT 0,
    failure_ticks INTEGER NOT NULL DEFAULT 0,
    created_by TEXT NOT NULL,
    created_turn_id TEXT,
    closed_by TEXT,
    closed_turn_id TEXT,
    outcome TEXT,
    converted_to_clock_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TEXT,
    PRIMARY KEY (campaign_id, scene_id, beat_id),
    FOREIGN KEY (campaign_id, scene_id, clock_id) REFERENCES scene_clocks (campaign_id, scene_id, clock_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS facts (
    uid TEXT PRIMARY KEY,
    id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_id TEXT,
    claim_text TEXT NOT NULL,
    visibility TEXT NOT NULL DEFAULT 'public',
    status TEXT NOT NULL DEFAULT 'active',
    salience TEXT NOT NULL DEFAULT 'medium',
    salience_rank INTEGER NOT NULL DEFAULT 2,
    audience TEXT NOT NULL DEFAULT 'continuity',
    source_turn_id TEXT,
    actor TEXT,
    mode TEXT,
    scene_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (campaign_id, scope_id, subject_id, predicate, object_id)
);
CREATE INDEX IF NOT EXISTS facts_pack_idx ON facts (campaign_id, status, scope_id, salience_rank DESC, updated_at DESC);

CREATE TABLE IF NOT EXISTS lore_entries (
    uid TEXT PRIMARY KEY,
    campaign_id TEXT,
    id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    title TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'reference',
    visibility TEXT NOT NULL DEFAULT 'public',
    source TEXT,
    tags JSON NOT NULL DEFAULT '[]',
    tags_text TEXT NOT NULL DEFAULT '',
    body_text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS lore_search_idx ON lore_entries (namespace, visibility, updated_at DESC);
