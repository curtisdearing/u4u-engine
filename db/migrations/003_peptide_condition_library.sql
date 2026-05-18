-- =============================================================================
-- Migration: 003_peptide_condition_library.sql
-- Description: Creates the Peptide Condition Library tables for PeptidIQ V3.
--              For each annotated variant the engine can query this library to
--              determine the patient's predicted response to specific peptides
--              and hormones used in menopause/HRT protocols.
-- Author:  PeptidIQ Engineering
-- Date:    2026-04-08
-- Depends: 001_initial_schema.sql, 002_annotation_cache.sql
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1.  AUTO-UPDATE TRIGGER FUNCTION  (shared by both tables)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$;


-- ---------------------------------------------------------------------------
-- 2.  TABLE: peptide_condition_library
--     Core lookup table — one row per gene × variant × peptide combination.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS peptide_condition_library (
    id                      SERIAL          PRIMARY KEY,

    -- Variant identity
    gene_symbol             VARCHAR(20)     NOT NULL,
    variant_type            VARCHAR(20)     NOT NULL,   -- 'SNP' | 'CNV' | 'STR_repeat'
    rsid                    VARCHAR(20),                -- NULL for CNVs / STRs
    variant_description     TEXT,                       -- e.g. "CAG repeat < 22", "PvuII T allele"

    -- Peptide / compound identity
    peptide_name            VARCHAR(100)    NOT NULL,   -- e.g. "Testosterone (topical)"
    peptide_class           VARCHAR(50),                -- e.g. "Androgen", "HRT", "GLP-1 RA"
    target_receptor         VARCHAR(50),                -- e.g. "AR", "MC3R/MC4R", "GLP1R"

    -- Response characterisation
    response_direction      VARCHAR(20)     NOT NULL,   -- 'enhanced' | 'standard' | 'blunted' | 'contraindicated'
    confidence_tier         CHAR(1)         NOT NULL,   -- 'A' = RCT/meta-analysis
                                                        -- 'B' = cohort/case-control
                                                        -- 'C' = case series/expert consensus
    CONSTRAINT chk_confidence_tier CHECK (confidence_tier IN ('A', 'B', 'C')),

    -- Clinical content
    mechanism_summary       TEXT            NOT NULL,   -- 2-3 sentence scientific explanation
    dosing_guidance         TEXT,                       -- genotype-informed dosing context
    trade_off_text          TEXT,                       -- "No Free Lunch": biological costs, conversion risks

    -- Safety flags
    contraindication_flag   BOOLEAN         NOT NULL DEFAULT FALSE,
    contraindication_genes  TEXT[],                     -- e.g. ARRAY['TP53','BRCA1']

    -- Pathway / evidence linkage
    kegg_pathways           TEXT[],                     -- e.g. ARRAY['hsa04915','hsa04912']
    source_pmids            TEXT[],                     -- e.g. ARRAY['24165020','23844628']

    -- Auditing
    created_at              TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP       NOT NULL DEFAULT NOW(),

    -- Uniqueness: one clinical recommendation per gene-variant-peptide triplet
    CONSTRAINT uq_gene_variant_peptide UNIQUE (gene_symbol, rsid, variant_description, peptide_name)
);

COMMENT ON TABLE  peptide_condition_library                  IS 'Core lookup table for PeptidIQ V3: one row per gene×variant×peptide combination, describing predicted response direction, mechanism, dosing guidance, and safety flags.';
COMMENT ON COLUMN peptide_condition_library.confidence_tier  IS 'Evidence quality tier: A=RCT/meta-analysis, B=cohort/case-control, C=case series/expert consensus.';
COMMENT ON COLUMN peptide_condition_library.response_direction IS 'Predicted treatment response: enhanced | standard | blunted | contraindicated.';
COMMENT ON COLUMN peptide_condition_library.contraindication_genes IS 'Array of gene symbols that render this peptide unsafe for this patient (e.g. ARRAY[''TP53'',''BRCA1'']).';
COMMENT ON COLUMN peptide_condition_library.kegg_pathways    IS 'KEGG pathway IDs this entry maps to (e.g. ARRAY[''hsa04915'']).';
COMMENT ON COLUMN peptide_condition_library.source_pmids     IS 'PubMed IDs supporting this entry.';


-- Trigger: keep updated_at current on every UPDATE
CREATE TRIGGER trg_peptide_condition_library_updated_at
    BEFORE UPDATE ON peptide_condition_library
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();


-- ---------------------------------------------------------------------------
-- 3.  TABLE: peptide_trade_offs
--     Compound-level trade-off and anecdote data — one row per compound.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS peptide_trade_offs (
    id                          SERIAL          PRIMARY KEY,

    peptide_name                VARCHAR(100)    NOT NULL UNIQUE,
    peptide_class               VARCHAR(50),

    -- Regulatory & clinical context
    regulatory_status           VARCHAR(50),
        -- 'FDA-approved' | 'Compounded' | 'Research only' | 'FDA safety concern'

    -- Pharmacogenomics / dosing logic
    efficacy_med_logic          TEXT,           -- how genetics modify minimum effective dose

    -- Safety & risk profile
    known_trade_offs            TEXT            NOT NULL,
    hormonal_conversion_risks   TEXT,           -- downstream conversion pathways
    clinical_anecdotes          TEXT,           -- de-identified real-world observations

    -- Contraindication genetics (absolute)
    contraindication_genetics   TEXT[],         -- gene symbols that are hard contraindications

    -- Evidence
    source_pmids                TEXT[],

    -- Review provenance
    last_reviewed               DATE,
    reviewed_by                 VARCHAR(100),

    -- Auditing
    created_at                  TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  peptide_trade_offs                            IS 'Compound-level trade-off, regulatory, and anecdote data for PeptidIQ V3 — one row per unique peptide/compound.';
COMMENT ON COLUMN peptide_trade_offs.regulatory_status          IS 'FDA-approved | Compounded | Research only | FDA safety concern';
COMMENT ON COLUMN peptide_trade_offs.efficacy_med_logic         IS 'Describes how patient genetics modify the minimum effective dose for this compound.';
COMMENT ON COLUMN peptide_trade_offs.hormonal_conversion_risks  IS 'Specific downstream conversion pathways (e.g. testosterone → DHT via SRD5A2).';
COMMENT ON COLUMN peptide_trade_offs.contraindication_genetics  IS 'Gene symbols representing absolute genetic contraindications for this compound.';


-- Trigger: keep updated_at current on every UPDATE
CREATE TRIGGER trg_peptide_trade_offs_updated_at
    BEFORE UPDATE ON peptide_trade_offs
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();


-- ---------------------------------------------------------------------------
-- 4.  INDEXES  — tuned for the query patterns used by the annotation engine
-- ---------------------------------------------------------------------------

-- Fast lookup by gene symbol (most common filter in annotation pipeline)
CREATE INDEX IF NOT EXISTS idx_pcl_gene_symbol
    ON peptide_condition_library (gene_symbol);

-- Fast lookup by rsid (SNP lookups from VCF annotation hits)
CREATE INDEX IF NOT EXISTS idx_pcl_rsid
    ON peptide_condition_library (rsid)
    WHERE rsid IS NOT NULL;          -- partial index: skip NULL rows (CNVs/STRs)

-- Fast lookup by peptide name (cross-variant compound queries)
CREATE INDEX IF NOT EXISTS idx_pcl_peptide_name
    ON peptide_condition_library (peptide_name);

-- Fast lookup by response direction (safety-alert dashboards, filtering)
CREATE INDEX IF NOT EXISTS idx_pcl_response_direction
    ON peptide_condition_library (response_direction);

-- Composite index for the primary annotation-engine query pattern:
--   WHERE gene_symbol = $1 AND (rsid = $2 OR rsid IS NULL)
CREATE INDEX IF NOT EXISTS idx_pcl_gene_rsid
    ON peptide_condition_library (gene_symbol, rsid);

-- Partial index: quickly surface all contraindication rows
CREATE INDEX IF NOT EXISTS idx_pcl_contraindication_flag
    ON peptide_condition_library (contraindication_flag)
    WHERE contraindication_flag = TRUE;

-- GIN indexes for array column searches (e.g. "find all entries for pathway hsa04915")
CREATE INDEX IF NOT EXISTS idx_pcl_kegg_pathways_gin
    ON peptide_condition_library USING GIN (kegg_pathways);

CREATE INDEX IF NOT EXISTS idx_pcl_source_pmids_gin
    ON peptide_condition_library USING GIN (source_pmids);

CREATE INDEX IF NOT EXISTS idx_pcl_contraindication_genes_gin
    ON peptide_condition_library USING GIN (contraindication_genes);

-- peptide_trade_offs: peptide_name already covered by UNIQUE (index implicit)
-- Additional index on peptide_class for class-level queries
CREATE INDEX IF NOT EXISTS idx_pto_peptide_class
    ON peptide_trade_offs (peptide_class);


COMMIT;
