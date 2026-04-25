CREATE TABLE IF NOT EXISTS chunks_metadata (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id    UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    chunk_text   TEXT NOT NULL,
    pinecone_id  TEXT,
    token_count  INTEGER,
    source_url   TEXT,
    source_title TEXT
);

CREATE INDEX IF NOT EXISTS idx_chunks_source_id ON chunks_metadata(source_id);
