# Project Status

---

## MVP scope

VCF upload → annotation engine → interactive dashboard. No genome storage. Email capture for future research updates. Target: 4 weeks.

---

## What works

- Parses VCF / `.vcf.gz` (MVP primary), 23andMe `.txt`, CSV, rsID lists
- 10-step pipeline: validate → parse → quality filter → whitelist → rsID resolution → deduplicate → annotate → score → summarize → sort
- Annotates against ClinVar, gnomAD, Ensembl VEP (retry + fallback)
- Returns plain-English headline, consequence, rarity, action hint per variant
- FastAPI job queue (`api.py`) — `POST /analyze` → 202 + `job_id`, `GET /jobs/:id` for polling
- Postgres schema (`db/schema.sql`) — jobs, results, condition_library, annotation_cache
- CI on push via GitHub Actions (Python 3.11 and 3.12)

### PeptidIQ V3 — Peptide Response Interpretation Engine ✅

Added April 2026. Extends the genomics pipeline into a clinically actionable peptide and hormone response system.

**Peptide Condition Library** (`db/migrations/003_peptide_condition_library.sql`, `db/models/peptide_models.py`, `db/seeds/peptide_seed_data.sql`)
- Two new Postgres tables: `peptide_condition_library` and `peptide_trade_offs`
- SQLAlchemy 2.0 ORM models with async helpers (`get_peptide_responses`, `get_trade_off`, `get_contraindicated_peptides`)
- 12 seeded rows covering AR, ESR1, ESR2, OXTR, MC4R, GLP1R, RET, TP53, BRCA1 with clinically detailed genotype–peptide response data
- JSON Schema 2020-12 for scoring engine input/output format (`data/peptidiq_engine_schema.json`)

**ExpansionHunter STR Calling** (`engine/repeat_callers/expansion_hunter.py`)
- Wraps Illumina ExpansionHunter binary to call AR CAG repeat directly from BAM/CRAM files
- Clinical interpretation with 6 sensitivity tiers (VERY_LOW_PATHOLOGIC → VERY_HIGH) and severity flags
- Ancestry-adjusted reference ranges (African, Caucasian, Hispanic, Asian)
- Graceful degradation: operates from VCF-only when no BAM is available
- 58 unit tests — all passing (`tests/test_engine/test_expansion_hunter.py`)

**KEGG Pathway Mapper** (`engine/annotators/kegg_mapper.py`)
- Maps patient variant gene symbols to 8 priority KEGG pathways: Estrogen signalling, GnRH signalling, Serotonergic synapse, MAPK, PI3K-AKT, Adipocytokine, Melanocortin/MC4R, Steroid hormone biosynthesis
- Fully offline via hardcoded gene membership; optional KEGG REST API refresh with SQLite caching
- Per-gene clinical implication generation (~50 curated gene–pathway notes)
- Cross-pathway combination notes for 7 clinically relevant co-hit pairs
- 53 unit tests — all passing (`tests/test_engine/test_kegg_mapper.py`)

**Predictive Logic Architecture** — spec documented in Notion (Predictive Logic Architecture page); 4-layer scoring engine (Input → Evidence [35/25/20/20 weights] → Outcome → Logic Flow).

---

## Repo

```
engine/
  annotators/       ClinVar, gnomAD, VEP, MyVariant, kegg_mapper modules
  repeat_callers/   ExpansionHunter STR caller (AR CAG repeat)
  pipeline.py       run_pipeline() entry point
  scoring.py        scoring + tier logic
  summary.py        plain-English text generation
api.py              FastAPI job queue
db/
  schema.sql        base Postgres schema (jobs, results, condition_library)
  migrations/       incremental migration files (003 = Peptide Condition Library)
  models/           SQLAlchemy ORM models (peptide_models.py)
  seeds/            seed data SQL (peptide_seed_data.sql)
data/
  acmg81_rsids.txt
  condition_library_for_sasank.xlsx
  peptidiq_engine_schema.json     ← JSON Schema 2020-12 for scoring engine I/O
tests/test_engine/  all unit + integration tests
docs/               documentation (this file, architecture, roadmap, etc.)
.github/            CI, issue templates, PR template
```

---

## What doesn't exist

| Area | Status |
|------|--------|
| Docker build + K8s deployment | Not deployed |
| Postgres instance running | Schema exists — not wired |
| Condition library content | 81 ACMG SF rows needed |
| Frontend | Not built — spec in `docs/frontend.md` |
| Domain + DNS | Not registered |
| Security audit | Not started — plan in `U4U_Cybersecurity_Execution_Plan.docx` |
| PeptidIQ scoring engine (Layer 3 Outcome) | Architecture spec done, implementation pending |
| FastAPI endpoints for peptide response | Not yet wired to new ORM models |
| ExpansionHunter binary + reference FASTA | Must be installed in deployment environment |

---

## UI spec

Full spec in `docs/frontend.md`.

Three screens: Upload → Processing → Results.

Results screen is a **prioritized findings report** — single column, expandable rows with a colored left border (tier color). Two sections: "Needs Attention" (critical + high) and "For Your Records" (medium + low + carrier, collapsed by default).

**Tier visual treatment:**

| `tier` | Border | Emoji |
|--------|--------|-------|
| critical | red | 🔴 |
| high | orange | 🟠 |
| medium | yellow | 🟡 |
| low | green | 🟢 |
| carrier | blue | 🔵 |

**Error states:**

| State | Behavior |
|-------|----------|
| File too large / unsupported format | Inline error before submit |
| Invalid VCF header | Error screen after submit |
| All variants filtered | Results page with explanation |
| Zero ACMG findings | Message, not blank |
| Network error | Error screen with retry |
| Partial results | Show succeeded, note how many failed |

---

## Not in V1

User accounts, saved results, email delivery, pharmacogenomics, research tracking, PRS, mobile, API access for external developers.

Roadmap: `docs/roadmap.md`
