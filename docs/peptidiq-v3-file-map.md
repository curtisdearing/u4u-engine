# PeptidIQ V3 — File Map & Module Reference

Generated: April 2026
Author: Claude (Anthropic) on behalf of Curtis Dearing / Florida Man Biosciences

This document maps every file produced during the PeptidIQ V3 sprint and explains its purpose, dependencies, and integration points.

---

## Directory Tree (V3 additions highlighted)

```
u4u-engine/
│
├── api.py                              Base FastAPI job queue (pre-existing)
├── data/
│   ├── acmg81_rsids.txt               ACMG SF v3.1 rsID whitelist (pre-existing)
│   ├── condition_library_for_sasank.xlsx  Condition library spreadsheet (pre-existing)
│   └── peptidiq_engine_schema.json  ★  JSON Schema 2020-12 for scoring engine I/O
│
├── db/
│   ├── schema.sql                     Base schema: jobs, results, condition_library (pre-existing)
│   ├── migrations/
│   │   └── 003_peptide_condition_library.sql  ★  Adds peptide tables + indexes + triggers
│   ├── models/
│   │   └── peptide_models.py          ★  SQLAlchemy 2.0 ORM for peptide tables
│   └── seeds/
│       └── peptide_seed_data.sql      ★  12 rows of clinical genotype–peptide seed data
│
├── engine/
│   ├── __init__.py                    (pre-existing)
│   ├── annotators/
│   │   ├── __init__.py                (pre-existing)
│   │   ├── clinvar.py                 (pre-existing)
│   │   ├── gnomad.py                  (pre-existing)
│   │   ├── myvariant.py               (pre-existing)
│   │   ├── vep.py                     (pre-existing)
│   │   └── kegg_mapper.py             ★  KEGG pathway mapper (8 pathways, offline + API)
│   ├── repeat_callers/
│   │   ├── __init__.py                ★  Package init
│   │   └── expansion_hunter.py        ★  AR CAG STR caller (wraps ExpansionHunter binary)
│   ├── pipeline.py                    (pre-existing)
│   ├── scoring.py                     (pre-existing)
│   └── summary.py                     (pre-existing)
│
├── tests/test_engine/
│   ├── __init__.py                    (pre-existing)
│   ├── test_annotators.py             (pre-existing)
│   ├── test_deduplicator.py           (pre-existing)
│   ├── test_parsers.py                (pre-existing)
│   ├── test_pipeline_integration.py   (pre-existing)
│   ├── test_quality_filter.py         (pre-existing)
│   ├── test_scoring.py                (pre-existing)
│   ├── test_expansion_hunter.py       ★  58 tests for AR STR caller (all passing)
│   └── test_kegg_mapper.py            ★  53 tests for KEGG mapper (all passing)
│
└── docs/
    ├── architecture.md                (pre-existing)
    ├── peptidiq-v3-file-map.md        ★  This file
    ├── project-status.md              ★  Updated with V3 completed work
    └── roadmap.md                     (pre-existing)
```

★ = new file added in PeptidIQ V3 sprint

---

## Module Reference

### `data/peptidiq_engine_schema.json`

**What it is:** JSON Schema (draft 2020-12) formally specifying the input and output contract for the PeptidIQ scoring engine.

**Key structure:**
- `input_layer` — variant data, patient demographics, ancestry, sample metadata
- `evidence_layer` — 4 evidence buckets with enforced const weights: genomic (0.35), clinical literature (0.25), pathway (0.20), phenotype (0.20)
- `outcome_layer` — populated post-scoring; not in `required` (engine writes it)
- `logic_flow` — references to pipeline step sequence

**Use it for:** validating engine payloads at ingestion, auto-generating API docs, ensuring weight constants never drift.

---

### `db/migrations/003_peptide_condition_library.sql`

**What it is:** Postgres migration that creates the two peptide tables. Wrapped in `BEGIN`/`COMMIT` so it is atomic.

**Tables created:**
- `peptide_condition_library` — core genotype–peptide response rows (gene, variant, peptide name, response level, mechanism, dosing notes, clinical flags, contraindications)
- `peptide_trade_offs` — linked trade-off rows for complex peptide interactions

**Indexes:** 10 total — partial index on `response_level = 'contraindicated'`, GIN index on `gene_variants TEXT[]`, composite indexes on `(gene, peptide_name)` and `(gene, response_level)`.

**Triggers:** `set_updated_at()` fires on UPDATE for both tables.

**Run with:**
```bash
psql $DATABASE_URL -f db/migrations/003_peptide_condition_library.sql
```

---

### `db/models/peptide_models.py`

**What it is:** SQLAlchemy 2.0 ORM models for the peptide tables, using `Mapped[]` type annotations and `AsyncSession`.

**Classes:**
- `PeptideConditionLibrary` — maps to `peptide_condition_library`
- `PeptideTradeOff` — maps to `peptide_trade_offs`

**Async helper functions:**
- `get_peptide_responses(session, gene, variant)` — returns all peptide responses for a gene+variant
- `get_trade_off(session, library_id)` — returns trade-off rows for a given library entry
- `get_contraindicated_peptides(session, gene)` — returns all contraindicated peptides for a gene

**Import:**
```python
from db.models.peptide_models import PeptideConditionLibrary, get_peptide_responses
```

---

### `db/seeds/peptide_seed_data.sql`

**What it is:** 12 INSERT rows populating `peptide_condition_library` with clinically validated genotype–peptide data.

**Genes covered:** AR (CAG short/long), ESR1 (rs9340799), ESR2 (rs4986938), OXTR (rs53576), MC4R (Val103Ile), GLP1R (Ala316Thr), RET (M918T), TP53 (R175H), BRCA1 (pathogenic)

**Run after the migration:**
```bash
psql $DATABASE_URL -f db/seeds/peptide_seed_data.sql
```

---

### `engine/repeat_callers/expansion_hunter.py`

**What it is:** Python wrapper around Illumina's ExpansionHunter binary for calling short tandem repeats (STRs) from BAM/CRAM files.

**Entry point:**
```python
from engine.repeat_callers.expansion_hunter import call_ar_cag_repeat

result = call_ar_cag_repeat(
    bam_path="/data/patient.bam",
    sex="male",
    ancestry="Caucasian"
)
# result["repeat_count"], result["sensitivity_tier"], result["clinical_flag"]
```

**Key constants:**
- `AR_CAG_REPEAT_SPEC` — chrX:67545316–67545385 (hg38), primary allele = AR
- Ancestry reference means: African=20, Caucasian=22, Hispanic=23, Asian=24

**Sensitivity tiers (shorter CAG = higher AR sensitivity):**

| CAG count | Tier | Severity |
|-----------|------|----------|
| < 18 | VERY_HIGH | CRITICAL |
| 18–22 | HIGH | MEDIUM |
| 23–26 | NORMAL | INFO |
| 27–31 | REDUCED | MEDIUM |
| 32–35 | LOW | HIGH |
| > 35 | VERY_LOW_PATHOLOGIC | CRITICAL |

**Graceful degradation:** If no BAM path is provided but a VCF is available, `parse_eh_output()` can extract repeat counts directly from ExpansionHunter VCF/JSON output without rerunning the binary.

**Dependencies:** ExpansionHunter binary must be on PATH; hg38 reference FASTA required for live BAM calling.

---

### `engine/annotators/kegg_mapper.py`

**What it is:** Maps patient variant gene symbols to 8 priority KEGG signaling pathways and generates plain-English clinical implication text.

**Entry points:**
```python
from engine.annotators.kegg_mapper import map_variants_to_pathways, generate_pathway_summary

hits = map_variants_to_pathways(["ESR1", "AR", "GLP1R", "MC4R"])
summary = generate_pathway_summary(hits)
```

**Priority pathways:**

| KEGG ID | Name | Key Genes |
|---------|------|-----------|
| hsa04915 | Estrogen signaling | ESR1, ESR2, NCOA1 |
| hsa04912 | GnRH signaling | GNRHR, KISS1R, AR |
| hsa04726 | Serotonergic synapse | HTR2A, SLC6A4, MAOA |
| hsa04010 | MAPK signaling | BRAF, RET, TP53 |
| hsa04151 | PI3K-AKT signaling | GLP1R, PIK3CA, BRCA1 |
| hsa04920 | Adipocytokine signaling | PPARG, ADIPOQ, LEPR |
| hsa04916 | Melanocortin/appetite | MC4R, POMC, AGRP |
| map00140 | Steroid hormone biosynthesis | CYP19A1, HSD17B1, SRD5A2 |

**Offline-first design:** All gene membership is hardcoded. Pass `use_api=True` with a `KEGGCache` instance to optionally refresh from rest.kegg.jp (results cached in SQLite, refreshed every 30 days).

**Cross-pathway combination notes:** 7 clinically relevant co-hit pairs trigger additional interpretive text (e.g. ESR1 + CYP19A1 → compounded estrogen activity note).

---

### `tests/test_engine/test_expansion_hunter.py`

58 tests across 7 test classes. Covers: repeat spec constants, all 6 sensitivity tier boundary conditions (21 parametrized), ancestry correction, graceful degradation, VCF/JSON parsing fixtures, subprocess mocking, integration flow.

**Run:** `pytest tests/test_engine/test_expansion_hunter.py -v`
**Status:** ✅ 58 passed

---

### `tests/test_engine/test_kegg_mapper.py`

53 tests across 7 test classes. Covers: hardcoded pathway completeness, gene mapping with known/unknown/case-insensitive inputs, sorting, implication generation for all 8 pathways, cross-pathway summary, SQLite cache lifecycle (stale checks, nested dirs, API mocking).

**Run:** `pytest tests/test_engine/test_kegg_mapper.py -v`
**Status:** ✅ 53 passed

---

## Integration Notes

### Running both test suites together
```bash
cd u4u-engine
pytest tests/test_engine/test_expansion_hunter.py tests/test_engine/test_kegg_mapper.py -v
```

### Database setup sequence
```bash
# 1. Apply base schema
psql $DATABASE_URL -f db/schema.sql

# 2. Apply peptide migration
psql $DATABASE_URL -f db/migrations/003_peptide_condition_library.sql

# 3. Seed peptide data
psql $DATABASE_URL -f db/seeds/peptide_seed_data.sql
```

### Wiring kegg_mapper into the pipeline
The KEGG mapper is designed to be called after variant annotation, using the `genes` field already returned by VEP:
```python
from engine.annotators.kegg_mapper import map_variants_to_pathways

# variant["genes"] is already populated by the VEP annotator
kegg_hits = map_variants_to_pathways(variant["genes"])
variant["kegg_pathways"] = kegg_hits
```

### Wiring expansion_hunter into the pipeline
Insert after the VCF parse step when a BAM path is available:
```python
from engine.repeat_callers.expansion_hunter import call_ar_cag_repeat

if bam_path and sex:
    ar_result = call_ar_cag_repeat(bam_path=bam_path, sex=sex, ancestry=patient_ancestry)
    job_context["ar_cag_result"] = ar_result
```

---

## What's Next (V3 → V4)

| Task | Priority | Notes |
|------|----------|-------|
| Wire `peptide_models.py` into FastAPI endpoints | High | New `/peptide-response` route |
| Plug `kegg_mapper` output into scoring engine evidence layer | High | Uses pathway weight (0.20) |
| Plug `expansion_hunter` into pipeline BAM processing step | High | Requires deployment env setup |
| Implement outcome layer scoring logic (Layer 3) | High | Architecture spec in Notion |
| Install ExpansionHunter binary + hg38 reference in Docker image | Medium | Needed for live BAM calling |
| Expand seed data beyond 12 rows | Medium | Target: 50+ gene–peptide combinations |
| Wire condition library to frontend results display | Medium | Join on `condition_key` |
| Security audit | Low | Plan in `U4U_Cybersecurity_Execution_Plan.docx` |
