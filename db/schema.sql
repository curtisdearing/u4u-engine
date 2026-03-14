-- db/schema.sql — U4U Engine PostgreSQL schema
-- ============================================
-- Run once against a fresh database:
--   psql $DATABASE_URL -f db/schema.sql
--
-- Designed to mirror the in-memory _jobs dict in api.py so switching from
-- in-memory to DB persistence is a drop-in replacement for _jobs reads/writes.
-- No ORM — plain SQL so Hampton can read it without a Python environment.

-- ── Extensions ────────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- fast text search on disease_name

-- ── jobs ──────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS jobs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    status          TEXT        NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending','running','done','failed')),

    -- file metadata (stored before processing, never the file content)
    filename        TEXT        NOT NULL,
    file_size_bytes INT         NOT NULL,

    -- progress (updated in real time by the pipeline)
    progress_step   TEXT,
    progress_pct    SMALLINT    DEFAULT 0,

    -- result summary (populated when status = 'done')
    variant_count   INT,

    -- error message (populated when status = 'failed')
    error_message   TEXT,

    -- timing
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_jobs_status     ON jobs (status);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs (created_at DESC);

COMMENT ON TABLE jobs IS
    'One row per /analyze request. Tracks pipeline lifecycle and timing.';
COMMENT ON COLUMN jobs.id IS
    'UUID returned to the client as job_id. Used to poll /jobs/{job_id}.';
COMMENT ON COLUMN jobs.filename IS
    'Original upload filename — format detection only. File bytes are never stored.';


-- ── results ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS results (
    id                      BIGSERIAL   PRIMARY KEY,
    job_id                  UUID        NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,

    -- Core identity (from engine/__init__.py field list)
    variant_id              TEXT        NOT NULL,   -- rsid or "chrom:pos"
    rsid                    TEXT,
    location                TEXT,                   -- "chrom:pos"
    chrom                   TEXT,
    pos                     INT,
    ref                     TEXT,
    alt                     TEXT,
    zygosity                TEXT,                   -- "heterozygous"|"homozygous_alt"|"unknown"

    -- Annotation
    consequence             TEXT,                   -- VEP SO term
    genes                   TEXT[],                 -- affected gene symbols
    clinvar                 TEXT,                   -- lowercased clinical significance
    clinvar_raw             TEXT,                   -- original ClinVar value
    disease_name            TEXT,
    condition_key           TEXT,                   -- "OMIM:<id>"|"MedGen:<id>"|"ClinVar:<uid>"|NULL
    gnomad_af               DOUBLE PRECISION,
    gnomad_popmax           DOUBLE PRECISION,
    gnomad_homozygote_count INT,

    -- Scoring
    score                   INT         NOT NULL,
    tier                    TEXT        NOT NULL
                            CHECK (tier IN ('critical','high','medium','low')),
    reasons                 TEXT[],                 -- human-readable scoring factors
    frequency_derived_label TEXT,
    carrier_note            TEXT,

    -- Consumer summary (plain English)
    emoji                   TEXT,
    headline                TEXT,
    consequence_plain       TEXT,
    rarity_plain            TEXT,
    clinvar_plain           TEXT,
    action_hint             TEXT,
    zygosity_plain          TEXT,

    -- Full result blob for any fields added in future engine versions
    full_json               JSONB       NOT NULL,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_results_job_id       ON results (job_id);
CREATE INDEX IF NOT EXISTS idx_results_job_tier      ON results (job_id, tier);
CREATE INDEX IF NOT EXISTS idx_results_score         ON results (job_id, score DESC);
CREATE INDEX IF NOT EXISTS idx_results_condition_key ON results (condition_key)
    WHERE condition_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_results_disease_trgm  ON results
    USING gin (disease_name gin_trgm_ops)
    WHERE disease_name IS NOT NULL;

COMMENT ON TABLE results IS
    'One row per variant per job. All engine output fields stored flat + full_json blob.';
COMMENT ON COLUMN results.full_json IS
    'Complete run_pipeline() result dict as JSONB. Catches any new fields added to
     the engine without requiring a schema migration. The flat columns exist for
     indexed queries (dashboard filters, tier counts, etc.).';
COMMENT ON COLUMN results.condition_key IS
    'Stable lookup key into the condition_library. Priority: OMIM > MedGen > ClinVar UID.
     Used by the dashboard to join with Sasank''s consumer-facing text.';


-- ── condition_library ─────────────────────────────────────────────────────────
-- Populated by importing data/condition_library_for_sasank.xlsx.
-- One row per condition (not per gene — multiple genes can share a condition).

CREATE TABLE IF NOT EXISTS condition_library (
    condition_key       TEXT        PRIMARY KEY,   -- "OMIM:<id>"|"MedGen:<id>"|"ClinVar:<uid>"
    display_name        TEXT        NOT NULL,
    gene_symbols        TEXT[],
    inheritance_pattern TEXT,                      -- "Autosomal dominant" etc.
    acmg_sf             BOOLEAN     NOT NULL DEFAULT FALSE,
    category            TEXT,                      -- "Cancer","Cardiac","Metabolic"…
    prevalence          TEXT,                      -- e.g. "1 in 500"

    -- Sasank writes these
    plain_description   TEXT,                      -- what this condition means in plain English
    action_guidance     TEXT,                      -- what the patient should do next
    carrier_note        TEXT,                      -- override for carrier-specific language

    last_reviewed       DATE,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE condition_library IS
    'Consumer-facing condition text reviewed by Sasank. Joined to results on condition_key
     to replace raw ClinVar strings with plain-English descriptions and action guidance.';


-- ── Helpful views ─────────────────────────────────────────────────────────────

-- Quick job summary with tier breakdown — useful for the dashboard header
CREATE OR REPLACE VIEW job_summary AS
SELECT
    j.id                                                AS job_id,
    j.status,
    j.filename,
    j.variant_count,
    j.created_at,
    j.finished_at,
    ROUND(EXTRACT(EPOCH FROM (j.finished_at - j.started_at))::NUMERIC, 1) AS runtime_seconds,
    COUNT(r.id) FILTER (WHERE r.tier = 'critical')      AS critical_count,
    COUNT(r.id) FILTER (WHERE r.tier = 'high')          AS high_count,
    COUNT(r.id) FILTER (WHERE r.tier = 'medium')        AS medium_count,
    COUNT(r.id) FILTER (WHERE r.tier = 'low')           AS low_count
FROM jobs j
LEFT JOIN results r ON r.job_id = j.id
GROUP BY j.id;

COMMENT ON VIEW job_summary IS
    'Per-job variant counts by tier. Used for the dashboard summary card.';
