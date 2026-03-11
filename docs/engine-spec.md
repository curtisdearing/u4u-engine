# U4U — Engine Specification

> **Status:** Accurate as of engine v1.0.0. Curtis maintains this. Sasank reads the interpretation sections. Tom reads the API output section. Hampton reads the integration section.

This document describes what the engine does in words — inputs, outputs, expected behaviors, and what constitutes correct vs. incorrect behavior. It is the non-code specification that any team member (or AI assistant) can read to understand what `run_pipeline()` is supposed to do.

---

## What the engine is

A standalone Python package (`u4u-engine`) that takes a raw genome file and returns a list of annotated, scored, and interpreted variants. It has no knowledge of web servers, databases, job queues, or UI frameworks. It is imported by a backend worker and called as a function.

```python
from engine import run_pipeline

results = run_pipeline(file_bytes, "my_23andme.txt", filters=["acmg81_rsids.txt"])
# returns: list[dict], sorted by score descending
```

---

## Inputs

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_bytes` | `bytes` | Yes | Raw file content. Never written to disk by the engine. |
| `filename` | `str` | Yes | Original filename. Used only for format detection (extension). |
| `filters` | `list[str]` | No | rsID whitelist filenames. Empty = process all variants. |
| `data_dir` | `str` | No | Directory containing filter files. Default: `"data"`. |
| `progress_callback` | `callable` | No | Called as `fn(step: str, pct: int)`. For progress bars. |

---

## Output

A `list[dict]`, sorted by `score` descending. Each dict contains all fields documented in `engine/__init__.py`. Key fields:

### Identity
- `variant_id` — rsid if available, otherwise `"chrom:pos"`
- `rsid`, `chrom`, `pos`, `ref`, `alt`
- `location` — `"chrom:pos"` string
- `zygosity` — `"heterozygous"`, `"homozygous_alt"`, or `"unknown"`

### Annotation
- `consequence` — VEP SO term (e.g., `"missense_variant"`)
- `genes` — list of gene symbols (e.g., `["BRCA1"]`)
- `clinvar` — lowercased ClinVar classification or `null`
- `clinvar_raw` — original ClinVar value, never modified
- `disease_name` — condition name from ClinVar or `null`
- `condition_key` — OMIM ID or ClinVar disease ID for condition library lookup
- `gnomad_af` — allele frequency or `null`
- `gnomad_popmax` — highest AF across ancestry groups
- `gnomad_homozygote_count`

### Scoring
- `score` — integer priority score
- `tier` — `"critical"`, `"high"`, `"medium"`, or `"low"`
- `reasons` — list of human-readable scoring factors
- `frequency_derived_label` — additive frequency context when ClinVar is absent/VUS (never overwrites `clinvar`)
- `carrier_note` — set for heterozygous variants in recessive genes; `null` otherwise

### Consumer summary
- `emoji` — `🔴`, `🟠`, `🟡`, `🟢`, or `🔵`
- `headline` — one-sentence auto-generated summary
- `consequence_plain` — molecular impact in plain English
- `rarity_plain` — population frequency in plain English
- `clinvar_plain` — ClinVar classification in plain English
- `action_hint` — auto-generated recommended next step
- `zygosity_plain` — plain-English zygosity statement or `null`

---

## Pipeline steps

### Step 1: Validate

**Inputs:** file_bytes, filename  
**Expected behavior:**
- Raise `ValueError` if file is empty
- Raise `ValueError` if file exceeds 100 MB
- Raise `ValueError` if filename ends with `.vcf` and file does not start with `##fileformat=VCF`
- Raise `ValueError` if filename ends with `.txt` or `.csv` and file is not valid UTF-8

**What NOT to do:** Do not attempt to parse the file if validation fails.

---

### Step 2: Parse

**Inputs:** file_bytes, filename  
**Expected behavior by format:**

**23andMe (.txt):**
- Skip all lines starting with `#`
- Skip lines where the first column does not start with `rs` (internal IDs like `i7001348`)
- Skip lines where the genotype is a failed call: `--`, `NN`, `.`, `-`, `DI`, `II`, `DD`, or any genotype containing `I` or `D`
- Return rsid_only variants with the genotype string preserved
- Infer zygosity from the two-character genotype: two identical chars → homozygous, two different chars → heterozygous

**VCF (.vcf, .vcf.gz):**
- Parse using pysam
- Extract one variant dict per alt allele
- Extract zygosity from the GT field of the first sample column: `0/1` → heterozygous, `1/1` → homozygous_alt, `0/0` → homozygous_ref
- Extract GQ and DP from sample FORMAT fields

**Plain rsID list (.txt without 23andMe format):**
- One rsID per line
- Skip blank lines

**CSV (.csv):**
- Columns: chrom, pos, ref, alt, rsid (any subset)
- Coordinate variant if both chrom and pos are present; rsid_only otherwise

**All formats:** Strip `chr` prefix from chromosome names. Normalize alleles to uppercase.

---

### Step 3: Quality filter

**Expected behavior:**
- Drop any variant where `zygosity == "homozygous_ref"` — the user carries the reference allele; this is not a variant
- Drop genotype strings: `--`, `NN`, `.`, `-`, `DI`, `II`, `DD`
- Drop any genotype containing `I` or `D`
- Drop VCF variants with `GQ < 20`
- Drop VCF variants with `DP < 5`
- Drop variants where ref or alt length > 1 (indels — not supported in V1)
- Drop 23andMe variants with no ref/alt and genotype length > 2

**What NOT to do:** Do not raise an error for filtered variants. Log or count them silently.

---

### Step 4: Whitelist filter

**Expected behavior:**
- If `filters` is empty, return all variants unchanged
- If `filters` is non-empty, keep only variants whose `rsid` appears in at least one filter file
- Filter files are plain text, one rsID per line, cached in memory after first load
- If a filter file does not exist, treat it as an empty set (do not crash)

---

### Step 5: rsID resolution

**Expected behavior:**
- Only runs for variants where `variant_type == "rsid_only"`
- Calls Ensembl Variation API: `GET /variation/human/{rsid}`
- Uses `mappings[0]` (primary assembly)
- **Genotype-aware:** if the variant has a genotype string, only return alt alleles the user actually carries (chars in the genotype that differ from the reference). If all genotype chars match the reference → return nothing (homozygous reference)
- Without a genotype, return all alt alleles from `allele_string`
- Return empty list if the rsID cannot be resolved (do not crash)

---

### Step 6: Deduplicate

**Key:** `(chrom, pos, ref, alt)` — all normalized (no chr prefix, uppercase)

**Expected behavior:**
- When two variants share a key, keep the one with an rsID
- If both have rsIDs or neither does, keep the first
- Skip variants missing pos/ref/alt — they cannot be keyed

---

### Step 7: Annotate

Called once per unique variant. Expected behavior:

**VEP:**
- POST to `https://rest.ensembl.org/vep/human/region`
- Region string format: `{chrom}:{pos}-{pos}:1/{alt}`
- Select canonical consequence: MANE Select flag first, then canonical=1, then most_severe_consequence
- Extract ClinVar colocated data as fallback
- If VEP returns null or fails: `consequence="unknown"`, `genes=[]`

**ClinVar:**
- Search by rsID via NCBI eUtils esearch, then esummary
- Primary over VEP colocated data
- Try three schema paths for clinical significance field (ClinVar has changed its format)
- If no record: `clinvar=null`, `disease_name=null`

**gnomAD:**
- Try gnomAD r4 via GraphQL, then r2.1
- Prefer genome data over exome data when both have allele counts
- If absent from both datasets: `gnomad_af=null`

**MyVariant.info (fallback):**
- Called only when ClinVar AND gnomAD both returned null
- Validate hit's coordinates match the variant before accepting data

---

### Step 8: Score

**Short-circuit rules (nothing overrides these):**
- `clinvar == "pathogenic"` → score = 1000, tier = critical, return immediately
- `clinvar == "benign"` → score = 1, tier = low, return immediately

**Score components:**
| Signal | Points |
|--------|--------|
| ClinVar likely pathogenic | +500 |
| ClinVar likely benign | score = 5 |
| ClinVar VUS / uncertain significance | +50 |
| High-impact consequence (stop_gained, frameshift, splice site, start_lost, stop_lost, transcript_ablation) | +100 |
| Moderate-impact consequence (missense, inframe_del, inframe_ins) | +50 |
| Low-impact consequence (synonymous, intron, intergenic, UTR) | +5 |
| Unknown/unclassified consequence | +1 |
| gnomAD AF = 0 | +30 |
| gnomAD AF < 0.0001 | +20 |
| gnomAD AF < 0.001 | +10 |
| gnomAD AF < 0.01 | +5 |
| gnomAD AF ≥ 0.01 | −20 |
| No gnomAD data | 0 |
| No gene annotation | −10 |

**Carrier modifier:** If `zygosity == "heterozygous"` AND disease name or ClinVar text contains recessive keywords → multiply final score by 0.5, set `carrier_note`.

**Tier assignment:**
- CRITICAL: score ≥ 500
- HIGH: score ≥ 100
- MEDIUM: score ≥ 30
- LOW: score < 30

**`frequency_derived_label` (additive only — never overwrites `clinvar`):**
- If ClinVar is absent or VUS AND gnomAD AF ≥ 0.05 → `"Likely benign (common in population)"`
- If ClinVar is absent or VUS AND gnomAD AF < 0.0001 → `"Uncertain significance (ultra-rare variant)"`
- Otherwise: `null`

---

### Step 9: Summarize

Generates plain-English text from structured fields. See `engine/summary.py` for the full text of each generated string. Key behaviors:

- Carrier finding (`carrier_note` is set) → emoji = 🔵, headline = "You appear to be a carrier of a variant in [gene]."
- Critical → 🔴, "This variant in [gene] is known to cause disease."
- High → 🟠, "This variant in [gene] is highly suspicious or likely to disrupt gene function."
- Medium → 🟡, "There is currently uncertain or limited evidence about this variant in [gene]."
- Low → 🟢, "This is a low-risk variant in [gene]."
- `zygosity_plain` is set for heterozygous ("one copy") and homozygous_alt ("two copies")

---

### Step 10: Sort

Sort by `score` descending. Ties are broken by original list order (stable sort).

---

## Behaviors the engine must NOT exhibit

These are the bugs that existed in prior versions. Do not reintroduce them.

1. **Gene hardcoded to "N/A"** — genes must always come from VEP transcript_consequences
2. **Annotating homozygous-reference variants** — quality filter must drop them before annotation
3. **Accepting MyVariant hits without coordinate validation** — validate chrom/pos match
4. **Hardcoded variant cap (the `:10` slice)** — removed; process all variants
5. **No deduplication** — always deduplicate before annotation
6. **Frequency heuristic overwriting ClinVar** — `frequency_derived_label` is additive; `clinvar` is never overwritten
7. **Inconsistent chr prefix** — strip internally, normalize everywhere
8. **No retry logic on API calls** — all external calls wrapped with tenacity

---

## Test cases (in words)

These are the behaviors tests must verify. The actual test code is in `tests/test_engine/`.

**Parsers:**
- 23andMe file with `--` genotype: that variant does not appear in output
- 23andMe file with `i7001348` internal ID: skipped
- 23andMe file with `CT` genotype: `zygosity = "heterozygous"`
- 23andMe file with `TT` genotype: `zygosity = "homozygous_alt"`
- CSV with `chr19` chromosome: stored as `"19"` (no chr prefix)
- Unsupported extension `.bam`: raises `ValueError`

**Quality filter:**
- `zygosity = "homozygous_ref"`: dropped
- `gq = 15`: dropped (below threshold of 20)
- `ref = "AT"` (indel): dropped
- `genotype = "DI"`: dropped

**Deduplicator:**
- Two identical `(chrom, pos, ref, alt)` entries: one result
- Entry without rsID + entry with rsID at same locus: entry with rsID kept
- `chr1` and `1` at same position: deduplicated (treated as same)

**Scoring:**
- `clinvar = "pathogenic"`: score = 1000, tier = critical
- `clinvar = "benign"`: score = 1, tier = low
- `clinvar = "uncertain significance"`, `gnomad_af = 0.10`: `frequency_derived_label = "Likely benign (common in population)"`, `clinvar` field unchanged
- `clinvar = "uncertain significance"`, `disease_name = "autosomal recessive ataxia"`, `zygosity = "heterozygous"`: `carrier_note` is set, score halved

**Pipeline:**
- Empty file: raises `ValueError`
- Invalid VCF header: raises `ValueError`
- Two identical variants in CSV: one result (deduplicated)
- Pathogenic variant: appears first in sorted results

---

*Curtis maintains this document. It is the written spec that code is checked against. When behavior changes, update this document first.*
