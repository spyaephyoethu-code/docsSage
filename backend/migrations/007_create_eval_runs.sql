CREATE TABLE IF NOT EXISTS eval_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kb_id           UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    dataset_version TEXT,
    config          JSONB,
    metrics         JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
