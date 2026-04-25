CREATE TABLE IF NOT EXISTS sources (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kb_id       UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    type        TEXT NOT NULL,
    url_or_path TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    chunk_count INTEGER,
    ingested_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_sources_kb_id ON sources(kb_id);
