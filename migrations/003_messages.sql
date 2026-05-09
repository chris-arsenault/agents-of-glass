-- Messages: typed inter-agent communication, durable and queryable.
-- Schema follows docs/design/messaging.md.
--
-- Type vocabulary is validated by the CLI against
-- sessions/shared/vocabulary/message-types.md (table-talk, banter,
-- instruction, plot-hint, secret). New types require a vocabulary
-- entry and CLI update; this table doesn't enforce a CHECK so the
-- vocabulary can evolve without a schema migration.

CREATE TABLE IF NOT EXISTS messages (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id     text NOT NULL,
    session_id      text NOT NULL,
    sender          text NOT NULL,            -- agent id
    recipient       text NOT NULL,            -- agent id, 'party', or 'dm'
    type            text NOT NULL,            -- vocabulary-validated by CLI
    body            text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS messages_recipient_idx
    ON messages (campaign_id, recipient, created_at);
CREATE INDEX IF NOT EXISTS messages_sender_idx
    ON messages (campaign_id, sender, created_at);
CREATE INDEX IF NOT EXISTS messages_type_idx
    ON messages (campaign_id, type, created_at);
CREATE INDEX IF NOT EXISTS messages_session_idx
    ON messages (session_id, created_at);


-- Per-agent read checkpoints. Each agent records which messages it has
-- read; `glass msg read --since-checkpoint` returns only those without
-- a row in this table for the agent.
CREATE TABLE IF NOT EXISTS message_reads (
    agent_id        text NOT NULL,
    message_id      uuid NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    read_at         timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (agent_id, message_id)
);

CREATE INDEX IF NOT EXISTS message_reads_agent_idx
    ON message_reads (agent_id, read_at DESC);
