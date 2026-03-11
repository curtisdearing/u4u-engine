# U4U — Data Sources

> **Status:** Accurate as of engine v1.0.0. Curtis maintains this. Update it when annotators change.

---

## Overview

The U4U engine contacts four external data sources per variant annotation. Each is described below: what it provides, how we use it, its URL, any API keys required, rate limits, and fallback behavior.

No data is stored from these sources beyond what appears in the analysis results returned to the user. Raw genome files are never sent to external APIs — only specific coordinates (chromosome, position, alleles) or rsIDs are transmitted.

---

## 1. Ensembl VEP (Variant Effect Predictor)

**What it provides:** Functional consequence of the variant at the molecular level. Which gene is affected, what the variant does to the protein, and how severe that effect is likely to be. Also returns ClinVar colocated data as a secondary source.

**How we use it:** Step 7 of the pipeline (annotate). Called once per variant. The engine selects the canonical consequence using MANE Select transcript priority, then VEP canonical flag, then `most_severe_consequence` as a fallback.

**Endpoint:** `POST https://rest.ensembl.org/vep/human/region`

**Auth:** None required for public use.

**Rate limit:** 15 requests/second unauthenticated. The engine annotates variants sequentially, which naturally stays within limits for typical file sizes.

**What we extract:**
- `most_severe_consequence` — the SO term (e.g., `"missense_variant"`)
- `transcript_consequences[].gene_symbol` — gene name
- `colocated_variants[].clin_sig` — ClinVar significance as a fallback (used only when direct ClinVar lookup returns nothing)

**Retry behavior:** 3 attempts with exponential backoff (2s, 4s, 8s). Network timeouts and connection errors trigger retry. Non-200 responses do not retry.

**Fallback if unavailable:** `consequence` set to `"unknown"`, `genes` set to `[]`.

**Reference:** https://rest.ensembl.org/documentation/info/vep_region_post

---

## 2. NCBI ClinVar (eUtils)

**What it provides:** Clinical significance classification for a variant. Whether clinical geneticists have determined it to be pathogenic, likely pathogenic, benign, likely benign, or VUS. Also returns the associated disease/condition name.

**How we use it:** Step 7 of the pipeline. Two-step lookup: esearch (rsID → ClinVar UID), then esummary (UID → classification). Called only when the variant has an rsID.

**Endpoints:**
- `GET https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi`
- `GET https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi`

**Auth:** Set `NCBI_API_KEY` environment variable to increase rate limit from 3 to 10 requests/second. Get a key at: https://www.ncbi.nlm.nih.gov/account/

**Rate limit:** 3 req/sec without key, 10 req/sec with key. The engine sleeps 350ms between calls (no key) or 100ms (with key).

**What we extract:**
- `clinical_significance.description` (or `germline_classification.description` — ClinVar has changed its schema multiple times; we try all known paths)
- `trait_set[0].trait_name` — associated condition name

**Retry behavior:** 3 attempts with exponential backoff on timeout/connection errors.

**Fallback if unavailable:** Falls back to ClinVar data embedded in VEP's `colocated_variants` response. If that is also absent, `clinvar` is set to `null`.

**Reference:** https://www.ncbi.nlm.nih.gov/clinvar/

---

## 3. gnomAD (Genome Aggregation Database)

**What it provides:** Population allele frequency — how common or rare the variant is across ~800,000 human genomes. Essential for distinguishing rare potentially pathogenic variants from common benign ones.

**How we use it:** Step 7 of the pipeline. GraphQL query per variant. Tries gnomAD r4 first; if the variant is absent from r4, falls back to r2.1.

**Endpoint:** `POST https://gnomad.broadinstitute.org/api/`

**Auth:** None required.

**Rate limit:** Unofficial. The engine annotates sequentially and does not aggressively parallelize, which has been sufficient in testing. For large batch jobs, consider adding sleep between variants.

**What we extract:**
- `genome.af` — allele frequency from genome data (preferred)
- `exome.af` — allele frequency from exome data (fallback if genome AC = 0)
- `genome.homozygote_count` — number of homozygous carriers observed
- `genome.popmax.af` — highest AF across ancestry groups

**Datasets tried (in order):**
1. `gnomad_r4` — current release, genome build GRCh38
2. `gnomad_r2_1` — older release, used for variants not yet in r4

**Retry behavior:** 3 attempts with exponential backoff on timeout/connection errors.

**Fallback if unavailable:** `gnomad_af` set to `null`. The scoring model treats `null` as "no frequency data" and neither adds nor subtracts from the score.

**Reference:** https://gnomad.broadinstitute.org/

---

## 4. MyVariant.info (Fallback Only)

**What it provides:** An aggregation service that combines ClinVar, gnomAD, dbSNP, and other sources into a single REST endpoint. Less authoritative than the primary sources but useful as a safety net.

**How we use it:** Called only when the primary annotators (ClinVar eUtils + gnomAD GraphQL) both return nothing. This is the last resort — not the first call.

**Endpoint:** `GET https://myvariant.info/v1/query` (by rsID) or `GET https://myvariant.info/v1/variant/{hgvs}` (by coordinate)

**Auth:** None required.

**Rate limit:** 10 req/sec, 1000 req/day for unauthenticated use. Sufficient for typical usage.

**Hit validation:** When we query by rsID, we validate that the returned hit's genomic position matches what we have for the variant. This prevents accepting data for a different locus that shares an rsID due to genome build differences.

**What we extract:** ClinVar classification and condition name (lower priority than direct ClinVar), gnomAD AF (lower priority than direct gnomAD).

**Retry behavior:** 3 attempts with exponential backoff.

**Reference:** https://myvariant.info/

---

## Priority order when sources conflict

The engine never lets a lower-priority source override a higher-priority one:

| Field | Priority order |
|-------|---------------|
| `clinvar` | Direct ClinVar eUtils > VEP colocated fallback > MyVariant.info |
| `gnomad_af` | Direct gnomAD GraphQL (r4 then r2.1) > MyVariant.info |
| `consequence` | VEP MANE Select > VEP canonical > VEP most_severe_consequence |

The `clinvar` field is **never overwritten by a frequency heuristic.** The `frequency_derived_label` field is additive context only — it exists alongside `clinvar`, not instead of it.

---

## rsID resolution (Ensembl Variation API)

Before annotation, 23andMe files contain rsIDs without coordinates. The engine resolves them to genomic coordinates using:

**Endpoint:** `GET https://rest.ensembl.org/variation/human/{rsid}`

**What we use:** `mappings[0].seq_region_name` (chromosome), `mappings[0].start` (position), `mappings[0].allele_string` (ref/alt alleles).

**Genotype-aware:** When a 23andMe genotype string is available (e.g., "CT"), the engine uses it to select only the allele the user actually carries, rather than returning all possible alts for the rsID.

**Rate limit:** 15 requests/second. Engine sleeps 70ms between calls.

---

## Internal filter files (local, no network)

These files live in the `data/` directory and are used by the whitelist filter step. They are plain text, one rsID per line.

| File | Contents |
|------|----------|
| `acmg81_rsids.txt` | All pathogenic/likely pathogenic rsIDs in ACMG SF v3.2 genes |
| `pharma_rsids.txt` | Pharmacogenomics rsIDs (CYP2C19, CYP2D6, VKORC1, etc.) |
| `carrier_rsids.txt` | Carrier screening gene rsIDs |
| `health_traits_rsids.txt` | Health trait associations |
| `all_clinvar_rsids.txt.gz` | All ClinVar rsIDs (large — use sparingly) |

These files are generated from ClinVar bulk downloads and committed to the repo. They do not update automatically. The process for regenerating them is in `scripts/generate_filters.py` (to be written).

---

## Condition library (Sasank's spreadsheet → database)

A separate curated data source maintained by Sasank. Not an external API — a CSV/spreadsheet that gets loaded into the database at deploy time.

Keyed by `condition_key` (OMIM ID or ClinVar disease ID). The engine returns `condition_key` in each result; the backend uses it to look up the corresponding row in the condition library and merge the curated content into the API response.

Schema is defined in `docs/interpretation-spec.md`.

---

## What user data leaves our system

| Data | Sent to | When |
|------|---------|------|
| Individual variant coordinates (chrom, pos, ref, alt) | Ensembl VEP | During annotation |
| rsIDs | Ensembl Variation API, NCBI ClinVar, MyVariant.info | During annotation |
| Raw genome file | Nobody | Never. File is parsed locally and discarded. |
| User identity | Nobody | We don't have it in V1 |

The raw genome file is never transmitted to any external service. Only the specific variant data needed for each API call is sent.

---

*Curtis maintains this document. If an annotator changes, this doc changes first.*
