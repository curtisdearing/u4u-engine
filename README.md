# u4u-engine

[![tests](https://github.com/curtisdearing/u4u-engine/actions/workflows/test.yml/badge.svg)](https://github.com/curtisdearing/u4u-engine/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Standalone genomics variant analysis engine for the U4U platform.

Takes a raw genome file, runs it through a 10-step annotation pipeline, and returns a scored, prioritized list of variants with plain-English summaries. No web framework dependencies — import it wherever and call `run_pipeline()`.

---

## Documentation

All product, clinical, and infrastructure specs live in [`docs/`](docs/):

| Document | Audience | What it covers |
|----------|----------|----------------|
| [`docs/narrative.md`](docs/narrative.md) | Everyone | Product mission — what U4U is and why it exists |
| [`docs/product-spec.md`](docs/product-spec.md) | Tom, Rocky | Every screen, every state, every UI element |
| [`docs/engine-spec.md`](docs/engine-spec.md) | Curtis, Hampton | Engine API, pipeline steps, expected behaviors, test cases |
| [`docs/data-sources.md`](docs/data-sources.md) | Curtis, Hampton, Cane | External APIs, rate limits, what user data leaves the system |
| [`docs/interpretation-spec.md`](docs/interpretation-spec.md) | Sasank, Rocky | Finding tiers, VUS policy, condition library schema |
| [`docs/team.md`](docs/team.md) | Everyone | Who owns what, critical path, open decisions |

---

## Install

```bash
# From the repo root
pip install -e ./engine

# With VCF support (Linux/Mac only — pysam requires a C compiler)
pip install -e "./engine[vcf]"
```

**Required dependencies:** `requests>=2.31`, `tenacity>=8.2`

---

## Quick Start

```python
from engine import run_pipeline

with open("my_file.vcf", "rb") as f:
    results = run_pipeline(f.read(), "my_file.vcf")

for r in results:
    print(r["tier"], r["genes"], r["headline"])
```

---

## Pipeline Steps

| Step | What happens |
|------|-------------|
| 1. Validate | File size ≤ 100 MB, VCF header check, UTF-8 |
| 2. Parse | VCF / 23andMe / rsID list / CSV → variant dicts |
| 3. Quality filter | Drop hom-ref, failed calls (--/NN/DI), low GQ/DP, indels |
| 4. Whitelist filter | Keep only ACMG81 / pharma / carrier variants (optional) |
| 5. rsID resolution | Ensembl REST: rsid_only variants → coordinates |
| 6. Deduplicate | By (chrom, pos, ref, alt) — eliminates double-annotation |
| 7. Annotate | VEP (consequence + gene) + ClinVar + gnomAD + MyVariant fallback |
| 8. Score | ClinVar > consequence > frequency. Carrier detection for recessive genes |
| 9. Summarize | Plain-English headline, rarity, action hint, zygosity |
| 10. Sort | By score descending |

---

## Result Dict Fields

Each variant in the returned list contains:

```
variant_id         str        rsid or "chrom:pos"
rsid               str|None   dbSNP rsID
location           str        "chrom:pos"
chrom              str        chromosome (no chr prefix)
pos                int        1-based position
ref, alt           str        alleles
zygosity           str        "heterozygous" | "homozygous_alt" | "unknown"

consequence        str        VEP SO term (e.g. "missense_variant")
genes              list[str]  affected gene symbols
clinvar            str|None   ClinVar classification (lowercased)
clinvar_raw        str|None   same — never overwritten by heuristics
disease_name       str|None   associated condition (human-readable, from ClinVar)
condition_key      str|None   stable lookup key for the condition library:
                              "OMIM:<id>" | "MedGen:<id>" | "ClinVar:<uid>" | null
gnomad_af          float|None allele frequency
gnomad_popmax      float|None highest AF across ancestry groups
gnomad_homozygote_count int|None

score              int        priority score
tier               str        "critical" | "high" | "medium" | "low"
reasons            list[str]  scoring factors
frequency_derived_label str|None  additive frequency context (never overwrites clinvar)
carrier_note       str|None   set for heterozygous variants in recessive genes

emoji              str        🔴🟠🟡🟢🔵
headline           str        one-sentence plain-English summary
consequence_plain  str        molecular impact in plain English
rarity_plain       str        population frequency in plain English
clinvar_plain      str        ClinVar classification in plain English
action_hint        str        recommended next step
zygosity_plain     str|None   plain-English zygosity statement
```

### condition_key format

`condition_key` is the stable identifier used to look up the associated condition in the condition library (Sasank's spreadsheet). Priority order:

1. `"OMIM:<MIM number>"` — preferred; sourced from ClinVar trait cross-references
2. `"MedGen:<concept id>"` — NCBI MedGen CUI; fallback when no OMIM xref exists
3. `"ClinVar:<variation uid>"` — ClinVar Variation ID; last resort when no disease xref exists
4. `null` — no ClinVar record found for this variant

The backend uses `condition_key` to retrieve `condition_display_name`, `plain_description`, and `action_guidance` from the condition library. See [`docs/interpretation-spec.md`](docs/interpretation-spec.md) for the full condition library schema.

---

## Accepted File Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| VCF | `.vcf`, `.vcf.gz` | Requires `pysam`. GQ/DP/GT extracted from FORMAT fields |
| 23andMe | `.txt` | rsID + genotype format. ref/alt resolved via Ensembl |
| rsID list | `.txt` | One rsID per line |
| CSV | `.csv` | Columns: chrom, pos, ref, alt, rsid (any subset) |

---

## rsID Whitelist Filters

Place filter files in the `data/` directory:

| Filename | Gene set |
|----------|----------|
| `acmg81_rsids.txt` | ACMG SF v3.2 actionable genes |
| `pharma_rsids.txt` | Pharmacogenomics (CYP2C19, CYP2D6, VKORC1, …) |
| `carrier_rsids.txt` | Carrier screening genes |
| `health_traits_rsids.txt` | Health trait associations |
| `all_clinvar_rsids.txt.gz` | All ClinVar rsIDs |

Apply with:
```python
results = run_pipeline(
    file_bytes, "my_23andme.txt",
    filters=["acmg81_rsids.txt", "pharma_rsids.txt"],
    data_dir="data",
)
```

---

## Wrapping for a FastAPI Worker

```python
from fastapi import FastAPI, UploadFile
from engine import run_pipeline

app = FastAPI()

@app.post("/analyze")
async def analyze(file: UploadFile, filters: list[str] = ["acmg81_rsids.txt"]):
    file_bytes = await file.read()
    results = run_pipeline(
        file_bytes,
        file.filename,
        filters=filters,
        progress_callback=lambda step, pct: print(f"[{pct}%] {step}"),
    )
    return {"count": len(results), "results": results}
```

---

## Wrapping for a Celery Worker

```python
from celery import Celery
from engine import run_pipeline

app = Celery("u4u")

@app.task(bind=True)
def run_analysis(self, file_bytes: bytes, filename: str, filters: list):
    def progress(step, pct):
        self.update_state(state="PROGRESS", meta={"step": step, "pct": pct})

    return run_pipeline(file_bytes, filename, filters=filters, progress_callback=progress)
```

---

## Scoring Model

| Signal | Points |
|--------|--------|
| ClinVar pathogenic | +1000 (short-circuit → CRITICAL) |
| ClinVar likely pathogenic | +500 |
| ClinVar benign | score=1 (short-circuit → LOW) |
| ClinVar VUS | +50 |
| Loss-of-function consequence | +100 |
| Missense / in-frame | +50 |
| Synonymous / intronic | +5 |
| Absent in gnomAD | +30 |
| Ultra-rare (AF < 0.0001) | +20 |
| Very rare (AF < 0.001) | +10 |
| Rare (AF < 0.01) | +5 |
| Common (AF ≥ 0.05) | −20 |
| Carrier in recessive gene | ×0.5 |
| Intergenic | −10 |

**Tiers:** CRITICAL ≥ 500 · HIGH ≥ 100 · MEDIUM ≥ 30 · LOW < 30

---

## Environment Variables

| Variable | Default | Effect |
|----------|---------|--------|
| `NCBI_API_KEY` | _(none)_ | Raises ClinVar rate limit from 3 to 10 req/s |

---

## Tests

```bash
pytest tests/

# without pytest:
PYTHONPATH=. python3 -m unittest discover tests/
```
