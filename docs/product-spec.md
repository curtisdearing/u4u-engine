# U4U — Product Specification

> **Status:** Draft. Tom and Rocky build against this. Curtis owns it. Update it before changing behavior, not after.

---

## Overview

U4U is a single-purpose web application. A user uploads a genome file, waits while it processes, and sees a prioritized list of their variants with plain-English interpretations. That is the entire product for V1.

There are three screens. Each is described below in full: what the user sees, what they can interact with, what happens when they do, and what states exist.

---

## Screen 1 — Upload

### What the user sees

- The U4U logo and a one-sentence tagline ("Understand what's in your genome.")
- A file upload area (drag-and-drop or click to browse)
- A short explanation of accepted formats: 23andMe raw data (.txt), VCF (.vcf), or CSV
- A consent checkbox the user must check before uploading
- An "Analyze" button that is disabled until a file is selected and the checkbox is checked

### Consent checkbox text

> "I understand this is not medical advice. U4U provides information from public scientific databases to help me understand my own genomic data. I will not use this information to self-diagnose or replace professional medical guidance."

This checkbox is required. The Analyze button does not activate until it is checked.

### File size limit

100 MB. If the user selects a file over 100 MB, show an inline error before upload:
> "This file is too large (X MB). Maximum size is 100 MB. For whole-genome VCFs, contact us."

### Accepted file types

| Type | Extension | Notes |
|------|-----------|-------|
| 23andMe raw data | `.txt` | Must contain rsid/chromosome/position/genotype columns |
| VCF | `.vcf` | Must begin with `##fileformat=VCF` |
| Gzipped VCF | `.vcf.gz` | Same requirement |
| CSV | `.csv` | Columns: chrom, pos, ref, alt, rsid (any subset) |

If the user uploads an unsupported format, show an inline error:
> "We couldn't read this file. Accepted formats: .txt (23andMe), .vcf, .vcf.gz, .csv"

### Gene panel selector (optional — shown on upload screen)

A secondary control below the file upload, collapsed by default. User can expand it to choose which gene panels to run. If collapsed (default), the ACMG SF v3.2 panel runs automatically.

Options:
- ✅ ACMG Secondary Findings v3.2 (default, always on)
- ☐ Pharmacogenomics (CYP2C19, CYP2D6, VKORC1, and related)
- ☐ Carrier screening
- ☐ All variants in file (no panel filter — may produce a large result set)

---

## Screen 2 — Processing

### What the user sees

- A progress bar
- A status line that updates as the pipeline runs (e.g., "Parsing file… Resolving variants… Annotating…")
- An estimated time remaining (if determinable)
- No way to navigate away (or a warning if they try)

### Progress steps shown to the user

These map to `progress_callback(step, pct)` in the engine:

| Engine step | User-facing label |
|-------------|-------------------|
| Validating file (2%) | Checking file… |
| Parsing file (5%) | Reading your variants… |
| Applying quality filter (8%) | Filtering low-quality calls… |
| Applying gene panel filter (12%) | Applying gene panel… |
| Resolving rsIDs (15–25%) | Looking up variant coordinates… |
| Deduplicating (26%) | Removing duplicates… |
| Annotating variant N/total (30–88%) | Annotating variant N of total… |
| Scoring (88%) | Scoring variants… |
| Generating summaries (94%) | Preparing your results… |
| Complete (100%) | Done — loading results… |

### Error states

If the pipeline fails (invalid file, network error, etc.), show a clear error screen with:
- What went wrong in plain English
- What the user can do (try again, try a different file, contact support)
- Do not show a stack trace or technical error message

---

## Screen 3 — Results

This is the primary product screen. It is the reason U4U exists.

### Layout

**Header:** variant count and a one-line summary ("We found 12 findings worth reviewing.")

**Filter bar:** tier filter chips the user can toggle:
- 🔴 Critical (N)
- 🟠 High (N)
- 🟡 Medium / VUS (N)
- 🟢 Low (N)
- 🔵 Carrier (N)

Default view: Critical and High are shown. Medium, Low, and Carrier are hidden by default but accessible with one click.

**Results list:** one card per variant, sorted by score descending. See "Result Card" below.

**Disclaimer footer:** persistent on this screen.
> "This information is not medical advice. Findings are sourced from ClinVar, gnomAD, and Ensembl VEP. Always discuss significant findings with a qualified healthcare provider or genetic counselor."

---

### Result Card — Collapsed state

Each variant shows as a card. Collapsed state contains:

| Element | Content | Source field |
|---------|---------|-------------|
| Emoji + tier badge | 🔴 CRITICAL | `emoji`, `tier` |
| Gene name | BRCA1 | `genes[0]` |
| Headline | "This variant in BRCA1 is known to cause disease." | `headline` |
| Condition name | Hereditary Breast and Ovarian Cancer | `condition_display_name` (from condition library) or `disease_name` |
| ClinVar badge | Pathogenic | `clinvar` |

Clicking the card expands it.

---

### Result Card — Expanded state

Expanded card shows all of:

**Section: What this means**
- `headline` — already shown collapsed
- `consequence_plain` — "At the molecular level, this variant changes a single building block (amino acid) in the protein."
- `zygosity_plain` — "You carry one copy of this variant (heterozygous)."

**Section: How common is this**
- `rarity_plain` — "In the general population, this variant is ultra-rare (seen in less than 1 in 10,000 people)."

**Section: Clinical classification**
- `clinvar_plain` — "According to clinical geneticists, this variant is classified as disease-causing (pathogenic) for Hereditary Breast and Ovarian Cancer."
- If `frequency_derived_label` is set: show it as a secondary note, visually distinct from ClinVar
- If `carrier_note` is set: show it in the blue 🔵 carrier section

**Section: What to do**
- `action_hint` — "Consider discussing this finding with a genetic counselor or your doctor, especially if you have a personal or family history of related conditions."
- `condition_guidance` (from condition library if available) — condition-specific action guidance Sasank writes

**Section: Sources**
- Link to ClinVar record (if rsid exists: `https://www.ncbi.nlm.nih.gov/clinvar/?term={rsid}`)
- Link to ACMG statement (if ACMG SF gene: from `acmg_url` in condition library)
- gnomAD link: `https://gnomad.broadinstitute.org/variant/{chrom}-{pos}-{ref}-{alt}`

---

### Carrier card (🔵)

Carrier findings are visually separated from risk findings. The card uses blue styling and a distinct layout:

- Header: 🔵 CARRIER FINDING
- Headline: "You appear to be a carrier of a variant in [gene]."
- `carrier_note` text
- Condition name
- `action_hint`
- Sources

---

### VUS card (🟡)

VUS findings require specific language. Per product and clinical agreement:

- We surface them. We do not suppress them.
- We are explicit that there is no scientific consensus.
- We show population frequency and functional consequence as supporting context.
- We do not suggest the variant is harmful or harmless — we present the data.

VUS card expanded section — "Clinical classification":
> "This variant is classified as having **uncertain significance (VUS)**. The scientific community has not yet reached consensus on whether this variant affects health. Below is what the available data suggests."

Then show `consequence_plain`, `rarity_plain`, and `frequency_derived_label` if set.

---

## States the application must handle

| State | What happens |
|-------|-------------|
| File too large | Inline error on upload screen, before submit |
| Unsupported file format | Inline error on upload screen, before submit |
| Invalid VCF (bad header) | Error screen after submit |
| All variants filtered out | Results screen with zero cards and a message explaining why |
| Zero ACMG findings | Show "No findings in ACMG secondary findings genes" — do not show blank screen |
| Network error during annotation | Graceful error screen, offer retry |
| Partial results (some variants failed annotation) | Show results that succeeded, note that N variants could not be annotated |
| Pipeline timeout | Error screen with explanation and retry option |

---

## What is explicitly NOT in V1

- User accounts or saved results
- Email delivery of results
- Sharing results with a provider
- Comparing results across family members
- PRS (polygenic risk scores)
- Mobile app
- API access for external developers

---

*Tom builds against this. Rocky designs against this. If something in here is wrong or unclear, fix the spec — do not silently deviate from it.*
