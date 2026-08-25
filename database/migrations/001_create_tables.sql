CREATE EXTENSION IF NOT EXISTS vector;


-- =========================================================
-- EU Combined Nomenclature tariff items
-- =========================================================

CREATE TABLE IF NOT EXISTS tariff_items (
    id BIGSERIAL PRIMARY KEY,

    -- Final 8-digit NC classification
    nc_code TEXT NOT NULL,

    -- Full reconstructed description used for semantic search
    description TEXT NOT NULL,


    -- -----------------------------------------------------
    -- NC hierarchy
    -- -----------------------------------------------------

    -- 4-digit heading
    heading_4_code TEXT,
    heading_4_description TEXT,

    -- Optional hierarchy level between HS4 and HS6
    intermediate_heading TEXT,
    intermediate_is_residual BOOLEAN,

    -- 6-digit HS / NC level
    heading_6_code TEXT,
    heading_6_description TEXT,
    heading_6_is_residual BOOLEAN,

    -- Additional subheading text inherited by the leaf
    subheading TEXT,
    subheading_is_residual BOOLEAN,

    -- Most specific description associated with nc_code
    leaf_description TEXT,
    leaf_is_residual BOOLEAN NOT NULL DEFAULT FALSE,

    -- Immediate parent code when available
    parent_code TEXT,

    -- True when any parent hierarchy level is residual
    has_residual_ancestor BOOLEAN NOT NULL DEFAULT FALSE,


    -- -----------------------------------------------------
    -- Standard tariff information
    -- -----------------------------------------------------

    duty_rate NUMERIC(8,4),
    duty_text TEXT,
    supplementary_unit TEXT,


    -- -----------------------------------------------------
    -- Source evidence
    -- -----------------------------------------------------

    source_document TEXT,
    source_section TEXT,
    source_page INTEGER,
    source_excerpt TEXT,


    -- -----------------------------------------------------
    -- Semantic search
    -- -----------------------------------------------------

    embedding VECTOR(1024),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE UNIQUE INDEX IF NOT EXISTS
idx_tariff_items_nc_code
ON tariff_items (
    nc_code
);


CREATE INDEX IF NOT EXISTS
idx_tariff_items_heading_4_code
ON tariff_items (
    heading_4_code
);


CREATE INDEX IF NOT EXISTS
idx_tariff_items_heading_6_code
ON tariff_items (
    heading_6_code
);


CREATE INDEX IF NOT EXISTS
idx_tariff_items_parent_code
ON tariff_items (
    parent_code
);


CREATE INDEX IF NOT EXISTS
idx_tariff_items_embedding_hnsw
ON tariff_items
USING hnsw (
    embedding vector_cosine_ops
);


-- =========================================================
-- FTA legal text chunks
-- =========================================================

CREATE TABLE IF NOT EXISTS fta_chunks (
    id BIGSERIAL PRIMARY KEY,

    agreement_code TEXT NOT NULL,
    agreement_name TEXT NOT NULL,

    exporter_country TEXT NOT NULL,
    importer_region TEXT NOT NULL,

    chunk_type TEXT NOT NULL,

    article TEXT,
    section TEXT,

    text TEXT NOT NULL,

    source_document TEXT NOT NULL,
    source_page INTEGER,
    source_excerpt TEXT,

    embedding VECTOR(1024),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS
idx_fta_chunks_agreement
ON fta_chunks (
    agreement_code
);


CREATE INDEX IF NOT EXISTS
idx_fta_chunks_embedding_hnsw
ON fta_chunks
USING hnsw (
    embedding vector_cosine_ops
);


CREATE UNIQUE INDEX IF NOT EXISTS
idx_fta_chunks_unique
ON fta_chunks (
    agreement_code,
    chunk_type,
    article,
    source_page
);


-- =========================================================
-- FTA product-specific origin rules
-- =========================================================

CREATE TABLE IF NOT EXISTS fta_origin_rules (
    id BIGSERIAL PRIMARY KEY,

    agreement_code TEXT NOT NULL,

    exporter_country TEXT NOT NULL,
    importer_region TEXT NOT NULL,

    -- Product scope used by the agreement's origin rule.
    -- For the current prototype this is a 4-digit HS heading.
    hs_code TEXT NOT NULL,

    description TEXT,

    rule_text TEXT NOT NULL,

    max_non_originating_material_pct
        NUMERIC(8,4),

    value_basis TEXT,

    source_document TEXT NOT NULL,
    source_section TEXT NOT NULL,
    source_page INTEGER,
    source_excerpt TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS
idx_fta_origin_rules_lookup
ON fta_origin_rules (
    agreement_code,
    hs_code
);


CREATE UNIQUE INDEX IF NOT EXISTS
idx_fta_origin_rules_unique
ON fta_origin_rules (
    agreement_code,
    hs_code
);


-- =========================================================
-- FTA historical tariff schedule lines
-- =========================================================

CREATE TABLE IF NOT EXISTS fta_tariff_lines (
    id BIGSERIAL PRIMARY KEY,

    agreement_code TEXT NOT NULL,

    exporter_country TEXT NOT NULL,
    importer_region TEXT NOT NULL,

    -- Exact tariff code appearing in the FTA tariff schedule.
    tariff_code TEXT NOT NULL,

    -- 4-digit HS heading used for structured narrowing
    -- before semantic search.
    hs4_code TEXT NOT NULL,

    -- Nomenclature used by the historical schedule.
    -- Example: NC2007.
    nomenclature_version TEXT,


    -- -----------------------------------------------------
    -- Historical tariff hierarchy
    -- -----------------------------------------------------

    heading_4_description TEXT,

    branch_context TEXT,

    heading_6_code TEXT,
    heading_6_description TEXT,

    subheading_context TEXT,

    leaf_description TEXT,

    -- Full reconstructed historical description used
    -- for semantic search.
    description TEXT NOT NULL,


    -- -----------------------------------------------------
    -- Tariff schedule information
    -- -----------------------------------------------------

    -- Base customs-duty rate appearing in the FTA schedule.
    base_rate_pct NUMERIC(8,4),

    -- Original wording from the source.
    -- Examples:
    --     "exemption"
    --     "14"
    base_rate_text TEXT,

    -- Tariff dismantling category from the agreement.
    tariff_category TEXT,

    -- Entry-price information when present.
    entry_price_text TEXT,


    -- -----------------------------------------------------
    -- Source evidence
    -- -----------------------------------------------------

    source_document TEXT NOT NULL,
    source_section TEXT,
    source_page INTEGER,
    source_excerpt TEXT NOT NULL,


    -- -----------------------------------------------------
    -- Semantic search
    -- -----------------------------------------------------

    embedding VECTOR(1024),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- Structured narrowing:
--
-- agreement + HS4
--        ↓
-- candidate historical tariff lines
CREATE INDEX IF NOT EXISTS
idx_fta_tariff_lines_lookup
ON fta_tariff_lines (
    agreement_code,
    hs4_code
);


CREATE UNIQUE INDEX IF NOT EXISTS
idx_fta_tariff_lines_unique
ON fta_tariff_lines (
    agreement_code,
    tariff_code
);


CREATE INDEX IF NOT EXISTS
idx_fta_tariff_lines_embedding_hnsw
ON fta_tariff_lines
USING hnsw (
    embedding vector_cosine_ops
);