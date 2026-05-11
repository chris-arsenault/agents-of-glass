CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE search_chunks
    ADD COLUMN IF NOT EXISTS embedding_vector vector(768);

CREATE INDEX IF NOT EXISTS search_chunks_embedding_vector_hnsw_idx
    ON search_chunks
    USING hnsw (embedding_vector vector_cosine_ops)
    WHERE embedding_vector IS NOT NULL;

DROP FUNCTION IF EXISTS aog_cosine_similarity(double precision[], double precision[]);

ALTER TABLE search_chunks
    DROP COLUMN IF EXISTS embedding;
