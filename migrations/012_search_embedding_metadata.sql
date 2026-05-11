ALTER TABLE search_chunks
    ADD COLUMN IF NOT EXISTS embedding_model text,
    ADD COLUMN IF NOT EXISTS embedding_provider text,
    ADD COLUMN IF NOT EXISTS embedding_dim integer,
    ADD COLUMN IF NOT EXISTS embedded_at timestamptz;

CREATE INDEX IF NOT EXISTS search_chunks_embedding_ready_idx
    ON search_chunks (campaign_id, source_type, visibility, embedding_dim)
    WHERE embedding IS NOT NULL;

CREATE OR REPLACE FUNCTION aog_cosine_similarity(
    a double precision[],
    b double precision[]
) RETURNS double precision
LANGUAGE sql
IMMUTABLE
STRICT
AS $$
    SELECT CASE
        WHEN cardinality(a) = 0 THEN NULL
        WHEN cardinality(a) <> cardinality(b) THEN NULL
        WHEN sums.norm_a = 0 OR sums.norm_b = 0 THEN NULL
        ELSE sums.dot / (sqrt(sums.norm_a) * sqrt(sums.norm_b))
    END
    FROM (
        SELECT
            sum(x * y) AS dot,
            sum(x * x) AS norm_a,
            sum(y * y) AS norm_b
        FROM unnest(a, b) AS item(x, y)
    ) AS sums
$$;
