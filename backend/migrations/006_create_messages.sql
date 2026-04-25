CREATE TABLE IF NOT EXISTS messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    citations       JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    latency_ms      INTEGER,
    cost_usd        NUMERIC(10, 6)
);

CREATE INDEX IF NOT EXISTS idx_messages_conv_id ON messages(conversation_id);
