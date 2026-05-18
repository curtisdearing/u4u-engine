# u4u-engine: peptideIQ

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

---

## Running with Docker

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (v20+ recommended)
- [Docker Compose](https://docs.docker.com/compose/install/) (included with Docker Desktop)

### Backend API (port 8000)

The backend API serves the engine pipeline via FastAPI/uvicorn.

```bash
# 1. Create an .env file with your API keys (optional but recommended)
cp .env.example .env   # edit .env and set NCBI_API_KEY if you have one

# 2. Build and start the backend
docker compose up --build

# 3. Verify it's running
curl http://localhost:8000/health
# → {"status":"ok","jobs_running":0,"jobs_pending":0}

# 4. Run an analysis
curl -X POST http://localhost:8000/analyze -F "file=@your_file.vcf"
# → {"job_id":"...","status":"pending","poll_url":"/jobs/..."}
```

### Frontend UI (port 3000)

The frontend is a Next.js app that provides a browser-based interface for uploading genome files and viewing results.

```bash
# 1. Build the frontend Docker image
docker build -t u4u-frontend ./frontend

# 2. Run the frontend container
#    Point NEXT_PUBLIC_API_BASE at the backend API
docker run -d \
  --name u4u-frontend \
  -p 3000:3000 \
  -e NEXT_PUBLIC_API_BASE=http://localhost:8000 \
  u4u-frontend

# 3. Open in your browser
#    → http://localhost:3000
```

> **Note:** If you're running both containers, the frontend needs network access
> to the backend. On Linux, use `--network host` or a shared Docker network.
> On macOS/Windows with Docker Desktop, `http://localhost:8000` works out of
> the box from the frontend container.

### Full-stack with Docker Compose

To run both backend and frontend together, you can extend `docker-compose.yml`:

```yaml
# In docker-compose.yml, add under services:
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_BASE=http://api:8000
    depends_on:
      - api
    restart: unless-stopped
```

Then run:

```bash
docker compose up --build
```

Open **http://localhost:3000** in your browser to access the genome analysis UI.

### Environment Variables

| Variable | Default | Effect |
|----------|---------|--------|
| `NCBI_API_KEY` | _(none)_ | Raises ClinVar rate limit from 3 to 10 req/s |
| `DATA_DIR` | `data` | Path to rsID filter files inside the container |
| `FILTERS` | `acmg81_rsids.txt` | Comma-separated filter filenames (empty = all variants) |
| `WORKERS` | `4` | Thread pool size for concurrent pipeline runs |
| `MAX_UPLOAD_MB` | `100` | Maximum upload file size in megabytes |
| `JOB_TTL_HOURS` | `24` | Hours to keep completed jobs in memory |
| `NEXT_PUBLIC_API_BASE` | `https://flmanbiosci.net/api/v1` | Backend API URL for the frontend |

### Stopping

```bash
# Stop all containers
docker compose down

# Stop and remove volumes
docker compose down -v
```

---

## Grok Plan for Predicting BPC-157 Response

**BPC-157 (Body Protection Compound-157, also called bepecin or PL 14736) is the peptide in question.** “BCP-157” and “BPC-175” appear to be common misspellings or typos; no distinct compound called BPC-175 exists in the literature. BPC-157 is a synthetic 15-amino-acid peptide derived from a protein in human gastric juice. It has been studied extensively in preclinical (mostly rodent) models for regenerative, cytoprotective, anti-inflammatory, and angiogenic effects but **is not FDA-approved for any medical use**. It cannot be legally compounded or sold as a supplement in the US, and human data are extremely limited (small retrospective case series and pilots only, no large randomized controlled trials).

**Strong disclaimer**: Any use is experimental/off-label. Potential risks (including unknown long-term effects, theoretical angiogenesis concerns in cancer, sourcing/quality issues, and legal/regulatory problems) are not fully characterized. This is **not medical advice**. Consult a qualified physician experienced in peptide or regenerative medicine. Baseline and follow-up labs, informed consent, and monitoring are essential. Evidence quality is low for human efficacy and safety.

### Most Common Off-Label Use Cases
Based on preclinical data, anecdotal reports (e.g., athletes, bodybuilders, chronic pain patients), clinic marketing, and the handful of tiny human series, the leading off-label applications are:

1. **Musculoskeletal/soft-tissue healing and pain** (most common by far): Tendon/ligament injuries (e.g., Achilles tendinopathy, tennis/golfer’s elbow), muscle tears/strains, joint pain (especially knee osteoarthritis or chronic knee pain), rotator cuff issues, and post-surgical or overuse recovery. Animal studies show accelerated tendon-to-bone healing, enhanced collagen organization, fibroblast activity, and biomechanical strength. A small retrospective human series (n=12–16) of intra-articular knee injections reported pain relief in ~11–14 patients lasting months (highly confounded, no controls).

2. **Gastrointestinal repair and cytoprotection**: Leaky gut/intestinal barrier dysfunction, NSAID- or alcohol-induced damage, ulcers, and inflammatory bowel disease (ulcerative colitis/Crohn’s) symptoms or flares. Strong preclinical evidence for mucosal healing, reduced colitis inflammation, stabilized permeability, and protection against toxins via the nitric oxide (NO) system. Older (unpublished or hard-to-access) trials explored enemas for UC.

3. **General anti-inflammatory effects and recovery**: Chronic low-grade inflammation, athletic performance/recovery enhancement, wound healing (skin, fistulas), and organ protection (liver, etc.). Users often report faster resolution of nagging injuries or reduced systemic inflammation.

4. **Emerging/less common**: Interstitial cystitis/bladder pain syndrome (small 2024 pilot, n=12 women; intravesical 10 mg injection led to complete symptom resolution in 10/12 with no adverse events reported—again, uncontrolled). Limited anecdotal or preclinical interest in neuroprotection (stroke models, serotonin/dopamine modulation) or cachexia.

**Human evidence summary**: Only three small published human reports exist (knee pain retrospective, IC pilot, tiny IV safety note in 2 women). A 2015 Phase I oral safety/PK trial (n=42) was completed but results were never fully published/publicly analyzed in detail. All other data are rodent/cell/animal. Effects appear pleiotropic but translation to humans is unproven.

### Proposed Biomarkers to Test Effectiveness
No validated, BPC-157-specific biomarkers exist (lack of large trials). The suggestions below are **mechanistic and logical extrapolations** from known pathways, preclinical cytokine/growth factor changes, and practical clinical monitoring recommendations in peptide literature. They are **not proven surrogates** for “effectiveness.” Always pair with clinical outcomes (pain VAS scores, symptom questionnaires like IBD indices or LEFS for lower extremity function, functional testing, imaging/endoscopy where appropriate).

**Recommended panel (baseline + 4–8 weeks post-initiation or per protocol; adjust for route: oral vs. injectable vs. local):**

- **Inflammatory markers (core, most actionable)**: High-sensitivity CRP (hs-CRP), IL-6, TNF-α. **Expected change if responding**: Significant decrease (BPC-157 consistently attenuates these in models and is cited as a way to track anti-inflammatory activity).

- **Gut-specific (for GI indications)**: Fecal calprotectin (↓ with reduced intestinal inflammation), serum/fecal zonulin or lactulose/mannitol permeability test (↓ if barrier repair occurs), or repeat endoscopy/biopsy for mucosal healing.

- **Tissue repair/collagen turnover (MSK focus)**: Procollagen type III N-terminal propeptide (PIIINP) or type I (PINP) — expect increase reflecting enhanced synthesis (supported by tendon fibroblast and wound-healing models). Bone-specific if relevant: PINP/CTX balance.

- **Angiogenesis/vascular (mechanistic)**: Serum VEGF (may rise modestly, reflecting VEGFR2 upregulation and pro-angiogenic signaling central to healing). Endothelial function or NO-related metabolites (research/clinical availability limited).

- **Oxidative stress/antioxidant (supportive)**: Malondialdehyde (MDA, lipid peroxidation — ↓) or total antioxidant capacity; heme oxygenase-1 (HO-1) expression is upregulated preclinically but not routine clinically.

- **Hormonal (speculative, via growth hormone receptor upregulation in fibroblasts)**: IGF-1 or GH levels/response to stimulation (possible enhancement of GH signaling in repair tissues).

- **Safety (mandatory)**: CBC (platelets, as NO effects theoretical), comprehensive metabolic panel (liver/kidney), coagulation studies if indicated.

**Additional practical monitoring**: Subjective symptom logs, range-of-motion/strength testing, ultrasound/MRI for tendon healing (structural, not pure biomarker), Global Response Assessment (used in IC pilot). Track alongside lifestyle factors (sleep, nutrition, physical therapy) that synergize with healing.

These should be interpreted by a clinician; isolated lab changes without clinical improvement are meaningless. Advanced/research options (e.g., specific gene expression for eNOS/VEGFR2) exist but are not practical for routine use.

### Table: Ideas for Predicting Good Candidates for BPC-157
These are **speculative, mechanism- and use-case-based ideas** only—not validated selection criteria or predictors from trials. They draw from BPC-157’s primary actions (NO/eNOS modulation, VEGFR2/angiogenesis, cytokine reduction, GHR upregulation in tendons, gut cytoprotection, antioxidant induction). Ideal candidates would have a condition matching strong preclinical data, measurable baseline abnormalities that the peptide targets, and low risk profile. Assessment combines history, exam, imaging, and labs.

**Predictor / Factor** | **Rationale (Mechanism or Use Case)** | **How to Assess / Predict** | **Expected Benefit if Positive Responder Profile**
--- | --- | --- | ---
High baseline systemic or local inflammation (↑ hs-CRP, IL-6, TNF-α) | Potent attenuation of pro-inflammatory cytokines and NF-κB; shifts M1→M2 macrophages; core to most healing benefits | Baseline inflammatory panel + symptom duration/severity | Faster symptom relief and reduced swelling/pain; stronger signal in chronic inflammatory states
Chronic refractory soft-tissue injury (tendinopathy, ligament, muscle >3–6 months; failed PT/rest) | Upregulates growth hormone receptors in tendon fibroblasts; enhances collagen deposition, angiogenesis, and biomechanical repair | History, ultrasound/MRI, failed conservative care, functional scores (e.g., VISA-A for Achilles) | Accelerated healing timeline, improved strength/return to activity; best match for popular athletic use
GI barrier dysfunction or IBD features (high zonulin, positive permeability test, NSAID history, or mild-moderate colitis symptoms) | Cytoprotective on gastric/intestinal mucosa; stabilizes tight junctions; reduces colitis inflammation via NO system | GI history, zonulin/fecal calprotectin/permeability testing, endoscopy if indicated | Improved gut symptoms, reduced permeability/inflammation; strong preclinical support
Refractory localized pain syndromes matching small human data (e.g., chronic knee OA pain or interstitial cystitis/bladder pain) | Anti-nociceptive, anti-inflammatory, and tissue-repair effects; direct pilot data for intra-articular knee and intravesical bladder use | Pain scores, specific diagnosis (IC criteria), prior treatment failures | High chance of subjective improvement (per small series: 10–11/12 responders); local injection route may enhance
Impaired healing milieu (older age, diabetes, smoking, poor nutrition, low antioxidants/oxidative stress markers) | Boosts angiogenesis (VEGF/VEGFR2), antioxidants (HO-1 etc.), and NO signaling to overcome stalled repair | Age/comorbidities, baseline oxidative stress labs (MDA, TAC), nutrient panel (Vit D, omega-3) | Potential rescue of delayed healing; caution with active comorbidities
Athlete or high physical-demand individual with recurrent overuse injuries | Enhances recovery, collagen remodeling, and perfusion; popular in sports contexts | Training history, injury recurrence rate, performance metrics | Reduced downtime, better resilience; pairs well with structured rehab
Absence of theoretical risks (no active cancer, bleeding diathesis, pregnancy, severe renal/hepatic disease) | Angiogenesis (VEGFR2) raises theoretical tumor-growth concern; NO effects on platelets/vessels | Full history, screening labs/imaging as indicated, oncology clearance if cancer history | Safer profile for trial; ethical use only in low-risk patients
Motivated for multimodal approach (PT, nutrition, sleep optimization) | Pleiotropic effects amplified by supportive care; not a standalone “miracle” | Patient buy-in, adherence plan, baseline lifestyle audit | Superior and more sustainable outcomes; realistic expectations improve perceived success

**Additional notes on prediction**: No genetic biomarkers are established. Response may be faster (1–2 weeks subjective) for acute inflammation vs. structural repair (4–12+ weeks). A short supervised trial (e.g., 2–4 weeks) with objective re-assessment can serve as its own predictor. Combine with proven therapies—BPC-157 is adjunctive at best.

In summary, while preclinical promise is substantial (especially for tendon/gut healing and inflammation), human data are too sparse for confident predictions or biomarker validation. Work with a knowledgeable provider for personalized labs, monitoring, and risk-benefit discussion. Future trials (e.g., ongoing hamstring injury study) may clarify these areas.
